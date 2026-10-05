import { AlertTriangle, ClipboardCheck, FileQuestion, FileText, FolderOpen, PlayCircle, ScrollText } from "lucide-react";
import type { Assessment, ClarificationQuestion, RequirementWithEvidence } from "../types";
import { assessmentSummary, countByStatus, criticalMissing, evidenceStatuses, formatPercent } from "../utils/status";
import { MetricCard } from "./MetricCard";
import { StatusBadge } from "./StatusBadge";

interface DashboardProps {
  assessment: Assessment | null;
  requirements: RequirementWithEvidence[];
  questions: ClarificationQuestion[];
  running: boolean;
  onRunAssessment: () => Promise<void>;
  onSelectTab: (tab: string) => void;
}

export function Dashboard({ assessment, requirements, questions, running, onRunAssessment, onSelectTab }: DashboardProps) {
  const summary = assessmentSummary(assessment, requirements);
  const mandatoryCounts = countByStatus(requirements, "mandatory");
  const recommendedCounts = countByStatus(requirements, "recommended");
  const critical = criticalMissing(requirements);
  const openQuestions = questions.filter((question) => question.state === "open").length;

  return (
    <div className="space-y-5">
      {assessment?.is_stale ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-950">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <AlertTriangle aria-hidden="true" className="mt-0.5 h-5 w-5" />
              <div>
                <p className="font-semibold">Source documents have changed since this assessment was generated.</p>
                <p className="mt-1 text-sm">{assessment.stale_reason ?? "Run a new assessment for current results."}</p>
              </div>
            </div>
            <button className="btn-primary" type="button" disabled={running} onClick={onRunAssessment}>
              <PlayCircle aria-hidden="true" className="h-4 w-4" />
              Run New Assessment
            </button>
          </div>
        </div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Overall complete"
          value={formatPercent(assessment?.overall_completeness)}
          detail={assessment ? "Weighted mandatory and recommended score" : "Run an assessment to score"}
        />
        <MetricCard
          label="Mandatory"
          value={formatPercent(assessment?.mandatory_completeness)}
          detail={`${summary.mandatorySupported} / ${summary.mandatoryTotal} supported`}
        />
        <MetricCard
          label="Recommended"
          value={formatPercent(assessment?.recommended_completeness)}
          detail={`${summary.recommendedSupported} / ${summary.recommendedTotal} supported`}
        />
        <div className="rounded-lg border border-line bg-white p-4 shadow-sm">
          <div className="text-sm font-medium text-slate-500">Review status</div>
          <div className="mt-3">
            <StatusBadge status={assessment?.overall_status ?? "not_run"} />
          </div>
          <div className="mt-4 flex items-center gap-2 text-sm text-slate-600">
            <FileQuestion aria-hidden="true" className="h-4 w-4" />
            {openQuestions} open clarification question{openQuestions === 1 ? "" : "s"}
          </div>
        </div>
      </section>

      <section className="panel p-4">
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary" type="button" onClick={() => onSelectTab("requirements")}>
            <ClipboardCheck aria-hidden="true" className="h-4 w-4" />
            View Requirements
          </button>
          <button className="btn-secondary" type="button" onClick={() => onSelectTab("evidence")}>
            <FileText aria-hidden="true" className="h-4 w-4" />
            Review Evidence
          </button>
          <button className="btn-secondary" type="button" onClick={() => onSelectTab("documents")}>
            <FolderOpen aria-hidden="true" className="h-4 w-4" />
            Supporting Documents
          </button>
          <button className="btn-primary" type="button" disabled={running} onClick={onRunAssessment}>
            <PlayCircle aria-hidden="true" className="h-4 w-4" />
            Run Assessment
          </button>
          <button
            className="btn-secondary"
            type="button"
            disabled
            title="Report endpoint is not available in the current backend."
          >
            <ScrollText aria-hidden="true" className="h-4 w-4" />
            Generate Report
          </button>
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="panel p-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-base font-bold text-ink">Status Counts</h2>
            <button className="btn-secondary" type="button" onClick={() => onSelectTab("requirements")}>
              <ClipboardCheck aria-hidden="true" className="h-4 w-4" />
              View Requirements
            </button>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line text-xs uppercase text-slate-500">
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Mandatory</th>
                  <th className="py-2 pr-4">Recommended</th>
                </tr>
              </thead>
              <tbody>
                {evidenceStatuses.map((status) => (
                  <tr className="border-b border-slate-100" key={status}>
                    <td className="py-2 pr-4">
                      <StatusBadge status={status} compact />
                    </td>
                    <td className="py-2 pr-4 font-semibold">{mandatoryCounts[status]}</td>
                    <td className="py-2 pr-4 font-semibold">{recommendedCounts[status]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel p-4">
          <h2 className="text-base font-bold text-ink">Critical Missing Items</h2>
          <p className="mt-1 text-sm text-slate-500">Mandatory requirements that block readiness.</p>
          <div className="mt-4 space-y-3">
            {critical.length === 0 ? (
              <p className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">
                No mandatory missing, contradictory, or rejected items found.
              </p>
            ) : (
              critical.map((requirement) => (
                <div className="rounded-md border border-line p-3" key={requirement.id}>
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold text-ink">{requirement.requirement_id}</p>
                    <StatusBadge status={requirement.evidence?.effective_status ?? "MISSING"} compact />
                  </div>
                  <p className="mt-1 text-sm text-slate-700">{requirement.title}</p>
                  {requirement.evidence?.missing_items?.length ? (
                    <p className="mt-2 text-xs text-slate-500">
                      Missing: {requirement.evidence.missing_items.join("; ")}
                    </p>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      <p className="rounded-lg border border-line bg-panel p-3 text-sm text-slate-600">
        This is an evidence-based completeness review, not a legal or funding-eligibility decision.
      </p>
    </div>
  );
}
