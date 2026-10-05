"""
Tests for Phase 7: deterministic backend scoring engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.models.enums import EvidenceStatus, OverallReviewStatus, RequirementPriority
from app.scoring import score


@dataclass
class RequirementStub:
    id: str
    requirement_id: str
    title: str
    priority: RequirementPriority


@dataclass
class MappingStub:
    requirement_id: str
    status: EvidenceStatus
    missing_items: list[str] = field(default_factory=list)
    reviewed_status: EvidenceStatus | None = None

    @property
    def effective_status(self) -> EvidenceStatus:
        return self.reviewed_status or self.status


def req(
    number: int,
    priority: RequirementPriority = RequirementPriority.MANDATORY,
) -> RequirementStub:
    return RequirementStub(
        id=f"db-{number:03d}",
        requirement_id=f"REQ-{number:03d}",
        title=f"Requirement {number:03d}",
        priority=priority,
    )


def mapping(
    requirement: RequirementStub,
    status: EvidenceStatus,
    missing_items: list[str] | None = None,
    reviewed_status: EvidenceStatus | None = None,
) -> MappingStub:
    return MappingStub(
        requirement_id=requirement.id,
        status=status,
        missing_items=missing_items or [],
        reviewed_status=reviewed_status,
    )


def test_all_supported_is_ready_for_review():
    requirements = [req(1), req(2), req(3, RequirementPriority.RECOMMENDED)]
    mappings = [mapping(item, EvidenceStatus.SUPPORTED) for item in requirements]

    result = score(requirements, mappings)

    assert result.mandatory_completeness == 1.0
    assert result.recommended_completeness == 1.0
    assert result.overall_completeness == 1.0
    assert result.overall_status == OverallReviewStatus.READY_FOR_REVIEW
    assert result.critical_missing_items == []


def test_all_missing_is_not_ready():
    requirements = [req(1), req(2)]

    result = score(requirements, [])

    assert result.mandatory_completeness == 0.0
    assert result.overall_completeness == 0.0
    assert result.overall_status == OverallReviewStatus.NOT_READY
    assert [item.requirement_id for item in result.critical_missing_items] == [
        "REQ-001",
        "REQ-002",
    ]


def test_worked_example_ten_mandatory_is_75_percent_and_not_ready():
    requirements = [req(number) for number in range(1, 11)]
    statuses = (
        [EvidenceStatus.SUPPORTED] * 7
        + [EvidenceStatus.PARTIALLY_SUPPORTED]
        + [EvidenceStatus.MISSING] * 2
    )
    mappings = [
        mapping(requirement, status)
        for requirement, status in zip(requirements, statuses, strict=True)
    ]

    result = score(requirements, mappings)

    assert result.mandatory.points == 7.5
    assert result.mandatory.denominator == 10
    assert result.mandatory_completeness == 0.75
    assert result.overall_status == OverallReviewStatus.NOT_READY


def test_not_applicable_is_excluded_from_denominator():
    requirements = [req(1), req(2)]
    mappings = [
        mapping(requirements[0], EvidenceStatus.SUPPORTED),
        mapping(requirements[1], EvidenceStatus.NOT_APPLICABLE),
    ]

    result = score(requirements, mappings)

    assert result.mandatory.denominator == 1
    assert result.mandatory_completeness == 1.0
    assert result.mandatory.counts[EvidenceStatus.NOT_APPLICABLE] == 1
    assert result.overall_status == OverallReviewStatus.READY_FOR_REVIEW


def test_rejected_counts_as_zero_and_blocks_readiness():
    requirement = req(1)
    result = score(
        [requirement],
        [mapping(requirement, EvidenceStatus.REJECTED, ["Reviewer rejected mapping."])],
    )

    assert result.mandatory_completeness == 0.0
    assert result.overall_status == OverallReviewStatus.NOT_READY
    assert result.critical_missing_items[0].status == EvidenceStatus.REJECTED


def test_zero_denominators_return_none_not_zero_or_one():
    requirements = [req(1), req(2, RequirementPriority.RECOMMENDED)]
    mappings = [
        mapping(requirements[0], EvidenceStatus.NOT_APPLICABLE),
        mapping(requirements[1], EvidenceStatus.NOT_APPLICABLE),
    ]

    result = score(requirements, mappings)

    assert result.mandatory_completeness is None
    assert result.recommended_completeness is None
    assert result.overall_completeness is None


def test_mandatory_vs_recommended_weighting():
    mandatory = req(1, RequirementPriority.MANDATORY)
    recommended = req(2, RequirementPriority.RECOMMENDED)

    result = score(
        [mandatory, recommended],
        [
            mapping(mandatory, EvidenceStatus.SUPPORTED),
            mapping(recommended, EvidenceStatus.MISSING),
        ],
    )

    assert result.mandatory_completeness == 1.0
    assert result.recommended_completeness == 0.0
    assert result.overall_completeness == pytest.approx(2 / 3)
    assert result.overall_status == OverallReviewStatus.READY_FOR_REVIEW


def test_needs_attention_when_mandatory_partial_or_ambiguous_only():
    requirements = [req(1), req(2)]
    mappings = [
        mapping(requirements[0], EvidenceStatus.SUPPORTED),
        mapping(requirements[1], EvidenceStatus.AMBIGUOUS),
    ]

    result = score(requirements, mappings)

    assert result.overall_status == OverallReviewStatus.NEEDS_ATTENTION


def test_contradictory_mandatory_is_critical_missing():
    requirement = req(1)
    result = score(
        [requirement],
        [mapping(requirement, EvidenceStatus.CONTRADICTORY, ["Resolve conflict."])],
    )

    assert result.overall_status == OverallReviewStatus.NOT_READY
    assert result.critical_missing_items[0].requirement_id == "REQ-001"
    assert result.critical_missing_items[0].missing_items == ["Resolve conflict."]


def test_recommended_missing_never_changes_ready_status():
    mandatory = req(1, RequirementPriority.MANDATORY)
    recommended = req(2, RequirementPriority.RECOMMENDED)

    result = score(
        [mandatory, recommended],
        [
            mapping(mandatory, EvidenceStatus.SUPPORTED),
            mapping(recommended, EvidenceStatus.MISSING),
        ],
    )

    assert result.overall_status == OverallReviewStatus.READY_FOR_REVIEW
    assert result.critical_missing_items == []


def test_reviewed_status_is_effective_status():
    requirement = req(1)
    result = score(
        [requirement],
        [
            mapping(
                requirement,
                EvidenceStatus.SUPPORTED,
                reviewed_status=EvidenceStatus.REJECTED,
            )
        ],
    )

    assert result.mandatory.counts[EvidenceStatus.REJECTED] == 1
    assert result.mandatory.counts[EvidenceStatus.SUPPORTED] == 0
    assert result.overall_status == OverallReviewStatus.NOT_READY


def test_mapping_dictionary_can_use_public_requirement_identifier():
    requirement = req(1)

    result = score(
        [requirement],
        {
            "REQ-001": {
                "status": EvidenceStatus.PARTIALLY_SUPPORTED,
                "missing_items": ["Add measurable outcomes."],
            }
        },
    )

    assert result.mandatory_completeness == 0.5
    assert result.overall_status == OverallReviewStatus.NEEDS_ATTENTION
