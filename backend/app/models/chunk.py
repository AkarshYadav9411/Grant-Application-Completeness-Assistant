"""
DocumentChunk model for granular text excerpts from guidelines and applications.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import DocumentType

if TYPE_CHECKING:
    from app.models.application import ApplicationVersion
    from app.models.guideline import GuidelineVersion


class DocumentChunk(Base):
    """
    Structured text chunk extracted from a guideline or application document.
    Maintains provenance (page, section, character offsets) for evidence citations.
    """

    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    guideline_version_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("guideline_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    application_version_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("application_versions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(
            DocumentType,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    page_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    section_heading: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    paragraph_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    char_start: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    char_end: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    token_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    # Table arguments: Indexes & Constraints
    __table_args__ = (
        Index("ix_chunks_guideline_idx", "guideline_version_id", "chunk_index"),
        Index("ix_chunks_app_idx", "application_version_id", "chunk_index"),
        CheckConstraint(
            "(guideline_version_id IS NOT NULL AND application_version_id IS NULL) OR "
            "(guideline_version_id IS NULL AND application_version_id IS NOT NULL)",
            name="ck_document_chunk_owner",
        ),
    )

    # Relationships
    guideline_version: Mapped[Optional[GuidelineVersion]] = relationship(
        "GuidelineVersion",
        back_populates="chunks",
    )
    application_version: Mapped[Optional[ApplicationVersion]] = relationship(
        "ApplicationVersion",
        back_populates="chunks",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk(id={self.id!r}, type={self.document_type.value!r}, "
            f"index={self.chunk_index}, page={self.page_number})>"
        )
