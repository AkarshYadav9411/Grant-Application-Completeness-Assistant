"""
EvidenceMapping and UserReview models for AI-extracted evidence and human audit trail (§8, §17).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import EvidenceSourceType, EvidenceStatus, ReviewAction

if TYPE_CHECKING:
    from app.models.application import ApplicationVersion
    from app.models.assessment import Assessment
    from app.models.chunk import DocumentChunk
    from app.models.project import Project
    from app.models.question import ClarificationQuestion
    from app.models.requirement import Requirement
    from app.models.supporting_doc import SupportingDocument


class EvidenceMapping(Base):
    """
    Mapping of application evidence to a specific guideline requirement (§8).
    Maintains AI proposed status, confidence, citations, and links to user reviews.
    """

    __tablename__ = "evidence_mappings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assessment_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_version_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("application_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[EvidenceStatus] = mapped_column(
        SQLEnum(
            EvidenceStatus,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=EvidenceStatus.MISSING,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    evidence_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    source_document: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    source_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    source_page: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    source_section: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    source_chunk_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    explanation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    missing_items: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    contradictory_evidence: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
    )
    source_type: Mapped[EvidenceSourceType] = mapped_column(
        SQLEnum(
            EvidenceSourceType,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=EvidenceSourceType.APPLICATION,
        nullable=False,
    )
    supporting_document_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("supporting_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    citation_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Table arguments
    __table_args__ = (
        Index("ix_evidence_proj_req", "project_id", "requirement_id"),
        Index("ix_evidence_status", "status"),
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="evidence_mappings",
    )
    assessment: Mapped[Optional[Assessment]] = relationship(
        "Assessment",
        back_populates="evidence_mappings",
    )
    requirement: Mapped[Requirement] = relationship(
        "Requirement",
        back_populates="evidence_mappings",
    )
    application_version: Mapped[Optional[ApplicationVersion]] = relationship(
        "ApplicationVersion",
        back_populates="evidence_mappings",
    )
    source_chunk: Mapped[Optional[DocumentChunk]] = relationship(
        "DocumentChunk",
    )
    supporting_document: Mapped[Optional[SupportingDocument]] = relationship(
        "SupportingDocument",
    )
    user_review: Mapped[Optional[UserReview]] = relationship(
        "UserReview",
        back_populates="evidence_mapping",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    clarification_questions: Mapped[List[ClarificationQuestion]] = relationship(
        "ClarificationQuestion",
        back_populates="evidence_mapping",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def effective_status(self) -> EvidenceStatus:
        """
        The effective status used in scoring (§16, §17).
        Returns human-reviewed status if reviewed, else the AI-generated status.
        """
        if self.user_review is not None:
            if self.user_review.action == ReviewAction.CONFIRMED:
                return self.status
            elif self.user_review.action == ReviewAction.REJECTED:
                return EvidenceStatus.REJECTED
            elif (
                self.user_review.action == ReviewAction.EDITED
                and self.user_review.reviewed_status is not None
            ):
                return self.user_review.reviewed_status
        return self.status

    @property
    def effective_evidence_text(self) -> Optional[str]:
        """User-edited evidence if edited, else original AI evidence."""
        if (
            self.user_review is not None
            and self.user_review.action == ReviewAction.EDITED
            and self.user_review.reviewed_evidence_text is not None
        ):
            return self.user_review.reviewed_evidence_text
        return self.evidence_text

    @property
    def effective_explanation(self) -> Optional[str]:
        """User-edited explanation if edited, else original AI explanation."""
        if (
            self.user_review is not None
            and self.user_review.action == ReviewAction.EDITED
            and self.user_review.reviewed_explanation is not None
        ):
            return self.user_review.reviewed_explanation
        return self.explanation

    def __repr__(self) -> str:
        return (
            f"<EvidenceMapping(id={self.id!r}, req_id={self.requirement_id!r}, "
            f"ai_status={self.status.value!r}, effective={self.effective_status.value!r})>"
        )


class UserReview(Base):
    """
    Human review decision for an evidence mapping (§17).
    Never overwrites original AI values; stores reviewer override and audit trail.
    """

    __tablename__ = "user_reviews"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    evidence_mapping_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evidence_mappings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    action: Mapped[ReviewAction] = mapped_column(
        SQLEnum(
            ReviewAction,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    reviewed_status: Mapped[Optional[EvidenceStatus]] = mapped_column(
        SQLEnum(
            EvidenceStatus,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    reviewed_evidence_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    reviewed_explanation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    reviewer_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        default="Reviewer",
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    evidence_mapping: Mapped[EvidenceMapping] = relationship(
        "EvidenceMapping",
        back_populates="user_review",
    )

    def __repr__(self) -> str:
        return f"<UserReview(id={self.id!r}, action={self.action.value!r})>"
