/**
 * Hook — fetch + poll the pipeline list, enriched with each pipeline's latest run.
 *
 * Why enrichment: GET /pipelines returns the pipeline row (incl. `name`) but not
 * `latest_run` -- that requires fanning out to GET /pipelines/{id} per row.
 *
 * Shared singleton store (26-Jul-2026 fix -- P0 UAT finding): every one of the 14
 * real call sites (sidebar, DashboardView, RunEvaluationPanel, DeploymentCenter,
 * ObserverDashboardClient, ExperimentsPageClient, etc.) invokes usePipelines() with
 * no arguments. Previously each call site owned its own useEffect fetch-on-mount
 * AND its own setInterval, so N mounted components meant N independent, uncoordinated
 * pollers hammering GET /pipelines + one GET /pipelines/{id} per pipeline. Confirmed
 * via Playwright network capture: this produced enough overlapping/aborted duplicate
 * requests to intermittently kill an unrelated real request (POST /pipelines during
 * pipeline creation) with net::ERR_FAILED under the local single-worker dev backend.
 * Fix: one shared module-level store per distinct projectId filter, reference-counted
 * by mounted subscribers -- one fetch, one interval, no matter how many components
 * are mounted; the interval stops entirely once the last subscriber unmounts. Public
 * hook API is unchanged, so no call site needed to change.
 *
 * Polling (AC #6): 5s while any run is `running`, otherwise 30s. Native fetch via
 * apiClient + setInterval -- no SWR/React Query dependency (CLAUDE.md §6).
 */

"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient } from "@/services/api-client";
import type { PipelineWithRun } from "@/types";

const FAST_POLL_MS = 5_000;
const SLOW_POLL_MS = 30_000;
const ALL_KEY = "__all__";

interface UsePipelinesOptions {
  projectId?: string;
}

interface UsePipelinesResult {
  pipelines: PipelineWithRun[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

interface StoreState {
  pipelines: PipelineWithRun[];
  isLoading: boolean;
  error: Error | null;
}

type Listener = (state: StoreState) => void;

interface Store {
  state: StoreState;
  listeners: Set<Listener>;
  intervalId: ReturnType<typeof setInterval> | null;
}

// One store per distinct projectId filter -- every real caller today uses the
// unfiltered ALL_KEY, but a projectId-scoped caller gets its own isolated cache
// rather than silently sharing (or corrupting) the unfiltered one.
const stores = new Map<string, Store>();

function getStore(key: string): Store {
  let store = stores.get(key);
  if (!store) {
    store = { state: { pipelines: [], isLoading: true, error: null }, listeners: new Set(), intervalId: null };
    stores.set(key, store);
  }
  return store;
}

function notify(key: string): void {
  const store = stores.get(key);
  if (!store) return;
  for (const listener of store.listeners) listener(store.state);
}

function anyRunning(pipelines: PipelineWithRun[]): boolean {
  return pipelines.some((p) => p.latest_run?.status === "running");
}

function rescheduleInterval(key: string, projectId: string | undefined): void {
  const store = getStore(key);
  if (store.intervalId) clearInterval(store.intervalId);
  if (store.listeners.size === 0) {
    store.intervalId = null;
    return;
  }
  const intervalMs = anyRunning(store.state.pipelines) ? FAST_POLL_MS : SLOW_POLL_MS;
  store.intervalId = setInterval(() => void load(key, projectId), intervalMs);
}

async function load(key: string, projectId: string | undefined): Promise<void> {
  const store = getStore(key);
  try {
    // 26-Jul-2026: GET /pipelines now returns latest_run inline (one batched
    // query server-side) -- previously this fanned out a GET /pipelines/{id}
    // per row via Promise.all, which at ~20 pipelines became a real burst of
    // concurrent requests large enough to intermittently overwhelm the local
    // backend (confirmed live, independent of frontend dev/production build).
    const list = await apiClient.listPipelines(projectId);
    store.state = { pipelines: list, isLoading: false, error: null };
  } catch (err) {
    store.state = {
      ...store.state,
      isLoading: false,
      error: err instanceof Error ? err : new Error("Failed to load pipelines"),
    };
  }
  notify(key);
  // Only a live subscriber's interval should survive; a store that lost its
  // last listener while this load() was in flight shouldn't resurrect one.
  if (getStore(key).listeners.size > 0) rescheduleInterval(key, projectId);
}

export function usePipelines(options: UsePipelinesOptions = {}): UsePipelinesResult {
  const { projectId } = options;
  const key = projectId ?? ALL_KEY;
  const [state, setState] = useState<StoreState>(() => getStore(key).state);

  useEffect(() => {
    const store = getStore(key);
    const listener: Listener = (s) => setState(s);
    store.listeners.add(listener);
    setState(store.state);

    if (store.listeners.size === 1) {
      // First subscriber for this key: kick off the one shared fetch. load()
      // reschedules the interval itself once the response lands.
      void load(key, projectId);
    } else if (!store.intervalId) {
      rescheduleInterval(key, projectId);
    }

    return () => {
      store.listeners.delete(listener);
      if (store.listeners.size === 0 && store.intervalId) {
        clearInterval(store.intervalId);
        store.intervalId = null;
      }
    };
  }, [key, projectId]);

  const refetch = useCallback(() => {
    void load(key, projectId);
  }, [key, projectId]);

  return { pipelines: state.pipelines, isLoading: state.isLoading, error: state.error, refetch };
}
