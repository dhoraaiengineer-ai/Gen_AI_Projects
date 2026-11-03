"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Menu, LogOut, ChevronDown, Play } from "lucide-react";
import { useState } from "react";

import { useHealth } from "@/hooks/use-health";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { QuickSearch } from "@/components/layout/QuickSearch";

interface DashboardTopbarProps {
  onMenuClick?: () => void;
}

/**
 * Global application nav (20-Jul-2026 rebuild #2, per direct product
 * review: "the navbar and page header feel like the same component";
 * 25-Jul-2026: added the global QuickSearch bar per a new explicit request).
 * Fixed 64px, page-agnostic -- brand mark, quick search, connectivity,
 * primary CTA, theme toggle, user menu. No breadcrumb, no page title, no
 * platform metadata (environment / version / agent count / pipeline count)
 * -- those still live in PageHeaderBar and the Dashboard hero respectively,
 * so this bar's *shape* stays constant across routes even though it now
 * carries search. AppShell renders a 1px divider directly below it.
 */
export function DashboardTopbar({ onMenuClick }: DashboardTopbarProps) {
  const { healthy } = useHealth();
  const router = useRouter();
  const [dropOpen, setDropOpen] = useState(false);

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/");
  }

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between gap-4 bg-sidebar-2 shadow-[0_2px_8px_rgba(15,23,42,0.08)] px-6">
      <div className="flex min-w-0 shrink-0 items-center gap-2.5">
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Open navigation"
          className="shrink-0 rounded-md p-1.5 text-text-2 hover:bg-accent/10 md:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <span className="font-head text-sm font-bold tracking-tight text-foreground">AutoRAG</span>
      </div>

      <QuickSearch />

      <div className="flex shrink-0 items-center gap-3">
        {/* Backend health */}
        <div
          className={cn(
            "flex items-center gap-1.5 rounded-lg border px-2.5 py-1",
            healthy
              ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-600"
              : "border-red-500/20 bg-red-500/10 text-red-600",
          )}
          title={healthy ? "Backend connected" : "Backend unreachable — check autorag-server"}
        >
          <span
            className={cn("h-1.5 w-1.5 rounded-full", healthy ? "bg-emerald-500" : "bg-red-500")}
            aria-hidden="true"
          />
          <span className="text-xs font-semibold">{healthy ? "Online" : "Offline"}</span>
        </div>

        <ThemeToggle />

        {/* Run demo CTA — always one click from starting the journey */}
        <Link
          href="/configurator"
          className="flex h-[42px] items-center gap-1.5 rounded-xl bg-orange-500 px-4 text-xs font-bold text-foreground shadow-[0_1px_3px_rgba(15,23,42,0.15)] transition-colors motion-safe:duration-150 hover:bg-orange-600"
        >
          <Play className="h-3.5 w-3.5" aria-hidden="true" />
          New Pipeline
        </Link>

        {/* User menu */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setDropOpen((o) => !o)}
            aria-expanded={dropOpen}
            className={cn(
              "flex items-center gap-2 rounded-lg border border-border py-1 pl-1 pr-2 transition-colors motion-safe:duration-150",
              dropOpen ? "bg-accent/15" : "bg-accent/5 hover:bg-accent/15",
            )}
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-light_bronze-400 to-light_bronze-300 text-[10px] font-bold text-foreground">
              DA
            </span>
            <span className="hidden text-left sm:block">
              <span className="block text-xs font-semibold leading-tight text-foreground">Dhoraaiengineer</span>
              <span className="block text-[10px] leading-tight text-text-3">Platform Admin</span>
            </span>
            <ChevronDown
              className={cn("h-3.5 w-3.5 text-text-3 transition-transform motion-safe:duration-200", dropOpen && "rotate-180")}
              aria-hidden="true"
            />
          </button>

          {dropOpen && (
            <div className="absolute right-0 top-[calc(100%+6px)] z-50 min-w-[200px] rounded-xl border border-border bg-card p-2 shadow-xl">
              <div className="mb-1 border-b border-border px-3 pb-2.5 pt-2">
                <div className="text-[13px] font-semibold text-foreground">Dhoraaiengineer</div>
                <div className="text-[11px] text-text-3">Platform Admin</div>
              </div>
              <button
                type="button"
                onClick={() => void handleLogout()}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[13px] font-medium text-rose-600 transition-colors motion-safe:duration-150 hover:bg-rose-500/10"
              >
                <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
