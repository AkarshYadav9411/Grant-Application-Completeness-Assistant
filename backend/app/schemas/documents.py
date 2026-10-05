"""
Pydantic schemas for uploaded guideline and application versions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SupportingDocumentStatus


class DocumentVersionRead(BaseModel):
    """Response schema shared by guideline and application versions."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    version_number: int
    filename: str
    file_hash: str
    file_size_bytes: int
    mime_type: str
    total_pages: Optional[int]
    total_chunks: int
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    """Upload response including the parent document slot."""

    document_id: str
    version: DocumentVersionRead


class SupportingDocumentCreate(BaseModel):
    """Supporting-document metadata creation request."""

    name: str = Field(..., min_length=1, max_length=255)
    document_type: Optional[str] = Field(default=None, max_length=100)
    status: SupportingDocumentStatus = SupportingDocumentStatus.MISSING
    related_requirement_ids: list[str] = Field(default_factory=list)
    notes: Optional[str] = None


class SupportingDocumentUpdate(BaseModel):
    """Supporting-document metadata update request."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    document_type: Optional[str] = Field(default=None, max_length=100)
    status: Optional[SupportingDocumentStatus] = None
    related_requirement_ids: Optional[list[str]] = None
    notes: Optional[str] = None


class SupportingDocumentRead(BaseModel):
    """Supporting-document metadata response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    document_type: Optional[str]
    status: SupportingDocumentStatus
    related_requirement_ids: list[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
