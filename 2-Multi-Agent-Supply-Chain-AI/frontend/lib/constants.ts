import type { AgentRunStatus, RiskLevel, Severity } from "@/types";

export const APP_NAME = "SupplyAI";

/** "mock" = demo mode with realistic generated data; "api" = FastAPI backend through the /api proxy. */
export const DATA_SOURCE: "mock" | "api" = process.env.NEXT_PUBLIC_DATA_SOURCE === "api" ? "api" : "mock";

export const ENVIRONMENT_LABEL = process.env.NEXT_PUBLIC_ENVIRONMENT ?? (DATA_SOURCE === "mock" ? "Demo" : "Production");

export const REQUEST_TIMEOUT_MS = 20_000;
export const ACTIVITY_POLL_MS = 10_000;
export const NOTIFICATION_POLL_MS = 30_000;

/** Semantic status styles — colour always paired with a text label and icon (never colour alone). */
export const RISK_STYLES: Record<RiskLevel, { label: string; badge: string; dot: string; text: string }> = {
  critical: {
    label: "Critical",
    badge: "bg-critical/10 text-critical ring-critical/20",
    dot: "bg-critical",
    text: "text-critical",
  },
  high: { label: "High", badge: "bg-warning/10 text-warning-foreground ring-warning/25", dot: "bg-warning", text: "text-warning-foreground" },
  medium: { label: "Medium", badge: "bg-info/10 text-info ring-info/20", dot: "bg-info", text: "text-info" },
  low: { label: "Low", badge: "bg-success/10 text-success ring-success/20", dot: "bg-success", text: "text-success" },
};

export const SEVERITY_STYLES: Record<Severity, { label: string; dot: string; badge: string }> = {
  critical: { label: "Critical", dot: "bg-critical", badge: "bg-critical/10 text-critical ring-critical/20" },
  warning: { label: "Warning", dot: "bg-warning", badge: "bg-warning/10 text-warning-foreground ring-warning/25" },
  insight: { label: "AI Insight", dot: "bg-ai", badge: "bg-ai/10 text-ai ring-ai/20" },
  info: { label: "Info", dot: "bg-muted-foreground", badge: "bg-muted text-muted-foreground ring-border" },
  success: { label: "Success", dot: "bg-success", badge: "bg-success/10 text-success ring-success/20" },
};

export const RUN_STATUS_LABEL: Record<AgentRunStatus, string> = {
  waiting: "Waiting",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  skipped: "Skipped",
};

export const SUGGESTED_PROMPTS = [
  "Which products are at risk of stockout?",
  "Why is SKU-100 inventory low?",
  "Which supplier should we choose for SKU-100?",
  "Show delayed shipments.",
  "Forecast demand for SKU-100 next month.",
  "Give me a complete recommendation for SKU-100.",
];

export const PRODUCT_CATEGORIES = [
  "Power Systems",
  "Electronics",
  "Mechanical Parts",
  "Packaging",
  "Raw Materials",
  "Safety Equipment",
  "Fluids & Lubricants",
  "Fasteners",
] as const;
