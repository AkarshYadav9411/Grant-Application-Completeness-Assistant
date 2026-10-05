"""
Pydantic schemas for requirement extraction, validation, and CRUD.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RequirementCategory, RequirementPriority


class RequirementSource(BaseModel):
    """Source metadata returned by an AI provider."""

    chunk_id: str
    document: str
    version: int
    page: Optional[int] = None
    section: Optional[str] = None


class ExtractedRequirement(BaseModel):
    """One provider-proposed requirement."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    category: RequirementCategory = RequirementCategory.OTHER
    priority: RequirementPriority = RequirementPriority.MANDATORY
    source: RequirementSource
    source_text: str = Field(..., min_length=1)


class RequirementExtractionPayload(BaseModel):
    """Provider response shape for requirement extraction."""

    requirements: list[ExtractedRequirement]


class RequirementRead(BaseModel):
    """Requirement API response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    guideline_version_id: str
    requirement_id: str
    title: str
    description: str
    category: RequirementCategory
    priority: RequirementPriority
    source_document: Optional[str]
    source_page: Optional[int]
    source_section: Optional[str]
    source_text: Optional[str]
    source_chunk_id: Optional[str]
    is_manually_added: bool
    priority_flagged_for_review: bool
    created_at: datetime
    updated_at: datetime


class RequirementCreate(BaseModel):
    """Manual requirement creation request."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    category: RequirementCategory = RequirementCategory.OTHER
    priority: RequirementPriority = RequirementPriority.MANDATORY
    source_text: Optional[str] = None


class RequirementUpdate(BaseModel):
    """Requirement edit request. All fields are optional."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, min_length=1)
    category: Optional[RequirementCategory] = None
    priority: Optional[RequirementPriority] = None
    source_text: Optional[str] = None


class RequirementExtractionResponse(BaseModel):
    """Response from POST /requirements/extract."""

    guideline_version_id: str
    count: int
    requirements: list[RequirementRead]
