import { describe, expect, it } from "vitest";
import type { EvidenceMapping, Requirement } from "../types";
import { countByStatus, criticalMissing, formatPercent, joinRequirementsWithEvidence } from "./status";

const baseRequirement: Requirement = {
  id: "req-1",
  guideline_version_id: "gv-1",
  requirement_id: "REQ-001",
  title: "Budget",
  description: "Provide a budget.",
  category: "budget",
  priority: "mandatory",
  source_document: "guideline.pdf",
  source_page: 1,
  source_section: "Budget",
  source_text: "Provide a budget.",
  source_chunk_id: "chunk-1",
  is_manually_added: false,
  priority_flagged_for_review: false,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z"
};

const baseEvidence: EvidenceMapping = {
  id: "ev-1",
  project_id: "project-1",
  assessment_id: "assessment-1",
  requirement_id: "req-1",
  application_version_id: "app-v1",
  status: "SUPPORTED",
  confidence: 0.9,
  evidence_text: "Budget is included.",
  source_document: "application.pdf",
  source_version: "1",
  source_page: 3,
  source_section: "Budget",
  source_chunk_id: "chunk-2",
  explanation: "The application includes a budget.",
  missing_items: [],
  contradictory_evidence: null,
  source_type: "application",
  supporting_document_id: null,
  citation_verified: true,
  effective_status: "SUPPORTED",
  effective_evidence_text: "Budget is included.",
  effective_explanation: "The application includes a budget.",
  user_review: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z"
};

describe("status utilities", () => {
  it("formats null percentages as N/A", () => {
    expect(formatPercent(null)).toBe("N/A");
    expect(formatPercent(0.755)).toBe("76%");
  });

  it("joins evidence by internal requirement id", () => {
    const joined = joinRequirementsWithEvidence([baseRequirement], [baseEvidence]);
    expect(joined[0].evidence?.id).toBe("ev-1");
  });

  it("counts missing requirements with no mapping", () => {
    const joined = joinRequirementsWithEvidence([baseRequirement, { ...baseRequirement, id: "req-2", requirement_id: "REQ-002" }], [baseEvidence]);
    expect(countByStatus(joined, "mandatory").SUPPORTED).toBe(1);
    expect(countByStatus(joined, "mandatory").MISSING).toBe(1);
  });

  it("finds critical mandatory blockers", () => {
    const missingRequirement = { ...baseRequirement, id: "req-2", requirement_id: "REQ-002" };
    const recommendedMissing = { ...baseRequirement, id: "req-3", requirement_id: "REQ-003", priority: "recommended" as const };
    const joined = joinRequirementsWithEvidence([baseRequirement, missingRequirement, recommendedMissing], [baseEvidence]);
    expect(criticalMissing(joined).map((requirement) => requirement.requirement_id)).toEqual(["REQ-002"]);
  });
});
