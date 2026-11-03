"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";

import { NAV_ITEMS } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { apiClient } from "@/services/api-client";
import { Input } from "@/components/ui/input";
import type { Pipeline } from "@/types";

const MAX_RESULTS_PER_GROUP = 5;

/**
 * Global quick-search (25-Jul-2026, Magnific-reference sidebar/topbar pass).
 * No cross-entity search endpoint exists in the API, so this only surfaces
 * real data already available client-side: the governance-approved static
 * NAV_ITEMS list, and real pipelines fetched once via the same
 * apiClient.listPipelines() call sidebar.tsx already makes for its footer
 * counter (no new fetch pattern). Filtering is in-memory substring match --
 * no per-keystroke API calls.
 */
export function QuickSearch() {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [pipelines, setPipelines] = useState<Pipeline[] | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  function ensurePipelinesLoaded() {
    if (pipelines !== null) return;
    apiClient
      .listPipelines()
      .then((list) => setPipelines(list))
      .catch(() => setPipelines([]));
  }

  const navResults = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return NAV_ITEMS.filter((item) => item.label.toLowerCase().includes(q)).slice(0, MAX_RESULTS_PER_GROUP);
  }, [query]);

  const pipelineResults = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || !pipelines) return [];
    return pipelines
      .filter((p) => p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q))
      .slice(0, MAX_RESULTS_PER_GROUP);
  }, [query, pipelines]);

  const hasQuery = query.trim().length > 0;
  const hasResults = navResults.length > 0 || pipelineResults.length > 0;

  return (
    <div ref={containerRef} className="relative hidden min-w-0 flex-1 max-w-md md:block">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
      <Input
        type="search"
        value={query}
        onFocus={() => {
          setOpen(true);
          ensurePipelinesLoaded();
        }}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        placeholder="Search pages and pipelines…"
        aria-label="Search pages and pipelines"
        className="h-9 rounded-full bg-card pl-9 pr-3"
      />

      {open && hasQuery && (
        <div className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 max-h-[360px] overflow-y-auto rounded-xl border border-border bg-card p-2 shadow-xl">
          {!hasResults && (
            <p className="px-3 py-2 text-xs text-text-3">No matches for &ldquo;{query}&rdquo;.</p>
          )}

          {navResults.length > 0 && (
            <div className="mb-1">
              <p className="px-3 pb-1 pt-1 text-[10px] font-bold uppercase tracking-[0.12em] text-text-3">Pages</p>
              {navResults.map((item) => {
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => {
                      setOpen(false);
                      setQuery("");
                    }}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-foreground transition-colors motion-safe:duration-150 hover:bg-sidebar-2",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <span className="truncate">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          )}

          {pipelineResults.length > 0 && (
            <div>
              <p className="px-3 pb-1 pt-1 text-[10px] font-bold uppercase tracking-[0.12em] text-text-3">Pipelines</p>
              {pipelineResults.map((p) => (
                <Link
                  key={p.id}
                  href={`/pipelines/${p.id}/history`}
                  onClick={() => {
                    setOpen(false);
                    setQuery("");
                  }}
                  className="flex items-center justify-between gap-2.5 rounded-lg px-3 py-2 text-sm text-foreground transition-colors motion-safe:duration-150 hover:bg-sidebar-2"
                >
                  <span className="truncate">{p.name || p.id.slice(0, 8)}</span>
                  <span className="shrink-0 text-[10px] font-medium uppercase text-text-3">{p.status}</span>
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
