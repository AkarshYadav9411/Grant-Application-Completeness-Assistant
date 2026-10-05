"""
Text extraction for supported document types.

This module performs deterministic, offline extraction only. OCR is deliberately
out of scope; PDFs without extractable text fail with a clear user-facing error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional

import fitz
from docx import Document
from fastapi import HTTPException

from app.utils.errors import raise_error


@dataclass(frozen=True)
class ExtractedChunk:
    """A single text chunk with citation metadata."""

    text: str
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    paragraph_index: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None

    @property
    def token_count(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class ExtractionResult:
    """Full extraction result for one document."""

    raw_text: str
    chunks: list[ExtractedChunk]
    total_pages: Optional[int] = None


def normalize_text(text: str) -> str:
    """Normalize text for storage while preserving human-readable paragraphs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _fail_extraction(message: str, code: str = "EXTRACTION_FAILED") -> None:
    raise_error(422, code, message)


def extract_text_from_bytes(filename: str, content: bytes) -> ExtractionResult:
    """Dispatch extraction based on file extension."""
    extension = Path(filename).suffix.lower()
    try:
        if extension == ".pdf":
            return extract_pdf(content)
        if extension == ".docx":
            return extract_docx(content)
        if extension in {".txt", ".md", ".markdown"}:
            return extract_plain_text(content, is_markdown=extension in {".md", ".markdown"})
    except HTTPException:
        raise
    except Exception:
        _fail_extraction(
            "Could not extract text from this file. Please verify the file is not corrupt."
        )

    _fail_extraction("Unsupported file type.")


def extract_pdf(content: bytes) -> ExtractionResult:
    """Extract text chunks from a PDF using PyMuPDF."""
    try:
        pdf = fitz.open(stream=content, filetype="pdf")
    except Exception:
        _fail_extraction(
            "Could not read this PDF. It may be corrupt or password-protected.",
            "PDF_EXTRACTION_FAILED",
        )

    if pdf.needs_pass:
        pdf.close()
        _fail_extraction(
            "This PDF is password-protected. Please upload an unlocked file.",
            "PDF_PASSWORD_PROTECTED",
        )

    chunks: list[ExtractedChunk] = []
    raw_pages: list[str] = []
    char_cursor = 0

    try:
        total_pages = pdf.page_count
        for page_index in range(total_pages):
            page = pdf.load_page(page_index)
            page_text = normalize_text(page.get_text("text"))
            if not page_text:
                continue
            raw_pages.append(page_text)
            paragraphs = _split_paragraphs(page_text)
            for paragraph_index, paragraph in enumerate(paragraphs):
                chunks.append(
                    ExtractedChunk(
                        text=paragraph,
                        page_number=page_index + 1,
                        section_heading=_infer_heading(paragraph),
                        paragraph_index=paragraph_index,
                        char_start=char_cursor,
                        char_end=char_cursor + len(paragraph),
                    )
                )
                char_cursor += len(paragraph) + 2
    finally:
        pdf.close()

    raw_text = normalize_text("\n\n".join(raw_pages))
    if not raw_text or not chunks:
        _fail_extraction(
            "No extractable text was found in this PDF. OCR is not supported.",
            "NO_EXTRACTABLE_TEXT",
        )

    return ExtractionResult(raw_text=raw_text, chunks=chunks, total_pages=total_pages)


def extract_docx(content: bytes) -> ExtractionResult:
    """Extract paragraph chunks from a DOCX file."""
    try:
        document = Document(BytesIO(content))
    except Exception:
        _fail_extraction(
            "Could not read this DOCX file. It may be corrupt.",
            "DOCX_EXTRACTION_FAILED",
        )

    chunks: list[ExtractedChunk] = []
    raw_parts: list[str] = []
    current_heading: Optional[str] = None
    char_cursor = 0

    for paragraph_index, paragraph in enumerate(document.paragraphs):
        text = normalize_text(paragraph.text)
        if not text:
            continue
        style_name = (paragraph.style.name if paragraph.style is not None else "").lower()
        if "heading" in style_name:
            current_heading = text[:255]

        raw_parts.append(text)
        chunks.append(
            ExtractedChunk(
                text=text,
                section_heading=current_heading or _infer_heading(text),
                paragraph_index=paragraph_index,
                char_start=char_cursor,
                char_end=char_cursor + len(text),
            )
        )
        char_cursor += len(text) + 2

    raw_text = normalize_text("\n\n".join(raw_parts))
    if not raw_text or not chunks:
        _fail_extraction("No extractable text was found in this DOCX file.", "NO_EXTRACTABLE_TEXT")

    return ExtractionResult(raw_text=raw_text, chunks=chunks)


def extract_plain_text(content: bytes, *, is_markdown: bool) -> ExtractionResult:
    """Extract paragraph chunks from TXT or Markdown bytes."""
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            _fail_extraction("Text files must be UTF-8 encoded.", "TEXT_DECODE_FAILED")

    raw_text = normalize_text(decoded)
    if not raw_text:
        _fail_extraction("No extractable text was found in this file.", "NO_EXTRACTABLE_TEXT")

    chunks: list[ExtractedChunk] = []
    current_heading: Optional[str] = None
    char_cursor = 0
    for paragraph_index, paragraph in enumerate(_split_paragraphs(raw_text)):
        if is_markdown and paragraph.startswith("#"):
            current_heading = paragraph.lstrip("#").strip()[:255] or current_heading
        else:
            inferred_heading = _infer_heading(paragraph)
            if inferred_heading:
                current_heading = inferred_heading

        chunks.append(
            ExtractedChunk(
                text=paragraph,
                section_heading=current_heading,
                paragraph_index=paragraph_index,
                char_start=char_cursor,
                char_end=char_cursor + len(paragraph),
            )
        )
        char_cursor += len(paragraph) + 2

    return ExtractionResult(raw_text=raw_text, chunks=chunks)


def _split_paragraphs(text: str) -> list[str]:
    """Split text into stable chunks by paragraphs, falling back to lines."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if len(paragraphs) == 1:
        paragraphs = [part.strip() for part in text.split("\n") if part.strip()]
    return paragraphs


def _infer_heading(text: str) -> Optional[str]:
    """Infer simple headings without making semantic claims."""
    stripped = text.strip().strip(":")
    if not stripped or len(stripped) > 80:
        return None
    if stripped.startswith("#"):
        return stripped.lstrip("#").strip()[:255] or None
    if stripped.isupper() and any(char.isalpha() for char in stripped):
        return stripped[:255]
    if re.match(r"^\d+(\.\d+)*\s+[A-Z][A-Za-z0-9 ,/&()-]+$", stripped):
        return stripped[:255]
    return None
