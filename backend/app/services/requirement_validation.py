"""
Validation helpers for AI-proposed requirements.
"""

from __future__ import annotations

import re

from app.ai.providers import classify_priority
from app.models import DocumentChunk
from app.models.enums import RequirementPriority
from app.schemas.requirements import ExtractedRequirement


def whitespace_normalize(text: str) -> str:
    """Normalize whitespace for verbatim substring checks."""
    return re.sub(r"\s+", " ", text).strip()


def source_text_in_chunk(source_text: str, chunk: DocumentChunk) -> bool:
    """Return True when source_text appears verbatim after whitespace normalization."""
    return whitespace_normalize(source_text) in whitespace_normalize(chunk.text)


def priority_flagged_for_review(requirement: ExtractedRequirement) -> bool:
    """Flag AI priority when deterministic cue logic disagrees."""
    cue_priority = classify_priority(requirement.source_text)
    return cue_priority is not None and cue_priority != requirement.priority
