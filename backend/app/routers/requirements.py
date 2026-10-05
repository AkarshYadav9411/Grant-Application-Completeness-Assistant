"""
Requirement extraction and review endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers import get_requirement_provider
from app.config import Settings, get_settings
from app.database import get_db
from app.models import Requirement
from app.schemas.requirements import (
    RequirementCreate,
    RequirementExtractionResponse,
    RequirementRead,
    RequirementUpdate,
)
from app.services.document_upload import get_project_or_404
from app.services.requirement_extraction import (
    extract_requirements_for_project,
    get_current_guideline_version,
    get_requirement_or_404,
    list_current_requirements,
    next_manual_requirement_id,
)
from app.services.staleness import mark_project_assessments_stale, project_id_for_requirement

router = APIRouter(tags=["requirements"])


@router.post(
    "/api/projects/{project_id}/requirements/extract",
    response_model=RequirementExtractionResponse,
)
async def extract_requirements(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RequirementExtractionResponse:
    """Extract requirements from the latest guideline version."""
    await get_project_or_404(db, project_id)
    provider = get_requirement_provider(settings)
    requirements = await extract_requirements_for_project(
        db,
        project_id=project_id,
        provider=provider,
    )
    await mark_project_assessments_stale(
        db,
        project_id,
        "Requirements were re-extracted for the current guideline version.",
    )
    guideline_version_id = requirements[0].guideline_version_id if requirements else (
        await get_current_guideline_version(db, project_id)
    ).id
    return RequirementExtractionResponse(
        guideline_version_id=guideline_version_id,
        count=len(requirements),
        requirements=[RequirementRead.model_validate(item) for item in requirements],
    )


@router.get("/api/projects/{project_id}/requirements", response_model=list[RequirementRead])
async def get_requirements(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[Requirement]:
    """List requirements for the latest guideline version."""
    await get_project_or_404(db, project_id)
    return await list_current_requirements(db, project_id)


@router.post("/api/projects/{project_id}/requirements", response_model=RequirementRead, status_code=201)
async def add_requirement(
    project_id: str,
    payload: RequirementCreate,
    db: AsyncSession = Depends(get_db),
) -> Requirement:
    """Manually add a requirement to the latest guideline version."""
    await get_project_or_404(db, project_id)
    guideline_version = await get_current_guideline_version(db, project_id)
    requirement = Requirement(
        guideline_version_id=guideline_version.id,
        requirement_id=await next_manual_requirement_id(db, guideline_version.id),
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        source_document=guideline_version.filename,
        source_text=payload.source_text,
        is_manually_added=True,
        priority_flagged_for_review=False,
    )
    db.add(requirement)
    await db.flush()
    await db.refresh(requirement)
    await mark_project_assessments_stale(
        db,
        project_id,
        "A requirement was added.",
    )
    return requirement


@router.put("/api/requirements/{requirement_id}", response_model=RequirementRead)
async def update_requirement(
    requirement_id: str,
    payload: RequirementUpdate,
    db: AsyncSession = Depends(get_db),
) -> Requirement:
    """Edit a requirement."""
    requirement = await get_requirement_or_404(db, requirement_id)
    project_id = await project_id_for_requirement(db, requirement.id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(requirement, field, value)
    await db.flush()
    await db.refresh(requirement)
    if project_id is not None:
        await mark_project_assessments_stale(
            db,
            project_id,
            "A requirement was edited.",
        )
    return requirement


@router.delete("/api/requirements/{requirement_id}", status_code=204)
async def delete_requirement(
    requirement_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a requirement."""
    requirement = await get_requirement_or_404(db, requirement_id)
    project_id = await project_id_for_requirement(db, requirement.id)
    await db.delete(requirement)
    await db.flush()
    if project_id is not None:
        await mark_project_assessments_stale(
            db,
            project_id,
            "A requirement was deleted.",
        )
    return Response(status_code=204)
