"""
Tests for Phase 11: exportable assessment reports.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


GUIDELINE = (
    b"Eligibility\n\n"
    b"Applicants must be registered nonprofit organizations.\n\n"
    b"Budget\n\n"
    b"The application must include a detailed project budget."
)

APPLICATION = (
    b"Eligibility\n\n"
    b"Our organization is a registered nonprofit organization.\n\n"
    b"Budget\n\n"
    b"The total project budget is $50,000."
)


async def prepare_assessed_project(client: AsyncClient) -> tuple[str, dict]:
    response = await client.post("/api/projects", json={"name": "Export Report"})
    assert response.status_code == 201
    project_id = response.json()["id"]

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


class TestAssessmentReportExport:
    """Assessment reports provide a portable review artifact."""

    @pytest.mark.asyncio
    async def test_latest_assessment_report_exports_markdown(self, client: AsyncClient):
        project_id, assessment = await prepare_assessed_project(client)

        response = await client.get(f"/api/projects/{project_id}/assessment/report")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert "attachment;" in response.headers["content-disposition"]
        assert "export-report" in response.headers["content-disposition"]
        assert "# Grant Completeness Report: Export Report" in response.text
        assert f"Assessment ID: {assessment['assessment_id']}" in response.text
        assert "## Completeness" in response.text
        assert "## Requirement Results" in response.text

    @pytest.mark.asyncio
    async def test_latest_assessment_report_missing_returns_404(self, client: AsyncClient):
        project = await client.post("/api/projects", json={"name": "No Report Yet"})
        assert project.status_code == 201

        response = await client.get(f"/api/projects/{project.json()['id']}/assessment/report")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ASSESSMENT_NOT_FOUND"
