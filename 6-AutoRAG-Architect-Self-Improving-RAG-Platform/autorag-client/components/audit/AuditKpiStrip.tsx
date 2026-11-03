"use client";

import { useEffect, useState } from "react";
import { ScrollText, ShieldAlert, Rocket, RotateCcw, Clock } from "lucide-react";

import { StatCard } from "@/components/ui/stat-card";
import { apiClient } from "@/services/api-client";
import { relativeTime } from "@/lib/format";

interface AuditKpiState {
  total: number | null;
  security: number | null;
  deployments: number | null;
  rollbacks: number | null;
  mostRecent: string | null;
}

/**
 * Real audit KPI strip (25-Jul-2026, capability-first polish pass). Every
 * number is a real `count` from GET /api/v1/audit-log -- five cheap
 * `limit: 1` calls (one per category filter) rather than fetching all rows;
 * "Today" was dropped from scope because the real endpoint has no date
 * filter (see FilterBar.tsx), and computing it honestly would mean fetching
 * every row -- "Most Recent" (a real timestamp) is shown instead.
 */
export function AuditKpiStrip() {
  const [state, setState] = useState<AuditKpiState>({
    total: null,
    security: null,
    deployments: null,
    rollbacks: null,
    mostRecent: null,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);

    Promise.all([
      apiClient.listAuditLog({ limit: 1 }),
      apiClient.listAuditLog({ event_type: "guardrail_blocked", limit: 1 }),
      apiClient.listAuditLog({ event_type: "pii_redacted", limit: 1 }),
      apiClient.listAuditLog({ event_type: "deploy_completed", limit: 1 }),
      apiClient.listAuditLog({ event_type: "rollback_triggered", limit: 1 }),
    ])
      .then(([all, guardrail, pii, deployments, rollbacks]) => {
        if (!mounted) return;
        setState({
          total: all.count,
          security: guardrail.count + pii.count,
          deployments: deployments.count,
          rollbacks: rollbacks.count,
          mostRecent: all.items[0]?.created_at ?? null,
        });
      })
      .catch(() => {
        if (mounted) setState({ total: null, security: null, deployments: null, rollbacks: null, mostRecent: null });
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const v = (val: number | null) => (loading || val === null ? "—" : val);

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      <StatCard label="Total Events"  value={v(state.total)}       icon={ScrollText}  iconColor="#0EA5E9" />
      <StatCard label="Security"      value={v(state.security)}    icon={ShieldAlert} iconColor="#F43F5E" />
      <StatCard label="Deployments"   value={v(state.deployments)} icon={Rocket}      iconColor="#10B981" />
      <StatCard label="Rollbacks"     value={v(state.rollbacks)}   icon={RotateCcw}   iconColor="#F59E0B" />
      <StatCard
        label="Most Recent"
        value={loading || !state.mostRecent ? "—" : relativeTime(state.mostRecent)}
        icon={Clock}
        iconColor="#EA580C"
      />
    </div>
  );
}
