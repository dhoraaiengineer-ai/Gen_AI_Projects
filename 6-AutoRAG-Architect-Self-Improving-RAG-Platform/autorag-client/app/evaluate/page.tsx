import { redirect } from "next/navigation";

interface EvaluatePageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * /evaluate is consolidated into /evaluation (Redesign Phase 3).
 * Preserves query params (e.g. ?runId=…) so deep links keep working.
 * Defaults `tab=run` (25-Jul-2026 fix, per user report) so the nav item
 * labeled "Evaluate" actually opens the single-question Run Evaluation tab
 * instead of always landing on Overview -- callers can still override it
 * with an explicit `?tab=` of their own.
 */
export default async function EvaluatePage({ searchParams }: EvaluatePageProps) {
  const params = await searchParams;
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === "string") qs.set(key, value);
    else if (Array.isArray(value)) for (const v of value) qs.append(key, v);
  }
  if (!qs.has("tab")) qs.set("tab", "run");
  redirect(`/evaluation?${qs.toString()}`);
}
