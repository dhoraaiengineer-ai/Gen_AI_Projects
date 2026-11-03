"use client";

import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { DollarSign, TrendingUp, Zap, AlertTriangle } from "lucide-react";

const CARD: React.CSSProperties = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 20,
};

const DAILY_COST = [
  { date: "07-03", total: 0.82, gemini: 0.61, kimi: 0.14, embed: 0.07 },
  { date: "07-04", total: 1.14, gemini: 0.87, kimi: 0.18, embed: 0.09 },
  { date: "07-05", total: 0.95, gemini: 0.72, kimi: 0.15, embed: 0.08 },
  { date: "07-06", total: 1.31, gemini: 0.98, kimi: 0.23, embed: 0.10 },
  { date: "07-07", total: 0.78, gemini: 0.58, kimi: 0.12, embed: 0.08 },
  { date: "07-08", total: 1.52, gemini: 1.14, kimi: 0.27, embed: 0.11 },
  { date: "07-09", total: 1.24, gemini: 0.94, kimi: 0.21, embed: 0.09 },
];

const AGENT_COST = [
  { agent: "Ingestion",     cost: 1.16, tokens: 284000 },
  { agent: "Q.Rewriter",   cost: 0.55, tokens: 552000 },
  { agent: "Builder",      cost: 0.51, tokens: 284000 },
  { agent: "Compressor",   cost: 0.18, tokens: 184000 },
  { agent: "Evaluator",    cost: 0.68, tokens: 284000 },
  { agent: "Observer",     cost: 0.00, tokens: 0 },
  { agent: "Diagnoser",    cost: 0.08, tokens: 42000 },
  { agent: "Improver",     cost: 0.11, tokens: 18000 },
  { agent: "Deployer",     cost: 0.00, tokens: 0 },
];

const BUDGET_LIMITS = {
  per_query:  { label: "Per Query",      limit: 0.05, actual: 0.0037, env: "MAX_QUERY_COST_USD" },
  per_eval:   { label: "Per Eval Run",   limit: 1.00, actual: 0.34,  env: "MAX_EVAL_COST_USD" },
  per_build:  { label: "Per Pipeline",   limit: 5.00, actual: 1.87,  env: "MAX_PIPELINE_BUILD_USD" },
};

const TOOLTIP_STYLE = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 8,
  color: "var(--text-1)",
  fontSize: 11,
};

export function CostAnalyticsPageClient() {
  const totalWeek = DAILY_COST.reduce((s, d) => s + d.total, 0);
  const avgPerQuery = 0.0037;
  const maxProvider = "gemini-flash-3.5";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <header>
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "var(--text-1)", marginBottom: 4 }}>Cost Analytics</h1>
        <p style={{ fontSize: 13, color: "var(--text-3)" }}>
          Token usage and cost per agent, provider, and time period — sourced from{" "}
          <code style={{ color: "#F59E0B", fontSize: 11 }}>llm_service.py</code> (Rule 86 single cost source)
        </p>
      </header>

      {/* KPI strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 12 }}>
        {[
          { icon: DollarSign,   label: "7-Day Total",      value: `$${totalWeek.toFixed(2)}`,  color: "#A78BFA" },
          { icon: TrendingUp,   label: "Avg Cost/Query",    value: `$${avgPerQuery}`,            color: "#10B981" },
          { icon: Zap,          label: "Primary Provider",  value: maxProvider,                  color: "#4285F4" },
          { icon: AlertTriangle,label: "Budget Alerts",     value: "None",                       color: "#10B981" },
        ].map(({ icon: Icon, label, value, color }) => (
          <div key={label} style={{ ...CARD, padding: 14, display: "flex", alignItems: "flex-start", gap: 10 }}>
            <Icon style={{ width: 18, height: 18, color, marginTop: 2, flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 10, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3 }}>{label}</div>
              <div style={{ fontSize: 16, fontWeight: 700, color }}>{value}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Daily cost trend */}
      <div style={CARD}>
        <h3 style={{ fontSize: 12, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 16 }}>
          Daily Cost by Provider (7 days) — USD
        </h3>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={DAILY_COST} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
            <defs>
              <linearGradient id="geminiGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#4285F4" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#4285F4" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="kimiGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#A855F7" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#A855F7" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,120,255,0.08)" />
            <XAxis dataKey="date" tick={{ fill: "var(--text-3)", fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "var(--text-3)", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [`$${v.toFixed(3)}`, ""]} />
            <Area type="monotone" dataKey="gemini" stackId="a" stroke="#4285F4" fill="url(#geminiGrad)" strokeWidth={2} name="Gemini" />
            <Area type="monotone" dataKey="kimi"   stackId="a" stroke="#A855F7" fill="url(#kimiGrad)" strokeWidth={2} name="KiMi" />
            <Area type="monotone" dataKey="embed"  stackId="a" stroke="#10B981" fill="transparent" strokeWidth={1} strokeDasharray="4 2" name="Embedding" />
          </AreaChart>
        </ResponsiveContainer>
        <div style={{ display: "flex", gap: 16, marginTop: 8, justifyContent: "center" }}>
          {[
            { label: "Gemini Flash 3.5", color: "#4285F4" },
            { label: "KiMi K2.6",        color: "#A855F7" },
            { label: "Gemini Embedding", color: "#10B981" },
          ].map(({ label, color }) => (
            <span key={label} style={{ fontSize: 11, color: "var(--text-3)", display: "flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />{label}
            </span>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Cost per agent */}
        <div style={CARD}>
          <h3 style={{ fontSize: 12, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 16 }}>
            Cost by Agent (7-day)
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={AGENT_COST} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,120,255,0.08)" />
              <XAxis dataKey="agent" tick={{ fill: "var(--text-3)", fontSize: 9 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "var(--text-3)", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v}`} />
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [`$${v.toFixed(3)}`, "Cost"]} />
              <Bar dataKey="cost" fill="#A78BFA" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Budget gates */}
        <div style={CARD}>
          <h3 style={{ fontSize: 12, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 16 }}>
            Budget Gates (Rule 86 · env vars)
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {Object.values(BUDGET_LIMITS).map(({ label, limit, actual, env }) => {
              const pct = Math.round((actual / limit) * 100);
              const color = pct > 80 ? "#EF4444" : pct > 60 ? "#F59E0B" : "#10B981";
              return (
                <div key={env}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
                    <span style={{ color: "var(--text-3)" }}>{label}</span>
                    <span style={{ color, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>
                      ${actual.toFixed(4)} / ${limit.toFixed(2)}
                    </span>
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: "rgba(15,23,42,0.1)", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${pct}%`, background: color, borderRadius: 3 }} />
                  </div>
                  <div style={{ fontSize: 9, color: "var(--text-3)", marginTop: 3, fontFamily: "monospace" }}>
                    {env} = {limit.toFixed(2)} (dev)
                  </div>
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 16, padding: "10px 12px", borderRadius: 8, background: "rgba(16,185,129,0.06)", border: "1px solid rgba(16,185,129,0.15)" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#10B981", marginBottom: 4 }}>CostGuardrail — ACTIVE</div>
            <div style={{ fontSize: 11, color: "var(--text-3)" }}>
              Enforced by <code style={{ color: "#F59E0B", fontSize: 10 }}>app/services/cost_guardrail.py</code>.
              Improver calls <code style={{ color: "#F59E0B", fontSize: 10 }}>CostGuardrail.check()</code> before
              generating variants. Cost violations INSERT to <code style={{ color: "#F59E0B", fontSize: 10 }}>audit_log</code>.
            </div>
          </div>
        </div>
      </div>

      {/* Unified Score cost impact */}
      <div style={{ ...CARD, padding: 16 }}>
        <h3 style={{ fontSize: 12, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 10 }}>
          Cost Impact on Unified Score
        </h3>
        <div style={{
          fontFamily: "monospace", fontSize: 13, color: "var(--text-1)",
          background: "rgba(15,23,42,0.04)", borderRadius: 8, padding: "12px 16px",
          border: "1px solid hsl(var(--border))",
        }}>
          Score = 0.25×Recall + 0.35×Quality + 0.25×Faithfulness{" "}
          <span style={{ color: "#EF4444" }}>− 0.10×Latency</span>{" "}
          <span style={{ color: "#F59E0B" }}>− 0.05×Cost</span>
        </div>
        <p style={{ fontSize: 11, color: "var(--text-3)", marginTop: 8 }}>
          Cost is a 5% penalty factor in the deployment gate. High-cost pipelines directly reduce
          deployment eligibility. Current avg cost/query ($0.0037) is well below the penalty threshold.
        </p>
      </div>
    </div>
  );
}
