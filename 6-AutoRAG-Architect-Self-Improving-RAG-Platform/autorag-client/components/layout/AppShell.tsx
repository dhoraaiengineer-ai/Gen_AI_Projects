"use client";

import { useState } from "react";

import { DashboardTopbar } from "@/components/layout/DashboardTopbar";
import { PageHeaderBar } from "@/components/layout/PageHeaderBar";
import { Sidebar } from "@/components/layout/sidebar";
import { ScrollToTop } from "@/components/ui/scroll-to-top";
import { useSidebarCollapsed } from "@/hooks/use-sidebar-collapsed";

interface AppShellProps {
  title?: string;
  /** One-line purpose statement shown under the title in PageHeaderBar. */
  description?: string;
  children: React.ReactNode;
  /**
   * Two-personality theme split (19-Jul-2026 review): "operations" (default)
   * is the dark monitoring workspace (Dashboard, Observer, Audit,
   * Deployments). "builder" is a slightly lighter workspace tone for
   * reading/editing-heavy screens (Configurator, Documents, Knowledge Base,
   * Retrieval Explorer) -- global nav (sidebar/topbar) stays dark either
   * way, only the workspace canvas differs. Reduces visual fatigue on long
   * sessions without losing the dark enterprise identity.
   */
  mode?: "operations" | "builder";
  /** Skip PageHeaderBar entirely for the handful of pages (Configurator,
   * Documents) that already render a richer in-content <PageHeader> (with
   * an eyebrow/icon/description) as their first child -- without this,
   * those pages would show two stacked H1-style headers. */
  hideHeaderBar?: boolean;
}

/**
 * Dashboard shell (20-Jul-2026 three-layer rebuild; 25-Jul-2026 icon-rail
 * collapse, widened 240px -> 280px same day per readability feedback;
 * 26-Jul-2026 narrowed to 212px per explicit request during the site_design
 * reference rollout). 212px sidebar (76px when collapsed, localStorage-
 * persisted -- see
 * use-sidebar-collapsed.ts) + a page-agnostic 64px topbar + a per-page
 * PageHeaderBar + workspace. The topbar's own 1px bottom border is the
 * divider the review asked for between "application shell" and "page" -- no
 * separate element needed. Colors/typography/topbar height are still the
 * frozen design system from the 20-Jul-2026 pass; only sidebar width is
 * reopened here, deliberately, per an explicit new request -- not a silent
 * reversal of that freeze.
 */
export function AppShell({ title, description, children, mode = "operations", hideHeaderBar = false }: AppShellProps) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const { collapsed, toggle } = useSidebarCollapsed();

  return (
    <div className={`grid min-h-screen grid-cols-1 ${collapsed ? "md:grid-cols-[76px_1fr]" : "md:grid-cols-[212px_1fr]"}`}>
      {/* Sidebar — hidden on mobile unless opened */}
      <div className={mobileNavOpen ? "block" : "hidden md:block"}>
        <Sidebar
          mobileOpen={mobileNavOpen}
          onNavigate={() => setMobileNavOpen(false)}
          collapsed={collapsed}
          onToggleCollapse={toggle}
        />
      </div>

      {/* Mobile scrim */}
      {mobileNavOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setMobileNavOpen(false)}
          className="fixed inset-0 z-30 bg-black/60 md:hidden"
        />
      )}

      {/* Topbar + page header + workspace */}
      <div className="flex min-w-0 flex-col">
        <DashboardTopbar onMenuClick={() => setMobileNavOpen(true)} />
        <div className="border-b border-border" aria-hidden="true" />
        {!hideHeaderBar && <PageHeaderBar title={title} description={description} />}

        <main
          className={`${mode === "builder" ? "page-bg-builder" : "page-bg"} relative flex-1 overflow-x-hidden [color-scheme:dark]`}
        >
          {/* Grid removed (13-Jul-2026 contrast correction) -- it added haze
              without hierarchy on the Mission Control shell. Vignette kept --
              a much subtler edge-darkening effect, not full-canvas noise. */}
          <div className="vignette pointer-events-none absolute inset-0 z-0" aria-hidden="true" />

          {/* 20-Jul-2026 final shell pass (per direct product review, then
              explicitly frozen after this): content padding 24px -> 32px
              ("enterprise dashboards feel more premium with more breathing
              room"). This is the last shell-level change -- see PLAN.md /
              session notes: freeze sidebar/topbar/page-header/hero/colors/
              typography as the design system, next work is per-page
              consistency review, not further shell redesign. */}
          <div className="relative z-10 mx-auto flex max-w-[1440px] flex-col gap-2 px-8 py-5 pb-10">
            {children}
          </div>

          <ScrollToTop />
        </main>
      </div>
    </div>
  );
}
