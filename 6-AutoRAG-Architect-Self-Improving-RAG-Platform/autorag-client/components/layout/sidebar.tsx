"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { NAV_SECTIONS, isActive } from "@/lib/nav";
import { AutoRagLogo, AutoRagLogoMark } from "@/components/brand/AutoRagLogo";
import { cn } from "@/lib/utils";
import { apiClient } from "@/services/api-client";

interface SidebarProps {
  mobileOpen?: boolean;
  onNavigate?: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

/**
 * Lifecycle sidebar (14-Jul-2026 IA redesign, 16-Jul-2026 premium shell pass,
 * 25-Jul-2026 icon-rail collapse): Build -> Retrieve -> Quality -> Release ->
 * Platform, mirrors AutoRAG's own closed-loop architecture. Desktop-only
 * collapse to an icon rail (see use-sidebar-collapsed.ts) is independent of
 * the mobile off-canvas open/close below -- two different mechanisms for two
 * different screen sizes, not merged. Onboarding lives on /dashboard's hero +
 * journey cards, not a numbered sidebar section.
 */
export function Sidebar({ mobileOpen, onNavigate, collapsed = false, onToggleCollapse }: SidebarProps) {
  const pathname = usePathname();

  // Real active-pipeline count for the footer widget — deliberately using
  // the raw listPipelines() call rather than the usePipelines() hook, which
  // does an N+1 getPipeline() detail fetch per row; not worth that cost for
  // a counter in a component mounted on every single page.
  const [pipelineCount, setPipelineCount] = useState<number | null>(null);
  useEffect(() => {
    let mounted = true;
    apiClient
      .listPipelines()
      .then((list) => { if (mounted) setPipelineCount(list.length); })
      .catch(() => { if (mounted) setPipelineCount(null); });
    return () => { mounted = false; };
  }, []);

  // Real one-shot GET /health for the footer's status dot -- a single probe,
  // not the full rolling-window logic use-system-health uses for the System
  // Health page (too heavy for a component mounted on every route). A failed
  // fetch is treated as "down" rather than left blank.
  const [platformStatus, setPlatformStatus] = useState<"healthy" | "down" | null>(null);
  useEffect(() => {
    let mounted = true;
    apiClient
      .getSystemHealth()
      .then((res) => { if (mounted) setPlatformStatus(res.status === "healthy" ? "healthy" : "down"); })
      .catch(() => { if (mounted) setPlatformStatus("down"); });
    return () => { mounted = false; };
  }, []);

  return (
    // 26-Jul-2026 (site_design reference rollout): dark gradient chrome,
    // matching EnterprisePlatformLayout.tsx exactly -- stone-950->stone-900
    // gradient, orange-600 filled active state (not the prior border-left
    // accent), stone-400 section labels/icons. The workspace canvas (main
    // content area, cards) stays warm-light -- only this chrome is dark.
    <aside
      aria-label="Primary navigation"
      className={cn(
        "sticky top-0 flex h-screen flex-col overflow-y-auto border-r border-stone-800 shadow-xl",
        "bg-gradient-to-b from-stone-950 via-stone-900 to-stone-950 text-stone-100 [scrollbar-width:none] transition-[width] motion-safe:duration-250",
        collapsed ? "w-[76px]" : "w-[212px]",
        mobileOpen ? "fixed z-40" : "",
      )}
    >
      {/* ── Brand ─────────────────────────────────────────────── */}
      <div className="flex shrink-0 items-center gap-1 border-b border-stone-800/80 px-3 py-3">
        <Link href="/dashboard" onClick={onNavigate} className="min-w-0 flex-1 overflow-hidden">
          {collapsed ? (
            <AutoRagLogoMark size={32} />
          ) : (
            <>
              {/* 26-Jul-2026: swapped the static /AutoRAG_logo.png (baked-in dark
                  navy "Auto" text) for the theme-aware AutoRagLogo component --
                  the PNG went invisible once the sidebar reverted to dark chrome. */}
              <AutoRagLogo size="sm" variant="dark" showTagline={false} />
              <span className="-mt-1 flex flex-col leading-tight">
                <span className="text-[11px] font-medium text-stone-400">Enterprise AI Platform</span>
                <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-stone-500">Version 3.0</span>
              </span>
            </>
          )}
        </Link>
        {onToggleCollapse && (
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="hidden shrink-0 rounded-lg border border-stone-800 bg-stone-900 p-1.5 text-stone-400 transition-colors motion-safe:duration-150 hover:bg-stone-800 hover:text-white md:flex"
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
        )}
      </div>

      {/* ── Nav sections ──────────────────────────────────────── */}
      <nav className="flex flex-1 flex-col gap-1 px-3.5 py-3">
        {NAV_SECTIONS.map((section, i) => {
          const isPinnedBottom = section.label === "System";

          return (
            <div
              key={section.label}
              className={cn(
                "flex flex-col",
                i > 0 && !isPinnedBottom && "mt-2 border-t border-stone-800 pt-2",
                isPinnedBottom && "mt-auto border-t border-stone-800 pt-3",
              )}
            >
              {/* Section label -- plain caps + tracking, no boxed pill
                  (25-Jul-2026 tightened grouping pass); hidden entirely
                  when collapsed, leaving just the divider above. */}
              {!collapsed && (
                <span className="mb-1.5 inline-block w-fit px-1 text-[10.5px] font-bold uppercase tracking-[0.14em] text-stone-400">
                  {section.label}
                </span>
              )}

              <ul className="flex flex-col gap-0.5">
                {section.items.map((item) => {
                  const active = isActive(pathname, item);
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={onNavigate}
                        aria-current={active ? "page" : undefined}
                        title={collapsed ? item.label : undefined}
                        className={cn(
                          "group flex h-11 items-center gap-2.5 rounded-xl px-2.5 text-sm transition-all motion-safe:duration-150",
                          collapsed && "justify-center px-0",
                          active
                            ? "bg-orange-600 font-bold text-white shadow-lg shadow-orange-600/30"
                            : "font-[450] text-stone-400 hover:bg-stone-900/90 hover:text-stone-100",
                        )}
                      >
                        <Icon
                          className={cn("h-5 w-5 shrink-0", active ? "text-white" : "text-stone-400")}
                          aria-hidden="true"
                        />
                        {!collapsed && <span className="truncate">{item.label}</span>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>

      {/* ── Footer widget — "Platform Status" card, real data only ──
          Replaced the old debug-log-style two rows (per review: "it looks
          like debug information") with a single status card: a real health
          dot from GET /health, then Version/Agents/Pipelines as a compact
          key-value grid. Hidden entirely when collapsed -- no room for the
          3-col grid, and a half-rendered version of it would be worse than
          nothing. */}
      {!collapsed && (
      <div className="shrink-0 border-t border-stone-800 bg-stone-900/50 px-3 py-3">
        <div className="rounded-xl border border-stone-800 bg-stone-900 p-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-stone-400">Platform Status</span>
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold">
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  platformStatus === "healthy" ? "bg-emerald-500" : platformStatus === "down" ? "bg-rose-500 animate-pulse" : "bg-stone-500",
                )}
                aria-hidden="true"
              />
              <span className={platformStatus === "healthy" ? "text-emerald-400" : platformStatus === "down" ? "text-rose-400" : "text-stone-400"}>
                {platformStatus === "healthy" ? "Healthy" : platformStatus === "down" ? "Down" : "—"}
              </span>
            </span>
          </div>
        </div>
        <div className="mt-2 grid grid-cols-3 gap-1 rounded-lg border border-stone-800 bg-stone-900/80 p-1.5 text-center text-[10px]">
          <div>
            <span className="block text-stone-500">Version</span>
            <span className="font-mono text-[13px] font-bold text-stone-200">v3.0</span>
          </div>
          <div>
            <span className="block text-stone-500">Agents</span>
            <span className="font-mono text-[13px] font-bold text-orange-400">9</span>
          </div>
          <div>
            <span className="block text-stone-500">Pipelines</span>
            <span className="font-mono text-[13px] font-bold tabular-nums text-emerald-400">{pipelineCount === null ? "—" : pipelineCount}</span>
          </div>
        </div>
      </div>
      )}
    </aside>
  );
}
