"""
Requirement extraction orchestration.

Routes call this service; AI provider code and validation stay outside FastAPI
route functions.
"""

from __future__ import annotations

import json

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.prompts import REQUIREMENT_EXTRACTION_REPAIR_PROMPT
from app.ai.providers import RequirementExtractionProvider
from app.models import DocumentChunk, GrantGuideline, GuidelineVersion, Requirement
from app.schemas.requirements import RequirementExtractionPayload
from app.services.requirement_validation import (
    priority_flagged_for_review,
    source_text_in_chunk,
)
from app.utils.errors import raise_error


async def get_current_guideline_version(
    db: AsyncSession,
    project_id: str,
) -> GuidelineVersion:
    """Return the latest guideline version for a project."""
    result = await db.execute(
        select(GrantGuideline)
        .where(GrantGuideline.project_id == project_id)
        .options(selectinload(GrantGuideline.versions))
    )
    guideline = result.scalar_one_or_none()
    if guideline is None or guideline.current_version is None:
        raise_error(
            400,
            "GUIDELINE_REQUIRED",
            "Upload a grant guideline before extracting requirements.",
        )
    return guideline.current_version


async def extract_requirements_for_project(
    db: AsyncSession,
    *,
    project_id: str,
    provider: RequirementExtractionProvider,
) -> list[Requirement]:
    """Extract, validate, and store requirements for the latest guideline version."""
    guideline_version = await get_current_guideline_version(db, project_id)
    chunks = await _load_guideline_chunks(db, guideline_version.id)
    if not chunks:
        raise_error(
            400,
            "NO_GUIDELINE_CHUNKS",
            "The current guideline version has no extracted text chunks.",
        )

    raw_response = await provider.extract_requirements(
        guideline_version=guideline_version,
        chunks=chunks,
    )
    payload = _parse_provider_payload(raw_response)
    if payload is None:
        raw_response = await provider.extract_requirements(
            guideline_version=guideline_version,
            chunks=chunks,
            repair_prompt=REQUIREMENT_EXTRACTION_REPAIR_PROMPT,
        )
        payload = _parse_provider_payload(raw_response)
    if payload is None:
        raise_error(
            502,
            "INVALID_AI_RESPONSE",
            "The AI provider returned invalid requirement JSON. Nothing was stored.",
        )

    chunk_by_id = {chunk.id: chunk for chunk in chunks}
    requirements: list[Requirement] = []
    for index, extracted in enumerate(payload.requirements, start=1):
        chunk = chunk_by_id.get(extracted.source.chunk_id)
        if chunk is None or not source_text_in_chunk(extracted.source_text, chunk):
            raise_error(
                422,
                "INVALID_REQUIREMENT_SOURCE",
                "A requirement quote was not found in the cited guideline chunk. Nothing was stored.",
            )
        requirements.append(
            Requirement(
                guideline_version_id=guideline_version.id,
                requirement_id=f"REQ-{index:03d}",
                title=extracted.title,
                description=extracted.description,
                category=extracted.category,
                priority=extracted.priority,
                source_document=extracted.source.document,
                source_page=extracted.source.page,
                source_section=extracted.source.section,
                source_text=extracted.source_text,
                source_chunk_id=chunk.id,
                is_manually_added=False,
                priority_flagged_for_review=priority_flagged_for_review(extracted),
            )
        )

    await db.execute(delete(Requirement).where(Requirement.guideline_version_id == guideline_version.id))
    db.add_all(requirements)
    await db.flush()
    for requirement in requirements:
        await db.refresh(requirement)
    return requirements


async def list_current_requirements(db: AsyncSession, project_id: str) -> list[Requirement]:
    """List requirements attached to the latest guideline version."""
    guideline_version = await get_current_guideline_version(db, project_id)
    result = await db.execute(
        select(Requirement)
        .where(Requirement.guideline_version_id == guideline_version.id)
        .order_by(Requirement.requirement_id)
    )
    return list(result.scalars().all())


async def next_manual_requirement_id(db: AsyncSession, guideline_version_id: str) -> str:
    """Return the next REQ-### identifier for a guideline version."""
    result = await db.execute(
        select(Requirement.requirement_id)
        .where(Requirement.guideline_version_id == guideline_version_id)
        .order_by(Requirement.requirement_id)
    )
    max_number = 0
    for identifier in result.scalars().all():
        try:
            max_number = max(max_number, int(identifier.replace("REQ-", "")))
        except ValueError:
            continue
    return f"REQ-{max_number + 1:03d}"


async def get_requirement_or_404(db: AsyncSession, requirement_pk: str) -> Requirement:
    """Fetch a requirement by database primary key."""
    requirement = await db.get(Requirement, requirement_pk)
    if requirement is None:
        raise_error(404, "REQUIREMENT_NOT_FOUND", "Requirement not found.")
    return requirement


async def _load_guideline_chunks(db: AsyncSession, guideline_version_id: str) -> list[DocumentChunk]:
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.guideline_version_id == guideline_version_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(result.scalars().all())


def _parse_provider_payload(raw_response: str) -> RequirementExtractionPayload | None:
    try:
        parsed = json.loads(raw_response)
        return RequirementExtractionPayload.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None
