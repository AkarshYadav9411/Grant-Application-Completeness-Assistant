"""
Requirement model representing structured requirements extracted from a grant guideline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RequirementCategory, RequirementPriority

if TYPE_CHECKING:
    from app.models.chunk import DocumentChunk
    from app.models.evidence import EvidenceMapping
    from app.models.guideline import GuidelineVersion
    from app.models.question import ClarificationQuestion


class Requirement(Base):
    """
    Structured grant requirement extracted from a guideline version (§6, §7).
    Belongs to a specific guideline version; can be AI-extracted or user-created.
    """

    __tablename__ = "requirements"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    guideline_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("guideline_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    category: Mapped[RequirementCategory] = mapped_column(
        SQLEnum(
            RequirementCategory,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=RequirementCategory.OTHER,
        nullable=False,
    )
    priority: Mapped[RequirementPriority] = mapped_column(
        SQLEnum(
            RequirementPriority,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=RequirementPriority.MANDATORY,
        nullable=False,
    )
    source_document: Mapped[Optional[str]] = mapped_column(
        String(255),
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
    source_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    source_chunk_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_manually_added: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    priority_flagged_for_review: Mapped[bool] = mapped_column(
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

    # Table arguments: Unique constraint and indexes
    __table_args__ = (
        UniqueConstraint("guideline_version_id", "requirement_id", name="uq_guideline_req_id"),
        Index("ix_requirements_guideline_category", "guideline_version_id", "category"),
        Index("ix_requirements_guideline_priority", "guideline_version_id", "priority"),
    )

    # Relationships
    guideline_version: Mapped[GuidelineVersion] = relationship(
        "GuidelineVersion",
        back_populates="requirements",
    )
    source_chunk: Mapped[Optional[DocumentChunk]] = relationship(
        "DocumentChunk",
    )
    evidence_mappings: Mapped[List[EvidenceMapping]] = relationship(
        "EvidenceMapping",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )
    clarification_questions: Mapped[List[ClarificationQuestion]] = relationship(
        "ClarificationQuestion",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Requirement(id={self.requirement_id!r}, priority={self.priority.value!r}, "
            f"category={self.category.value!r})>"
        )
