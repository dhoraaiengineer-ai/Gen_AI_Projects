"use client";

import { CheckCircle2, XCircle, AlertCircle, Server, Database, Cpu, BarChart2 } from "lucide-react";

const CARD: React.CSSProperties = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 20,
};

const STATUS = {
  healthy: { icon: CheckCircle2, color: "#10B981", label: "Healthy" },
  degraded: { icon: AlertCircle,  color: "#F59E0B", label: "Degraded" },
  down:     { icon: XCircle,      color: "#EF4444", label: "Down" },
} as const;

type ServiceStatus = keyof typeof STATUS;

interface ServiceInfo {
  name: string;
  category: string;
  status: ServiceStatus;
  url: string;
  metrics: { label: string; value: string; color?: string }[];
  notes?: string;
}

const SERVICES: ServiceInfo[] = [
  {
    name: "FastAPI (ECS Fargate)",
    category: "API",
    status: "healthy",
    url: "http://localhost:8000/health",
    metrics: [
      { label: "Tasks Running",   value: "2/2",       color: "#10B981" },
      { label: "CPU",             value: "18%",        color: "#60A5FA" },
      { label: "Memory",          value: "512MB",      color: "#60A5FA" },
      { label: "p95 Latency",     value: "1.84s",      color: "#F59E0B" },
      { label: "Error Rate",      value: "0.02%",      color: "#10B981" },
    ],
  },
  {
    name: "LangGraph Workers (ECS)",
    category: "Workers",
    status: "healthy",
    url: "—",
    metrics: [
      { label: "Tasks Running",   value: "4/4",       color: "#10B981" },
      { label: "CPU",             value: "34%",        color: "#60A5FA" },
      { label: "Memory",          value: "1.2GB",      color: "#60A5FA" },
      { label: "Queue Depth",     value: "3",          color: "#F59E0B" },
      { label: "Active Graphs",   value: "2",          color: "#A78BFA" },
    ],
  },
  {
    name: "Redis (Cache + Queue)",
    category: "Cache",
    status: "healthy",
    url: "—",
    metrics: [
      { label: "Memory Used",     value: "128MB",      color: "#60A5FA" },
      { label: "Hit Rate",        value: "87.4%",      color: "#10B981" },
      { label: "Queue Depth",     value: "3",          color: "#F59E0B" },
      { label: "Connected Clients",value: "12",         color: "#60A5FA" },
      { label: "Evictions",       value: "0",          color: "#10B981" },
    ],
  },
  {
    name: "Supabase PostgreSQL",
    category: "Database",
    status: "healthy",
    url: "https://app.supabase.com",
    metrics: [
      { label: "DB Size",         value: "2.4GB",      color: "#60A5FA" },
      { label: "Active Conns",    value: "18/100",     color: "#10B981" },
      { label: "Replication Lag", value: "0ms",        color: "#10B981" },
      { label: "Query p95",       value: "14ms",       color: "#10B981" },
      { label: "Tables",          value: "24",         color: "#60A5FA" },
    ],
  },
  {
    name: "Supabase Vector (pgvector)",
    category: "Vector DB",
    status: "healthy",
    url: "https://app.supabase.com",
    metrics: [
      { label: "Vector Tables",   value: "6",          color: "#60A5FA" },
      { label: "Dimensions",      value: "768",        color: "#A78BFA" },
      { label: "Index Type",      value: "HNSW",       color: "#60A5FA" },
      { label: "Total Vectors",   value: "284K",       color: "#10B981" },
      { label: "Storage",         value: "840MB",      color: "#60A5FA" },
    ],
  },
  {
    name: "Supabase Storage",
    category: "Storage",
    status: "healthy",
    url: "https://app.supabase.com",
    metrics: [
      { label: "Used",            value: "4.2GB",      color: "#60A5FA" },
      { label: "Documents",       value: "1,240",      color: "#60A5FA" },
      { label: "Buckets",         value: "3",          color: "#60A5FA" },
      { label: "Pipeline Snaps",  value: "24",         color: "#A78BFA" },
    ],
  },
  {
    name: "Prometheus",
    category: "Monitoring",
    status: "healthy",
    url: "http://localhost:9090",
    metrics: [
      { label: "Scrape Targets",  value: "8/8",       color: "#10B981" },
      { label: "Metrics Count",   value: "1,840",      color: "#60A5FA" },
      { label: "Retention",       value: "15 days",    color: "#60A5FA" },
      { label: "Scrape Interval", value: "15s",        color: "#60A5FA" },
    ],
  },
  {
    name: "Grafana",
    category: "Dashboards",
    status: "healthy",
    url: "http://localhost:3001",
    metrics: [
      { label: "Dashboards",      value: "4",          color: "#10B981" },
      { label: "Alert Rules",     value: "6",          color: "#F59E0B" },
      { label: "Active Alerts",   value: "0",          color: "#10B981" },
      { label: "Data Sources",    value: "1",          color: "#60A5FA" },
    ],
  },
  {
    name: "MLflow",
    category: "Experiment Tracking",
    status: "healthy",
    url: "http://localhost:5000",
    metrics: [
      { label: "Experiments",     value: "8",          color: "#60A5FA" },
      { label: "Total Runs",      value: "284",        color: "#60A5FA" },
      { label: "Active Runs",     value: "0",          color: "#10B981" },
      { label: "Models Registered",value: "3",         color: "#A78BFA" },
    ],
  },
];

const CATEGORY_ICON: Record<string, typeof Server> = {
  "API": Server, "Workers": Cpu, "Cache": BarChart2, "Database": Database,
  "Vector DB": Database, "Storage": Database, "Monitoring": BarChart2, "Dashboards": BarChart2,
  "Experiment Tracking": BarChart2,
};

export function InfrastructurePageClient() {
  const healthyCount  = SERVICES.filter(s => s.status === "healthy").length;
  const degradedCount = SERVICES.filter(s => s.status === "degraded").length;
  const downCount     = SERVICES.filter(s => s.status === "down").length;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <header>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-1)", marginBottom: 4 }}>Infrastructure Dashboard</h1>
        <p style={{ fontSize: 13, color: "var(--text-3)" }}>
          ECS Fargate, Redis, Supabase, Prometheus, Grafana, and MLflow service health
        </p>
      </header>

      {/* Overall health summary */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
        {[
          { label: "Services Healthy",  value: `${healthyCount}/${SERVICES.length}`,  color: "#10B981" },
          { label: "Degraded",          value: String(degradedCount),                  color: "#F59E0B" },
          { label: "Down",              value: String(downCount),                      color: "#EF4444" },
          { label: "ECS Tasks",         value: "6/6",                                  color: "#10B981" },
          { label: "Active Alerts",     value: "0",                                    color: "#10B981" },
        ].map(({ label, value, color }) => (
          <div key={label} style={{ ...CARD, padding: 14 }}>
            <div style={{ fontSize: 10, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3 }}>{label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Alert rule reference */}
      <div style={{ ...CARD, padding: 14 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
          Auto-Rollback Triggers (observability/alerts/)
        </div>
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap", fontSize: 11 }}>
          {[
            { label: "error_rate",     threshold: "> 1%",    color: "#EF4444" },
            { label: "p95 latency",    threshold: "> 3s",    color: "#F59E0B" },
            { label: "Unified Score",  threshold: "drop > 0.10", color: "#F59E0B" },
          ].map(({ label, threshold, color }) => (
            <span key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <AlertCircle style={{ width: 11, height: 11, color }} />
              <span style={{ color: "var(--text-3)" }}>{label}</span>
              <span style={{ color, fontWeight: 700 }}>{threshold}</span>
              <span style={{ color: "var(--text-3)" }}>→ rollback</span>
            </span>
          ))}
          <span style={{ color: "var(--text-3)", marginLeft: "auto", fontSize: 10 }}>10-minute canary window</span>
        </div>
      </div>

      {/* Service cards grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 14 }}>
        {SERVICES.map(svc => {
          const stat = STATUS[svc.status];
          const StatusIcon = stat.icon;
          const CategoryIcon = CATEGORY_ICON[svc.category] ?? Server;

          return (
            <div key={svc.name} style={{ ...CARD, border: `1px solid ${stat.color}18` }}>
              {/* Header */}
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                <div style={{
                  width: 34, height: 34, borderRadius: 9, flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: `${stat.color}12`, border: `1px solid ${stat.color}30`,
                }}>
                  <CategoryIcon style={{ width: 15, height: 15, color: stat.color }} />
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-1)" }}>{svc.name}</div>
                  <div style={{ fontSize: 10, color: "var(--text-3)" }}>{svc.category}</div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
                  <StatusIcon style={{ width: 13, height: 13, color: stat.color }} />
                  <span style={{ fontSize: 11, fontWeight: 700, color: stat.color }}>{stat.label}</span>
                </div>
              </div>

              {/* Metrics */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
                {svc.metrics.map(m => (
                  <div key={m.label} style={{ padding: "6px 8px", borderRadius: 6, background: "rgba(99,120,255,0.04)", border: "1px solid rgba(99,120,255,0.08)" }}>
                    <div style={{ fontSize: 9, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 2 }}>{m.label}</div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: m.color ?? "var(--text-1)" }}>{m.value}</div>
                  </div>
                ))}
              </div>

              {svc.url !== "—" && (
                <div style={{ marginTop: 10, fontSize: 10, color: "var(--text-3)", fontFamily: "monospace" }}>
                  {svc.url}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
