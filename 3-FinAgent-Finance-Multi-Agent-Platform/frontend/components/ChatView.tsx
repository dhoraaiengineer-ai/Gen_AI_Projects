"use client";
// View: question box, live agent timeline, streaming answer and the decision report.
import Link from "next/link";
import { useState } from "react";

import { money } from "@/lib/format";

import type { ChatTurn, TimelineItem } from "@/presenters/useChat";

const SAMPLES = [
  "Why has the risk of our technology portfolio increased, and what are the major contributors?",
  "Check Portfolio A against our policy limits",
  "Propose a rebalance for Portfolio A",
  "What does our investment policy say about single-issuer concentration?",
  "Is transaction TX-004512 fraudulent?",
  "Forecast NVTK volatility for next month",
];

const STATUS_DOT: Record<TimelineItem["status"], string> = {
  running: "bg-warn animate-pulse",
  ok: "bg-good",
  partial: "bg-warn",
  failed: "bg-bad",
  info: "bg-accent",
};

const RISK_COLOR: Record<string, string> = { LOW: "text-good", MEDIUM: "text-warn", HIGH: "text-bad", CRITICAL: "text-bad" };

export function ChatView({ turns, running, onAsk }: { turns: ChatTurn[]; running: boolean; onAsk: (q: string) => void }) {
  const [question, setQuestion] = useState("");
  const submit = (q: string) => {
    if (!q.trim() || running) return;
    onAsk(q);
    setQuestion("");
  };
  return (
    <section className="flex min-w-0 flex-1 flex-col gap-4">
      <div className="space-y-6">
        {turns.length === 0 && (
          <div className="rounded-2xl border border-white/10 bg-panel p-6">
            <h2 className="text-lg font-semibold">Ask FinAgent</h2>
            <p className="mt-1 text-sm text-muted">
              The supervisor routes your question to specialist agents (A2A), which call tools over MCP on your firm&apos;s data.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              {SAMPLES.map((s) => (
                <button key={s} onClick={() => submit(s)} className="rounded-full border border-white/10 px-3 py-1 text-left text-sm hover:border-accent">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {turns.map((turn, i) => <Turn key={i} turn={turn} />)}
      </div>
      <form
        className="sticky bottom-0 flex gap-2 rounded-2xl border border-white/10 bg-panel p-2"
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
      >
        <input value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={4000}
          placeholder="Ask about portfolio risk, limits, market context…" aria-label="Question"
          className="min-w-0 flex-1 bg-transparent px-3 py-2 outline-none" />
        <button type="submit" disabled={running} className="rounded-xl bg-accent px-4 py-2 font-medium text-ink disabled:opacity-50">
          {running ? "Working…" : "Ask"}
        </button>
      </form>
    </section>
  );
}

function Turn({ turn }: { turn: ChatTurn }) {
  const report = turn.report;
  return (
    <article className="space-y-3">
      <div className="ml-auto max-w-[85%] rounded-2xl bg-accent/15 px-4 py-2 text-sm">{turn.question}</div>
      <div className="rounded-2xl border border-white/10 bg-panel p-4">
        <ol className="space-y-1.5 text-sm">
          {turn.timeline.map((item) => (
            <li key={item.id} className="flex items-start gap-2">
              <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${STATUS_DOT[item.status]}`} />
              <span className="w-12 shrink-0 tabular-nums text-muted">{item.at.toFixed(1)}s</span>
              <span className="min-w-0">
                <span className="font-medium">{item.label}</span>
                {item.detail && <span className="block truncate text-xs text-muted">{item.detail}</span>}
              </span>
            </li>
          ))}
          {turn.running && turn.timeline.length === 0 && <li className="text-muted">Starting…</li>}
        </ol>
        {(turn.narrative || report) && (
          <div className="mt-4 whitespace-pre-wrap border-t border-white/10 pt-4 text-[15px] leading-relaxed">
            {report?.sections.interpretation ?? turn.narrative}
          </div>
        )}
        {turn.error && <p role="alert" className="mt-3 text-sm text-bad">{turn.error}</p>}
      </div>
      {report && <ReportCard turn={turn} />}
    </article>
  );
}

function ReportCard({ turn }: { turn: ChatTurn }) {
  const r = turn.report!;
  return (
    <div className="space-y-4 rounded-2xl border border-white/10 bg-panel p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        {r.riskLevel && <span className={`rounded-full border border-current px-2 py-0.5 text-xs font-semibold ${RISK_COLOR[r.riskLevel] ?? ""}`}>RISK {r.riskLevel}</span>}
        {r.approval.required && <span className="rounded-full bg-warn/20 px-2 py-0.5 text-xs font-semibold text-warn">APPROVAL REQUIRED</span>}
        <span className="rounded-full bg-white/5 px-2 py-0.5 text-xs text-muted">confidence {Math.round(r.confidence * 100)}%</span>
        <span className="rounded-full bg-white/5 px-2 py-0.5 text-xs text-muted">answer: {r.sections.interpretationSource} · output {r.guard.output}</span>
      </div>
      <h3 className="text-base font-semibold">{r.headline}</h3>
      <Section title="Facts (from tools)" items={r.sections.facts.map((f) => `[${f.agent}] ${f.text}`)} />
      <Section
        title="ML predictions (estimates, not guarantees)"
        items={r.sections.mlPredictions.map((p) => `[${p.agent}] ${p.text}`)}
      />
      <Section title="Recommendations (drafts need approval)" items={r.sections.recommendations} />
      <Section title="Approval reasons" items={r.approval.reasons} />
      {r.approval.approvalId && (
        <div className="rounded-xl border border-warn/30 bg-warn/5 p-3">
          <p className="font-medium text-warn">
            Paused for human approval · {r.approval.draftOrders?.length ?? 0} draft orders (
            {money((r.approval.draftOrders ?? []).reduce((sum, o) => sum + o.value, 0))}) · status {r.approval.status}
          </p>
          <p className="mt-1 text-xs text-muted">Nothing is executed. An approver other than the requester must decide.</p>
          <Link href="/approvals" className="mt-2 inline-block text-accent hover:underline">Review in Approvals →</Link>
        </div>
      )}
      <Section title="Assumptions" items={r.sections.assumptions} />
      <Section title="Uncertainty" items={r.sections.uncertainty} />
      {r.evidence.some((e) => e.url) && (
        <div>
          <h4 className="mb-1 font-medium text-muted">Sources</h4>
          <ul className="space-y-1">
            {r.evidence.filter((e) => e.url).map((e) => (
              <li key={e.url}><a href={e.url!} target="_blank" rel="noreferrer" className="text-accent hover:underline">{e.citation}</a></li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-muted">
        {r.disclaimer} · {r.agents.map((a) => a.name).join(", ")} · {((r.durationMs ?? 0) / 1000).toFixed(1)}s
        {turn.ttfeMs !== null && ` · TTFE ${turn.ttfeMs} ms`}{turn.ttftMs !== null && ` · TTFT ${(turn.ttftMs / 1000).toFixed(1)} s`}
      </p>
    </div>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h4 className="mb-1 font-medium text-muted">{title}</h4>
      <ul className="list-disc space-y-1 pl-5">{items.map((item, i) => <li key={i}>{item}</li>)}</ul>
    </div>
  );
}
