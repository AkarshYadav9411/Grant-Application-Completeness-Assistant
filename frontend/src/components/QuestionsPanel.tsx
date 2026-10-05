import { CheckCircle2, XCircle } from "lucide-react";
import type { ClarificationQuestion, Requirement } from "../types";
import { StatusBadge } from "./StatusBadge";

interface QuestionsPanelProps {
  questions: ClarificationQuestion[];
  requirements: Requirement[];
  onUpdate: (id: string, payload: { state?: ClarificationQuestion["state"]; answer_text?: string }) => Promise<void>;
}

export function QuestionsPanel({ questions, requirements, onUpdate }: QuestionsPanelProps) {
  const requirementById = new Map(requirements.map((requirement) => [requirement.id, requirement]));
  return (
    <section className="panel overflow-hidden">
      <div className="border-b border-line p-4">
        <h2 className="text-base font-bold text-ink">Clarification Questions</h2>
      </div>
      {questions.length === 0 ? (
        <p className="p-4 text-sm text-slate-500">No clarification questions generated.</p>
      ) : (
        <div className="divide-y divide-line">
          {questions.map((question) => {
            const requirement = requirementById.get(question.requirement_id);
            return (
              <div className="p-4" key={question.id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-500">
                      {requirement?.requirement_id ?? "Requirement"} {requirement?.title ?? ""}
                    </p>
                    <p className="mt-1 font-medium text-ink">{question.question_text}</p>
                    {question.answer_text ? <p className="mt-2 text-sm text-slate-600">{question.answer_text}</p> : null}
                  </div>
                  <StatusBadge status={question.state} />
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    className="btn-secondary"
                    type="button"
                    onClick={() => onUpdate(question.id, { state: "answered", answer_text: question.answer_text ?? "Answered by reviewer." })}
                  >
                    <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
                    Mark Answered
                  </button>
                  <button className="btn-secondary" type="button" onClick={() => onUpdate(question.id, { state: "dismissed" })}>
                    <XCircle aria-hidden="true" className="h-4 w-4" />
                    Dismiss
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
