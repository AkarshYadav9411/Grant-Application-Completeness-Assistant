import axios, { AxiosError } from "axios";
import type {
  Assessment,
  ClarificationQuestion,
  DocumentVersion,
  EvidenceMapping,
  EvidenceStatus,
  Project,
  Requirement,
  RequirementCategory,
  RequirementPriority,
  SupportingDocument,
  SupportingDocumentStatus
} from "../types";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "",
  headers: {
    "Content-Type": "application/json"
  }
});

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ error?: { message?: string } }>;
    return axiosError.response?.data?.error?.message ?? axiosError.message;
  }
  return error instanceof Error ? error.message : "Something went wrong.";
}

export const api = {
  async listProjects(): Promise<Project[]> {
    const { data } = await client.get<Project[]>("/api/projects");
    return data;
  },
  async createProject(payload: { name: string; description?: string }): Promise<Project> {
    const { data } = await client.post<Project>("/api/projects", payload);
    return data;
  },
  async uploadGuideline(projectId: string, file: File): Promise<void> {
    const form = new FormData();
    form.append("file", file);
    await client.post(`/api/projects/${projectId}/guidelines`, form, {
      headers: { "Content-Type": "multipart/form-data" }
    });
  },
  async uploadApplication(projectId: string, file: File): Promise<void> {
    const form = new FormData();
    form.append("file", file);
    await client.post(`/api/projects/${projectId}/applications`, form, {
      headers: { "Content-Type": "multipart/form-data" }
    });
  },
  async listGuidelineVersions(projectId: string): Promise<DocumentVersion[]> {
    const { data } = await client.get<DocumentVersion[]>(`/api/projects/${projectId}/guidelines`);
    return data;
  },
  async listApplicationVersions(projectId: string): Promise<DocumentVersion[]> {
    const { data } = await client.get<DocumentVersion[]>(`/api/projects/${projectId}/applications`);
    return data;
  },
  async extractRequirements(projectId: string): Promise<Requirement[]> {
    const { data } = await client.post<{ requirements: Requirement[] }>(
      `/api/projects/${projectId}/requirements/extract`
    );
    return data.requirements;
  },
  async listRequirements(projectId: string): Promise<Requirement[]> {
    const { data } = await client.get<Requirement[]>(`/api/projects/${projectId}/requirements`);
    return data;
  },
  async createRequirement(
    projectId: string,
    payload: {
      title: string;
      description: string;
      category: RequirementCategory;
      priority: RequirementPriority;
      source_text?: string;
    }
  ): Promise<Requirement> {
    const { data } = await client.post<Requirement>(`/api/projects/${projectId}/requirements`, payload);
    return data;
  },
  async updateRequirement(
    requirementId: string,
    payload: Partial<Pick<Requirement, "title" | "description" | "category" | "priority" | "source_text">>
  ): Promise<Requirement> {
    const { data } = await client.put<Requirement>(`/api/requirements/${requirementId}`, payload);
    return data;
  },
  async deleteRequirement(requirementId: string): Promise<void> {
    await client.delete(`/api/requirements/${requirementId}`);
  },
  async runAssessment(projectId: string): Promise<void> {
    await client.post(`/api/projects/${projectId}/assess`);
  },
  async downloadAssessmentReport(projectId: string): Promise<Blob> {
    const { data } = await client.get<Blob>(`/api/projects/${projectId}/assessment/report`, {
      responseType: "blob"
    });
    return data;
  },
  async latestAssessment(projectId: string): Promise<Assessment | null> {
    try {
      const { data } = await client.get<Assessment>(`/api/projects/${projectId}/assessment`);
      return data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  },
  async assessmentHistory(projectId: string): Promise<Assessment[]> {
    const { data } = await client.get<Assessment[]>(`/api/projects/${projectId}/assessments`);
    return data;
  },
  async listEvidence(projectId: string): Promise<EvidenceMapping[]> {
    const { data } = await client.get<EvidenceMapping[]>(`/api/projects/${projectId}/evidence`);
    return data;
  },
  async confirmEvidence(evidenceId: string): Promise<EvidenceMapping> {
    const { data } = await client.post<EvidenceMapping>(`/api/evidence/${evidenceId}/confirm`, {
      reviewer_name: "Reviewer"
    });
    return data;
  },
  async rejectEvidence(evidenceId: string): Promise<EvidenceMapping> {
    const { data } = await client.post<EvidenceMapping>(`/api/evidence/${evidenceId}/reject`, {
      reviewer_name: "Reviewer"
    });
    return data;
  },
  async editEvidence(
    evidenceId: string,
    payload: {
      reviewed_status?: EvidenceStatus;
      reviewed_evidence_text?: string;
      reviewed_explanation?: string;
      notes?: string;
    }
  ): Promise<EvidenceMapping> {
    const { data } = await client.put<EvidenceMapping>(`/api/evidence/${evidenceId}`, {
      reviewer_name: "Reviewer",
      ...payload
    });
    return data;
  },
  async listQuestions(projectId: string): Promise<ClarificationQuestion[]> {
    const { data } = await client.get<ClarificationQuestion[]>(`/api/projects/${projectId}/questions`);
    return data;
  },
  async updateQuestion(
    questionId: string,
    payload: { state?: ClarificationQuestion["state"]; answer_text?: string }
  ): Promise<ClarificationQuestion> {
    const { data } = await client.put<ClarificationQuestion>(`/api/questions/${questionId}`, payload);
    return data;
  },
  async listSupportingDocuments(projectId: string): Promise<SupportingDocument[]> {
    const { data } = await client.get<SupportingDocument[]>(`/api/projects/${projectId}/documents`);
    return data;
  },
  async createSupportingDocument(
    projectId: string,
    payload: {
      name: string;
      document_type?: string;
      status: SupportingDocumentStatus;
      related_requirement_ids: string[];
      notes?: string;
    }
  ): Promise<SupportingDocument> {
    const { data } = await client.post<SupportingDocument>(`/api/projects/${projectId}/documents`, payload);
    return data;
  },
  async updateSupportingDocument(
    projectId: string,
    documentId: string,
    payload: Partial<Pick<SupportingDocument, "name" | "document_type" | "status" | "related_requirement_ids" | "notes">>
  ): Promise<SupportingDocument> {
    const { data } = await client.put<SupportingDocument>(
      `/api/projects/${projectId}/documents/${documentId}`,
      payload
    );
    return data;
  },
  async deleteSupportingDocument(projectId: string, documentId: string): Promise<void> {
    await client.delete(`/api/projects/${projectId}/documents/${documentId}`);
  }
};
