import {
  LayoutDashboard,
  Wand2,
  Gauge,
  Rocket,
  Database,
  Activity,
  HeartPulse,
  ScrollText,
  Settings,
  FlaskConical,
  GitBranch,
  FileText,
  Search,
  Microscope,
  TrendingUp,
  TestTube2,
  HelpCircle,
  LineChart,
  ListChecks,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href:  string;
  icon:  LucideIcon;
  match: string;
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

/**
 * Product-area navigation (26-Jul-2026 lifecycle-order IA pass — supersedes
 * the 24-Jul-2026 Phase 1 grouping; same 8 sections, reordered/renamed to
 * mirror the AutoRAG lifecycle end-to-end so the sidebar tells the product's
 * story: Dashboard -> Build Pipeline -> Prepare Knowledge -> Test Retrieval
 * -> Evaluate -> Optimize -> Deploy -> Operate. Flat, always-expanded
 * sections at the data level; the sidebar's own render mode (25-Jul-2026)
 * supports a desktop icon-rail collapse, persisted via localStorage in
 * hooks/use-sidebar-collapsed.ts — that's a rendering concern in
 * components/layout/sidebar.tsx, not a change to this data.
 *
 * **Navigation is a contract with the user**: a page appears here ONLY when
 * it is backed by production-ready APIs and live data. This is Phase 1 —
 * real pages only. Still excluded (fabricated, no real backend — hardcoded/
 * Math.random() data, see verification/releases/v4.0/audit/DEFERRED_BACKEND_WIRING.md):
 * Agent Hub, Agent State, Workflow, Chunk Explorer, Embeddings, AI Chat,
 * Cost Analytics, Security, Infrastructure, Prompt Studio. Each direct URL
 * still renders its existing page for future real wiring — Phase 2 makes
 * each one real and adds it back here; Phase 3 adopts the full grouping
 * (including an Agents and Developer Tools section) once every page in it
 * is real. Do not add a page here ahead of its real backend landing.
 */
export const NAV_SECTIONS: NavSection[] = [
  {
    label: "Core",
    items: [
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, match: "/dashboard" },
    ],
  },
  {
    label: "Pipeline Studio",
    items: [
      // 20-Jul-2026: "Configurator" -> "Pipeline Studio" (per direct product
      // review) -- same page, same href, just a clearer label for an
      // enterprise audience.
      { label: "Pipeline Studio",  href: "/configurator", icon: Wand2,     match: "/configurator" },
      { label: "Pipeline History", href: "/pipelines",    icon: GitBranch, match: "/pipelines"    },
    ],
  },
  {
    // 26-Jul-2026: item order swapped (Documents before Knowledge Base) to
    // match the actual workflow -- ingest documents first, then inspect
    // what got indexed. Section position/label unchanged.
    label: "Knowledge",
    items: [
      { label: "Documents",      href: "/documents",  icon: FileText, match: "/documents"   },
      { label: "Knowledge Base", href: "/knowledge",  icon: Database, match: "/knowledge"  },
    ],
  },
  {
    label: "Retrieval",
    items: [
      { label: "Retrieval Explorer", href: "/retrieve",   icon: Search,       match: "/retrieve"   },
      { label: "Query Playground",   href: "/playground", icon: FlaskConical, match: "/playground" },
    ],
  },
  {
    // 26-Jul-2026: "Evaluate" removed from the sidebar -- app/evaluate/page.tsx
    // is a pure redirect() to /evaluation?tab=run (Redesign Phase 3), not a
    // distinct workflow. The prior comment here claiming they "both stay"
    // was stale/contradicted by the actual page. The /evaluate route itself
    // is untouched (still resolves for old deep links), just not listed here.
    label: "Evaluation",
    items: [
      { label: "Evaluation Center", href: "/evaluation",  icon: Gauge,      match: "/evaluation"  },
      { label: "Golden Datasets",   href: "/datasets",    icon: ListChecks, match: "/datasets"    },
      { label: "Experiments",       href: "/experiments", icon: TestTube2,  match: "/experiments" },
    ],
  },
  {
    // Observer/Diagnoser/Improver plus Evolution History are the real
    // closed optimization loop (Observer detects -> Diagnoser explains ->
    // Improver recommends -> apply from Improver -> Evolution History shows
    // the resulting version history + rollback). 26-Jul-2026: "Autonomous
    // Optimization" -> "Optimization" (shorter; the individual pages already
    // communicate the autonomous aspect) and "Pipeline Evolution" -> "Evolution
    // History" (reads as history/workspace, not a standalone agent, consistent
    // with Observer/Diagnoser/Improver).
    label: "Optimization",
    items: [
      { label: "Observer",         href: "/observe",   icon: Activity,    match: "/observe"   },
      { label: "Diagnoser",        href: "/diagnose",  icon: Microscope,  match: "/diagnose"  },
      { label: "Improver",         href: "/improve",   icon: TrendingUp,  match: "/improve"   },
      { label: "Evolution History", href: "/evolution", icon: LineChart,   match: "/evolution" },
    ],
  },
  {
    label: "Deployment",
    items: [
      // 20-Jul-2026: "Deployments" -> "Deployment Center" (per direct
      // product review, matches "Evaluation Center" naming).
      { label: "Deployment Center", href: "/deploy", icon: Rocket,     match: "/deploy" },
      { label: "Audit Logs",        href: "/audit",  icon: ScrollText, match: "/audit"  },
    ],
  },
  {
    // 26-Jul-2026: "Platform" -> "System" (per direct product review) --
    // same items, clearer label for a section that's just health/settings/help.
    label: "System",
    items: [
      { label: "System Health", href: "/health",           icon: HeartPulse, match: "/health"   },
      { label: "Settings",      href: "/settings/profile", icon: Settings,   match: "/settings" },
      { label: "Documentation", href: "/help",             icon: HelpCircle, match: "/help"     },
    ],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_SECTIONS.flatMap((s) => s.items);

/**
 * Exact-segment active matching — `/agents` must NOT light up for `/agent-state`.
 * A route is active when the pathname equals the match or descends from it via "/".
 */
export function isActive(pathname: string, item: NavItem): boolean {
  return pathname === item.href
    || pathname === item.match
    || pathname.startsWith(`${item.match}/`);
}
