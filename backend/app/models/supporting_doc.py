"""
SupportingDocument model for tracking supporting document metadata (§15).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import SupportingDocumentStatus

if TYPE_CHECKING:
    from app.models.project import Project


class SupportingDocument(Base):
    """
    Supporting document metadata tracker (§15).
    Tracks external documents (audited accounts, CVs, letters of support)
    without ingesting their raw content. Feeds status into required document requirements.
    """

    __tablename__ = "supporting_documents"

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
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    document_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    status: Mapped[SupportingDocumentStatus] = mapped_column(
        SQLEnum(
            SupportingDocumentStatus,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=SupportingDocumentStatus.MISSING,
        nullable=False,
    )
    related_requirement_ids: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
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

    # Table arguments
    __table_args__ = (
        Index("ix_supp_docs_proj_status", "project_id", "status"),
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="supporting_documents",
    )

    def __repr__(self) -> str:
        return f"<SupportingDocument(id={self.id!r}, name={self.name!r}, status={self.status.value!r})>"
