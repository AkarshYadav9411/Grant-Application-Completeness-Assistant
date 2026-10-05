import { Check, Save, X } from "lucide-react";
import { FormEvent, useState } from "react";
import type { EvidenceMapping, EvidenceStatus, Requirement } from "../types";
import { evidenceStatuses, formatLabel } from "../utils/status";
import { StatusBadge } from "./StatusBadge";

interface EvidenceReviewProps {
  evidence: EvidenceMapping[];
  requirements: Requirement[];
  onConfirm: (id: string) => Promise<void>;
  onReject: (id: string) => Promise<void>;
  onEdit: (
    id: string,
    payload: {
      reviewed_status?: EvidenceStatus;
      reviewed_evidence_text?: string;
      reviewed_explanation?: string;
      notes?: string;
    }
  ) => Promise<void>;
}

export function EvidenceReview({ evidence, requirements, onConfirm, onReject, onEdit }: EvidenceReviewProps) {
  const requirementById = new Map(requirements.map((requirement) => [requirement.id, requirement]));
  const [editingId, setEditingId] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      {evidence.length === 0 ? (
        <div className="panel p-6 text-sm text-slate-500">Run an assessment to review evidence mappings.</div>
      ) : null}
      {evidence.map((mapping) => {
        const requirement = requirementById.get(mapping.requirement_id);
        return (
          <article className="panel p-4" key={mapping.id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-500">
                  {requirement?.requirement_id ?? "Requirement"} {requirement?.title ? `- ${requirement.title}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <StatusBadge status={mapping.effective_status} />
                  <span className="text-xs font-medium text-slate-500">Confidence {Math.round(mapping.confidence * 100)}%</span>
                  {mapping.user_review ? <StatusBadge status={mapping.user_review.action} compact /> : null}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn-secondary" type="button" onClick={() => onConfirm(mapping.id)}>
                  <Check aria-hidden="true" className="h-4 w-4" />
                  Confirm
                </button>
                <button className="btn-secondary" type="button" onClick={() => setEditingId(mapping.id)}>
                  <Save aria-hidden="true" className="h-4 w-4" />
                  Edit
                </button>
                <button className="btn-secondary text-danger" type="button" onClick={() => onReject(mapping.id)}>
                  <X aria-hidden="true" className="h-4 w-4" />
                  Reject
                </button>
              </div>
            </div>

            {editingId === mapping.id ? (
              <EvidenceEditForm
                mapping={mapping}
                onCancel={() => setEditingId(null)}
                onSave={async (payload) => {
                  await onEdit(mapping.id, payload);
                  setEditingId(null);
                }}
              />
            ) : (
              <div className="mt-4 grid gap-3 xl:grid-cols-3">
                <div className="rounded-md bg-panel p-3 xl:col-span-2">
                  <p className="text-xs font-semibold uppercase text-slate-500">Evidence</p>
                  <p className="mt-1 text-sm text-slate-700">{mapping.effective_evidence_text ?? "No evidence cited."}</p>
                  {mapping.effective_explanation ? (
                    <p className="mt-3 text-sm text-slate-600">{mapping.effective_explanation}</p>
                  ) : null}
                  {mapping.missing_items.length ? (
                    <p className="mt-3 text-sm text-slate-600">Missing: {mapping.missing_items.join("; ")}</p>
                  ) : null}
                </div>
                <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-600">
                  <p className="text-xs font-semibold uppercase text-slate-500">Citation</p>
                  <p className="mt-1">{mapping.source_document ?? "No source document"}</p>
                  <p className="mt-1">
                    {mapping.source_page ? `Page ${mapping.source_page}` : "No page"}
                    {mapping.source_section ? `, ${mapping.source_section}` : ""}
                  </p>
                  <p className="mt-1">Chunk: {mapping.source_chunk_id ?? "None"}</p>
                  <p className="mt-1">Verified: {mapping.citation_verified ? "Yes" : "No"}</p>
                </div>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

function EvidenceEditForm({
  mapping,
  onSave,
  onCancel
}: {
  mapping: EvidenceMapping;
  onSave: (payload: {
    reviewed_status?: EvidenceStatus;
    reviewed_evidence_text?: string;
    reviewed_explanation?: string;
    notes?: string;
  }) => Promise<void>;
  onCancel: () => void;
}) {
  const [status, setStatus] = useState<EvidenceStatus>(mapping.effective_status);
  const [evidenceText, setEvidenceText] = useState(mapping.effective_evidence_text ?? "");
  const [explanation, setExplanation] = useState(mapping.effective_explanation ?? "");
  const [notes, setNotes] = useState("");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    await onSave({
      reviewed_status: status,
      reviewed_evidence_text: evidenceText,
      reviewed_explanation: explanation,
      notes: notes || undefined
    });
  }

  return (
    <form className="mt-4 space-y-3 rounded-md border border-line bg-panel p-3" onSubmit={handleSubmit}>
      <select className="field" value={status} onChange={(event) => setStatus(event.target.value as EvidenceStatus)}>
        {evidenceStatuses.map((item) => (
          <option key={item} value={item}>
            {formatLabel(item)}
          </option>
        ))}
      </select>
      <textarea
        className="field min-h-24"
        value={evidenceText}
        onChange={(event) => setEvidenceText(event.target.value)}
        placeholder="Reviewed evidence text"
      />
      <textarea
        className="field min-h-24"
        value={explanation}
        onChange={(event) => setExplanation(event.target.value)}
        placeholder="Reviewed explanation"
      />
      <input className="field" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Review notes" />
      <div className="flex gap-2">
        <button className="btn-primary" type="submit">
          Save Review
        </button>
        <button className="btn-secondary" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
