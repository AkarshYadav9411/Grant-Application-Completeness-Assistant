"""
Tests for Phase 3: project creation plus guideline/application uploads.
"""

from __future__ import annotations

import hashlib

import pytest
from httpx import AsyncClient


async def create_project(client: AsyncClient) -> str:
    response = await client.post(
        "/api/projects",
        json={"name": "Community Health Grant", "description": "Phase 3 upload tests"},
    )
    assert response.status_code == 201
    return response.json()["id"]


class TestProjectsApi:
    """Basic project endpoints needed for the upload workflow."""

    @pytest.mark.asyncio
    async def test_create_list_get_project(self, client: AsyncClient):
        project_id = await create_project(client)

        list_response = await client.get("/api/projects")
        assert list_response.status_code == 200
        assert any(project["id"] == project_id for project in list_response.json())

        get_response = await client.get(f"/api/projects/{project_id}")
        assert get_response.status_code == 200
        assert get_response.json()["name"] == "Community Health Grant"

    @pytest.mark.asyncio
    async def test_get_missing_project_uses_error_format(self, client: AsyncClient):
        response = await client.get("/api/projects/not-a-real-project")
        assert response.status_code == 404
        assert response.json() == {
            "error": {
                "code": "PROJECT_NOT_FOUND",
                "message": "Project not found.",
            }
        }


class TestGuidelineUploads:
    """Guideline version upload validation and duplicate detection."""

    @pytest.mark.asyncio
    async def test_upload_guideline_creates_version_one(self, client: AsyncClient):
        project_id = await create_project(client)
        content = b"Applicants must include a complete budget narrative."

        response = await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline.txt", content, "text/plain")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["document_id"]
        assert data["version"]["version_number"] == 1
        assert data["version"]["filename"] == "guideline.txt"
        assert data["version"]["file_hash"] == hashlib.sha256(content).hexdigest()
        assert data["version"]["file_size_bytes"] == len(content)
        assert data["version"]["mime_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_upload_guideline_different_hash_creates_new_version(self, client: AsyncClient):
        project_id = await create_project(client)

        first = await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline.txt", b"First guideline text", "text/plain")},
        )
        second = await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline.txt", b"Updated guideline text", "text/plain")},
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert second.json()["version"]["version_number"] == 2

        versions = await client.get(f"/api/projects/{project_id}/guidelines")
        assert versions.status_code == 200
        assert [item["version_number"] for item in versions.json()] == [1, 2]

    @pytest.mark.asyncio
    async def test_duplicate_guideline_upload_returns_409(self, client: AsyncClient):
        project_id = await create_project(client)
        content = b"Identical guideline content"

        first = await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline.md", content, "text/markdown")},
        )
        duplicate = await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("renamed.md", content, "text/markdown")},
        )

        assert first.status_code == 201
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "DUPLICATE_UPLOAD"


class TestApplicationUploads:
    """Application upload validation and version listing."""

    @pytest.mark.asyncio
    async def test_upload_application_creates_version(self, client: AsyncClient):
        project_id = await create_project(client)
        content = b"This draft application includes a project timeline."

        response = await client.post(
            f"/api/projects/{project_id}/applications",
            files={"file": ("draft.txt", content, "text/plain")},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["version"]["version_number"] == 1
        assert data["version"]["filename"] == "draft.txt"

        versions = await client.get(f"/api/projects/{project_id}/applications")
        assert versions.status_code == 200
        assert len(versions.json()) == 1

    @pytest.mark.asyncio
    async def test_same_hash_allowed_in_different_slots(self, client: AsyncClient):
        project_id = await create_project(client)
        content = b"Same bytes can exist in guideline and application slots."

        guideline = await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline.txt", content, "text/plain")},
        )
        application = await client.post(
            f"/api/projects/{project_id}/applications",
            files={"file": ("application.txt", content, "text/plain")},
        )

        assert guideline.status_code == 201
        assert application.status_code == 201


class TestUploadValidation:
    """Invalid uploads should fail with friendly standard errors."""

    @pytest.mark.asyncio
    async def test_rejects_unsupported_extension(self, client: AsyncClient):
        project_id = await create_project(client)
        response = await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("notes.exe", b"not allowed", "application/octet-stream")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    @pytest.mark.asyncio
    async def test_rejects_mime_mismatch(self, client: AsyncClient):
        project_id = await create_project(client)
        response = await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline.pdf", b"fake pdf", "text/plain")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_MIME_TYPE"

    @pytest.mark.asyncio
    async def test_rejects_empty_upload(self, client: AsyncClient):
        project_id = await create_project(client)
        response = await client.post(
            f"/api/projects/{project_id}/applications",
            files={"file": ("draft.txt", b"", "text/plain")},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "EMPTY_FILE"

    @pytest.mark.asyncio
    async def test_rejects_oversize_upload(self, client: AsyncClient):
        project_id = await create_project(client)
        content = b"x" * (1024 * 1024 + 1)
        response = await client.post(
            f"/api/projects/{project_id}/applications",
            files={"file": ("draft.txt", content, "text/plain")},
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "FILE_TOO_LARGE"

    @pytest.mark.asyncio
    async def test_rejects_upload_for_missing_project(self, client: AsyncClient):
        response = await client.post(
            "/api/projects/missing-project/guidelines",
            files={"file": ("guideline.txt", b"content", "text/plain")},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"
