import { AlertCircle, CheckCircle2, CircleHelp, Clock3, FileX2, MinusCircle, XCircle } from "lucide-react";
import { formatLabel, statusTone } from "../utils/status";

interface StatusBadgeProps {
  status: string | null | undefined;
  compact?: boolean;
}

function iconForStatus(status: string) {
  switch (status) {
    case "SUPPORTED":
    case "READY_FOR_REVIEW":
    case "provided":
    case "confirmed":
      return <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />;
    case "PARTIALLY_SUPPORTED":
    case "NEEDS_ATTENTION":
      return <Clock3 aria-hidden="true" className="h-3.5 w-3.5" />;
    case "AMBIGUOUS":
    case "open":
      return <CircleHelp aria-hidden="true" className="h-3.5 w-3.5" />;
    case "MISSING":
    case "missing":
      return <FileX2 aria-hidden="true" className="h-3.5 w-3.5" />;
    case "CONTRADICTORY":
    case "REJECTED":
    case "NOT_READY":
      return <XCircle aria-hidden="true" className="h-3.5 w-3.5" />;
    case "NOT_APPLICABLE":
    case "not_required":
    case "dismissed":
      return <MinusCircle aria-hidden="true" className="h-3.5 w-3.5" />;
    default:
      return <AlertCircle aria-hidden="true" className="h-3.5 w-3.5" />;
  }
}

export function StatusBadge({ status, compact = false }: StatusBadgeProps) {
  const value = status ?? "not_run";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ring-1 ring-inset ${statusTone(
        value
      )}`}
    >
      {iconForStatus(value)}
      <span>{compact ? formatLabel(value).replace("Partially Supported", "Partial") : formatLabel(value)}</span>
    </span>
  );
}
