import type { Assessment, DocumentVersion } from "../types";
import { formatLabel, formatPercent } from "../utils/status";
import { StatusBadge } from "./StatusBadge";

interface VersionsPanelProps {
  guidelines: DocumentVersion[];
  applications: DocumentVersion[];
  assessments: Assessment[];
}

export function VersionsPanel({ guidelines, applications, assessments }: VersionsPanelProps) {
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <VersionList title="Guideline Versions" versions={guidelines} />
      <VersionList title="Application Versions" versions={applications} />
      <section className="panel overflow-hidden">
        <div className="border-b border-line p-4">
          <h2 className="text-base font-bold text-ink">Assessment History</h2>
        </div>
        {assessments.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">No assessments yet.</p>
        ) : (
          <div className="divide-y divide-line">
            {assessments.map((assessment) => (
              <div className="p-4" key={assessment.id}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <StatusBadge status={assessment.overall_status ?? assessment.assessment_status} compact />
                  {assessment.is_stale ? <StatusBadge status="STALE" compact /> : null}
                </div>
                <p className="mt-2 text-sm font-semibold text-ink">{formatPercent(assessment.overall_completeness)} overall</p>
                <p className="mt-1 text-xs text-slate-500">Guideline version ID: {assessment.guideline_version_id ?? "None"}</p>
                <p className="mt-1 text-xs text-slate-500">Application version ID: {assessment.application_version_id ?? "None"}</p>
                <p className="mt-1 text-xs text-slate-500">{new Date(assessment.created_at).toLocaleString()}</p>
                {assessment.stale_reason ? <p className="mt-2 text-xs text-amber-800">{assessment.stale_reason}</p> : null}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function VersionList({ title, versions }: { title: string; versions: DocumentVersion[] }) {
  return (
    <section className="panel overflow-hidden">
      <div className="border-b border-line p-4">
        <h2 className="text-base font-bold text-ink">{title}</h2>
      </div>
      {versions.length === 0 ? (
        <p className="p-4 text-sm text-slate-500">No versions uploaded.</p>
      ) : (
        <div className="divide-y divide-line">
          {versions
            .slice()
            .sort((a, b) => b.version_number - a.version_number)
            .map((version) => (
              <div className="p-4" key={version.id}>
                <p className="font-semibold text-ink">
                  v{version.version_number} {version.filename}
                </p>
                <p className="mt-1 text-xs text-slate-500">{formatLabel(version.mime_type)}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {version.total_chunks} chunks{version.total_pages ? `, ${version.total_pages} pages` : ""}
                </p>
                <p className="mt-1 text-xs text-slate-500">{new Date(version.created_at).toLocaleString()}</p>
                <p className="mt-2 break-all text-xs text-slate-400">SHA-256: {version.file_hash}</p>
              </div>
            ))}
        </div>
      )}
    </section>
  );
}
