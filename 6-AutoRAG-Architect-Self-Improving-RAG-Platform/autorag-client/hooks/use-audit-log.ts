/**
 * Hook — fetch a page of audit_log rows for the current filter/pagination state.
 *
 * Mirrors hooks/use-deployment.ts: native fetch via apiClient, no SWR/React Query
 * dependency (CLAUDE.md §6 "avoid unnecessary dependencies"). No polling — audit
 * logs aren't a live dashboard; `refetch` backs a manual Refresh affordance.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiClient } from "@/services/api-client";
import type { AuditEvent, AuditEventType } from "@/types";

const PAGE_SIZE = 25;

interface UseAuditLogParams {
  eventType?: AuditEventType;
  runId?: string;
  page: number;
}

interface UseAuditLogResult {
  items: AuditEvent[];
  count: number;
  pageSize: number;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useAuditLog({ eventType, runId, page }: UseAuditLogParams): UseAuditLogResult {
  const [items, setItems] = useState<AuditEvent[]>([]);
  const [count, setCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await apiClient.listAuditLog({
        event_type: eventType,
        run_id: runId,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      });
      if (!mountedRef.current) return;
      setItems(res.items);
      setCount(res.count);
      setError(null);
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err : new Error("Failed to load audit log"));
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [eventType, runId, page]);

  useEffect(() => {
    mountedRef.current = true;
    void load();
    return () => {
      mountedRef.current = false;
    };
  }, [load]);

  const refetch = useCallback(() => {
    void load();
  }, [load]);

  return { items, count, pageSize: PAGE_SIZE, isLoading, error, refetch };
}
