/**
 * System Health derivation (F-19) — pure, React-free, cheaply unit-testable.
 *
 * The only live health signal is GET /health (FastAPI). This module turns a
 * rolling series of client-side probe samples into the derived figures the
 * dashboard shows: overall status, session uptime, and latency classification.
 * Nothing here fabricates per-service health — the platform exposes no such
 * endpoints (see SystemHealthPageClient for the "focused live-only" scope).
 */

export type OverallStatus = "healthy" | "warning" | "critical";
export type LatencyClass = "good" | "fair" | "poor";

/** A single probe result appended by use-system-health. */
export interface HealthSample {
  ok: boolean;
  latencyMs: number | null;
  at: number;
}

/** Consecutive-failure thresholds for status escalation. */
const WARNING_FAILS = 1;
const CRITICAL_FAILS = 3;

/**
 * Overall platform status from the live probe state.
 * - critical: currently offline, or ≥3 consecutive failures
 * - warning:  online but 1–2 recent failures (flapping)
 * - healthy:  online with a clean recent streak
 */
export function deriveOverallStatus(isOnline: boolean, failStreak: number): OverallStatus {
  if (!isOnline || failStreak >= CRITICAL_FAILS) return "critical";
  if (failStreak >= WARNING_FAILS) return "warning";
  return "healthy";
}

/** Session uptime as a 0..1 ratio of successful probes over total probes. */
export function sessionUptime(successful: number, total: number): number {
  if (total <= 0) return 0;
  return successful / total;
}

/** Classify a round-trip latency: <300ms good, <1000ms fair, else poor. */
export function latencyClass(ms: number | null): LatencyClass {
  if (ms === null) return "poor";
  if (ms < 300) return "good";
  if (ms < 1000) return "fair";
  return "poor";
}

/** Count of active alerts derived from live state (down = 1 critical alert). */
export function activeAlerts(isOnline: boolean, failStreak: number): number {
  return deriveOverallStatus(isOnline, failStreak) === "critical" ? 1 : 0;
}

// ── Formatting ────────────────────────────────────────────────────────────────
export function formatUptime(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`;
}

export function formatLatency(ms: number | null): string {
  return ms === null ? "—" : `${Math.round(ms)} ms`;
}

/** Tailwind text colour per overall status (shared by cards + badges). */
export const STATUS_TEXT: Record<OverallStatus, string> = {
  healthy: "text-green-400",
  warning: "text-amber-400",
  critical: "text-red-400",
};

/** Tailwind bg colour per overall status (dots / bars). */
export const STATUS_DOT: Record<OverallStatus, string> = {
  healthy: "bg-green-400",
  warning: "bg-amber-400",
  critical: "bg-red-400",
};

export const STATUS_LABEL: Record<OverallStatus, string> = {
  healthy: "Healthy",
  warning: "Warning",
  critical: "Critical",
};
