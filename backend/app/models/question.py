"""
ClarificationQuestion model for targeted application clarification inquiries (§14).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import QuestionState

if TYPE_CHECKING:
    from app.models.evidence import EvidenceMapping
    from app.models.project import Project
    from app.models.requirement import Requirement


class ClarificationQuestion(Base):
    """
    Actionable clarification question generated for missing, partial, ambiguous,
    or contradictory evidence (§14). Tracks lifecycle (open, answered, dismissed).
    """

    __tablename__ = "clarification_questions"

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
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_mapping_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("evidence_mappings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    state: Mapped[QuestionState] = mapped_column(
        SQLEnum(
            QuestionState,
            native_enum=False,
            length=50,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        default=QuestionState.OPEN,
        nullable=False,
    )
    answer_text: Mapped[Optional[str]] = mapped_column(
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
        Index("ix_questions_project_state", "project_id", "state"),
    )

    # Relationships
    project: Mapped[Project] = relationship(
        "Project",
        back_populates="clarification_questions",
    )
    requirement: Mapped[Requirement] = relationship(
        "Requirement",
        back_populates="clarification_questions",
    )
    evidence_mapping: Mapped[Optional[EvidenceMapping]] = relationship(
        "EvidenceMapping",
        back_populates="clarification_questions",
    )

    def __repr__(self) -> str:
        return (
            f"<ClarificationQuestion(id={self.id!r}, req_id={self.requirement_id!r}, "
            f"state={self.state.value!r})>"
        )
