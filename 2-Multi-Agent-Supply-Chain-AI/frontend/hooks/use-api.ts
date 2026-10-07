"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ForecastHorizon, InventoryQuery, ShipmentStatus, SupplierSort } from "@/types";
import { getApi, type SupplyApi } from "@/lib/api";
import { ACTIVITY_POLL_MS, NOTIFICATION_POLL_MS } from "@/lib/constants";

/** Wraps an API method in a query function so every call goes through the selected data source. */
function call<T>(fn: (api: SupplyApi) => Promise<T>): () => Promise<T> {
  return async () => fn(await getApi());
}

export const queryKeys = {
  me: ["me"] as const,
  status: ["system-status"] as const,
  overview: ["overview"] as const,
  inventorySummary: ["inventory", "summary"] as const,
  inventory: (q: InventoryQuery) => ["inventory", "list", q] as const,
  forecast: (sku: string, h: ForecastHorizon) => ["demand", sku, h] as const,
  skus: ["demand", "skus"] as const,
  suppliers: (sort: SupplierSort, sku?: string) => ["suppliers", sort, sku ?? "all"] as const,
  supplierRec: (sku: string) => ["suppliers", "recommendation", sku] as const,
  shipments: (status: string, search: string) => ["shipments", status, search] as const,
  logistics: ["logistics", "summary"] as const,
  agents: ["agents"] as const,
  documents: ["documents"] as const,
  documentStats: ["documents", "stats"] as const,
  activity: ["activity"] as const,
  notifications: ["notifications"] as const,
  analytics: ["analytics"] as const,
  approvals: ["approvals", "pending"] as const,
};

export const useCurrentUser = () => useQuery({ queryKey: queryKeys.me, queryFn: call((a) => a.getCurrentUser()), staleTime: 5 * 60_000 });
export const useSystemStatus = () => useQuery({ queryKey: queryKeys.status, queryFn: call((a) => a.getSystemStatus()), refetchInterval: 60_000 });
export const useOverview = () => useQuery({ queryKey: queryKeys.overview, queryFn: call((a) => a.getOverview()) });
export const useInventorySummary = () => useQuery({ queryKey: queryKeys.inventorySummary, queryFn: call((a) => a.getInventorySummary()) });
export const useInventory = (q: InventoryQuery) =>
  useQuery({ queryKey: queryKeys.inventory(q), queryFn: call((a) => a.getInventory(q)), placeholderData: keepPreviousData });
export const useDemandForecast = (sku: string, horizon: ForecastHorizon) =>
  useQuery({ queryKey: queryKeys.forecast(sku, horizon), queryFn: call((a) => a.getDemandForecast(sku, horizon)), placeholderData: keepPreviousData });
export const useForecastableSkus = () => useQuery({ queryKey: queryKeys.skus, queryFn: call((a) => a.getForecastableSkus()), staleTime: 10 * 60_000 });
export const useSuppliers = (sort: SupplierSort, sku?: string) =>
  useQuery({ queryKey: queryKeys.suppliers(sort, sku), queryFn: call((a) => a.getSuppliers({ sort, sku })), placeholderData: keepPreviousData });
export const useSupplierRecommendation = (sku: string) =>
  useQuery({ queryKey: queryKeys.supplierRec(sku), queryFn: call((a) => a.getSupplierRecommendation(sku)) });
export const useShipments = (status: ShipmentStatus | "all", search: string) =>
  useQuery({ queryKey: queryKeys.shipments(status, search), queryFn: call((a) => a.getShipments({ status, search })), placeholderData: keepPreviousData });
export const useLogisticsSummary = () => useQuery({ queryKey: queryKeys.logistics, queryFn: call((a) => a.getLogisticsSummary()) });
export const useAgents = () => useQuery({ queryKey: queryKeys.agents, queryFn: call((a) => a.getAgents()), refetchInterval: 30_000 });
export const useDocuments = () => useQuery({ queryKey: queryKeys.documents, queryFn: call((a) => a.getDocuments()) });
export const useDocumentStats = () => useQuery({ queryKey: queryKeys.documentStats, queryFn: call((a) => a.getDocumentStats()) });
export const useActivity = () =>
  useQuery({ queryKey: queryKeys.activity, queryFn: call((a) => a.getActivity()), refetchInterval: ACTIVITY_POLL_MS });
export const useNotifications = () =>
  useQuery({ queryKey: queryKeys.notifications, queryFn: call((a) => a.getNotifications()), refetchInterval: NOTIFICATION_POLL_MS });
export const useAnalytics = () => useQuery({ queryKey: queryKeys.analytics, queryFn: call((a) => a.getAnalytics()) });
export const usePendingApprovals = () =>
  useQuery({ queryKey: queryKeys.approvals, queryFn: call((a) => a.getPendingApprovals()), refetchInterval: 30_000 });

export function useMarkNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (ids: string[] | "all") => (await getApi()).markNotificationsRead(ids),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.notifications }),
  });
}

export function useDecideApproval() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { id: string; decision: "approved" | "rejected"; comment?: string }) =>
      (await getApi()).decideApproval(v.id, v.decision, v.comment),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.approvals });
      qc.invalidateQueries({ queryKey: queryKeys.activity });
    },
  });
}

export function useDocumentMutations() {
  const qc = useQueryClient();
  const refresh = () => {
    qc.invalidateQueries({ queryKey: queryKeys.documents });
    qc.invalidateQueries({ queryKey: queryKeys.documentStats });
  };
  return {
    upload: useMutation({ mutationFn: async (files: File[]) => (await getApi()).uploadDocuments(files), onSuccess: refresh }),
    remove: useMutation({ mutationFn: async (id: string) => (await getApi()).deleteDocument(id), onSuccess: refresh }),
    reindex: useMutation({ mutationFn: async (id: string) => (await getApi()).reindexDocument(id), onSuccess: refresh }),
  };
}
