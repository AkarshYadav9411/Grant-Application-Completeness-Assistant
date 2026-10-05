"""
Assessment and AssessmentItem models for evaluation runs, scoring history, and staleness (§16, §18, §19).
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
from app.models.enums import (
    AssessmentStatus,
    EvidenceStatus,
    OverallReviewStatus,
    RequirementCategory,
    RequirementPriority,
)

if TYPE_CHECKING:
    from app.models.application import ApplicationVersion
    from app.models.evidence import EvidenceMapping
    from app.models.guideline import GuidelineVersion
    from app.models.project import Project
    from app.models.requirement import Requirement


class Assessment(Base):
    """
    Assessment run record containing deterministic completeness scores and statistics (§16).
    Links to source guideline and application versions; tracks staleness (§19).
    """

    __tablename__ = "assessments"

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
    guideline_version_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("guideline_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    application_version_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("application_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assessment_status: Mapped[AssessmentStatus] = mapped_column(
        SQLEnum(
            AssessmentStatus,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=AssessmentStatus.IN_PROGRESS,
        nullable=False,
    )
    overall_status: Mapped[Optional[OverallReviewStatus]] = mapped_column(
        SQLEnum(
            OverallReviewStatus,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=True,
    )
    mandatory_completeness: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    recommended_completeness: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    overall_completeness: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # Counts per status (mandatory)
    mandatory_supported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mandatory_partial_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mandatory_missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mandatory_ambiguous_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mandatory_contradictory_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mandatory_rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mandatory_total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Counts per status (recommended)
    recommended_supported_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommended_partial_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommended_missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommended_ambiguous_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommended_contradictory_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommended_rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recommended_total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Critical missing items and snapshot
    critical_missing_items: Mapped[List[Any]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    requirements_snapshot: Mapped[List[Any]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    # Staleness management (§19)
    is_stale: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    stale_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
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

    # Table arguments
    __table_args__ = (
        Index("ix_assessments_proj_date", "project_id", "created_at"),
        Index("ix_assessments_stale", "project_id", "is_stale"),
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="assessments",
    )
    guideline_version: Mapped[Optional[GuidelineVersion]] = relationship(
        "GuidelineVersion",
        back_populates="assessments",
    )
    application_version: Mapped[Optional[ApplicationVersion]] = relationship(
        "ApplicationVersion",
        back_populates="assessments",
    )
    items: Mapped[List[AssessmentItem]] = relationship(
        "AssessmentItem",
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="AssessmentItem.requirement_identifier",
        lazy="selectin",
    )
    evidence_mappings: Mapped[List[EvidenceMapping]] = relationship(
        "EvidenceMapping",
        back_populates="assessment",
    )

    def __repr__(self) -> str:
        return (
            f"<Assessment(id={self.id!r}, project_id={self.project_id!r}, "
            f"overall={self.overall_completeness}, status={self.overall_status})>"
        )


class AssessmentItem(Base):
    """
    Individual requirement assessment record within an assessment run.
    Preserves historical state and deterministic point calculations.
    """

    __tablename__ = "assessment_items"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    assessment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence_mapping_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("evidence_mappings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    requirement_identifier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    requirement_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    requirement_category: Mapped[RequirementCategory] = mapped_column(
        SQLEnum(
            RequirementCategory,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    requirement_priority: Mapped[RequirementPriority] = mapped_column(
        SQLEnum(
            RequirementPriority,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    ai_status: Mapped[EvidenceStatus] = mapped_column(
        SQLEnum(
            EvidenceStatus,
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
    effective_status: Mapped[EvidenceStatus] = mapped_column(
        SQLEnum(
            EvidenceStatus,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    points: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    in_denominator: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    evidence_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    source_citation: Mapped[Optional[Any]] = mapped_column(
        JSON,
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Table arguments
    __table_args__ = (
        Index("ix_assessment_items_effective_status", "effective_status"),
    )

    # Relationships
    assessment: Mapped[Assessment] = relationship(
        "Assessment",
        back_populates="items",
    )
    requirement: Mapped[Optional[Requirement]] = relationship(
        "Requirement",
    )
    evidence_mapping: Mapped[Optional[EvidenceMapping]] = relationship(
        "EvidenceMapping",
    )

    def __repr__(self) -> str:
        return (
            f"<AssessmentItem(id={self.id!r}, req={self.requirement_identifier!r}, "
            f"effective={self.effective_status.value!r}, points={self.points})>"
        )
