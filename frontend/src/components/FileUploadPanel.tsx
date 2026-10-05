import { FileUp } from "lucide-react";
import { ChangeEvent, useRef, useState } from "react";

interface FileUploadPanelProps {
  label: string;
  help: string;
  onUpload: (file: File) => Promise<void>;
}

export function FileUploadPanel({ label, help, onUpload }: FileUploadPanelProps) {
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  async function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await onUpload(file);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <label className="block rounded-lg border border-dashed border-line bg-white p-4 transition hover:border-brand">
      <span className="flex items-center gap-2 text-sm font-semibold text-ink">
        <FileUp aria-hidden="true" className="h-4 w-4 text-brand" />
        {label}
      </span>
      <span className="mt-1 block text-xs text-slate-500">{help}</span>
      <input
        ref={inputRef}
        className="mt-3 block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-slate-700 hover:file:bg-slate-200"
        type="file"
        accept=".pdf,.docx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown"
        disabled={uploading}
        onChange={handleChange}
      />
      {uploading ? <span className="mt-2 block text-xs text-slate-500">Uploading and extracting...</span> : null}
    </label>
  );
}
