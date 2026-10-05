"""
Guideline and draft application upload/version endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import Settings, get_settings
from app.database import get_db
from app.models import Application, GrantGuideline, SupportingDocument
from app.schemas.documents import (
    DocumentUploadResponse,
    DocumentVersionRead,
    SupportingDocumentCreate,
    SupportingDocumentRead,
    SupportingDocumentUpdate,
)
from app.services.document_upload import (
    get_project_or_404,
    upload_application_version,
    upload_guideline_version,
)
from app.services.staleness import mark_project_assessments_stale
from app.utils.errors import raise_error

router = APIRouter(prefix="/api/projects/{project_id}", tags=["documents"])


@router.post("/guidelines", response_model=DocumentUploadResponse, status_code=201)
async def upload_guideline(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DocumentUploadResponse:
    """Upload a new immutable grant guideline version."""
    guideline, version = await upload_guideline_version(
        db,
        project_id=project_id,
        file=file,
        settings=settings,
    )
    return DocumentUploadResponse(
        document_id=guideline.id,
        version=DocumentVersionRead.model_validate(version),
    )


@router.get("/guidelines", response_model=list[DocumentVersionRead])
async def list_guideline_versions(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list:
    """Return all guideline versions for a project."""
    await get_project_or_404(db, project_id)
    result = await db.execute(
        select(GrantGuideline)
        .where(GrantGuideline.project_id == project_id)
        .options(selectinload(GrantGuideline.versions))
    )
    guideline = result.scalar_one_or_none()
    return [] if guideline is None else guideline.versions


@router.post("/applications", response_model=DocumentUploadResponse, status_code=201)
async def upload_application(
    project_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DocumentUploadResponse:
    """Upload a new immutable draft application version."""
    application, version = await upload_application_version(
        db,
        project_id=project_id,
        file=file,
        settings=settings,
    )
    return DocumentUploadResponse(
        document_id=application.id,
        version=DocumentVersionRead.model_validate(version),
    )


@router.get("/applications", response_model=list[DocumentVersionRead])
async def list_application_versions(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list:
    """Return all draft application versions for a project."""
    await get_project_or_404(db, project_id)
    result = await db.execute(
        select(Application)
        .where(Application.project_id == project_id)
        .options(selectinload(Application.versions))
    )
    application = result.scalar_one_or_none()
    return [] if application is None else application.versions


@router.post("/documents", response_model=SupportingDocumentRead, status_code=201)
async def create_supporting_document(
    project_id: str,
    payload: SupportingDocumentCreate,
    db: AsyncSession = Depends(get_db),
) -> SupportingDocument:
    """Create supporting-document metadata. File contents are not analyzed."""
    await get_project_or_404(db, project_id)
    document = SupportingDocument(
        project_id=project_id,
        name=payload.name.strip(),
        document_type=payload.document_type,
        status=payload.status,
        related_requirement_ids=payload.related_requirement_ids,
        notes=payload.notes,
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)
    await mark_project_assessments_stale(
        db,
        project_id,
        "A supporting document was added.",
    )
    return document


@router.get("/documents", response_model=list[SupportingDocumentRead])
async def list_supporting_documents(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[SupportingDocument]:
    """List supporting-document metadata for a project."""
    await get_project_or_404(db, project_id)
    result = await db.execute(
        select(SupportingDocument)
        .where(SupportingDocument.project_id == project_id)
        .order_by(SupportingDocument.created_at)
    )
    return list(result.scalars().all())


async def _get_supporting_document_or_404(
    db: AsyncSession,
    document_id: str,
) -> SupportingDocument:
    document = await db.get(SupportingDocument, document_id)
    if document is None:
        raise_error(404, "SUPPORTING_DOCUMENT_NOT_FOUND", "Supporting document not found.")
    return document


@router.put("/documents/{document_id}", response_model=SupportingDocumentRead)
async def update_supporting_document(
    project_id: str,
    document_id: str,
    payload: SupportingDocumentUpdate,
    db: AsyncSession = Depends(get_db),
) -> SupportingDocument:
    """Update supporting-document metadata."""
    await get_project_or_404(db, project_id)
    document = await _get_supporting_document_or_404(db, document_id)
    if document.project_id != project_id:
        raise_error(404, "SUPPORTING_DOCUMENT_NOT_FOUND", "Supporting document not found.")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        updates["name"] = updates["name"].strip()
    for field, value in updates.items():
        setattr(document, field, value)
    await db.flush()
    await db.refresh(document)
    await mark_project_assessments_stale(
        db,
        project_id,
        "A supporting document was updated.",
    )
    return document


@router.delete("/documents/{document_id}", status_code=204)
async def delete_supporting_document(
    project_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete supporting-document metadata."""
    await get_project_or_404(db, project_id)
    document = await _get_supporting_document_or_404(db, document_id)
    if document.project_id != project_id:
        raise_error(404, "SUPPORTING_DOCUMENT_NOT_FOUND", "Supporting document not found.")
    await db.delete(document)
    await db.flush()
    await mark_project_assessments_stale(
        db,
        project_id,
        "A supporting document was removed.",
    )
    return Response(status_code=204)
