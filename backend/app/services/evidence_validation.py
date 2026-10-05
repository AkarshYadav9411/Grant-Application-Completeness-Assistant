"""
Validation helpers for evidence citations.
"""

from __future__ import annotations

import re

from app.models import DocumentChunk


def whitespace_normalize(text: str) -> str:
    """Normalize whitespace for verbatim substring checks."""
    return re.sub(r"\s+", " ", text).strip()


def evidence_in_chunk(evidence_text: str, chunk: DocumentChunk) -> bool:
    """Return True when evidence text appears in the cited chunk after whitespace normalization."""
    return whitespace_normalize(evidence_text) in whitespace_normalize(chunk.text)
