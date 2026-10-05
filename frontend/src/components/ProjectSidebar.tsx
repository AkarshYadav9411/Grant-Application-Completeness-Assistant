import { FolderPlus, RefreshCcw } from "lucide-react";
import { FormEvent, useState } from "react";
import type { Project } from "../types";

interface ProjectSidebarProps {
  projects: Project[];
  selectedProjectId: string | null;
  loading: boolean;
  onSelect: (projectId: string) => void;
  onRefresh: () => void;
  onCreate: (payload: { name: string; description?: string }) => Promise<void>;
}

export function ProjectSidebar({
  projects,
  selectedProjectId,
  loading,
  onSelect,
  onRefresh,
  onCreate
}: ProjectSidebarProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onCreate({ name: name.trim(), description: description.trim() || undefined });
      setName("");
      setDescription("");
    } finally {
      setSaving(false);
    }
  }

  return (
    <aside className="flex h-full flex-col border-r border-line bg-white">
      <div className="border-b border-line p-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h1 className="text-lg font-bold text-ink">Completeness Assistant</h1>
            <p className="mt-1 text-xs text-slate-500">Evidence-based grant review</p>
          </div>
          <button className="btn-secondary px-2" type="button" onClick={onRefresh} title="Refresh projects">
            <RefreshCcw aria-hidden="true" className="h-4 w-4" />
            <span className="sr-only">Refresh projects</span>
          </button>
        </div>
      </div>

      <form className="border-b border-line p-4" onSubmit={handleSubmit}>
        <label className="text-sm font-semibold text-slate-700" htmlFor="project-name">
          New review
        </label>
        <input
          className="field mt-2"
          id="project-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Project name"
        />
        <textarea
          className="field mt-2 min-h-20 resize-y"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="Optional description"
          aria-label="Project description"
        />
        <button className="btn-primary mt-3 w-full" type="submit" disabled={saving || !name.trim()}>
          <FolderPlus aria-hidden="true" className="h-4 w-4" />
          Create Review
        </button>
      </form>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-auto p-3">
        {loading ? <p className="p-3 text-sm text-slate-500">Loading projects...</p> : null}
        {!loading && projects.length === 0 ? (
          <p className="p-3 text-sm text-slate-500">Create a review to begin.</p>
        ) : null}
        <div className="space-y-2">
          {projects.map((project) => (
            <button
              key={project.id}
              className={`w-full rounded-md border p-3 text-left transition ${
                selectedProjectId === project.id
                  ? "border-brand bg-blue-50"
                  : "border-transparent hover:border-line hover:bg-slate-50"
              }`}
              type="button"
              onClick={() => onSelect(project.id)}
            >
              <span className="block text-sm font-semibold text-ink">{project.name}</span>
              {project.description ? (
                <span className="mt-1 block line-clamp-2 text-xs text-slate-500">{project.description}</span>
              ) : null}
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
}
