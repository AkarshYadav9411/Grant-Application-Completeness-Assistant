import { Plus, Trash2 } from "lucide-react";
import { FormEvent, useState } from "react";
import type { Requirement, SupportingDocument, SupportingDocumentStatus } from "../types";
import { formatLabel } from "../utils/status";
import { StatusBadge } from "./StatusBadge";

interface SupportingDocumentsProps {
  documents: SupportingDocument[];
  requirements: Requirement[];
  onCreate: (payload: {
    name: string;
    document_type?: string;
    status: SupportingDocumentStatus;
    related_requirement_ids: string[];
    notes?: string;
  }) => Promise<void>;
  onUpdate: (id: string, payload: Partial<SupportingDocument>) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}

export function SupportingDocuments({ documents, requirements, onCreate, onUpdate, onDelete }: SupportingDocumentsProps) {
  const [name, setName] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [status, setStatus] = useState<SupportingDocumentStatus>("missing");
  const [related, setRelated] = useState("");
  const [notes, setNotes] = useState("");
  const requiredDocRequirements = requirements.filter((requirement) => requirement.category === "required_documents");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    await onCreate({
      name: name.trim(),
      document_type: documentType.trim() || undefined,
      status,
      related_requirement_ids: related
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      notes: notes.trim() || undefined
    });
    setName("");
    setDocumentType("");
    setStatus("missing");
    setRelated("");
    setNotes("");
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
      <form className="panel p-4" onSubmit={handleSubmit}>
        <h2 className="text-base font-bold text-ink">Add Supporting Document</h2>
        <input className="field mt-3" value={name} onChange={(event) => setName(event.target.value)} placeholder="Document name" />
        <input
          className="field mt-2"
          value={documentType}
          onChange={(event) => setDocumentType(event.target.value)}
          placeholder="Type, e.g. IRS letter"
        />
        <select className="field mt-2" value={status} onChange={(event) => setStatus(event.target.value as SupportingDocumentStatus)}>
          <option value="provided">Provided</option>
          <option value="missing">Missing</option>
          <option value="not_required">Not Required</option>
        </select>
        <input
          className="field mt-2"
          value={related}
          onChange={(event) => setRelated(event.target.value)}
          placeholder="Related requirement UUIDs, comma-separated"
        />
        <textarea className="field mt-2 min-h-24" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Notes" />
        <button className="btn-primary mt-3 w-full" type="submit" disabled={!name.trim()}>
          <Plus aria-hidden="true" className="h-4 w-4" />
          Add Document
        </button>

        {requiredDocRequirements.length ? (
          <div className="mt-5 rounded-md bg-panel p-3">
            <p className="text-sm font-semibold text-ink">Required-document cues</p>
            <div className="mt-2 space-y-2">
              {requiredDocRequirements.map((requirement) => (
                <p className="text-xs text-slate-600" key={requirement.id}>
                  {requirement.requirement_id}: {requirement.title}
                </p>
              ))}
            </div>
          </div>
        ) : null}
      </form>

      <section className="panel overflow-hidden">
        <div className="border-b border-line p-4">
          <h2 className="text-base font-bold text-ink">Supporting Documents</h2>
        </div>
        {documents.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">No supporting documents tracked yet.</p>
        ) : (
          <div className="divide-y divide-line">
            {documents.map((document) => (
              <div className="p-4" key={document.id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-ink">{document.name}</p>
                    <p className="mt-1 text-sm text-slate-500">{document.document_type ?? "No type"}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <select
                      className="field w-auto"
                      value={document.status}
                      onChange={(event) =>
                        onUpdate(document.id, { status: event.target.value as SupportingDocumentStatus })
                      }
                    >
                      <option value="provided">Provided</option>
                      <option value="missing">Missing</option>
                      <option value="not_required">Not Required</option>
                    </select>
                    <button className="btn-secondary text-danger" type="button" onClick={() => onDelete(document.id)}>
                      <Trash2 aria-hidden="true" className="h-4 w-4" />
                      Delete
                    </button>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <StatusBadge status={document.status} />
                  <span className="text-xs text-slate-500">
                    Related:{" "}
                    {document.related_requirement_ids.length
                      ? document.related_requirement_ids
                          .map((id) => requirements.find((requirement) => requirement.id === id)?.requirement_id ?? id)
                          .join(", ")
                      : "None"}
                  </span>
                </div>
                {document.notes ? <p className="mt-2 text-sm text-slate-600">{document.notes}</p> : null}
                <p className="mt-2 text-xs text-slate-400">Status updates mark existing assessments stale.</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
