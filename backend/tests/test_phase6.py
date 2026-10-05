"""
Tests for Phase 6: evidence mapping, citation validation, and clarification questions.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Application,
    ApplicationVersion,
    DocumentChunk,
    EvidenceMapping,
    GrantGuideline,
    GuidelineVersion,
    Project,
    Requirement,
)
from app.models.enums import EvidenceStatus, RequirementCategory, RequirementPriority
from app.services.evidence_mapping import run_evidence_mapping_for_project


async def create_project(client: AsyncClient) -> str:
    response = await client.post("/api/projects", json={"name": "Evidence Mapping"})
    assert response.status_code == 201
    return response.json()["id"]


async def upload_guideline_and_extract_requirements(client: AsyncClient, project_id: str):
    guideline_text = (
        b"Eligibility\n\n"
        b"Applicants must be registered nonprofit organizations.\n\n"
        b"Budget\n\n"
        b"The application must include a detailed project budget.\n\n"
        b"Outcomes\n\n"
        b"Applicants should consider including measurable outcomes.\n\n"
        b"Required Documents\n\n"
        b"Applicants must provide an IRS determination letter."
    )
    upload = await client.post(
        f"/api/projects/{project_id}/guidelines",
        files={"file": ("guideline.txt", guideline_text, "text/plain")},
    )
    assert upload.status_code == 201
    extract = await client.post(f"/api/projects/{project_id}/requirements/extract")
    assert extract.status_code == 200
    return extract.json()


async def upload_application(client: AsyncClient, project_id: str):
    application_text = (
        b"Eligibility\n\n"
        b"Our organization is a registered nonprofit organization.\n\n"
        b"Budget\n\n"
        b"The total project budget is $50,000.\n\n"
        b"Outcomes\n\n"
        b"The expected outcomes are positive impact."
    )
    response = await client.post(
        f"/api/projects/{project_id}/applications",
        files={"file": ("application.txt", application_text, "text/plain")},
    )
    assert response.status_code == 201


class TestEvidenceMappingApi:
    """End-to-end evidence mapping through the assessment endpoint."""

    @pytest.mark.asyncio
    async def test_run_assessment_maps_evidence_and_questions(self, client: AsyncClient):
        project_id = await create_project(client)
        await upload_guideline_and_extract_requirements(client, project_id)
        await upload_application(client, project_id)

        response = await client.post(f"/api/projects/{project_id}/assess")

        assert response.status_code == 200
        data = response.json()
        assert data["assessment_id"]
        assert data["evidence_count"] == 4
        assert data["question_count"] == 3

        statuses = {item["status"] for item in data["evidence"]}
        assert "SUPPORTED" in statuses
        assert "PARTIALLY_SUPPORTED" in statuses
        assert "AMBIGUOUS" in statuses
        assert "MISSING" in statuses

        cited = [item for item in data["evidence"] if item["status"] != "MISSING"]
        assert all(item["citation_verified"] is True for item in cited)
        assert all(item["source_chunk_id"] for item in cited)

    @pytest.mark.asyncio
    async def test_get_evidence_and_questions(self, client: AsyncClient):
        project_id = await create_project(client)
        await upload_guideline_and_extract_requirements(client, project_id)
        await upload_application(client, project_id)
        await client.post(f"/api/projects/{project_id}/assess")

        evidence = await client.get(f"/api/projects/{project_id}/evidence")
        questions = await client.get(f"/api/projects/{project_id}/questions")

        assert evidence.status_code == 200
        assert questions.status_code == 200
        assert len(evidence.json()) == 4
        assert len(questions.json()) == 3

    @pytest.mark.asyncio
    async def test_update_question_state(self, client: AsyncClient):
        project_id = await create_project(client)
        await upload_guideline_and_extract_requirements(client, project_id)
        await upload_application(client, project_id)
        assessment = await client.post(f"/api/projects/{project_id}/assess")
        question_id = assessment.json()["questions"][0]["id"]

        response = await client.put(
            f"/api/questions/{question_id}",
            json={"state": "answered", "answer_text": "Budget detail will be added in Appendix B."},
        )

        assert response.status_code == 200
        assert response.json()["state"] == "answered"
        assert "Appendix B" in response.json()["answer_text"]

    @pytest.mark.asyncio
    async def test_assess_requires_application(self, client: AsyncClient):
        project_id = await create_project(client)
        await upload_guideline_and_extract_requirements(client, project_id)

        response = await client.post(f"/api/projects/{project_id}/assess")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "APPLICATION_REQUIRED"

    @pytest.mark.asyncio
    async def test_assess_requires_requirements(self, client: AsyncClient):
        project_id = await create_project(client)
        guideline = await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline.txt", b"Applicants must be eligible.", "text/plain")},
        )
        assert guideline.status_code == 201
        await upload_application(client, project_id)

        response = await client.post(f"/api/projects/{project_id}/assess")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "REQUIREMENTS_REQUIRED"


class FabricatingEvidenceProvider:
    """Provider that returns a cited quote not present in the cited chunk."""

    def __init__(self):
        self.calls = 0

    async def map_evidence(self, *, application_version, requirements, chunks, repair_prompt=None):
        self.calls += 1
        return json.dumps(
            {
                "mappings": [
                    {
                        "requirement_id": requirements[0].requirement_id,
                        "status": "SUPPORTED",
                        "confidence": 0.9,
                        "evidence_text": "This quote does not exist in the application.",
                        "source": {
                            "chunk_id": chunks[0].id,
                            "document": application_version.filename,
                            "version": application_version.version_number,
                            "page": chunks[0].page_number,
                            "section": chunks[0].section_heading,
                        },
                        "explanation": "Fabricated evidence should be rejected.",
                        "missing_items": [],
                    }
                ]
            }
        )


async def build_unit_project(db_session: AsyncSession) -> str:
    project = Project(name="Fabricated Citation")
    db_session.add(project)
    await db_session.flush()

    guideline = GrantGuideline(project_id=project.id)
    db_session.add(guideline)
    await db_session.flush()
    guideline_version = GuidelineVersion(
        guideline_id=guideline.id,
        version_number=1,
        filename="guideline.txt",
        file_path="/tmp/guideline.txt",
        file_hash="g-hash",
        file_size_bytes=50,
        mime_type="text/plain",
        raw_text="Applicants must provide a project budget.",
        total_chunks=1,
    )
    db_session.add(guideline_version)
    await db_session.flush()
    requirement = Requirement(
        guideline_version_id=guideline_version.id,
        requirement_id="REQ-001",
        title="Project Budget",
        description="Applicants must provide a project budget.",
        category=RequirementCategory.BUDGET,
        priority=RequirementPriority.MANDATORY,
        source_text="Applicants must provide a project budget.",
    )
    db_session.add(requirement)

    application = Application(project_id=project.id)
    db_session.add(application)
    await db_session.flush()
    application_version = ApplicationVersion(
        application_id=application.id,
        version_number=1,
        filename="application.txt",
        file_path="/tmp/application.txt",
        file_hash="a-hash",
        file_size_bytes=50,
        mime_type="text/plain",
        raw_text="The project budget is $50,000.",
        total_chunks=1,
    )
    db_session.add(application_version)
    await db_session.flush()
    chunk = DocumentChunk(
        application_version_id=application_version.id,
        document_type="application",
        chunk_index=0,
        text="The project budget is $50,000.",
    )
    db_session.add(chunk)
    await db_session.flush()
    return project.id


class TestEvidenceCitationValidation:
    """Citation validation safety behavior."""

    @pytest.mark.asyncio
    async def test_unverifiable_citation_downgrades_after_retry(self, db_session: AsyncSession):
        project_id = await build_unit_project(db_session)
        provider = FabricatingEvidenceProvider()

        _, mappings, questions = await run_evidence_mapping_for_project(
            db_session,
            project_id=project_id,
            provider=provider,
        )

        assert provider.calls == 2
        assert len(mappings) == 1
        assert mappings[0].status == EvidenceStatus.MISSING
        assert mappings[0].citation_verified is False
        assert "unverifiable citation" in mappings[0].explanation
        assert len(questions) == 1

        rows = (await db_session.execute(select(EvidenceMapping))).scalars().all()
        assert len(rows) == 1
        assert rows[0].status == EvidenceStatus.MISSING
