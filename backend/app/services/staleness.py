"""
Backend-owned stale assessment handling.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Assessment, GrantGuideline, GuidelineVersion, Requirement


async def mark_project_assessments_stale(
    db: AsyncSession,
    project_id: str,
    reason: str,
) -> None:
    """Mark all non-stale assessments for a project as stale."""
    await db.execute(
        update(Assessment)
        .where(Assessment.project_id == project_id, Assessment.is_stale.is_(False))
        .values(is_stale=True, stale_reason=reason)
    )


async def project_id_for_requirement(db: AsyncSession, requirement_id: str) -> str | None:
    """Resolve a requirement primary key to its project id."""
    result = await db.execute(
        select(GrantGuideline.project_id)
        .join(GuidelineVersion, GuidelineVersion.guideline_id == GrantGuideline.id)
        .join(Requirement, Requirement.guideline_version_id == GuidelineVersion.id)
        .where(Requirement.id == requirement_id)
    )
    return result.scalar_one_or_none()
