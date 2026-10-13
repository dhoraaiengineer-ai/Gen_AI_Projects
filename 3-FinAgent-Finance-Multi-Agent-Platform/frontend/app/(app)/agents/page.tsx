"use client";
// Agents & system: A2A agent cards with 7-day statistics, registered ML models, dependency status,
// circuit breakers and the configured model chains.
import { Badge, Card, ErrorBox, Loading, PageHeader, Table, statusTone } from "@/components/ui";
import { api } from "@/lib/api";
import { label, num, when } from "@/lib/format";
import { useResource } from "@/presenters/useResource";

// The API reports breaker states as CLOSED / HALF_OPEN / OPEN.
const breakerTone = (state: string) =>
  ({ closed: "good", half_open: "warn", open: "bad" } as const)[state.toLowerCase() as "closed"] ?? "muted";

export default function AgentsPage() {
  const agents = useResource("agents", api.agents);
  const models = useResource("models", api.models);
  const system = useResource("system", api.system);
  const s = system.data;
  return (
    <>
      <PageHeader title="Agents & system" subtitle="Specialists reached over A2A; tools over MCP; ML models from the MLflow registry." />
      <Card title="System status">
        <ErrorBox message={system.error} onRetry={system.reload} />
        {!s && !system.error && <Loading />}
        {s && (
          <div className="grid gap-4 text-sm md:grid-cols-3">
            <div className="space-y-1">
              {Object.entries(s.checks).map(([k, v]) => (
                <p key={k}>{k}: <Badge tone={v === "ok" ? "good" : v === "disabled" ? "muted" : "warn"}>{v}</Badge></p>
              ))}
              <p>shared state: <Badge>{s.kvStore}</Badge></p>
              <p className="text-muted">{s.environment}{s.demoMode ? " · demo mode" : ""}</p>
            </div>
            <div>
              <p className="mb-1 text-xs uppercase tracking-wide text-muted">Answer chain</p>
              <ol className="list-decimal pl-5">{s.answerChain.map((m) => <li key={m} className="font-mono text-xs">{m}</li>)}</ol>
              <p className="mb-1 mt-3 text-xs uppercase tracking-wide text-muted">Agent chain</p>
              <ol className="list-decimal pl-5">{s.agentChain.map((m) => <li key={m} className="font-mono text-xs">{m}</li>)}</ol>
            </div>
            <div>
              <p className="mb-1 text-xs uppercase tracking-wide text-muted">Circuit breakers</p>
              {Object.keys(s.circuits).length === 0 && <p className="text-muted">All closed (no failures recorded).</p>}
              {Object.entries(s.circuits).map(([k, v]) => (
                <p key={k} className="font-mono text-xs">{k}: <Badge tone={breakerTone(v)}>{v.toLowerCase()}</Badge></p>
              ))}
            </div>
          </div>
        )}
      </Card>
      <Card title="Agents">
        <ErrorBox message={agents.error} onRetry={agents.reload} />
        {!agents.data && !agents.error && <Loading />}
        {agents.data && (
          <Table head={["Agent", "Tasks", "Tools (LLM)", "Runs (7d)", "Avg duration", "Avg confidence", "Failed", "Last run"]}>
            {agents.data.agents.map((a) => (
              <tr key={a.name}>
                <td className="px-2 py-2"><span className="font-medium">{a.name}</span><span className="block text-xs text-muted">{a.description}</span></td>
                <td className="px-2 py-2 text-xs">{a.tasks.join(", ")}</td>
                <td className="px-2 py-2 text-xs text-muted">{a.tools.length}</td>
                <td className="px-2 py-2 tabular-nums">{a.stats?.runs ?? 0}</td>
                <td className="px-2 py-2 tabular-nums">{a.stats ? `${(a.stats.avgDurationMs / 1000).toFixed(1)} s` : "–"}</td>
                <td className="px-2 py-2 tabular-nums">{a.stats?.avgConfidence != null ? num(a.stats.avgConfidence) : "–"}</td>
                <td className="px-2 py-2">{a.stats?.failed ? <Badge tone="bad">{a.stats.failed}</Badge> : "0"}</td>
                <td className="whitespace-nowrap px-2 py-2 text-muted">{when(a.stats?.lastRunAt)}</td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      <Card title="ML models">
        <ErrorBox message={models.error} onRetry={models.reload} />
        {!models.data && !models.error && <Loading />}
        {models.data && (
          <Table head={["Model", "Version", "Algorithm", "Features", "Test metrics", "Trained"]} empty={!models.data.length}>
            {models.data.map((m) => (
              <tr key={m.kind}>
                <td className="px-2 py-2"><span className="font-mono text-xs">{m.name}</span> <Badge tone={statusTone("ok")}>{label(m.kind)}</Badge></td>
                <td className="px-2 py-2">{m.version ?? "–"}</td>
                <td className="px-2 py-2 text-xs">{m.algorithm}</td>
                <td className="px-2 py-2 tabular-nums">{m.features}</td>
                <td className="px-2 py-2 text-xs">
                  {Object.entries(m.testMetrics).slice(0, 6).map(([k, v]) => `${k.replace("test_", "")} ${num(v, 3)}`).join(" · ")}
                </td>
                <td className="whitespace-nowrap px-2 py-2 text-muted">{when(m.trainedAt)}</td>
              </tr>
            ))}
          </Table>
        )}
        <p className="mt-3 text-xs text-muted">Models are trained on synthetic data with time-based splits; predictions are estimates, not guarantees.</p>
      </Card>
    </>
  );
}
