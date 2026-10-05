import { Edit3, Search, Trash2 } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import type { EvidenceStatus, RequirementCategory, RequirementPriority, RequirementWithEvidence } from "../types";
import { evidenceStatuses, formatLabel } from "../utils/status";
import { StatusBadge } from "./StatusBadge";

type FilterValue =
  | "all"
  | RequirementPriority
  | "SUPPORTED"
  | "PARTIALLY_SUPPORTED"
  | "MISSING"
  | "AMBIGUOUS"
  | "CONTRADICTORY";

interface RequirementsTableProps {
  requirements: RequirementWithEvidence[];
  onUpdate: (
    id: string,
    payload: {
      title?: string;
      description?: string;
      category?: RequirementCategory;
      priority?: RequirementPriority;
      source_text?: string;
    }
  ) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onCreate: (payload: {
    title: string;
    description: string;
    category: RequirementCategory;
    priority: RequirementPriority;
    source_text?: string;
  }) => Promise<void>;
}

const categories: RequirementCategory[] = [
  "eligibility",
  "required_information",
  "required_documents",
  "project_description",
  "objectives",
  "budget",
  "timeline",
  "organization_information",
  "evaluation_criteria",
  "submission_requirements",
  "formatting_requirements",
  "other"
];

export function RequirementsTable({ requirements, onUpdate, onDelete, onCreate }: RequirementsTableProps) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<FilterValue>("all");
  const [selectedId, setSelectedId] = useState<string | null>(requirements[0]?.id ?? null);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return requirements.filter((requirement) => {
      const status = requirement.evidence?.effective_status ?? "MISSING";
      const matchesQuery =
        !normalized ||
        requirement.requirement_id.toLowerCase().includes(normalized) ||
        requirement.title.toLowerCase().includes(normalized) ||
        requirement.description.toLowerCase().includes(normalized);
      const matchesFilter =
        filter === "all" ||
        requirement.priority === filter ||
        (evidenceStatuses.includes(filter as EvidenceStatus) && status === filter);
      return matchesQuery && matchesFilter;
    });
  }, [filter, query, requirements]);

  const selected = requirements.find((requirement) => requirement.id === selectedId) ?? filtered[0];

  async function handleAdd(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !description.trim()) return;
    await onCreate({
      title: title.trim(),
      description: description.trim(),
      category: "other",
      priority: "mandatory",
      source_text: "Manually added by reviewer."
    });
    setTitle("");
    setDescription("");
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
      <section className="panel overflow-hidden">
        <div className="border-b border-line p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <h2 className="text-base font-bold text-ink">Requirements</h2>
            <div className="flex flex-1 flex-wrap justify-end gap-2">
              <label className="relative min-w-64 flex-1 md:max-w-80">
                <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  className="field pl-9"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search requirements"
                />
              </label>
              <select className="field w-auto" value={filter} onChange={(event) => setFilter(event.target.value as FilterValue)}>
                <option value="all">All</option>
                <option value="mandatory">Mandatory</option>
                <option value="recommended">Recommended</option>
                <option value="SUPPORTED">Supported</option>
                <option value="PARTIALLY_SUPPORTED">Partial</option>
                <option value="MISSING">Missing</option>
                <option value="AMBIGUOUS">Ambiguous</option>
                <option value="CONTRADICTORY">Contradictory</option>
              </select>
            </div>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-line bg-panel text-xs uppercase text-slate-500">
                <th className="px-4 py-3">ID</th>
                <th className="px-4 py-3">Requirement</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Evidence</th>
                <th className="px-4 py-3">Source</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((requirement) => (
                <tr
                  className={`cursor-pointer border-b border-slate-100 hover:bg-blue-50 ${
                    selected?.id === requirement.id ? "bg-blue-50" : ""
                  }`}
                  key={requirement.id}
                  onClick={() => {
                    setSelectedId(requirement.id);
                    setEditing(false);
                  }}
                >
                  <td className="px-4 py-3 font-semibold text-ink">{requirement.requirement_id}</td>
                  <td className="max-w-80 px-4 py-3">
                    <span className="block font-medium text-ink">{requirement.title}</span>
                    <span className="line-clamp-2 text-xs text-slate-500">{requirement.description}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{formatLabel(requirement.category)}</td>
                  <td className="px-4 py-3 text-slate-600">{formatLabel(requirement.priority)}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={requirement.evidence?.effective_status ?? "MISSING"} compact />
                  </td>
                  <td className="max-w-72 px-4 py-3 text-slate-600">
                    {requirement.evidence?.effective_evidence_text ?? requirement.evidence?.missing_items?.join("; ") ?? "No mapping"}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {requirement.evidence?.source_document
                      ? `${requirement.evidence.source_document}${
                          requirement.evidence.source_page ? ` p. ${requirement.evidence.source_page}` : ""
                        }`
                      : requirement.source_document ?? "None"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <aside className="space-y-4">
        <section className="panel p-4">
          <h3 className="text-base font-bold text-ink">Requirement Detail</h3>
          {selected ? (
            <div className="mt-4 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{selected.requirement_id}</span>
                <StatusBadge status={selected.evidence?.effective_status ?? "MISSING"} compact />
                {selected.priority_flagged_for_review ? (
                  <span className="rounded-full bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-900 ring-1 ring-amber-200">
                    Priority needs review
                  </span>
                ) : null}
              </div>
              {editing ? (
                <EditRequirementForm requirement={selected} onCancel={() => setEditing(false)} onUpdate={onUpdate} />
              ) : (
                <>
                  <div>
                    <p className="font-semibold text-ink">{selected.title}</p>
                    <p className="mt-1 text-sm text-slate-600">{selected.description}</p>
                  </div>
                  <div className="rounded-md bg-panel p-3 text-sm text-slate-600">
                    <p className="font-semibold text-ink">Evidence</p>
                    <p className="mt-1">{selected.evidence?.effective_evidence_text ?? "No cited evidence."}</p>
                    {selected.evidence?.effective_explanation ? (
                      <p className="mt-2 text-xs">{selected.evidence.effective_explanation}</p>
                    ) : null}
                    {selected.evidence?.missing_items?.length ? (
                      <p className="mt-2 text-xs">Missing: {selected.evidence.missing_items.join("; ")}</p>
                    ) : null}
                  </div>
                  <div className="rounded-md bg-slate-50 p-3 text-xs text-slate-600">
                    <p className="font-semibold text-ink">Citation</p>
                    <p className="mt-1">
                      {selected.evidence?.source_document ?? selected.source_document ?? "No source document"}
                      {selected.evidence?.source_page ? `, page ${selected.evidence.source_page}` : ""}
                      {selected.evidence?.source_section ? `, ${selected.evidence.source_section}` : ""}
                    </p>
                    <p className="mt-1">
                      Verified citation: {selected.evidence?.citation_verified ? "Yes" : "No"}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button className="btn-secondary" type="button" onClick={() => setEditing(true)}>
                      <Edit3 aria-hidden="true" className="h-4 w-4" />
                      Edit
                    </button>
                    <button className="btn-secondary text-danger" type="button" onClick={() => onDelete(selected.id)}>
                      <Trash2 aria-hidden="true" className="h-4 w-4" />
                      Delete
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-500">No requirements available.</p>
          )}
        </section>

        <form className="panel p-4" onSubmit={handleAdd}>
          <h3 className="text-base font-bold text-ink">Add Requirement</h3>
          <input
            className="field mt-3"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Requirement title"
          />
          <textarea
            className="field mt-2 min-h-24"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Requirement description"
          />
          <button className="btn-primary mt-3 w-full" type="submit" disabled={!title.trim() || !description.trim()}>
            Add Requirement
          </button>
        </form>
      </aside>
    </div>
  );
}

function EditRequirementForm({
  requirement,
  onUpdate,
  onCancel
}: {
  requirement: RequirementWithEvidence;
  onUpdate: RequirementsTableProps["onUpdate"];
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(requirement.title);
  const [description, setDescription] = useState(requirement.description);
  const [category, setCategory] = useState<RequirementCategory>(requirement.category);
  const [priority, setPriority] = useState<RequirementPriority>(requirement.priority);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    await onUpdate(requirement.id, { title, description, category, priority });
    onCancel();
  }

  return (
    <form className="space-y-3" onSubmit={handleSubmit}>
      <input className="field" value={title} onChange={(event) => setTitle(event.target.value)} />
      <textarea className="field min-h-24" value={description} onChange={(event) => setDescription(event.target.value)} />
      <select className="field" value={category} onChange={(event) => setCategory(event.target.value as RequirementCategory)}>
        {categories.map((item) => (
          <option key={item} value={item}>
            {formatLabel(item)}
          </option>
        ))}
      </select>
      <select className="field" value={priority} onChange={(event) => setPriority(event.target.value as RequirementPriority)}>
        <option value="mandatory">Mandatory</option>
        <option value="recommended">Recommended</option>
      </select>
      <div className="flex gap-2">
        <button className="btn-primary" type="submit">
          Save
        </button>
        <button className="btn-secondary" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
