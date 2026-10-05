"""
Tests for Phase 9: stale assessments, version history, and supporting documents.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


GUIDELINE = (
    b"Eligibility\n\n"
    b"Applicants must be registered nonprofit organizations.\n\n"
    b"Budget\n\n"
    b"The application must include a detailed project budget.\n\n"
    b"Outcomes\n\n"
    b"Applicants should consider including measurable outcomes.\n\n"
    b"Required Documents\n\n"
    b"Applicants must provide an IRS determination letter."
)

APPLICATION = (
    b"Eligibility\n\n"
    b"Our organization is a registered nonprofit organization.\n\n"
    b"Budget\n\n"
    b"The total project budget is $50,000.\n\n"
    b"Outcomes\n\n"
    b"The expected outcomes are positive impact."
)


async def create_project(client: AsyncClient) -> str:
    response = await client.post("/api/projects", json={"name": "Stale Assessment"})
    assert response.status_code == 201
    return response.json()["id"]


async def prepare_assessed_project(client: AsyncClient) -> tuple[str, dict]:
    project_id = await create_project(client)
    guideline = await client.post(
        f"/api/projects/{project_id}/guidelines",
        files={"file": ("guideline.txt", GUIDELINE, "text/plain")},
    )
    assert guideline.status_code == 201
    extract = await client.post(f"/api/projects/{project_id}/requirements/extract")
    assert extract.status_code == 200
    application = await client.post(
        f"/api/projects/{project_id}/applications",
        files={"file": ("application.txt", APPLICATION, "text/plain")},
    )
    assert application.status_code == 201
    assessment = await client.post(f"/api/projects/{project_id}/assess")
    assert assessment.status_code == 200
    return project_id, assessment.json()


async def latest_assessment(client: AsyncClient, project_id: str) -> dict:
    response = await client.get(f"/api/projects/{project_id}/assessment")
    assert response.status_code == 200
    return response.json()


class TestAssessmentHistoryAndStaleness:
    """Source changes mark assessments stale; review-only changes do not."""

    @pytest.mark.asyncio
    async def test_latest_assessment_starts_not_stale(self, client: AsyncClient):
        project_id, assessment = await prepare_assessed_project(client)

        latest = await latest_assessment(client, project_id)

        assert latest["id"] == assessment["assessment_id"]
        assert latest["is_stale"] is False
        assert latest["stale_reason"] is None
        assert latest["guideline_version_id"] == assessment["guideline_version_id"]
        assert latest["application_version_id"] == assessment["application_version_id"]

    @pytest.mark.asyncio
    async def test_new_guideline_version_marks_existing_assessment_stale(
        self,
        client: AsyncClient,
    ):
        project_id, _ = await prepare_assessed_project(client)

        upload = await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline-v2.txt", GUIDELINE + b"\nNew rule.", "text/plain")},
        )

        assert upload.status_code == 201
        latest = await latest_assessment(client, project_id)
        assert latest["is_stale"] is True
        assert latest["stale_reason"] == "New guideline version uploaded (v2)"

    @pytest.mark.asyncio
    async def test_new_application_version_marks_existing_assessment_stale(
        self,
        client: AsyncClient,
    ):
        project_id, _ = await prepare_assessed_project(client)

        upload = await client.post(
            f"/api/projects/{project_id}/applications",
            files={"file": ("application-v2.txt", APPLICATION + b"\nAppendix added.", "text/plain")},
        )

        assert upload.status_code == 201
        latest = await latest_assessment(client, project_id)
        assert latest["is_stale"] is True
        assert latest["stale_reason"] == "New application version uploaded (v2)"

    @pytest.mark.asyncio
    async def test_requirement_edit_marks_assessment_stale(self, client: AsyncClient):
        project_id, _ = await prepare_assessed_project(client)
        requirements = await client.get(f"/api/projects/{project_id}/requirements")
        requirement_id = requirements.json()[0]["id"]

        update = await client.put(
            f"/api/requirements/{requirement_id}",
            json={"title": "Updated eligibility"},
        )

        assert update.status_code == 200
        latest = await latest_assessment(client, project_id)
        assert latest["is_stale"] is True
        assert latest["stale_reason"] == "A requirement was edited."

    @pytest.mark.asyncio
    async def test_supporting_document_add_marks_assessment_stale(self, client: AsyncClient):
        project_id, _ = await prepare_assessed_project(client)

        response = await client.post(
            f"/api/projects/{project_id}/documents",
            json={
                "name": "IRS determination letter",
                "document_type": "tax",
                "status": "provided",
                "related_requirement_ids": ["REQ-004"],
            },
        )

        assert response.status_code == 201
        latest = await latest_assessment(client, project_id)
        assert latest["is_stale"] is True
        assert latest["stale_reason"] == "A supporting document was added."

    @pytest.mark.asyncio
    async def test_supporting_document_status_change_marks_assessment_stale(
        self,
        client: AsyncClient,
    ):
        project_id = await create_project(client)
        await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline.txt", GUIDELINE, "text/plain")},
        )
        await client.post(f"/api/projects/{project_id}/requirements/extract")
        await client.post(
            f"/api/projects/{project_id}/applications",
            files={"file": ("application.txt", APPLICATION, "text/plain")},
        )
        document = await client.post(
            f"/api/projects/{project_id}/documents",
            json={"name": "IRS letter", "status": "missing"},
        )
        assert document.status_code == 201
        assessment = await client.post(f"/api/projects/{project_id}/assess")
        assert assessment.status_code == 200

        update = await client.put(
            f"/api/projects/{project_id}/documents/{document.json()['id']}",
            json={"status": "provided"},
        )

        assert update.status_code == 200
        latest = await latest_assessment(client, project_id)
        assert latest["is_stale"] is True
        assert latest["stale_reason"] == "A supporting document was updated."

    @pytest.mark.asyncio
    async def test_supporting_document_delete_marks_assessment_stale(
        self,
        client: AsyncClient,
    ):
        project_id = await create_project(client)
        await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline.txt", GUIDELINE, "text/plain")},
        )
        await client.post(f"/api/projects/{project_id}/requirements/extract")
        await client.post(
            f"/api/projects/{project_id}/applications",
            files={"file": ("application.txt", APPLICATION, "text/plain")},
        )
        document = await client.post(
            f"/api/projects/{project_id}/documents",
            json={"name": "IRS letter", "status": "provided"},
        )
        await client.post(f"/api/projects/{project_id}/assess")

        delete = await client.delete(
            f"/api/projects/{project_id}/documents/{document.json()['id']}"
        )

        assert delete.status_code == 204
        latest = await latest_assessment(client, project_id)
        assert latest["is_stale"] is True
        assert latest["stale_reason"] == "A supporting document was removed."

    @pytest.mark.asyncio
    async def test_user_review_does_not_mark_assessment_stale(self, client: AsyncClient):
        project_id, assessment = await prepare_assessed_project(client)
        evidence_id = assessment["evidence"][0]["id"]

        response = await client.post(
            f"/api/evidence/{evidence_id}/confirm",
            json={"notes": "Reviewed."},
        )

        assert response.status_code == 200
        latest = await latest_assessment(client, project_id)
        assert latest["is_stale"] is False

    @pytest.mark.asyncio
    async def test_answering_question_does_not_mark_assessment_stale(self, client: AsyncClient):
        project_id, assessment = await prepare_assessed_project(client)
        question_id = assessment["questions"][0]["id"]

        response = await client.put(
            f"/api/questions/{question_id}",
            json={"state": "answered", "answer_text": "Will provide this appendix."},
        )

        assert response.status_code == 200
        latest = await latest_assessment(client, project_id)
        assert latest["is_stale"] is False

    @pytest.mark.asyncio
    async def test_new_assessment_after_source_change_keeps_history(
        self,
        client: AsyncClient,
    ):
        project_id, first = await prepare_assessed_project(client)
        await client.post(
            f"/api/projects/{project_id}/applications",
            files={"file": ("application-v2.txt", APPLICATION + b"\nAppendix added.", "text/plain")},
        )

        second = await client.post(f"/api/projects/{project_id}/assess")
        history = await client.get(f"/api/projects/{project_id}/assessments")

        assert second.status_code == 200
        assert history.status_code == 200
        rows = history.json()
        assert len(rows) == 2
        assert {row["id"] for row in rows} == {first["assessment_id"], second.json()["assessment_id"]}
        by_id = {row["id"]: row for row in rows}
        assert by_id[first["assessment_id"]]["is_stale"] is True
        assert by_id[second.json()["assessment_id"]]["is_stale"] is False

    @pytest.mark.asyncio
    async def test_document_version_history_is_viewable(self, client: AsyncClient):
        project_id = await create_project(client)
        await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline.txt", GUIDELINE, "text/plain")},
        )
        await client.post(
            f"/api/projects/{project_id}/guidelines",
            files={"file": ("guideline-v2.txt", GUIDELINE + b"\nMore text.", "text/plain")},
        )
        await client.post(
            f"/api/projects/{project_id}/applications",
            files={"file": ("application.txt", APPLICATION, "text/plain")},
        )

        guidelines = await client.get(f"/api/projects/{project_id}/guidelines")
        applications = await client.get(f"/api/projects/{project_id}/applications")

        assert [item["version_number"] for item in guidelines.json()] == [1, 2]
        assert [item["version_number"] for item in applications.json()] == [1]

    @pytest.mark.asyncio
    async def test_latest_assessment_missing_returns_404(self, client: AsyncClient):
        project_id = await create_project(client)

        response = await client.get(f"/api/projects/{project_id}/assessment")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ASSESSMENT_NOT_FOUND"
