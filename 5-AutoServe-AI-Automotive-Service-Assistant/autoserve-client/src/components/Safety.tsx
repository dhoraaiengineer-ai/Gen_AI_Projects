import type { Citation, SafetyInfo } from "../api/schemas";

/** Red/amber safety banner. Text always comes from the server's fixed rules/55 texts — never written here. */
export function SafetyBanner({ safety }: { safety: SafetyInfo }) {
  if (safety.banner_tier === "none" || !safety.banner_text) return null;
  const stop = safety.banner_tier === "stop";
  return (
    <div
      role="alert"
      className={`mb-2 rounded border-l-4 p-3 text-sm ${
        stop ? "border-red-700 bg-red-50 text-red-900" : "border-amber-600 bg-amber-50 text-amber-900"
      }`}
    >
      <p className="font-semibold">{safety.banner_text}</p>
      {safety.required_action_quote && (
        <p className="mt-1">
          The manual says: “{safety.required_action_quote.quote}”{" "}
          <CitationChip citation={safety.required_action_quote} />
        </p>
      )}
      {safety.escalation && <p className="mt-1">{safety.escalation}</p>}
    </div>
  );
}

export function CitationChip({ citation }: { citation: Citation }) {
  return (
    <span
      className="ml-1 inline-flex items-center rounded-full border border-slate-300 bg-white px-2 py-0.5 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200"
      title={`“${citation.quote}”`}
    >
      {citation.section_title} · {citation.source_file} p.{citation.page}
    </span>
  );
}

export function AIAssessmentBanner() {
  return <p className="text-xs text-slate-500">AI-generated preliminary assessment — not a decision.</p>;
}
