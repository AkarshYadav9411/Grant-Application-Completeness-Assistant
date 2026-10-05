"""
Document upload validation, hashing, storage, and version creation.

This stores immutable file versions, extracts text, and creates structured chunks
that later AI/citation workflows can reference.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Literal

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.models import (
    Application,
    ApplicationVersion,
    DocumentChunk,
    DocumentType,
    GrantGuideline,
    GuidelineVersion,
    Project,
)
from app.services.document_extraction import ExtractionResult, extract_text_from_bytes
from app.services.staleness import mark_project_assessments_stale
from app.utils.errors import raise_error

DocumentSlot = Literal["guideline", "application"]

ALLOWED_MIME_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
    ".markdown": {"text/markdown", "text/plain"},
}


def sanitize_filename(filename: str) -> str:
    """Return a safe display/storage filename while preserving the extension."""
    raw_name = Path(filename or "uploaded-document").name.strip()
    if not raw_name:
        raw_name = "uploaded-document"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_name).strip("._")
    return safe_name or "uploaded-document"


def validate_upload_metadata(file: UploadFile, content: bytes, settings: Settings) -> str:
    """Validate extension, MIME type, size, and emptiness; return normalized extension."""
    safe_name = sanitize_filename(file.filename or "")
    extension = Path(safe_name).suffix.lower()
    if extension not in ALLOWED_MIME_TYPES:
        allowed = ", ".join(sorted(ALLOWED_MIME_TYPES))
        raise_error(
            400,
            "UNSUPPORTED_FILE_TYPE",
            f"Unsupported file type. Please upload one of: {allowed}.",
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_MIME_TYPES[extension]:
        raise_error(
            400,
            "INVALID_MIME_TYPE",
            f"The uploaded file extension does not match its MIME type ({content_type or 'unknown'}).",
        )

    if not content:
        raise_error(400, "EMPTY_FILE", "The uploaded file is empty.")

    if len(content) > settings.max_upload_bytes:
        raise_error(
            413,
            "FILE_TOO_LARGE",
            f"The uploaded file exceeds the {settings.max_upload_mb} MB limit.",
        )

    return extension


def sha256_hex(content: bytes) -> str:
    """Calculate a SHA-256 digest for duplicate upload detection."""
    return hashlib.sha256(content).hexdigest()


async def get_project_or_404(db: AsyncSession, project_id: str) -> Project:
    """Fetch a project by ID or raise a consistent 404 error."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise_error(404, "PROJECT_NOT_FOUND", "Project not found.")
    return project


async def _get_or_create_guideline(db: AsyncSession, project_id: str) -> GrantGuideline:
    result = await db.execute(
        select(GrantGuideline)
        .where(GrantGuideline.project_id == project_id)
        .options(selectinload(GrantGuideline.versions))
    )
    guideline = result.scalar_one_or_none()
    if guideline is None:
        guideline = GrantGuideline(project_id=project_id)
        db.add(guideline)
        await db.flush()
        await db.refresh(guideline, attribute_names=["versions"])
    return guideline


async def _get_or_create_application(db: AsyncSession, project_id: str) -> Application:
    result = await db.execute(
        select(Application)
        .where(Application.project_id == project_id)
        .options(selectinload(Application.versions))
    )
    application = result.scalar_one_or_none()
    if application is None:
        application = Application(project_id=project_id)
        db.add(application)
        await db.flush()
        await db.refresh(application, attribute_names=["versions"])
    return application


def _write_upload_file(
    *,
    settings: Settings,
    project_id: str,
    slot: DocumentSlot,
    version_number: int,
    filename: str,
    content: bytes,
    digest: str,
) -> Path:
    """Persist uploaded bytes under the backend upload directory."""
    slot_dir = settings.upload_dir / project_id / slot
    slot_dir.mkdir(parents=True, exist_ok=True)
    extension = Path(filename).suffix.lower()
    destination = slot_dir / f"v{version_number}_{digest[:12]}{extension}"
    destination.write_bytes(content)
    return destination


def _build_guideline_chunks(
    version_id: str,
    extraction: ExtractionResult,
) -> list[DocumentChunk]:
    """Convert extracted chunks to guideline DocumentChunk rows."""
    return [
        DocumentChunk(
            guideline_version_id=version_id,
            document_type=DocumentType.GUIDELINE,
            chunk_index=index,
            text=chunk.text,
            page_number=chunk.page_number,
            section_heading=chunk.section_heading,
            paragraph_index=chunk.paragraph_index,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            token_count=chunk.token_count,
        )
        for index, chunk in enumerate(extraction.chunks)
    ]


def _build_application_chunks(
    version_id: str,
    extraction: ExtractionResult,
) -> list[DocumentChunk]:
    """Convert extracted chunks to application DocumentChunk rows."""
    return [
        DocumentChunk(
            application_version_id=version_id,
            document_type=DocumentType.APPLICATION,
            chunk_index=index,
            text=chunk.text,
            page_number=chunk.page_number,
            section_heading=chunk.section_heading,
            paragraph_index=chunk.paragraph_index,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            token_count=chunk.token_count,
        )
        for index, chunk in enumerate(extraction.chunks)
    ]


async def upload_guideline_version(
    db: AsyncSession,
    *,
    project_id: str,
    file: UploadFile,
    settings: Settings,
) -> tuple[GrantGuideline, GuidelineVersion]:
    """Create a new immutable guideline version for a project."""
    await get_project_or_404(db, project_id)
    content = await file.read()
    validate_upload_metadata(file, content, settings)
    filename = sanitize_filename(file.filename or "guideline")
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    digest = sha256_hex(content)
    extraction = extract_text_from_bytes(filename, content)

    guideline = await _get_or_create_guideline(db, project_id)
    if any(version.file_hash == digest for version in guideline.versions):
        raise_error(
            409,
            "DUPLICATE_UPLOAD",
            "This guideline file has already been uploaded for this project.",
        )

    version_number = len(guideline.versions) + 1
    path = _write_upload_file(
        settings=settings,
        project_id=project_id,
        slot="guideline",
        version_number=version_number,
        filename=filename,
        content=content,
        digest=digest,
    )

    version = GuidelineVersion(
        guideline_id=guideline.id,
        version_number=version_number,
        filename=filename,
        file_path=str(path),
        file_hash=digest,
        file_size_bytes=len(content),
        mime_type=content_type,
        raw_text=extraction.raw_text,
        total_pages=extraction.total_pages,
        total_chunks=len(extraction.chunks),
    )
    db.add(version)
    await db.flush()
    db.add_all(_build_guideline_chunks(version.id, extraction))
    await db.flush()
    await db.refresh(version)
    await mark_project_assessments_stale(
        db,
        project_id,
        f"New guideline version uploaded (v{version.version_number})",
    )
    return guideline, version


async def upload_application_version(
    db: AsyncSession,
    *,
    project_id: str,
    file: UploadFile,
    settings: Settings,
) -> tuple[Application, ApplicationVersion]:
    """Create a new immutable draft application version for a project."""
    await get_project_or_404(db, project_id)
    content = await file.read()
    validate_upload_metadata(file, content, settings)
    filename = sanitize_filename(file.filename or "application")
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    digest = sha256_hex(content)
    extraction = extract_text_from_bytes(filename, content)

    application = await _get_or_create_application(db, project_id)
    if any(version.file_hash == digest for version in application.versions):
        raise_error(
            409,
            "DUPLICATE_UPLOAD",
            "This application file has already been uploaded for this project.",
        )

    version_number = len(application.versions) + 1
    path = _write_upload_file(
        settings=settings,
        project_id=project_id,
        slot="application",
        version_number=version_number,
        filename=filename,
        content=content,
        digest=digest,
    )

    version = ApplicationVersion(
        application_id=application.id,
        version_number=version_number,
        filename=filename,
        file_path=str(path),
        file_hash=digest,
        file_size_bytes=len(content),
        mime_type=content_type,
        raw_text=extraction.raw_text,
        total_pages=extraction.total_pages,
        total_chunks=len(extraction.chunks),
    )
    db.add(version)
    await db.flush()
    db.add_all(_build_application_chunks(version.id, extraction))
    await db.flush()
    await db.refresh(version)
    await mark_project_assessments_stale(
        db,
        project_id,
        f"New application version uploaded (v{version.version_number})",
    )
    return application, version
