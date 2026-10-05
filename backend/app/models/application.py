"""
Application and ApplicationVersion models for draft application tracking and versioning.
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
    from app.models.evidence import EvidenceMapping
    from app.models.project import Project


class Application(Base):
    """
    Application container entity for a project.
    Holds reference to all historical and current versions of draft applications.
    """

    __tablename__ = "applications"

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
        default="Grant Application",
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
        back_populates="application",
    )
    versions: Mapped[List[ApplicationVersion]] = relationship(
        "ApplicationVersion",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationVersion.version_number",
        lazy="selectin",
    )

    @property
    def current_version(self) -> Optional[ApplicationVersion]:
        """Return the latest version if available."""
        return self.versions[-1] if self.versions else None

    def __repr__(self) -> str:
        return f"<Application(id={self.id!r}, project_id={self.project_id!r})>"


class ApplicationVersion(Base):
    """
    Immutable version snapshot of an uploaded grant application document (§5, §18).
    Duplicate uploads within the same application slot are rejected by file_hash uniqueness.
    """

    __tablename__ = "application_versions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    application_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("applications.id", ondelete="CASCADE"),
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
        UniqueConstraint("application_id", "version_number", name="uq_application_version_number"),
        UniqueConstraint("application_id", "file_hash", name="uq_application_file_hash"),
        Index("ix_application_version_lookup", "application_id", "version_number"),
    )

    # Relationships
    application: Mapped[Application] = relationship(
        "Application",
        back_populates="versions",
    )
    chunks: Mapped[List[DocumentChunk]] = relationship(
        "DocumentChunk",
        back_populates="application_version",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
        lazy="selectin",
    )
    evidence_mappings: Mapped[List[EvidenceMapping]] = relationship(
        "EvidenceMapping",
        back_populates="application_version",
    )
    assessments: Mapped[List[Assessment]] = relationship(
        "Assessment",
        back_populates="application_version",
    )

    def __repr__(self) -> str:
        return (
            f"<ApplicationVersion(id={self.id!r}, v={self.version_number}, "
            f"filename={self.filename!r})>"
        )
