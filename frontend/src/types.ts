export type RequirementPriority = "mandatory" | "recommended";

export type RequirementCategory =
  | "eligibility"
  | "required_information"
  | "required_documents"
  | "project_description"
  | "objectives"
  | "budget"
  | "timeline"
  | "organization_information"
  | "evaluation_criteria"
  | "submission_requirements"
  | "formatting_requirements"
  | "other";

export type EvidenceStatus =
  | "SUPPORTED"
  | "PARTIALLY_SUPPORTED"
  | "MISSING"
  | "AMBIGUOUS"
  | "CONTRADICTORY"
  | "NOT_APPLICABLE"
  | "REJECTED";

export type OverallReviewStatus = "NOT_READY" | "NEEDS_ATTENTION" | "READY_FOR_REVIEW";
export type QuestionState = "open" | "answered" | "dismissed";
export type SupportingDocumentStatus = "provided" | "missing" | "not_required";

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentVersion {
  id: string;
  version_number: number;
  filename: string;
  file_hash: string;
  file_size_bytes: number;
  mime_type: string;
  total_pages: number | null;
  total_chunks: number;
  created_at: string;
}

export interface Requirement {
  id: string;
  guideline_version_id: string;
  requirement_id: string;
  title: string;
  description: string;
  category: RequirementCategory;
  priority: RequirementPriority;
  source_document: string | null;
  source_page: number | null;
  source_section: string | null;
  source_text: string | null;
  source_chunk_id: string | null;
  is_manually_added: boolean;
  priority_flagged_for_review: boolean;
  created_at: string;
  updated_at: string;
}

export interface EvidenceMapping {
  id: string;
  project_id: string;
  assessment_id: string | null;
  requirement_id: string;
  application_version_id: string | null;
  status: EvidenceStatus;
  confidence: number;
  evidence_text: string | null;
  source_document: string | null;
  source_version: string | null;
  source_page: number | null;
  source_section: string | null;
  source_chunk_id: string | null;
  explanation: string | null;
  missing_items: string[];
  contradictory_evidence: unknown;
  source_type: "application" | "supporting_document";
  supporting_document_id: string | null;
  citation_verified: boolean;
  effective_status: EvidenceStatus;
  effective_evidence_text: string | null;
  effective_explanation: string | null;
  user_review: UserReview | null;
  created_at: string;
  updated_at: string;
}

export interface UserReview {
  id: string;
  evidence_mapping_id: string;
  action: "confirmed" | "edited" | "rejected";
  reviewed_status: EvidenceStatus | null;
  reviewed_evidence_text: string | null;
  reviewed_explanation: string | null;
  reviewer_name: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClarificationQuestion {
  id: string;
  project_id: string;
  requirement_id: string;
  evidence_mapping_id: string | null;
  question_text: string;
  state: QuestionState;
  answer_text: string | null;
  created_at: string;
  updated_at: string;
}

export interface Assessment {
  id: string;
  project_id: string;
  guideline_version_id: string | null;
  application_version_id: string | null;
  assessment_status: "in_progress" | "completed" | "failed";
  overall_status: OverallReviewStatus | null;
  mandatory_completeness: number | null;
  recommended_completeness: number | null;
  overall_completeness: number | null;
  mandatory_total_count: number;
  recommended_total_count: number;
  critical_missing_items: Array<Record<string, unknown>>;
  requirements_snapshot: Array<Record<string, unknown>>;
  is_stale: boolean;
  stale_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface SupportingDocument {
  id: string;
  project_id: string;
  name: string;
  document_type: string | null;
  status: SupportingDocumentStatus;
  related_requirement_ids: string[];
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface RequirementWithEvidence extends Requirement {
  evidence?: EvidenceMapping;
}
