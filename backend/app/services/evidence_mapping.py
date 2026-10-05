"""
Evidence mapping orchestration and clarification-question generation.
"""

from __future__ import annotations

import json

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.prompts import EVIDENCE_MAPPING_REPAIR_PROMPT
from app.ai.providers import EvidenceMappingProvider
from app.models import (
    Application,
    ApplicationVersion,
    Assessment,
    AssessmentItem,
    ClarificationQuestion,
    DocumentChunk,
    EvidenceMapping,
    EvidenceSourceType,
    EvidenceStatus,
    Requirement,
    ReviewAction,
    UserReview,
)
from app.models.enums import AssessmentStatus, QuestionState
from app.scoring import score
from app.schemas.evidence import EvidenceMappingPayload, EvidenceReviewUpdate, ExtractedEvidenceMapping
from app.services.evidence_validation import evidence_in_chunk
from app.services.requirement_extraction import get_current_guideline_version, list_current_requirements
from app.utils.errors import raise_error


async def get_current_application_version(
    db: AsyncSession,
    project_id: str,
) -> ApplicationVersion:
    """Return the latest application version for a project."""
    result = await db.execute(
        select(Application)
        .where(Application.project_id == project_id)
        .options(selectinload(Application.versions))
    )
    application = result.scalar_one_or_none()
    if application is None or application.current_version is None:
        raise_error(
            400,
            "APPLICATION_REQUIRED",
            "Upload a draft application before running evidence mapping.",
        )
    return application.current_version


async def run_evidence_mapping_for_project(
    db: AsyncSession,
    *,
    project_id: str,
    provider: EvidenceMappingProvider,
) -> tuple[Assessment, list[EvidenceMapping], list[ClarificationQuestion]]:
    """Run evidence mapping for the latest guideline requirements and application."""
    guideline_version = await get_current_guideline_version(db, project_id)
    application_version = await get_current_application_version(db, project_id)
    requirements = await list_current_requirements(db, project_id)
    if not requirements:
        raise_error(
            400,
            "REQUIREMENTS_REQUIRED",
            "Extract or add requirements before running an assessment.",
        )
    chunks = await _load_application_chunks(db, application_version.id)
    if not chunks:
        raise_error(
            400,
            "NO_APPLICATION_CHUNKS",
            "The current application version has no extracted text chunks.",
        )

    raw_response = await provider.map_evidence(
        application_version=application_version,
        requirements=requirements,
        chunks=chunks,
    )
    payload = _parse_provider_payload(raw_response)
    if payload is None:
        raw_response = await provider.map_evidence(
            application_version=application_version,
            requirements=requirements,
            chunks=chunks,
            repair_prompt=EVIDENCE_MAPPING_REPAIR_PROMPT,
        )
        payload = _parse_provider_payload(raw_response)
    if payload is None:
        raise_error(
            502,
            "INVALID_AI_RESPONSE",
            "The AI provider returned invalid evidence JSON. Nothing was stored.",
        )

    payload = await _repair_unverifiable_citations_once(
        provider=provider,
        payload=payload,
        application_version=application_version,
        requirements=requirements,
        chunks=chunks,
    )

    requirement_by_identifier = {requirement.requirement_id: requirement for requirement in requirements}
    chunk_by_id = {chunk.id: chunk for chunk in chunks}

    assessment = Assessment(
        project_id=project_id,
        guideline_version_id=guideline_version.id,
        application_version_id=application_version.id,
        assessment_status=AssessmentStatus.COMPLETED,
        requirements_snapshot=[
            {
                "id": requirement.requirement_id,
                "title": requirement.title,
                "priority": requirement.priority.value,
                "category": requirement.category.value,
            }
            for requirement in requirements
        ],
    )
    db.add(assessment)
    await db.flush()

    await db.execute(delete(ClarificationQuestion).where(ClarificationQuestion.project_id == project_id))
    await db.execute(delete(EvidenceMapping).where(EvidenceMapping.project_id == project_id))

    mappings: list[EvidenceMapping] = []
    seen_identifiers: set[str] = set()
    for extracted in payload.mappings:
        requirement = requirement_by_identifier.get(extracted.requirement_id)
        if requirement is None:
            continue
        seen_identifiers.add(extracted.requirement_id)
        mappings.append(
            _to_evidence_mapping(
                extracted,
                project_id=project_id,
                assessment_id=assessment.id,
                requirement=requirement,
                application_version=application_version,
                chunk_by_id=chunk_by_id,
            )
        )

    for requirement in requirements:
        if requirement.requirement_id not in seen_identifiers:
            mappings.append(
                EvidenceMapping(
                    project_id=project_id,
                    assessment_id=assessment.id,
                    requirement_id=requirement.id,
                    application_version_id=application_version.id,
                    status=EvidenceStatus.MISSING,
                    confidence=0.0,
                    explanation="No evidence mapping was returned for this requirement.",
                    missing_items=[f"Provide verifiable application evidence for: {requirement.title}."],
                    citation_verified=False,
                )
            )

    db.add_all(mappings)
    await db.flush()
    for mapping in mappings:
        await db.refresh(mapping)

    _apply_score_to_assessment(assessment, requirements, mappings)
    db.add_all(_build_assessment_items(assessment, requirements, mappings))
    await db.flush()

    questions = _build_questions(project_id, mappings)
    db.add_all(questions)
    await db.flush()
    for question in questions:
        await db.refresh(question)
    await db.refresh(assessment)

    return assessment, mappings, questions


def _apply_score_to_assessment(
    assessment: Assessment,
    requirements: list[Requirement],
    mappings: list[EvidenceMapping],
) -> None:
    result = score(requirements, mappings)
    assessment.mandatory_completeness = result.mandatory_completeness
    assessment.recommended_completeness = result.recommended_completeness
    assessment.overall_completeness = result.overall_completeness
    assessment.overall_status = result.overall_status
    assessment.mandatory_supported_count = result.mandatory.counts[EvidenceStatus.SUPPORTED]
    assessment.mandatory_partial_count = result.mandatory.counts[EvidenceStatus.PARTIALLY_SUPPORTED]
    assessment.mandatory_missing_count = result.mandatory.counts[EvidenceStatus.MISSING]
    assessment.mandatory_ambiguous_count = result.mandatory.counts[EvidenceStatus.AMBIGUOUS]
    assessment.mandatory_contradictory_count = result.mandatory.counts[EvidenceStatus.CONTRADICTORY]
    assessment.mandatory_rejected_count = result.mandatory.counts[EvidenceStatus.REJECTED]
    assessment.mandatory_total_count = result.mandatory.denominator
    assessment.recommended_supported_count = result.recommended.counts[EvidenceStatus.SUPPORTED]
    assessment.recommended_partial_count = result.recommended.counts[EvidenceStatus.PARTIALLY_SUPPORTED]
    assessment.recommended_missing_count = result.recommended.counts[EvidenceStatus.MISSING]
    assessment.recommended_ambiguous_count = result.recommended.counts[EvidenceStatus.AMBIGUOUS]
    assessment.recommended_contradictory_count = result.recommended.counts[EvidenceStatus.CONTRADICTORY]
    assessment.recommended_rejected_count = result.recommended.counts[EvidenceStatus.REJECTED]
    assessment.recommended_total_count = result.recommended.denominator
    assessment.critical_missing_items = [
        {
            "id": item.requirement_id,
            "title": item.title,
            "status": item.status.value,
            "missing_items": item.missing_items,
        }
        for item in result.critical_missing_items
    ]


def _build_assessment_items(
    assessment: Assessment,
    requirements: list[Requirement],
    mappings: list[EvidenceMapping],
) -> list[AssessmentItem]:
    mapping_by_requirement = {mapping.requirement_id: mapping for mapping in mappings}
    items: list[AssessmentItem] = []
    for requirement in requirements:
        mapping = mapping_by_requirement.get(requirement.id)
        effective_status = mapping.effective_status if mapping else EvidenceStatus.MISSING
        points, in_denominator = _points_for_status(effective_status)
        items.append(
            AssessmentItem(
                assessment_id=assessment.id,
                requirement_id=requirement.id,
                evidence_mapping_id=mapping.id if mapping else None,
                requirement_identifier=requirement.requirement_id,
                requirement_title=requirement.title,
                requirement_category=requirement.category,
                requirement_priority=requirement.priority,
                ai_status=mapping.status if mapping else EvidenceStatus.MISSING,
                reviewed_status=(
                    mapping.user_review.reviewed_status
                    if mapping is not None and mapping.user_review is not None
                    else None
                ),
                effective_status=effective_status,
                points=points,
                in_denominator=in_denominator,
                evidence_text=mapping.effective_evidence_text if mapping else None,
                source_citation=_source_citation(mapping) if mapping else None,
                explanation=mapping.effective_explanation if mapping else None,
                missing_items=mapping.missing_items if mapping else [],
            )
        )
    return items


def _points_for_status(status: EvidenceStatus) -> tuple[float, bool]:
    if status == EvidenceStatus.NOT_APPLICABLE:
        return 0.0, False
    if status == EvidenceStatus.SUPPORTED:
        return 1.0, True
    if status == EvidenceStatus.PARTIALLY_SUPPORTED:
        return 0.5, True
    return 0.0, True


def _source_citation(mapping: EvidenceMapping | None) -> dict | None:
    if mapping is None or mapping.source_chunk_id is None:
        return None
    return {
        "document": mapping.source_document,
        "version": mapping.source_version,
        "page": mapping.source_page,
        "section": mapping.source_section,
        "chunk_id": mapping.source_chunk_id,
    }


async def list_evidence_mappings(db: AsyncSession, project_id: str) -> list[EvidenceMapping]:
    """List current evidence mappings for a project."""
    result = await db.execute(
        select(EvidenceMapping)
        .where(EvidenceMapping.project_id == project_id)
        .options(selectinload(EvidenceMapping.user_review))
        .order_by(EvidenceMapping.created_at)
    )
    return list(result.scalars().all())


async def get_evidence_mapping_or_404(db: AsyncSession, mapping_id: str) -> EvidenceMapping:
    """Fetch an evidence mapping with its review state."""
    result = await db.execute(
        select(EvidenceMapping)
        .where(EvidenceMapping.id == mapping_id)
        .options(selectinload(EvidenceMapping.user_review))
    )
    mapping = result.scalar_one_or_none()
    if mapping is None:
        raise_error(404, "EVIDENCE_NOT_FOUND", "Evidence mapping not found.")
    return mapping


async def confirm_evidence_mapping(
    db: AsyncSession,
    mapping_id: str,
    *,
    reviewer_name: str | None = "Reviewer",
    notes: str | None = None,
) -> EvidenceMapping:
    """Confirm an AI evidence mapping without overwriting AI values."""
    mapping = await get_evidence_mapping_or_404(db, mapping_id)
    await _upsert_user_review(
        db,
        mapping,
        action=ReviewAction.CONFIRMED,
        reviewed_status=None,
        reviewed_evidence_text=None,
        reviewed_explanation=None,
        reviewer_name=reviewer_name,
        notes=notes,
    )
    await db.flush()
    return await get_evidence_mapping_or_404(db, mapping_id)


async def reject_evidence_mapping(
    db: AsyncSession,
    mapping_id: str,
    *,
    reviewer_name: str | None = "Reviewer",
    notes: str | None = None,
) -> EvidenceMapping:
    """Reject an AI evidence mapping while preserving the original AI output."""
    mapping = await get_evidence_mapping_or_404(db, mapping_id)
    await _upsert_user_review(
        db,
        mapping,
        action=ReviewAction.REJECTED,
        reviewed_status=None,
        reviewed_evidence_text=None,
        reviewed_explanation=None,
        reviewer_name=reviewer_name,
        notes=notes,
    )
    await db.flush()
    return await get_evidence_mapping_or_404(db, mapping_id)


async def edit_evidence_mapping(
    db: AsyncSession,
    mapping_id: str,
    payload: EvidenceReviewUpdate,
) -> EvidenceMapping:
    """Save reviewer-edited effective mapping values separately from AI values."""
    mapping = await get_evidence_mapping_or_404(db, mapping_id)
    await _upsert_user_review(
        db,
        mapping,
        action=ReviewAction.EDITED,
        reviewed_status=payload.reviewed_status,
        reviewed_evidence_text=payload.reviewed_evidence_text,
        reviewed_explanation=payload.reviewed_explanation,
        reviewer_name=payload.reviewer_name,
        notes=payload.notes,
    )
    await db.flush()
    return await get_evidence_mapping_or_404(db, mapping_id)


async def list_questions(db: AsyncSession, project_id: str) -> list[ClarificationQuestion]:
    """List clarification questions for a project."""
    result = await db.execute(
        select(ClarificationQuestion)
        .where(ClarificationQuestion.project_id == project_id)
        .order_by(ClarificationQuestion.created_at)
    )
    return list(result.scalars().all())


async def get_question_or_404(db: AsyncSession, question_id: str) -> ClarificationQuestion:
    """Fetch a clarification question."""
    question = await db.get(ClarificationQuestion, question_id)
    if question is None:
        raise_error(404, "QUESTION_NOT_FOUND", "Clarification question not found.")
    return question


async def _upsert_user_review(
    db: AsyncSession,
    mapping: EvidenceMapping,
    *,
    action: ReviewAction,
    reviewed_status: EvidenceStatus | None,
    reviewed_evidence_text: str | None,
    reviewed_explanation: str | None,
    reviewer_name: str | None,
    notes: str | None,
) -> UserReview:
    review = mapping.user_review
    if review is None:
        review = UserReview(evidence_mapping_id=mapping.id, action=action)
        db.add(review)
        mapping.user_review = review

    review.action = action
    review.reviewed_status = reviewed_status
    review.reviewed_evidence_text = reviewed_evidence_text
    review.reviewed_explanation = reviewed_explanation
    review.reviewer_name = reviewer_name or "Reviewer"
    review.notes = notes
    return review


async def _load_application_chunks(db: AsyncSession, application_version_id: str) -> list[DocumentChunk]:
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.application_version_id == application_version_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(result.scalars().all())


def _parse_provider_payload(raw_response: str) -> EvidenceMappingPayload | None:
    try:
        parsed = json.loads(raw_response)
        return EvidenceMappingPayload.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


async def _repair_unverifiable_citations_once(
    *,
    provider: EvidenceMappingProvider,
    payload: EvidenceMappingPayload,
    application_version: ApplicationVersion,
    requirements: list[Requirement],
    chunks: list[DocumentChunk],
) -> EvidenceMappingPayload:
    if _all_citations_verified(payload, chunks):
        return payload

    repaired_raw = await provider.map_evidence(
        application_version=application_version,
        requirements=requirements,
        chunks=chunks,
        repair_prompt=EVIDENCE_MAPPING_REPAIR_PROMPT,
    )
    repaired = _parse_provider_payload(repaired_raw)
    if repaired is not None and _all_citations_verified(repaired, chunks):
        return repaired

    return EvidenceMappingPayload(
        mappings=[
            _downgrade_if_unverifiable(mapping, chunks)
            for mapping in payload.mappings
        ]
    )


def _all_citations_verified(payload: EvidenceMappingPayload, chunks: list[DocumentChunk]) -> bool:
    return all(_mapping_citation_verified(mapping, chunks) for mapping in payload.mappings)


def _mapping_citation_verified(mapping: ExtractedEvidenceMapping, chunks: list[DocumentChunk]) -> bool:
    if mapping.status == EvidenceStatus.MISSING:
        return True
    if not mapping.evidence_text or mapping.source is None:
        return False
    chunk = next((item for item in chunks if item.id == mapping.source.chunk_id), None)
    return chunk is not None and evidence_in_chunk(mapping.evidence_text, chunk)


def _downgrade_if_unverifiable(
    mapping: ExtractedEvidenceMapping,
    chunks: list[DocumentChunk],
) -> ExtractedEvidenceMapping:
    if _mapping_citation_verified(mapping, chunks):
        return mapping
    return ExtractedEvidenceMapping(
        requirement_id=mapping.requirement_id,
        status=EvidenceStatus.MISSING,
        confidence=0.0,
        evidence_text=None,
        source=None,
        explanation=(
            "The provider returned an unverifiable citation, so the mapping was downgraded to missing."
        ),
        missing_items=(mapping.missing_items or ["Provide verifiable evidence with a valid application citation."]),
    )


def _to_evidence_mapping(
    extracted: ExtractedEvidenceMapping,
    *,
    project_id: str,
    assessment_id: str,
    requirement: Requirement,
    application_version: ApplicationVersion,
    chunk_by_id: dict[str, DocumentChunk],
) -> EvidenceMapping:
    chunk = chunk_by_id.get(extracted.source.chunk_id) if extracted.source else None
    citation_verified = bool(
        extracted.evidence_text and chunk and evidence_in_chunk(extracted.evidence_text, chunk)
    )
    return EvidenceMapping(
        project_id=project_id,
        assessment_id=assessment_id,
        requirement_id=requirement.id,
        application_version_id=application_version.id,
        status=extracted.status,
        confidence=extracted.confidence,
        evidence_text=extracted.evidence_text,
        source_document=extracted.source.document if extracted.source else None,
        source_version=str(extracted.source.version) if extracted.source else None,
        source_page=extracted.source.page if extracted.source else None,
        source_section=extracted.source.section if extracted.source else None,
        source_chunk_id=extracted.source.chunk_id if extracted.source else None,
        explanation=extracted.explanation,
        missing_items=extracted.missing_items,
        contradictory_evidence=extracted.contradictory_evidence,
        source_type=EvidenceSourceType.APPLICATION,
        citation_verified=citation_verified,
    )


def _build_questions(project_id: str, mappings: list[EvidenceMapping]) -> list[ClarificationQuestion]:
    needs_question = {
        EvidenceStatus.PARTIALLY_SUPPORTED,
        EvidenceStatus.MISSING,
        EvidenceStatus.AMBIGUOUS,
        EvidenceStatus.CONTRADICTORY,
    }
    seen: set[tuple[str, str]] = set()
    questions: list[ClarificationQuestion] = []
    for mapping in mappings:
        if mapping.status not in needs_question:
            continue
        question_text = _question_for_mapping(mapping)
        key = (mapping.requirement_id, question_text.lower())
        if key in seen:
            continue
        seen.add(key)
        questions.append(
            ClarificationQuestion(
                project_id=project_id,
                requirement_id=mapping.requirement_id,
                evidence_mapping_id=mapping.id,
                question_text=question_text,
                state=QuestionState.OPEN,
            )
        )
    return questions


def _question_for_mapping(mapping: EvidenceMapping) -> str:
    if mapping.status == EvidenceStatus.CONTRADICTORY:
        return "Which cited application statement is correct for this requirement?"
    if mapping.status == EvidenceStatus.AMBIGUOUS:
        return "Can you clarify the specific evidence that satisfies this requirement?"
    if mapping.missing_items:
        return mapping.missing_items[0]
    return "What application evidence satisfies this requirement?"
