"use client";
// Knowledge base: grounded answers with [n] citations, the documents the user's role may read, and
// upload/delete for roles with documents:write.
import { useState, type FormEvent } from "react";

import { Badge, Button, Card, ErrorBox, Loading, PageHeader, Table, statusTone } from "@/components/ui";
import { api } from "@/lib/api";
import { when } from "@/lib/format";
import { useSession } from "@/presenters/session";
import { describe, useResource } from "@/presenters/useResource";
import type { RagAnswer, UploadResult } from "@/types";

const DOC_TYPES = ["policy", "regulation", "filing", "statement", "research", "news", "internal"];
const CLASSIFICATIONS = ["public", "internal", "restricted", "confidential"];
const EXAMPLES = [
  "What is the single-issuer concentration limit?",
  "What is the 1-day 95% VaR budget?",
  "Which securities are on the restricted list?",
];

export default function KnowledgePage() {
  const { token, can } = useSession();
  const docs = useResource("documents", api.documents);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<RagAnswer | null>(null);
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async (q: string) => {
    if (!token || q.trim().length < 3) return;
    setQuestion(q);
    setAsking(true);
    setError(null);
    try {
      setAnswer(await api.ragQuery(token, q));
    } catch (e) {
      setError(describe(e));
    } finally {
      setAsking(false);
    }
  };

  return (
    <>
      <PageHeader title="Knowledge base" subtitle="Hybrid search (vector + BM25), cross-encoder re-ranking, answers grounded only in your documents with citations." />
      {can("agents:run") && (
        <Card title="Ask the documents">
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void ask(question); }}>
            <input value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={1000} aria-label="Question for the knowledge base"
              placeholder="e.g. What does the investment policy say about sector limits?"
              className="min-w-0 flex-1 rounded-lg border border-white/10 bg-ink px-3 py-2 text-sm" />
            <Button type="submit" disabled={asking}>{asking ? "Searching…" : "Ask"}</Button>
          </form>
          <div className="mt-2 flex flex-wrap gap-2">
            {EXAMPLES.map((q) => (
              <button key={q} onClick={() => void ask(q)} className="rounded-full border border-white/10 px-3 py-1 text-xs hover:border-accent">{q}</button>
            ))}
          </div>
          <ErrorBox message={error} />
          {answer && (
            <div className="mt-4 space-y-3 border-t border-white/10 pt-4 text-sm">
              <p className="whitespace-pre-wrap text-[15px] leading-relaxed">{answer.answer}</p>
              <div className="flex flex-wrap gap-2 text-xs">
                <Badge tone={answer.answerSource === "llm" ? "good" : answer.answerSource === "refusal" ? "muted" : "warn"}>{answer.answerSource}</Badge>
                {answer.cached && <Badge>cached</Badge>}
                <Badge>KB v{answer.kbVersion}</Badge>
              </div>
              {answer.citations.length > 0 && (
                <ol className="space-y-1 text-xs text-muted">
                  {answer.citations.map((c) => <li key={c.n}>[{c.n}] {c.citation} <span className="tabular-nums">· relevance {c.relevanceScore.toFixed(2)}</span></li>)}
                </ol>
              )}
            </div>
          )}
        </Card>
      )}
      {can("documents:write") && <UploadCard token={token} onDone={docs.reload} />}
      <Card title={`Documents${docs.data ? ` (${docs.data.length})` : ""}`}>
        <ErrorBox message={docs.error} onRetry={docs.reload} />
        {docs.loading && !docs.data && <Loading />}
        {docs.data && (
          <Table head={["Source", "Type", "Classification", "Chunks", "Status", "Updated", ""]} empty={!docs.data.length}>
            {docs.data.map((d) => (
              <tr key={d.documentId}>
                <td className="px-2 py-2">{d.source}</td>
                <td className="px-2 py-2 text-muted">{d.docType}</td>
                <td className="px-2 py-2"><Badge tone={d.classification === "confidential" || d.classification === "restricted" ? "warn" : "muted"}>{d.classification}</Badge></td>
                <td className="px-2 py-2 tabular-nums">{d.chunks}</td>
                <td className="px-2 py-2"><Badge tone={statusTone(d.status)}>{d.status}</Badge></td>
                <td className="whitespace-nowrap px-2 py-2 text-muted">{when(d.updatedAt)}</td>
                <td className="px-2 py-2 text-right">
                  {can("documents:write") && (
                    <button className="text-xs text-bad hover:underline" onClick={async () => {
                      if (!token || !window.confirm(`Delete ${d.source} from the knowledge base?`)) return;
                      try { await api.deleteDocument(token, d.documentId); docs.reload(); } catch (e) { window.alert(describe(e)); }
                    }}>Delete</button>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </>
  );
}

function UploadCard({ token, onDone }: { token: string | null; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!token) return;
    const form = new FormData(e.currentTarget);
    if (!(form.get("file") instanceof File) || !(form.get("file") as File).size) return setError("Choose a file first.");
    setBusy(true);
    setError(null);
    try {
      setResult(await api.upload(token, form));
      onDone();
    } catch (err) {
      setError(describe(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Add a document">
      <form onSubmit={submit} className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-5">
        <input type="file" name="file" aria-label="File" className="lg:col-span-2" accept=".pdf,.docx,.xlsx,.pptx,.csv,.tsv,.txt,.md,.json,.xml,.html,.htm,.sql,.eml,.png,.jpg,.jpeg,.tiff" />
        <select name="docType" aria-label="Document type" className="rounded-lg border border-white/10 bg-ink px-2 py-1.5">
          {DOC_TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>
        <select name="classification" aria-label="Classification" defaultValue="internal" className="rounded-lg border border-white/10 bg-ink px-2 py-1.5">
          {CLASSIFICATIONS.map((c) => <option key={c}>{c}</option>)}
        </select>
        <input name="ticker" placeholder="Ticker (optional)" aria-label="Ticker" maxLength={12} className="rounded-lg border border-white/10 bg-ink px-2 py-1.5" />
        <div className="sm:col-span-2 lg:col-span-5"><Button type="submit" disabled={busy}>{busy ? "Ingesting…" : "Upload and ingest"}</Button></div>
      </form>
      <ErrorBox message={error} />
      {result && (
        <p role="status" className="mt-3 text-sm">
          <Badge tone={statusTone(result.status === "failed" ? "failed" : "ok")}>{result.status}</Badge> {result.source} · {result.chunks} chunks
          {result.error && <span className="text-bad"> · {result.error}</span>}
          {result.warnings.length > 0 && <span className="text-muted"> · {result.warnings.join("; ")}</span>}
        </p>
      )}
    </Card>
  );
}
