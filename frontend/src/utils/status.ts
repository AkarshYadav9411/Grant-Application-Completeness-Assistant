import type { Assessment, EvidenceMapping, EvidenceStatus, Requirement, RequirementWithEvidence } from "../types";

export const evidenceStatuses: EvidenceStatus[] = [
  "SUPPORTED",
  "PARTIALLY_SUPPORTED",
  "MISSING",
  "AMBIGUOUS",
  "CONTRADICTORY",
  "NOT_APPLICABLE",
  "REJECTED"
];

export function formatLabel(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return `${Math.round(value * 100)}%`;
}

export function statusTone(status: EvidenceStatus | string): string {
  switch (status) {
    case "SUPPORTED":
    case "READY_FOR_REVIEW":
    case "provided":
    case "confirmed":
      return "bg-emerald-50 text-emerald-800 ring-emerald-200";
    case "PARTIALLY_SUPPORTED":
    case "AMBIGUOUS":
    case "NEEDS_ATTENTION":
    case "open":
      return "bg-amber-50 text-amber-900 ring-amber-200";
    case "MISSING":
    case "CONTRADICTORY":
    case "REJECTED":
    case "NOT_READY":
    case "missing":
      return "bg-rose-50 text-rose-800 ring-rose-200";
    case "NOT_APPLICABLE":
    case "not_required":
    case "answered":
    case "dismissed":
      return "bg-slate-100 text-slate-700 ring-slate-200";
    default:
      return "bg-blue-50 text-blue-800 ring-blue-200";
  }
}

export function joinRequirementsWithEvidence(
  requirements: Requirement[],
  evidence: EvidenceMapping[]
): RequirementWithEvidence[] {
  const byRequirementId = new Map(evidence.map((item) => [item.requirement_id, item]));
  return requirements.map((requirement) => ({
    ...requirement,
    evidence: byRequirementId.get(requirement.id)
  }));
}

export function countSupported(requirements: RequirementWithEvidence[], priority: Requirement["priority"]): number {
  return requirements.filter(
    (requirement) => requirement.priority === priority && requirement.evidence?.effective_status === "SUPPORTED"
  ).length;
}

export function countByStatus(requirements: RequirementWithEvidence[], priority: Requirement["priority"]) {
  const counts: Record<EvidenceStatus, number> = {
    SUPPORTED: 0,
    PARTIALLY_SUPPORTED: 0,
    MISSING: 0,
    AMBIGUOUS: 0,
    CONTRADICTORY: 0,
    NOT_APPLICABLE: 0,
    REJECTED: 0
  };
  requirements
    .filter((requirement) => requirement.priority === priority)
    .forEach((requirement) => {
      const status = requirement.evidence?.effective_status ?? "MISSING";
      counts[status] += 1;
    });
  return counts;
}

export function criticalMissing(requirements: RequirementWithEvidence[]): RequirementWithEvidence[] {
  return requirements.filter((requirement) => {
    const status = requirement.evidence?.effective_status ?? "MISSING";
    return (
      requirement.priority === "mandatory" &&
      (status === "MISSING" || status === "CONTRADICTORY" || status === "REJECTED")
    );
  });
}

export function assessmentSummary(assessment: Assessment | null, requirements: RequirementWithEvidence[]) {
  const mandatoryTotal =
    assessment?.mandatory_total_count ?? requirements.filter((requirement) => requirement.priority === "mandatory").length;
  const recommendedTotal =
    assessment?.recommended_total_count ??
    requirements.filter((requirement) => requirement.priority === "recommended").length;
  return {
    mandatorySupported: countSupported(requirements, "mandatory"),
    mandatoryTotal,
    recommendedSupported: countSupported(requirements, "recommended"),
    recommendedTotal
  };
}
