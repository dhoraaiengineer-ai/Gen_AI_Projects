"use client";
// Audit: recent audited decisions and the full trace of one request (audit entries, agent runs,
// A2A envelopes, MCP tool calls).
import { useState } from "react";

import { Badge, Button, Card, ErrorBox, Loading, PageHeader, Table, statusTone } from "@/components/ui";
import { api } from "@/lib/api";
import { label, num, when } from "@/lib/format";
import { useSession } from "@/presenters/session";
import { describe, useResource } from "@/presenters/useResource";
import type { AuditTrace } from "@/types";

export default function AuditPage() {
  const { token } = useSession();
  const activity = useResource("activity", api.activity);
  const [requestId, setRequestId] = useState("");
  const [trace, setTrace] = useState<AuditTrace | null>(null);
  const [error, setError] = useState<string | null>(null);

  const open = async (id: string) => {
    if (!token || !id.trim()) return;
    setRequestId(id);
    setError(null);
    try {
      setTrace(await api.audit(token, id.trim()));
    } catch (e) {
      setError(describe(e));
    }
  };

  return (
    <>
      <PageHeader title="Audit" subtitle="Decisions and reasons — never secrets or raw sensitive data." />
      <Card title="Trace a request">
        <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); void open(requestId); }}>
          <input value={requestId} onChange={(e) => setRequestId(e.target.value)} placeholder="req_…" aria-label="Request id"
            className="min-w-0 flex-1 rounded-lg border border-white/10 bg-ink px-3 py-2 font-mono text-sm" />
          <Button type="submit">Open trace</Button>
        </form>
        <ErrorBox message={error} />
        {trace && <Trace trace={trace} />}
      </Card>
      <Card title="Recent activity">
        <ErrorBox message={activity.error} onRetry={activity.reload} />
        {!activity.data && !activity.error && <Loading />}
        {activity.data && (
          <Table head={["When", "Action", "Decision", "Reason", "Role", "Request"]} empty={!activity.data.length}>
            {activity.data.map((a, i) => (
              <tr key={i}>
                <td className="whitespace-nowrap px-2 py-2 text-muted">{when(a.at)}</td>
                <td className="px-2 py-2 font-mono text-xs">{a.action}</td>
                <td className="px-2 py-2"><Badge tone={statusTone(a.decision)}>{a.decision}</Badge></td>
                <td className="px-2 py-2">{a.reason ?? "–"}</td>
                <td className="px-2 py-2 text-muted">{label(a.userRole)}</td>
                <td className="px-2 py-2">
                  {a.requestId && <button className="font-mono text-xs text-accent hover:underline" onClick={() => void open(a.requestId!)}>{a.requestId}</button>}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </>
  );
}

function Trace({ trace }: { trace: AuditTrace }) {
  return (
    <div className="mt-4 space-y-4 text-sm">
      <p className="text-muted">
        {trace.agentRuns.length} agent runs · {trace.a2aMessages.length} A2A envelopes · {trace.toolCalls.length} MCP tool calls · {trace.audit.length} audit entries
      </p>
      {trace.audit.length > 0 && (
        <Table head={["When", "Action", "Decision", "Reason"]}>
          {trace.audit.map((a, i) => (
            <tr key={i}>
              <td className="whitespace-nowrap px-2 py-1.5 text-muted">{when(a.at)}</td>
              <td className="px-2 py-1.5 font-mono text-xs">{a.action}</td>
              <td className="px-2 py-1.5"><Badge tone={statusTone(a.decision)}>{a.decision}</Badge></td>
              <td className="px-2 py-1.5">{a.reason}</td>
            </tr>
          ))}
        </Table>
      )}
      <Table head={["Agent", "Task", "Status", "Duration", "Confidence", "Tool calls", "Error"]} empty={!trace.agentRuns.length}>
        {trace.agentRuns.map((r, i) => (
          <tr key={i}>
            <td className="px-2 py-1.5 font-medium">{r.agent}</td>
            <td className="px-2 py-1.5 text-xs">{r.task}</td>
            <td className="px-2 py-1.5"><Badge tone={statusTone(r.status)}>{r.status}</Badge></td>
            <td className="px-2 py-1.5 tabular-nums">{(r.durationMs / 1000).toFixed(1)} s</td>
            <td className="px-2 py-1.5 tabular-nums">{r.confidence != null ? num(r.confidence) : "–"}</td>
            <td className="px-2 py-1.5 tabular-nums">{r.toolCalls}</td>
            <td className="px-2 py-1.5 text-xs text-bad">{r.error ?? ""}</td>
          </tr>
        ))}
      </Table>
      <Table head={["Tool", "Server", "Agent", "Status", "Duration", "Error"]} empty={!trace.toolCalls.length}>
        {trace.toolCalls.map((t, i) => (
          <tr key={i}>
            <td className="px-2 py-1.5 font-mono text-xs">{t.tool}</td>
            <td className="px-2 py-1.5 text-muted">{t.server}</td>
            <td className="px-2 py-1.5">{t.agent ?? "–"}</td>
            <td className="px-2 py-1.5"><Badge tone={statusTone(t.status)}>{t.status}</Badge></td>
            <td className="px-2 py-1.5 tabular-nums">{Math.round(t.durationMs)} ms</td>
            <td className="px-2 py-1.5 text-xs text-bad">{t.errorCode ?? ""}</td>
          </tr>
        ))}
      </Table>
    </div>
  );
}
