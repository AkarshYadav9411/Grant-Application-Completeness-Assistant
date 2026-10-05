"""
GrantGuideline and GuidelineVersion models for guideline document management and versioning.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    DateTime,
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

if TYPE_CHECKING:
    from app.models.assessment import Assessment
    from app.models.chunk import DocumentChunk
    from app.models.project import Project
    from app.models.requirement import Requirement


class GrantGuideline(Base):
    """
    Guideline container entity for a project.
    Holds reference to all historical and current versions of guidelines.
    """

    __tablename__ = "grant_guidelines"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        default="Grant Guideline",
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

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="guideline",
    )
    versions: Mapped[List[GuidelineVersion]] = relationship(
        "GuidelineVersion",
        back_populates="guideline",
        cascade="all, delete-orphan",
        order_by="GuidelineVersion.version_number",
        lazy="selectin",
    )

    @property
    def current_version(self) -> Optional[GuidelineVersion]:
        """Return the latest version if available."""
        return self.versions[-1] if self.versions else None

    def __repr__(self) -> str:
        return f"<GrantGuideline(id={self.id!r}, project_id={self.project_id!r})>"


class GuidelineVersion(Base):
    """
    Immutable version snapshot of an uploaded grant guideline document (§5, §18).
    Duplicate uploads within the same guideline slot are rejected by file_hash uniqueness.
    """

    __tablename__ = "guideline_versions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    guideline_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("grant_guidelines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    raw_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    total_pages: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    total_chunks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Table arguments: Indexes & Constraints
    __table_args__ = (
        UniqueConstraint("guideline_id", "version_number", name="uq_guideline_version_number"),
        UniqueConstraint("guideline_id", "file_hash", name="uq_guideline_file_hash"),
        Index("ix_guideline_version_lookup", "guideline_id", "version_number"),
    )

    # Relationships
    guideline: Mapped[GrantGuideline] = relationship(
        "GrantGuideline",
        back_populates="versions",
    )
    chunks: Mapped[List[DocumentChunk]] = relationship(
        "DocumentChunk",
        back_populates="guideline_version",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
        lazy="selectin",
    )
    requirements: Mapped[List[Requirement]] = relationship(
        "Requirement",
        back_populates="guideline_version",
        cascade="all, delete-orphan",
        order_by="Requirement.requirement_id",
        lazy="selectin",
    )
    assessments: Mapped[List[Assessment]] = relationship(
        "Assessment",
        back_populates="guideline_version",
    )

    def __repr__(self) -> str:
        return (
            f"<GuidelineVersion(id={self.id!r}, v={self.version_number}, "
            f"filename={self.filename!r})>"
        )
