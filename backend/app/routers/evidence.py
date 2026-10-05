"""
Evidence mapping, assessment run, and clarification question endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.providers import get_evidence_provider
from app.config import Settings, get_settings
from app.database import get_db
from app.models import Assessment
from app.schemas.assessments import AssessmentRead
from app.schemas.evidence import (
    AssessmentRunResponse,
    ClarificationQuestionRead,
    ClarificationQuestionUpdate,
    EvidenceConfirmRequest,
    EvidenceMappingRead,
    EvidenceRejectRequest,
    EvidenceReviewUpdate,
)
from app.services.document_upload import get_project_or_404
from app.services.evidence_mapping import (
    confirm_evidence_mapping,
    edit_evidence_mapping,
    get_question_or_404,
    list_evidence_mappings,
    list_questions,
    reject_evidence_mapping,
    run_evidence_mapping_for_project,
)
from app.services.reporting import render_assessment_report, report_filename
from app.utils.errors import raise_error

router = APIRouter(tags=["evidence"])


@router.post("/api/projects/{project_id}/assess", response_model=AssessmentRunResponse)
async def run_assessment(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AssessmentRunResponse:
    """Run evidence mapping for the latest guideline/application versions."""
    await get_project_or_404(db, project_id)
    assessment, mappings, questions = await run_evidence_mapping_for_project(
        db,
        project_id=project_id,
        provider=get_evidence_provider(settings),
    )
    return AssessmentRunResponse(
        assessment_id=assessment.id,
        guideline_version_id=assessment.guideline_version_id,
        application_version_id=assessment.application_version_id,
        evidence_count=len(mappings),
        question_count=len(questions),
        evidence=[EvidenceMappingRead.model_validate(mapping) for mapping in mappings],
        questions=[ClarificationQuestionRead.model_validate(question) for question in questions],
    )


@router.get("/api/projects/{project_id}/evidence", response_model=list[EvidenceMappingRead])
async def get_evidence(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list:
    """List current evidence mappings for a project."""
    await get_project_or_404(db, project_id)
    return await list_evidence_mappings(db, project_id)


@router.get("/api/projects/{project_id}/assessment", response_model=AssessmentRead)
async def get_latest_assessment(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> Assessment:
    """Return the latest assessment for a project, including stored stale state."""
    await get_project_or_404(db, project_id)
    result = await db.execute(
        select(Assessment)
        .where(Assessment.project_id == project_id)
        .order_by(Assessment.created_at.desc())
        .limit(1)
    )
    assessment = result.scalar_one_or_none()
    if assessment is None:
        from app.utils.errors import raise_error

        raise_error(404, "ASSESSMENT_NOT_FOUND", "No assessment has been generated for this project.")
    return assessment


@router.get("/api/projects/{project_id}/assessments", response_model=list[AssessmentRead])
async def list_assessments(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[Assessment]:
    """Return assessment history for a project."""
    await get_project_or_404(db, project_id)
    result = await db.execute(
        select(Assessment)
        .where(Assessment.project_id == project_id)
        .order_by(Assessment.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/api/projects/{project_id}/assessment/report")
async def export_latest_assessment_report(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export the latest assessment as a Markdown report."""
    project = await get_project_or_404(db, project_id)
    result = await db.execute(
        select(Assessment)
        .where(Assessment.project_id == project_id)
        .options(selectinload(Assessment.items))
        .order_by(Assessment.created_at.desc())
        .limit(1)
    )
    assessment = result.scalar_one_or_none()
    if assessment is None:
        raise_error(404, "ASSESSMENT_NOT_FOUND", "No assessment has been generated for this project.")

    return Response(
        content=render_assessment_report(project, assessment),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{report_filename(project, assessment)}"'
        },
    )


@router.put("/api/evidence/{evidence_id}", response_model=EvidenceMappingRead)
async def edit_evidence(
    evidence_id: str,
    payload: EvidenceReviewUpdate,
    db: AsyncSession = Depends(get_db),
) -> EvidenceMappingRead:
    """Edit reviewer-effective status/evidence/explanation without overwriting AI output."""
    mapping = await edit_evidence_mapping(db, evidence_id, payload)
    return EvidenceMappingRead.model_validate(mapping)


@router.post("/api/evidence/{evidence_id}/confirm", response_model=EvidenceMappingRead)
async def confirm_evidence(
    evidence_id: str,
    payload: EvidenceConfirmRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> EvidenceMappingRead:
    """Confirm the AI mapping as reviewed."""
    payload = payload or EvidenceConfirmRequest()
    mapping = await confirm_evidence_mapping(
        db,
        evidence_id,
        reviewer_name=payload.reviewer_name,
        notes=payload.notes,
    )
    return EvidenceMappingRead.model_validate(mapping)


@router.post("/api/evidence/{evidence_id}/reject", response_model=EvidenceMappingRead)
async def reject_evidence(
    evidence_id: str,
    payload: EvidenceRejectRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> EvidenceMappingRead:
    """Reject the AI mapping as reviewed."""
    payload = payload or EvidenceRejectRequest()
    mapping = await reject_evidence_mapping(
        db,
        evidence_id,
        reviewer_name=payload.reviewer_name,
        notes=payload.notes,
    )
    return EvidenceMappingRead.model_validate(mapping)


@router.get("/api/projects/{project_id}/questions", response_model=list[ClarificationQuestionRead])
async def get_questions(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list:
    """List clarification questions for a project."""
    await get_project_or_404(db, project_id)
    return await list_questions(db, project_id)


@router.put("/api/questions/{question_id}", response_model=ClarificationQuestionRead)
async def update_question(
    question_id: str,
    payload: ClarificationQuestionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Answer or dismiss a clarification question."""
    question = await get_question_or_404(db, question_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(question, field, value)
    await db.flush()
    await db.refresh(question)
    return question
