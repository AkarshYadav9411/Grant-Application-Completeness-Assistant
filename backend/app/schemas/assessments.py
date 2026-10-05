"""
Pydantic schemas for assessment history and stale state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import AssessmentStatus, OverallReviewStatus


class AssessmentRead(BaseModel):
    """Assessment history response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    guideline_version_id: Optional[str]
    application_version_id: Optional[str]
    assessment_status: AssessmentStatus
    overall_status: Optional[OverallReviewStatus]
    mandatory_completeness: Optional[float]
    recommended_completeness: Optional[float]
    overall_completeness: Optional[float]
    mandatory_total_count: int
    recommended_total_count: int
    critical_missing_items: list[Any]
    requirements_snapshot: list[Any]
    is_stale: bool
    stale_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
