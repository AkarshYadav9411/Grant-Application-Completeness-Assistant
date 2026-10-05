"""
Tests for Phase 8: user review, correction, confirm, and reject actions.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def create_reviewable_project(client: AsyncClient) -> tuple[str, list[dict]]:
    project = await client.post("/api/projects", json={"name": "Reviewer Workflow"})
    assert project.status_code == 201
    project_id = project.json()["id"]

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
    guideline = await client.post(
        f"/api/projects/{project_id}/guidelines",
        files={"file": ("guideline.txt", guideline_text, "text/plain")},
    )
    assert guideline.status_code == 201

    extracted = await client.post(f"/api/projects/{project_id}/requirements/extract")
    assert extracted.status_code == 200

    application_text = (
        b"Eligibility\n\n"
        b"Our organization is a registered nonprofit organization.\n\n"
        b"Budget\n\n"
        b"The total project budget is $50,000.\n\n"
        b"Outcomes\n\n"
        b"The expected outcomes are positive impact."
    )
    application = await client.post(
        f"/api/projects/{project_id}/applications",
        files={"file": ("application.txt", application_text, "text/plain")},
    )
    assert application.status_code == 201

    assessment = await client.post(f"/api/projects/{project_id}/assess")
    assert assessment.status_code == 200
    return project_id, assessment.json()["evidence"]


class TestEvidenceUserReviewApi:
    """Review actions preserve AI mapping values and expose effective values."""

    @pytest.mark.asyncio
    async def test_confirm_mapping_preserves_ai_status_as_effective_status(
        self,
        client: AsyncClient,
    ):
        _, evidence = await create_reviewable_project(client)
        supported = next(item for item in evidence if item["status"] == "SUPPORTED")

        response = await client.post(
            f"/api/evidence/{supported['id']}/confirm",
            json={"reviewer_name": "Grant Lead", "notes": "Citation checked."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUPPORTED"
        assert data["effective_status"] == "SUPPORTED"
        assert data["user_review"]["action"] == "confirmed"
        assert data["user_review"]["reviewer_name"] == "Grant Lead"
        assert data["user_review"]["notes"] == "Citation checked."

    @pytest.mark.asyncio
    async def test_reject_mapping_keeps_ai_status_but_effective_status_is_rejected(
        self,
        client: AsyncClient,
    ):
        _, evidence = await create_reviewable_project(client)
        supported = next(item for item in evidence if item["status"] == "SUPPORTED")

        response = await client.post(
            f"/api/evidence/{supported['id']}/reject",
            json={"reviewer_name": "Reviewer", "notes": "Wrong section cited."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUPPORTED"
        assert data["effective_status"] == "REJECTED"
        assert data["user_review"]["action"] == "rejected"

    @pytest.mark.asyncio
    async def test_edit_mapping_sets_effective_reviewed_values_only(
        self,
        client: AsyncClient,
    ):
        _, evidence = await create_reviewable_project(client)
        partial = next(item for item in evidence if item["status"] == "PARTIALLY_SUPPORTED")
        original_ai_evidence = partial["evidence_text"]

        response = await client.put(
            f"/api/evidence/{partial['id']}",
            json={
                "reviewed_status": "SUPPORTED",
                "reviewed_evidence_text": "Reviewer verified the detailed budget in Appendix B.",
                "reviewed_explanation": "Appendix B contains the missing line-item details.",
                "reviewer_name": "Senior Reviewer",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PARTIALLY_SUPPORTED"
        assert data["evidence_text"] == original_ai_evidence
        assert data["effective_status"] == "SUPPORTED"
        assert data["effective_evidence_text"] == "Reviewer verified the detailed budget in Appendix B."
        assert data["effective_explanation"] == "Appendix B contains the missing line-item details."
        assert data["user_review"]["action"] == "edited"
        assert data["user_review"]["reviewed_status"] == "SUPPORTED"

    @pytest.mark.asyncio
    async def test_second_review_updates_existing_review_record(
        self,
        client: AsyncClient,
    ):
        _, evidence = await create_reviewable_project(client)
        item = evidence[0]

        first = await client.post(f"/api/evidence/{item['id']}/confirm", json={})
        assert first.status_code == 200
        first_review_id = first.json()["user_review"]["id"]

        second = await client.post(
            f"/api/evidence/{item['id']}/reject",
            json={"notes": "Changed after manual review."},
        )
        assert second.status_code == 200
        data = second.json()
        assert data["user_review"]["id"] == first_review_id
        assert data["user_review"]["action"] == "rejected"
        assert data["effective_status"] == "REJECTED"

    @pytest.mark.asyncio
    async def test_reviewing_missing_mapping_does_not_require_ai_citation(
        self,
        client: AsyncClient,
    ):
        _, evidence = await create_reviewable_project(client)
        missing = next(item for item in evidence if item["status"] == "MISSING")

        response = await client.put(
            f"/api/evidence/{missing['id']}",
            json={
                "reviewed_status": "NOT_APPLICABLE",
                "reviewed_explanation": "Reviewer determined this recommendation does not apply.",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "MISSING"
        assert response.json()["effective_status"] == "NOT_APPLICABLE"

    @pytest.mark.asyncio
    async def test_review_missing_evidence_returns_404(self, client: AsyncClient):
        response = await client.post("/api/evidence/not-a-real-id/confirm", json={})

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "EVIDENCE_NOT_FOUND"
