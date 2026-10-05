import { ClipboardList, Download, FileCheck2, FileClock, FileText, LayoutDashboard, Loader2, PlayCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Dashboard } from "./components/Dashboard";
import { EvidenceReview } from "./components/EvidenceReview";
import { FileUploadPanel } from "./components/FileUploadPanel";
import { ProjectSidebar } from "./components/ProjectSidebar";
import { QuestionsPanel } from "./components/QuestionsPanel";
import { RequirementsTable } from "./components/RequirementsTable";
import { SupportingDocuments } from "./components/SupportingDocuments";
import { VersionsPanel } from "./components/VersionsPanel";
import { api, getApiErrorMessage } from "./services/api";
import type {
  Assessment,
  ClarificationQuestion,
  DocumentVersion,
  EvidenceMapping,
  Project,
  Requirement,
  SupportingDocument
} from "./types";
import { joinRequirementsWithEvidence } from "./utils/status";

type Tab = "dashboard" | "requirements" | "evidence" | "documents" | "versions" | "questions";

const tabs: Array<{ id: Tab; label: string; icon: typeof LayoutDashboard }> = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "requirements", label: "Requirements", icon: ClipboardList },
  { id: "evidence", label: "Review Evidence", icon: FileCheck2 },
  { id: "documents", label: "Supporting Docs", icon: FileText },
  { id: "versions", label: "Versions", icon: FileClock },
  { id: "questions", label: "Questions", icon: ClipboardList }
];

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [evidence, setEvidence] = useState<EvidenceMapping[]>([]);
  const [questions, setQuestions] = useState<ClarificationQuestion[]>([]);
  const [supportingDocuments, setSupportingDocuments] = useState<SupportingDocument[]>([]);
  const [guidelineVersions, setGuidelineVersions] = useState<DocumentVersion[]>([]);
  const [applicationVersions, setApplicationVersions] = useState<DocumentVersion[]>([]);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [assessmentHistory, setAssessmentHistory] = useState<Assessment[]>([]);
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingProjectData, setLoadingProjectData] = useState(false);
  const [working, setWorking] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const requirementsWithEvidence = useMemo(
    () => joinRequirementsWithEvidence(requirements, evidence),
    [evidence, requirements]
  );

  const loadProjects = useCallback(async () => {
    setLoadingProjects(true);
    setError(null);
    try {
      const data = await api.listProjects();
      setProjects(data);
      setSelectedProjectId((current) => current ?? data[0]?.id ?? null);
    } catch (caught) {
      setError(getApiErrorMessage(caught));
    } finally {
      setLoadingProjects(false);
    }
  }, []);

  const loadProjectData = useCallback(async (projectId: string) => {
    setLoadingProjectData(true);
    setError(null);
    try {
      const [
        loadedRequirements,
        loadedEvidence,
        loadedQuestions,
        loadedDocuments,
        guidelines,
        applications,
        latest,
        history
      ] = await Promise.all([
        api.listRequirements(projectId),
        api.listEvidence(projectId),
        api.listQuestions(projectId),
        api.listSupportingDocuments(projectId),
        api.listGuidelineVersions(projectId),
        api.listApplicationVersions(projectId),
        api.latestAssessment(projectId),
        api.assessmentHistory(projectId)
      ]);
      setRequirements(loadedRequirements);
      setEvidence(loadedEvidence);
      setQuestions(loadedQuestions);
      setSupportingDocuments(loadedDocuments);
      setGuidelineVersions(guidelines);
      setApplicationVersions(applications);
      setAssessment(latest);
      setAssessmentHistory(history);
    } catch (caught) {
      setError(getApiErrorMessage(caught));
    } finally {
      setLoadingProjectData(false);
    }
  }, []);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  useEffect(() => {
    if (selectedProjectId) {
      void loadProjectData(selectedProjectId);
    }
  }, [loadProjectData, selectedProjectId]);

  async function refreshCurrent(message?: string) {
    if (!selectedProjectId) return;
    await loadProjectData(selectedProjectId);
    if (message) setNotice(message);
  }

  async function runWorkflowAction(action: () => Promise<unknown>, successMessage: string) {
    setWorking(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      await refreshCurrent(successMessage);
    } catch (caught) {
      setError(getApiErrorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  async function createProject(payload: { name: string; description?: string }) {
    setError(null);
    try {
      const project = await api.createProject(payload);
      await loadProjects();
      setSelectedProjectId(project.id);
      setNotice("Review created.");
    } catch (caught) {
      setError(getApiErrorMessage(caught));
    }
  }

  async function downloadReport() {
    if (!selectedProjectId || !selectedProject) return;
    setWorking(true);
    setError(null);
    setNotice(null);
    try {
      const blob = await api.downloadAssessmentReport(selectedProjectId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${selectedProject.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "grant-review"}-report.md`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setNotice("Assessment report downloaded.");
    } catch (caught) {
      setError(getApiErrorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  const selectedReady = Boolean(selectedProjectId);

  return (
    <div className="min-h-screen bg-[#eef3f8] text-ink">
      <div className="grid min-h-screen lg:grid-cols-[320px_1fr]">
        <ProjectSidebar
          projects={projects}
          selectedProjectId={selectedProjectId}
          loading={loadingProjects}
          onSelect={setSelectedProjectId}
          onRefresh={loadProjects}
          onCreate={createProject}
        />

        <main className="min-w-0">
          <header className="border-b border-line bg-white px-4 py-4 sm:px-6">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="text-sm font-semibold uppercase text-brand">Grant review workspace</p>
                <h2 className="mt-1 text-2xl font-bold text-ink">{selectedProject?.name ?? "Select or create a review"}</h2>
                <p className="mt-1 max-w-3xl text-sm text-slate-600">
                  {selectedProject?.description ??
                    "Upload a guideline and draft application, extract requirements, run evidence mapping, and review completeness."}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  className="btn-secondary"
                  type="button"
                  disabled={!selectedReady || working}
                  onClick={() =>
                    selectedProjectId &&
                    runWorkflowAction(() => api.extractRequirements(selectedProjectId), "Requirements extracted.")
                  }
                >
                  {working ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <ClipboardList aria-hidden="true" className="h-4 w-4" />}
                  Extract Requirements
                </button>
                <button
                  className="btn-primary"
                  type="button"
                  disabled={!selectedReady || working}
                  onClick={() =>
                    selectedProjectId && runWorkflowAction(() => api.runAssessment(selectedProjectId), "Assessment completed.")
                  }
                >
                  <PlayCircle aria-hidden="true" className="h-4 w-4" />
                  Run Assessment
                </button>
                <button
                  className="btn-secondary"
                  type="button"
                  disabled={!selectedReady || !assessment || working}
                  onClick={downloadReport}
                >
                  <Download aria-hidden="true" className="h-4 w-4" />
                  Export Report
                </button>
              </div>
            </div>
          </header>

          <div className="px-4 py-5 sm:px-6">
            {notice ? (
              <div className="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                {notice}
              </div>
            ) : null}
            {error ? (
              <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
                {error}
              </div>
            ) : null}

            {selectedProjectId ? (
              <>
                <section className="mb-5 grid gap-4 xl:grid-cols-2">
                  <FileUploadPanel
                    label="Upload Guideline"
                    help="PDF, DOCX, TXT, or Markdown. Duplicate versions are rejected by hash."
                    onUpload={(file) =>
                      runWorkflowAction(() => api.uploadGuideline(selectedProjectId, file), "Guideline version uploaded.")
                    }
                  />
                  <FileUploadPanel
                    label="Upload Draft Application"
                    help="Text is extracted without OCR and stored as versioned chunks."
                    onUpload={(file) =>
                      runWorkflowAction(() => api.uploadApplication(selectedProjectId, file), "Application version uploaded.")
                    }
                  />
                </section>

                <nav className="mb-5 flex gap-2 overflow-x-auto border-b border-line pb-2" aria-label="Workspace sections">
                  {tabs.map((tab) => {
                    const Icon = tab.icon;
                    return (
                      <button
                        className={`inline-flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm font-semibold ${
                          activeTab === tab.id ? "bg-ink text-white" : "bg-white text-slate-700 hover:bg-slate-100"
                        }`}
                        key={tab.id}
                        type="button"
                        onClick={() => setActiveTab(tab.id)}
                      >
                        <Icon aria-hidden="true" className="h-4 w-4" />
                        {tab.label}
                      </button>
                    );
                  })}
                </nav>

                {loadingProjectData ? (
                  <div className="panel flex items-center gap-3 p-6 text-sm text-slate-600">
                    <Loader2 aria-hidden="true" className="h-5 w-5 animate-spin" />
                    Loading review data...
                  </div>
                ) : null}

                {!loadingProjectData && activeTab === "dashboard" ? (
                  <Dashboard
                    assessment={assessment}
                    requirements={requirementsWithEvidence}
                    questions={questions}
                    running={working}
                    onRunAssessment={() =>
                      selectedProjectId
                        ? runWorkflowAction(() => api.runAssessment(selectedProjectId), "Assessment completed.")
                        : Promise.resolve()
                    }
                    onSelectTab={(tab) => setActiveTab(tab as Tab)}
                  />
                ) : null}

                {!loadingProjectData && activeTab === "requirements" ? (
                  <RequirementsTable
                    requirements={requirementsWithEvidence}
                    onCreate={(payload) =>
                      runWorkflowAction(() => api.createRequirement(selectedProjectId, payload), "Requirement added.")
                    }
                    onUpdate={(id, payload) =>
                      runWorkflowAction(() => api.updateRequirement(id, payload), "Requirement updated.")
                    }
                    onDelete={(id) => runWorkflowAction(() => api.deleteRequirement(id), "Requirement deleted.")}
                  />
                ) : null}

                {!loadingProjectData && activeTab === "evidence" ? (
                  <EvidenceReview
                    evidence={evidence}
                    requirements={requirements}
                    onConfirm={(id) => runWorkflowAction(() => api.confirmEvidence(id), "Evidence confirmed.")}
                    onReject={(id) => runWorkflowAction(() => api.rejectEvidence(id), "Evidence rejected.")}
                    onEdit={(id, payload) => runWorkflowAction(() => api.editEvidence(id, payload), "Evidence review saved.")}
                  />
                ) : null}

                {!loadingProjectData && activeTab === "documents" ? (
                  <SupportingDocuments
                    documents={supportingDocuments}
                    requirements={requirements}
                    onCreate={(payload) =>
                      runWorkflowAction(() => api.createSupportingDocument(selectedProjectId, payload), "Supporting document added.")
                    }
                    onUpdate={(id, payload) =>
                      runWorkflowAction(
                        () => api.updateSupportingDocument(selectedProjectId, id, payload),
                        "Supporting document updated."
                      )
                    }
                    onDelete={(id) =>
                      runWorkflowAction(() => api.deleteSupportingDocument(selectedProjectId, id), "Supporting document deleted.")
                    }
                  />
                ) : null}

                {!loadingProjectData && activeTab === "versions" ? (
                  <VersionsPanel
                    guidelines={guidelineVersions}
                    applications={applicationVersions}
                    assessments={assessmentHistory}
                  />
                ) : null}

                {!loadingProjectData && activeTab === "questions" ? (
                  <QuestionsPanel
                    questions={questions}
                    requirements={requirements}
                    onUpdate={(id, payload) => runWorkflowAction(() => api.updateQuestion(id, payload), "Question updated.")}
                  />
                ) : null}
              </>
            ) : (
              <div className="panel p-8 text-center">
                <h2 className="text-xl font-bold text-ink">Create a review to begin</h2>
                <p className="mx-auto mt-2 max-w-xl text-sm text-slate-600">
                  The workspace will guide you through uploading source documents, extracting requirements, mapping evidence,
                  reviewing AI suggestions, and tracking stale assessments.
                </p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
