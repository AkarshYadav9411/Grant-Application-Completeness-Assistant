"""
Markdown report generation for completed assessment runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import Assessment, AssessmentItem, Project


def render_assessment_report(project: Project, assessment: Assessment) -> str:
    """Render a concise Markdown report for a saved assessment."""
    lines = [
        f"# Grant Completeness Report: {project.name}",
        "",
        f"Generated: {_format_datetime(datetime.now(timezone.utc))} UTC",
        f"Assessment ID: {assessment.id}",
        f"Assessment date: {_format_datetime(assessment.created_at)}",
        f"Status: {_display_value(assessment.overall_status)}",
        f"Stale: {'yes' if assessment.is_stale else 'no'}",
    ]
    if assessment.stale_reason:
        lines.append(f"Stale reason: {assessment.stale_reason}")

    lines.extend(
        [
            "",
            "## Completeness",
            "",
            f"- Overall: {_format_percent(assessment.overall_completeness)}",
            f"- Mandatory: {_format_percent(assessment.mandatory_completeness)}",
            f"- Recommended: {_format_percent(assessment.recommended_completeness)}",
            f"- Mandatory requirements: {assessment.mandatory_total_count}",
            f"- Recommended requirements: {assessment.recommended_total_count}",
            "",
            "## Critical Missing Items",
            "",
        ]
    )

    if assessment.critical_missing_items:
        for item in assessment.critical_missing_items:
            lines.extend(_critical_item_lines(item))
    else:
        lines.append("No critical missing mandatory items were recorded.")

    lines.extend(["", "## Requirement Results", ""])
    for item in sorted(assessment.items, key=lambda row: row.requirement_identifier):
        lines.extend(_assessment_item_lines(item))

    lines.extend(
        [
            "",
            "---",
            "This report is evidence-based and is not an authoritative funding, legal, or eligibility decision.",
            "",
        ]
    )
    return "\n".join(lines)


def report_filename(project: Project, assessment: Assessment) -> str:
    """Build a stable, filesystem-friendly Markdown filename."""
    name = "".join(ch.lower() if ch.isalnum() else "-" for ch in project.name).strip("-")
    name = "-".join(part for part in name.split("-") if part)
    return f"{name or 'grant-review'}-{assessment.id[:8]}-report.md"


def _assessment_item_lines(item: AssessmentItem) -> list[str]:
    lines = [
        f"### {item.requirement_identifier}: {item.requirement_title}",
        "",
        f"- Priority: {_display_value(item.requirement_priority)}",
        f"- Category: {_display_value(item.requirement_category)}",
        f"- Effective status: {_display_value(item.effective_status)}",
        f"- Points: {item.points:g}",
    ]
    if item.evidence_text:
        lines.append(f"- Evidence: {item.evidence_text}")
    if item.explanation:
        lines.append(f"- Explanation: {item.explanation}")
    if item.missing_items:
        lines.append(f"- Missing items: {', '.join(item.missing_items)}")
    if item.source_citation:
        lines.append(f"- Source: {_format_source(item.source_citation)}")
    lines.append("")
    return lines


def _critical_item_lines(item: Any) -> list[str]:
    title = item.get("title", "Untitled requirement") if isinstance(item, dict) else str(item)
    identifier = item.get("requirement_id", "Requirement") if isinstance(item, dict) else "Requirement"
    status = item.get("status") if isinstance(item, dict) else None
    missing_items = item.get("missing_items", []) if isinstance(item, dict) else []

    lines = [f"- {identifier}: {title}" + (f" ({_display_value(status)})" if status else "")]
    for missing in missing_items:
        lines.append(f"  - {missing}")
    return lines


def _format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.0f}%"


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "unknown"
    return value.replace(tzinfo=None).isoformat(timespec="seconds")


def _display_value(value: Any) -> str:
    raw = getattr(value, "value", value)
    return str(raw).replace("_", " ").title()


def _format_source(source: Any) -> str:
    if not isinstance(source, dict):
        return str(source)
    parts = []
    for label, key in (
        ("document", "document"),
        ("version", "version"),
        ("page", "page"),
        ("section", "section"),
        ("chunk", "chunk_id"),
    ):
        value = source.get(key)
        if value is not None:
            parts.append(f"{label} {value}")
    return ", ".join(parts) if parts else str(source)
