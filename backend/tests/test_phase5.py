"""
Tests for Phase 5: requirement extraction provider abstraction and validation.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocumentChunk, GrantGuideline, GuidelineVersion, Requirement
from app.schemas.requirements import RequirementExtractionPayload
from app.services.requirement_extraction import extract_requirements_for_project


async def create_project(client: AsyncClient) -> str:
    response = await client.post("/api/projects", json={"name": "Requirement Extraction"})
    assert response.status_code == 201
    return response.json()["id"]


async def upload_guideline(client: AsyncClient, project_id: str, text: bytes | None = None):
    content = text or (
        b"Eligibility\n\n"
        b"Applicants must be registered nonprofit organizations.\n\n"
        b"Budget\n\n"
        b"The application must include a detailed project budget.\n\n"
        b"Outcomes\n\n"
        b"Applicants should consider including measurable outcomes.\n\n"
        b"Required Documents\n\n"
        b"Applicants must provide an IRS determination letter."
    )
    return await client.post(
        f"/api/projects/{project_id}/guidelines",
        files={"file": ("guideline.txt", content, "text/plain")},
    )


class TestRequirementExtractionApi:
    """End-to-end requirement extraction against uploaded guideline chunks."""

    @pytest.mark.asyncio
    async def test_extract_requirements_with_mock_provider(self, client: AsyncClient):
        project_id = await create_project(client)
        upload = await upload_guideline(client, project_id)
        assert upload.status_code == 201

        response = await client.post(f"/api/projects/{project_id}/requirements/extract")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 4
        assert [item["requirement_id"] for item in data["requirements"]] == [
            "REQ-001",
            "REQ-002",
            "REQ-003",
            "REQ-004",
        ]
        priorities = {item["title"]: item["priority"] for item in data["requirements"]}
        assert any(priority == "mandatory" for priority in priorities.values())
        assert any(priority == "recommended" for priority in priorities.values())
        assert all(item["source_text"] for item in data["requirements"])
        assert all(item["source_chunk_id"] for item in data["requirements"])

    @pytest.mark.asyncio
    async def test_list_requirements_returns_latest_guideline_requirements(self, client: AsyncClient):
        project_id = await create_project(client)
        await upload_guideline(client, project_id)
        await client.post(f"/api/projects/{project_id}/requirements/extract")

        response = await client.get(f"/api/projects/{project_id}/requirements")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4
        assert data[0]["requirement_id"] == "REQ-001"

    @pytest.mark.asyncio
    async def test_re_extract_replaces_same_version_requirements(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        project_id = await create_project(client)
        await upload_guideline(client, project_id)
        first = await client.post(f"/api/projects/{project_id}/requirements/extract")
        second = await client.post(f"/api/projects/{project_id}/requirements/extract")

        assert first.status_code == 200
        assert second.status_code == 200

        rows = (await db_session.execute(select(Requirement))).scalars().all()
        assert len(rows) == 4

    @pytest.mark.asyncio
    async def test_extract_without_guideline_returns_clear_error(self, client: AsyncClient):
        project_id = await create_project(client)
        response = await client.post(f"/api/projects/{project_id}/requirements/extract")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "GUIDELINE_REQUIRED"


class TestRequirementCrud:
    """Manual requirement review/edit endpoints."""

    @pytest.mark.asyncio
    async def test_manual_add_update_delete_requirement(self, client: AsyncClient):
        project_id = await create_project(client)
        await upload_guideline(client, project_id)

        create_response = await client.post(
            f"/api/projects/{project_id}/requirements",
            json={
                "title": "Manual board approval",
                "description": "Board approval must be documented.",
                "category": "required_documents",
                "priority": "mandatory",
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["requirement_id"] == "REQ-001"
        assert created["is_manually_added"] is True

        update_response = await client.put(
            f"/api/requirements/{created['id']}",
            json={"priority": "recommended", "title": "Board approval"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["priority"] == "recommended"
        assert update_response.json()["title"] == "Board approval"

        delete_response = await client.delete(f"/api/requirements/{created['id']}")
        assert delete_response.status_code == 204

        list_response = await client.get(f"/api/projects/{project_id}/requirements")
        assert list_response.status_code == 200
        assert list_response.json() == []


class BadThenGoodProvider:
    """Provider used to verify retry once on malformed JSON."""

    def __init__(self, valid_chunk: DocumentChunk, guideline_version: GuidelineVersion):
        self.calls = 0
        self.valid_chunk = valid_chunk
        self.guideline_version = guideline_version

    async def extract_requirements(self, *, guideline_version, chunks, repair_prompt=None):
        self.calls += 1
        if self.calls == 1:
            return "{not valid json"
        return json.dumps(
            {
                "requirements": [
                    {
                        "title": "Eligibility",
                        "description": "Applicants must be nonprofit organizations.",
                        "category": "eligibility",
                        "priority": "mandatory",
                        "source": {
                            "chunk_id": self.valid_chunk.id,
                            "document": self.guideline_version.filename,
                            "version": self.guideline_version.version_number,
                            "page": self.valid_chunk.page_number,
                            "section": self.valid_chunk.section_heading,
                        },
                        "source_text": "Applicants must be nonprofit organizations.",
                    }
                ]
            }
        )


class FabricatingProvider:
    """Provider that cites text not present in the chunk."""

    async def extract_requirements(self, *, guideline_version, chunks, repair_prompt=None):
        return json.dumps(
            {
                "requirements": [
                    {
                        "title": "Invented",
                        "description": "Applicants must own a spaceship.",
                        "category": "eligibility",
                        "priority": "mandatory",
                        "source": {
                            "chunk_id": chunks[0].id,
                            "document": guideline_version.filename,
                            "version": guideline_version.version_number,
                            "page": chunks[0].page_number,
                            "section": chunks[0].section_heading,
                        },
                        "source_text": "Applicants must own a spaceship.",
                    }
                ]
            }
        )


class DisagreeingPriorityProvider:
    """Provider that labels a mandatory cue as recommended."""

    async def extract_requirements(self, *, guideline_version, chunks, repair_prompt=None):
        return json.dumps(
            {
                "requirements": [
                    {
                        "title": "Budget",
                        "description": "The application must include a detailed project budget.",
                        "category": "budget",
                        "priority": "recommended",
                        "source": {
                            "chunk_id": chunks[0].id,
                            "document": guideline_version.filename,
                            "version": guideline_version.version_number,
                            "page": chunks[0].page_number,
                            "section": chunks[0].section_heading,
                        },
                        "source_text": "The application must include a detailed project budget.",
                    }
                ]
            }
        )


async def make_guideline_with_chunk(db_session: AsyncSession) -> tuple[str, GuidelineVersion, DocumentChunk]:
    from app.models import Project

    project = Project(name="Provider Unit Test")
    db_session.add(project)
    await db_session.flush()
    guideline = GrantGuideline(project_id=project.id)
    db_session.add(guideline)
    await db_session.flush()
    version = GuidelineVersion(
        guideline_id=guideline.id,
        version_number=1,
        filename="guideline.txt",
        file_path="/tmp/guideline.txt",
        file_hash="hash",
        file_size_bytes=100,
        mime_type="text/plain",
        raw_text="Applicants must be nonprofit organizations.",
        total_chunks=1,
    )
    db_session.add(version)
    await db_session.flush()
    chunk = DocumentChunk(
        guideline_version_id=version.id,
        document_type="guideline",
        chunk_index=0,
        text="Applicants must be nonprofit organizations. The application must include a detailed project budget.",
    )
    db_session.add(chunk)
    await db_session.flush()
    return project.id, version, chunk


class TestRequirementExtractionValidation:
    """Provider response validation and safety rules."""

    @pytest.mark.asyncio
    async def test_malformed_provider_response_retries_once(self, db_session: AsyncSession):
        project_id, guideline_version, chunk = await make_guideline_with_chunk(db_session)
        provider = BadThenGoodProvider(chunk, guideline_version)

        requirements = await extract_requirements_for_project(
            db_session,
            project_id=project_id,
            provider=provider,
        )

        assert provider.calls == 2
        assert len(requirements) == 1
        assert requirements[0].source_text == "Applicants must be nonprofit organizations."

    @pytest.mark.asyncio
    async def test_fabricated_source_text_is_rejected_and_nothing_stored(
        self,
        db_session: AsyncSession,
    ):
        project_id, _, _ = await make_guideline_with_chunk(db_session)

        with pytest.raises(Exception) as exc:
            await extract_requirements_for_project(
                db_session,
                project_id=project_id,
                provider=FabricatingProvider(),
            )

        assert "INVALID_REQUIREMENT_SOURCE" in str(exc.value)
        requirements = (await db_session.execute(select(Requirement))).scalars().all()
        assert requirements == []

    @pytest.mark.asyncio
    async def test_priority_cue_disagreement_is_flagged(self, db_session: AsyncSession):
        project_id, _, _ = await make_guideline_with_chunk(db_session)

        requirements = await extract_requirements_for_project(
            db_session,
            project_id=project_id,
            provider=DisagreeingPriorityProvider(),
        )

        assert len(requirements) == 1
        assert requirements[0].priority.value == "recommended"
        assert requirements[0].priority_flagged_for_review is True

    def test_payload_schema_rejects_malformed_requirement(self):
        with pytest.raises(Exception):
            RequirementExtractionPayload.model_validate({"requirements": [{"title": ""}]})
