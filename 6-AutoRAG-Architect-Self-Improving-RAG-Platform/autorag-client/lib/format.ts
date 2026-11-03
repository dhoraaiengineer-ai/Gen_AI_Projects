/**
 * Small pure formatting helpers shared across dashboard components.
 * Kept React-free for cheap unit testing.
 */

import type { Pipeline } from "@/types";

/** Resolve a human-friendly display name for a pipeline: "{name} · v{current_version}". */
export function pipelineDisplayName(
  pipeline: Pick<Pipeline, "id" | "current_version" | "name">,
): string {
  const base = pipeline.name || `Pipeline ${pipeline.id.slice(0, 8)}`;
  return `${base} · v${pipeline.current_version}`;
}

// The only user this local-dev environment ever seeds (backend's own seed
// row: id 00000000-...-000000000001, full_name "Local Dev User") — a real,
// known mapping, not a guess. Any other UUID (a real multi-user deployment)
// falls back to the raw ID since there's no user-lookup endpoint to resolve
// it against.
const KNOWN_USERS: Record<string, string> = {
  "00000000-0000-0000-0000-000000000001": "Local Dev User",
};

/** Resolve a user ID to a display name where actually known — never a guess. */
export function displayUser(userId: string): string {
  return KNOWN_USERS[userId] ?? userId;
}

/** Compact relative time, e.g. "3m ago" / "2h ago" / "5d ago". */
export function relativeTime(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  return `${days}d ago`;
}
