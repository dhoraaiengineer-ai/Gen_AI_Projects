import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AutoRAG Architect — Autonomous RAG Platform",
  description:
    "A closed-loop platform that builds, evaluates, observes, diagnoses, improves, and deploys Retrieval-Augmented Generation pipelines with 9 autonomous agents.",
};

/**
 * Marketing layout — public, unauthenticated landing page.
 * No shared AppShell/sidebar, matching the (auth) route group's pattern:
 * root layout already applies fonts/theme/query-client; this is a pure
 * passthrough so the page can define its own light, glass-panel visual
 * identity (see frontend_design.md §16 for the same exception on /login).
 */
export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
