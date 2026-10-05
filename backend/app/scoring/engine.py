"""
Deterministic completeness scoring engine.

The LLM never sets completeness percentages or final review status. This module
is intentionally pure: it reads requirement priorities and effective evidence
statuses, then returns a structured score result without database writes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from app.models.enums import EvidenceStatus, OverallReviewStatus, RequirementPriority


STATUS_POINTS: dict[EvidenceStatus, float] = {
    EvidenceStatus.SUPPORTED: 1.0,
    EvidenceStatus.PARTIALLY_SUPPORTED: 0.5,
    EvidenceStatus.MISSING: 0.0,
    EvidenceStatus.AMBIGUOUS: 0.0,
    EvidenceStatus.CONTRADICTORY: 0.0,
    EvidenceStatus.REJECTED: 0.0,
}

DENOMINATOR_STATUSES = set(STATUS_POINTS)
CRITICAL_MISSING_STATUSES = {
    EvidenceStatus.MISSING,
    EvidenceStatus.CONTRADICTORY,
    EvidenceStatus.REJECTED,
}
ATTENTION_STATUSES = {
    EvidenceStatus.PARTIALLY_SUPPORTED,
    EvidenceStatus.AMBIGUOUS,
}


@dataclass(frozen=True)
class CriticalMissingItem:
    """Mandatory requirement that blocks readiness."""

    requirement_id: str
    title: str
    status: EvidenceStatus
    missing_items: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScoreBucket:
    """Score details for one priority group."""

    points: float
    denominator: int
    completeness: float | None
    counts: dict[EvidenceStatus, int]


@dataclass(frozen=True)
class ScoreResult:
    """Complete deterministic scoring result."""

    mandatory_completeness: float | None
    recommended_completeness: float | None
    overall_completeness: float | None
    overall_status: OverallReviewStatus
    critical_missing_items: list[CriticalMissingItem]
    mandatory: ScoreBucket
    recommended: ScoreBucket


@dataclass(frozen=True)
class _RequirementState:
    identifier: str
    title: str
    priority: RequirementPriority
    status: EvidenceStatus
    missing_items: list[str]


def score(
    requirements: Iterable[Any],
    effective_mappings: Iterable[Any] | Mapping[str, Any],
    *,
    mandatory_weight: float = 2.0,
    recommended_weight: float = 1.0,
) -> ScoreResult:
    """
    Calculate deterministic completeness scores.

    Effective status is taken from a mapping's reviewed status when available
    through an ``effective_status`` attribute; otherwise its raw ``status`` is
    used. Requirements without a mapping count as MISSING.
    """
    requirement_list = list(requirements)
    mappings_by_requirement = _index_mappings(effective_mappings)
    states = [
        _state_for_requirement(requirement, mappings_by_requirement)
        for requirement in requirement_list
    ]

    mandatory_states = [
        state for state in states if state.priority == RequirementPriority.MANDATORY
    ]
    recommended_states = [
        state for state in states if state.priority == RequirementPriority.RECOMMENDED
    ]

    mandatory = _score_bucket(mandatory_states)
    recommended = _score_bucket(recommended_states)

    weighted_denominator = (
        mandatory.denominator * mandatory_weight
        + recommended.denominator * recommended_weight
    )
    if weighted_denominator == 0:
        overall_completeness = None
    else:
        overall_completeness = (
            mandatory.points * mandatory_weight
            + recommended.points * recommended_weight
        ) / weighted_denominator

    critical_missing_items = [
        CriticalMissingItem(
            requirement_id=state.identifier,
            title=state.title,
            status=state.status,
            missing_items=state.missing_items,
        )
        for state in sorted(mandatory_states, key=lambda item: item.identifier)
        if state.status in CRITICAL_MISSING_STATUSES
    ]

    overall_status = _overall_status(mandatory_states)

    return ScoreResult(
        mandatory_completeness=mandatory.completeness,
        recommended_completeness=recommended.completeness,
        overall_completeness=overall_completeness,
        overall_status=overall_status,
        critical_missing_items=critical_missing_items,
        mandatory=mandatory,
        recommended=recommended,
    )


def _score_bucket(states: list[_RequirementState]) -> ScoreBucket:
    counts = {status: 0 for status in EvidenceStatus}
    points = 0.0
    denominator = 0

    for state in states:
        counts[state.status] += 1
        if state.status in DENOMINATOR_STATUSES:
            denominator += 1
            points += STATUS_POINTS[state.status]

    completeness = None if denominator == 0 else points / denominator
    return ScoreBucket(
        points=points,
        denominator=denominator,
        completeness=completeness,
        counts=counts,
    )


def _overall_status(states: list[_RequirementState]) -> OverallReviewStatus:
    mandatory_in_denominator = [
        state for state in states if state.status in DENOMINATOR_STATUSES
    ]
    if any(state.status in CRITICAL_MISSING_STATUSES for state in mandatory_in_denominator):
        return OverallReviewStatus.NOT_READY
    if any(state.status in ATTENTION_STATUSES for state in mandatory_in_denominator):
        return OverallReviewStatus.NEEDS_ATTENTION
    return OverallReviewStatus.READY_FOR_REVIEW


def _index_mappings(effective_mappings: Iterable[Any] | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(effective_mappings, Mapping):
        return dict(effective_mappings)

    indexed: dict[str, Any] = {}
    for mapping in effective_mappings:
        key = _first_present_attr(mapping, "requirement_id", "requirement_identifier")
        if key is not None:
            indexed[str(key)] = mapping
    return indexed


def _state_for_requirement(
    requirement: Any,
    mappings_by_requirement: dict[str, Any],
) -> _RequirementState:
    identifier = str(_first_present_attr(requirement, "requirement_id", "id"))
    title = str(_first_present_attr(requirement, "title") or identifier)
    priority = _coerce_priority(_first_present_attr(requirement, "priority"))

    mapping = mappings_by_requirement.get(str(_first_present_attr(requirement, "id")))
    if mapping is None:
        mapping = mappings_by_requirement.get(identifier)

    if mapping is None:
        status = EvidenceStatus.MISSING
        missing_items = [f"Provide verifiable application evidence for: {title}."]
    else:
        status = _coerce_status(
            _first_present_attr(mapping, "effective_status", "status")
        )
        missing_items = list(_first_present_attr(mapping, "missing_items") or [])

    return _RequirementState(
        identifier=identifier,
        title=title,
        priority=priority,
        status=status,
        missing_items=missing_items,
    )


def _first_present_attr(item: Any, *names: str) -> Any:
    for name in names:
        if isinstance(item, Mapping) and name in item:
            return item[name]
        if hasattr(item, name):
            return getattr(item, name)
    return None


def _coerce_status(value: Any) -> EvidenceStatus:
    if isinstance(value, EvidenceStatus):
        return value
    return EvidenceStatus(str(value))


def _coerce_priority(value: Any) -> RequirementPriority:
    if isinstance(value, RequirementPriority):
        return value
    return RequirementPriority(str(value))
