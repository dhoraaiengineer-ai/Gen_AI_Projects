"use client";

import { useState } from "react";
import { Play, FlaskConical, Loader2 } from "lucide-react";
import { apiClient } from "@/services/api-client";
import { usePipelines } from "@/hooks/use-pipelines";
import { pipelineDisplayName } from "@/lib/format";
import type { RetrievalResult, QueryAnswerResult } from "@/types";

/* Light theme (13-Jul-2026 contrast correction) -- was a dark-gradient card
   left over from the pre-ADR-008 dark shell, unreadable against the light
   canvas everywhere else in the app. */
const CARD: React.CSSProperties = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  padding: 20,
  boxShadow: "0 1px 2px rgba(16,24,40,0.04), 0 4px 12px rgba(16,24,40,0.035)",
};

/**
 * P0.7 follow-up (13-Jul-2026): the previous version cast the response
 * `as unknown as RawQueryResponse` and read `unified_score`/`faithfulness`/
 * `cost_usd`/`provider`/`answer` fields that no real backend route has ever
 * returned -- unified_score/faithfulness/cost/provider always silently
 * fell back to fabricated defaults (0, "N/A", "gemini-flash-3.5"). This used
 * the real POST /api/v1/retrieve response directly: retrieval-only, no
 * answer generation, no score.
 *
 * 26-Jul-2026: retrieval-only made this page functionally identical to the
 * Retrieval Explorer, with no real distinction (direct product review).
 * Now also calls the real GET /api/v1/query generation endpoint, so this
 * page genuinely tests the full pipeline (retrieve -> rerank -> generate) a
 * real end user would hit -- still honest: no unified_score/faithfulness
 * here either, since that requires a real Evaluator run, not this endpoint.
 */
export function PlaygroundPageClient() {
  const { pipelines, isLoading: pipelinesLoading } = usePipelines();
  const [query, setQuery] = useState("");
  const [pipelineId, setPipelineId] = useState("");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RetrievalResult | null>(null);
  // 26-Jul-2026: this page previously ran the exact same retrieval-only call
  // as the Retrieval Explorer, with no real distinction between the two
  // pages. Query Playground now also calls the real GET /api/v1/query
  // generation endpoint (retrieve -> rerank -> LLM answer, prompt-constrained
  // to the provided context) so it genuinely tests the full pipeline an end
  // user would experience, not just retrieval -- that's the actual
  // difference from the Retrieval Explorer. A generation failure doesn't
  // blank out the retrieval result that already succeeded.
  const [answer, setAnswer] = useState<QueryAnswerResult | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);
  const [answerLoading, setAnswerLoading] = useState(false);

  const handleRun = async () => {
    if (!query.trim() || !pipelineId.trim()) {
      setError("A query and a pipeline selection are both required.");
      return;
    }
    setLoading(true);
    setError(null);
    setAnswer(null);
    setAnswerError(null);
    try {
      const data = await apiClient.queryRetrieval({
        pipeline_id: pipelineId.trim(),
        query: query.trim(),
        top_k: topK,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
      setLoading(false);
      return;
    }
    setLoading(false);

    setAnswerLoading(true);
    try {
      const answerData = await apiClient.queryAnswer({ pipeline_id: pipelineId.trim(), query: query.trim() });
      setAnswer(answerData);
    } catch (err) {
      setAnswerError(err instanceof Error ? err.message : "Answer generation failed");
    } finally {
      setAnswerLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Sandbox banner */}
      <div style={{
        padding: "10px 16px", borderRadius: 8,
        background: "rgba(245,158,11,0.06)", border: "1px solid rgba(245,158,11,0.20)",
        display: "flex", alignItems: "center", gap: 8,
      }}>
        <FlaskConical style={{ width: 14, height: 14, color: "#F59E0B", flexShrink: 0 }} />
        <span style={{ fontSize: 12, color: "#F59E0B" }}>
          Sandbox mode — queries run against a dev pipeline snapshot and do not affect production data, deployments, or evaluation history.
        </span>
      </div>

      {/* Config panel */}
      <div style={CARD}>
        <h3 style={{ fontSize: 12, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 14 }}>
          Sandbox Configuration
        </h3>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 180px 180px 180px auto", gap: 12, alignItems: "flex-end" }}>
          <div>
            <label style={{ display: "block", fontSize: 11, color: "var(--text-3)", marginBottom: 6 }}>Test Query</label>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your question..."
              onKeyDown={(e) => e.key === "Enter" && handleRun()}
              style={{
                width: "100%", padding: "9px 12px",
                background: "rgba(15,23,42,0.04)", border: "1px solid hsl(var(--border))",
                borderRadius: 8, color: "var(--text-1)", fontSize: 13,
              }}
            />
          </div>
          <div>
            <label style={{ display: "block", fontSize: 11, color: "var(--text-3)", marginBottom: 6 }}>Pipeline</label>
            <select
              value={pipelineId}
              onChange={(e) => setPipelineId(e.target.value)}
              disabled={pipelinesLoading}
              style={{
                width: "100%", padding: "9px 12px",
                background: "rgba(15,23,42,0.04)", border: "1px solid hsl(var(--border))",
                borderRadius: 8, color: "var(--text-1)", fontSize: 13,
              }}
            >
              <option value="">
                {pipelinesLoading ? "Loading pipelines…" : pipelines.length === 0 ? "No pipelines" : "Select a pipeline…"}
              </option>
              {pipelines.map((p) => (
                <option key={p.id} value={p.id}>
                  {pipelineDisplayName(p)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ display: "block", fontSize: 11, color: "var(--text-3)", marginBottom: 6 }}>Top-K</label>
            <input
              type="number"
              min={1}
              max={20}
              value={topK}
              onChange={(e) => setTopK(parseInt(e.target.value, 10) || 5)}
              style={{
                width: "100%", padding: "9px 12px",
                background: "rgba(15,23,42,0.04)", border: "1px solid hsl(var(--border))",
                borderRadius: 8, color: "var(--text-1)", fontSize: 13,
              }}
            />
          </div>
          <button
            onClick={handleRun}
            disabled={!query.trim() || loading}
            style={{
              padding: "9px 20px", borderRadius: 8,
              cursor: (query.trim() && !loading) ? "pointer" : "not-allowed",
              background: (query.trim() && !loading) ? "#5B5CE2" : "rgba(15,23,42,0.1)",
              border: "1px solid transparent",
              color: (query.trim() && !loading) ? "hsl(var(--card))" : "var(--text-3)",
              fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", gap: 7,
            }}
          >
            {loading
              ? <><Loader2 style={{ width: 13, height: 13, animation: "spin 1s linear infinite" }} /> Running</>
              : <><Play style={{ width: 13, height: 13 }} /> Run</>
            }
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div style={{ padding: "10px 16px", borderRadius: 8, background: "rgba(244,63,94,0.12)", border: "1px solid #FECDCA", fontSize: 13, color: "#B42318" }}>
          {error}
        </div>
      )}

      {/* Answer — real generation via GET /api/v1/query. This is what
          actually distinguishes Query Playground from the Retrieval
          Explorer: it runs the full retrieve -> rerank -> generate pipeline
          a real end user would hit, not just retrieval. */}
      {(answerLoading || answer || answerError) && (
        <div style={CARD}>
          <h3 style={{ fontSize: 12, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 12 }}>
            Answer
          </h3>
          {answerLoading && (
            <div style={{ fontSize: 13, color: "var(--text-3)", display: "flex", alignItems: "center", gap: 8 }}>
              <Loader2 style={{ width: 14, height: 14, animation: "spin 1s linear infinite" }} /> Generating answer…
            </div>
          )}
          {answerError && !answerLoading && (
            <div style={{ fontSize: 13, color: "#B42318" }}>{answerError}</div>
          )}
          {answer && !answerLoading && (
            <>
              <p style={{ fontSize: 14, color: "var(--text-1)", lineHeight: 1.6, marginBottom: 12, whiteSpace: "pre-wrap" }}>
                {answer.answer}
              </p>
              <div style={{ fontSize: 11, color: "var(--text-3)", display: "flex", gap: 14, flexWrap: "wrap" }}>
                <span>{answer.retrieval_count} chunk{answer.retrieval_count === 1 ? "" : "s"} used</span>
                <span>{answer.latency_ms}ms</span>
                {answer.citations.length > 0 && (
                  <span>
                    Sources:{" "}
                    {Array.from(new Set(answer.citations.map((c) => c.page).filter((p): p is number => p !== null)))
                      .sort((a, b) => a - b)
                      .map((p) => `p.${p}`)
                      .join(", ")}
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Retrieval detail — real retrieval-only data from POST /api/v1/retrieve,
          shown alongside the generated answer above so users can inspect
          exactly what context produced it. */}
      {result ? (
        <div style={CARD}>
          <h3 style={{ fontSize: 12, fontWeight: 700, color: "#FBBF24", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 16 }}>
            Retrieved Context
          </h3>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 16 }}>
            {[
              { label: "Chunks Retrieved", value: String(result.retrieved_chunks.length), color: "#3448C5" },
              { label: "Latency", value: `${result.total_latency_ms}ms`, color: "#FBBF24" },
              {
                label: "Recall@5",
                value: result.recall_at_5_measured && result.recall_at_5 !== null
                  ? result.recall_at_5.toFixed(3)
                  : "NOT_COLLECTED",
                color: result.recall_at_5_measured ? "#10B981" : "var(--text-3)",
              },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ padding: "8px 10px", borderRadius: 6, background: "rgba(15,23,42,0.04)", border: "1px solid hsl(var(--border))", textAlign: "center" }}>
                <div style={{ fontSize: 9, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 3 }}>{label}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color }}>{value}</div>
              </div>
            ))}
          </div>

          {/* Top chunk preview */}
          {result.retrieved_chunks[0] && (
            <div style={{ padding: 14, borderRadius: 8, background: "rgba(15,23,42,0.04)", border: "1px solid hsl(var(--border))", marginBottom: 12 }}>
              <div style={{ fontSize: 10, color: "var(--text-3)", marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                Top Chunk (rank 1{result.retrieved_chunks[0].rerank_score !== null ? `, rerank score ${result.retrieved_chunks[0].rerank_score.toFixed(3)}` : ""})
              </div>
              <p style={{ fontSize: 13, color: "var(--text-1)", margin: 0, lineHeight: 1.6 }}>
                {result.retrieved_chunks[0].preview}
              </p>
            </div>
          )}

          <div style={{ fontSize: 11, color: "var(--text-3)", display: "flex", gap: 14, flexWrap: "wrap" }}>
            <span><span style={{ color: "var(--text-3)" }}>Strategy:</span> {result.retrieval_strategy}</span>
          </div>
        </div>
      ) : !loading && (
        <div style={{ ...CARD, textAlign: "center", padding: 40 }}>
          <FlaskConical style={{ width: 32, height: 32, color: "var(--text-3)", margin: "0 auto 12px" }} />
          <div style={{ fontSize: 14, color: "var(--text-3)", marginBottom: 14 }}>
            Enter a query and click Run to test your pipeline
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 8 }}>
            {["What was the company's revenue in FY2025?", "Summarize the chairman's message.", "What are the major risk factors?"].map(
              (example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setQuery(example)}
                  style={{
                    padding: "6px 12px", borderRadius: 999, fontSize: 12, color: "var(--text-2)",
                    background: "rgba(15,23,42,0.04)", border: "1px solid hsl(var(--border))", cursor: "pointer",
                  }}
                >
                  {example}
                </button>
              ),
            )}
          </div>
        </div>
      )}
    </div>
  );
}
