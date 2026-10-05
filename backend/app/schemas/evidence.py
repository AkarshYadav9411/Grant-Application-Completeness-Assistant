"""
Pydantic schemas for evidence mapping and clarification questions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import EvidenceSourceType, EvidenceStatus, QuestionState, ReviewAction


class EvidenceSource(BaseModel):
    """Source metadata for a cited application chunk."""

    chunk_id: str
    document: str
    version: int
    page: Optional[int] = None
    section: Optional[str] = None


class ExtractedEvidenceMapping(BaseModel):
    """Provider-proposed evidence mapping for one requirement."""

    requirement_id: str
    status: EvidenceStatus
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_text: Optional[str] = None
    source: Optional[EvidenceSource] = None
    explanation: str = Field(..., min_length=1)
    missing_items: list[str] = Field(default_factory=list)
    contradictory_evidence: Optional[list[dict[str, Any]]] = None

    @model_validator(mode="after")
    def validate_evidence_for_status(self):
        evidence_required = {
            EvidenceStatus.SUPPORTED,
            EvidenceStatus.PARTIALLY_SUPPORTED,
            EvidenceStatus.AMBIGUOUS,
            EvidenceStatus.CONTRADICTORY,
        }
        if self.status in evidence_required and (not self.evidence_text or self.source is None):
            raise ValueError(f"{self.status.value} requires evidence_text and source")
        if self.status == EvidenceStatus.MISSING and not self.missing_items:
            raise ValueError("MISSING requires missing_items")
        if self.status == EvidenceStatus.NOT_APPLICABLE:
            raise ValueError("AI cannot finalize NOT_APPLICABLE")
        return self


class EvidenceMappingPayload(BaseModel):
    """Provider response shape for evidence mapping."""

    mappings: list[ExtractedEvidenceMapping]


class EvidenceMappingRead(BaseModel):
    """Evidence mapping API response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    assessment_id: Optional[str]
    requirement_id: str
    application_version_id: Optional[str]
    status: EvidenceStatus
    confidence: float
    evidence_text: Optional[str]
    source_document: Optional[str]
    source_version: Optional[str]
    source_page: Optional[int]
    source_section: Optional[str]
    source_chunk_id: Optional[str]
    explanation: Optional[str]
    missing_items: list[str]
    contradictory_evidence: Optional[Any]
    source_type: EvidenceSourceType
    supporting_document_id: Optional[str]
    citation_verified: bool
    effective_status: EvidenceStatus
    effective_evidence_text: Optional[str]
    effective_explanation: Optional[str]
    user_review: Optional["UserReviewRead"] = None
    created_at: datetime
    updated_at: datetime


class UserReviewRead(BaseModel):
    """Human review response attached to an evidence mapping."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    evidence_mapping_id: str
    action: ReviewAction
    reviewed_status: Optional[EvidenceStatus]
    reviewed_evidence_text: Optional[str]
    reviewed_explanation: Optional[str]
    reviewer_name: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class EvidenceConfirmRequest(BaseModel):
    """Confirm the AI-proposed mapping without changing it."""

    reviewer_name: Optional[str] = "Reviewer"
    notes: Optional[str] = None


class EvidenceRejectRequest(BaseModel):
    """Reject the AI-proposed mapping."""

    reviewer_name: Optional[str] = "Reviewer"
    notes: Optional[str] = None


class EvidenceReviewUpdate(BaseModel):
    """Reviewer edit for an evidence mapping.

    AI-generated values remain stored on EvidenceMapping. These fields are saved
    separately in UserReview and become the effective reviewed state.
    """

    reviewed_status: Optional[EvidenceStatus] = None
    reviewed_evidence_text: Optional[str] = None
    reviewed_explanation: Optional[str] = None
    reviewer_name: Optional[str] = "Reviewer"
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_has_review_change(self):
        if (
            self.reviewed_status is None
            and self.reviewed_evidence_text is None
            and self.reviewed_explanation is None
            and self.notes is None
        ):
            raise ValueError("Provide at least one review change.")
        return self


class ClarificationQuestionRead(BaseModel):
    """Clarification question API response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    requirement_id: str
    evidence_mapping_id: Optional[str]
    question_text: str
    state: QuestionState
    answer_text: Optional[str]
    created_at: datetime
    updated_at: datetime


class AssessmentRunResponse(BaseModel):
    """Response from POST /api/projects/{project_id}/assess in Phase 6."""

    assessment_id: str
    guideline_version_id: str
    application_version_id: str
    evidence_count: int
    question_count: int
    evidence: list[EvidenceMappingRead]
    questions: list[ClarificationQuestionRead]


class ClarificationQuestionUpdate(BaseModel):
    """Question update request."""

    state: Optional[QuestionState] = None
    answer_text: Optional[str] = None
