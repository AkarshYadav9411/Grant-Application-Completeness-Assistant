"""
Project model representing a grant application review workspace.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.application import Application
    from app.models.assessment import Assessment
    from app.models.evidence import EvidenceMapping
    from app.models.guideline import GrantGuideline
    from app.models.question import ClarificationQuestion
    from app.models.supporting_doc import SupportingDocument


class Project(Base):
    """
    Project workspace representing a single grant review engagement.
    Encapsulates guidelines, applications, requirements, supporting docs, and assessments.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
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
    guideline: Mapped[Optional[GrantGuideline]] = relationship(
        "GrantGuideline",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    application: Mapped[Optional[Application]] = relationship(
        "Application",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    supporting_documents: Mapped[List[SupportingDocument]] = relationship(
        "SupportingDocument",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    assessments: Mapped[List[Assessment]] = relationship(
        "Assessment",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    clarification_questions: Mapped[List[ClarificationQuestion]] = relationship(
        "ClarificationQuestion",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    evidence_mappings: Mapped[List[EvidenceMapping]] = relationship(
        "EvidenceMapping",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id!r}, name={self.name!r})>"
