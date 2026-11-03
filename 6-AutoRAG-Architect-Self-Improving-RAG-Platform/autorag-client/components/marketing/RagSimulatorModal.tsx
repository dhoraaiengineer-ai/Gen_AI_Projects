"use client";

import { useState } from "react";
import Link from "next/link";
import { SAMPLE_QUERIES } from "@/lib/marketing-data";
import { X, Play, RefreshCw, CheckCircle2, Terminal, Cpu, Info, ArrowRight } from "lucide-react";

interface RagSimulatorModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface StepLog {
  agentName: string;
  stepName: string;
  outputSnippet: string;
}

const SIMULATED_STEPS: StepLog[] = [
  { agentName: "Ingestion Agent", stepName: "Confirm document chunks are indexed", outputSnippet: "Vector index ready" },
  { agentName: "Query Rewriter Agent", stepName: "Reformulate query for retrieval", outputSnippet: "Query clarified" },
  { agentName: "Builder Agent", stepName: "Run 4-stage hybrid retrieval", outputSnippet: "Dense + BM25 fused, reranked" },
  { agentName: "Context Compressor Agent", stepName: "Trim context to token budget", outputSnippet: "Context compressed" },
  { agentName: "Evaluator Agent", stepName: "Compute Unified Score + RAGAS", outputSnippet: "Faithfulness and Recall scored" },
  { agentName: "Observer Agent", stepName: "Record run to telemetry", outputSnippet: "Trace recorded" },
];

export function RagSimulatorModal({ isOpen, onClose }: RagSimulatorModalProps) {
  const [query, setQuery] = useState(SAMPLE_QUERIES[0]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionLogs, setExecutionLogs] = useState<StepLog[]>([]);
  const [done, setDone] = useState(false);

  if (!isOpen) return null;

  const handleRunSimulator = () => {
    setIsExecuting(true);
    setExecutionLogs([]);
    setDone(false);

    SIMULATED_STEPS.forEach((step, idx) => {
      setTimeout(() => {
        setExecutionLogs((prev) => [...prev, step]);
        if (idx === SIMULATED_STEPS.length - 1) {
          setIsExecuting(false);
          setDone(true);
        }
      }, (idx + 1) * 350);
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md">
      <div className="bg-white rounded-3xl w-full max-w-4xl max-h-[90vh] overflow-hidden shadow-2xl border border-slate-200 flex flex-col">
        {/* Modal Header */}
        <div className="p-6 bg-slate-900 text-white flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center font-bold text-white shadow-md">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-extrabold text-white">Pipeline Walkthrough</h3>
                <span className="text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded border border-amber-500/30">
                  Illustrative
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium">A scripted walkthrough of the 9-agent flow</p>
            </div>
          </div>

          <button onClick={onClose} className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 bg-slate-50">
          <div className="flex items-start gap-2.5 p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs font-medium">
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              This is a scripted, timed animation of the pipeline steps — it is not connected to live
              infrastructure and doesn&apos;t call a real LLM. To run a real query against a real pipeline,{" "}
              <Link href="/login" onClick={onClose} className="font-bold underline">
                sign in
              </Link>
              .
            </span>
          </div>

          {/* Query Input Section */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">1. Sample Query</label>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="flex-1 px-4 py-3 bg-white text-slate-900 text-sm font-medium border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm"
                placeholder="Type a question..."
              />
              <button
                onClick={handleRunSimulator}
                disabled={isExecuting}
                className="px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-xl shadow-md transition-all flex items-center justify-center gap-2 disabled:opacity-50 shrink-0"
              >
                {isExecuting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Running...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-white" />
                    <span>Run Walkthrough</span>
                  </>
                )}
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2 pt-1">
              <span className="text-[11px] font-bold text-slate-500">Sample queries:</span>
              {SAMPLE_QUERIES.map((sq) => (
                <button
                  key={sq}
                  onClick={() => setQuery(sq)}
                  className="text-[11px] font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 px-2.5 py-1 rounded-lg border border-indigo-200/60 transition-colors truncate max-w-[280px]"
                >
                  {sq}
                </button>
              ))}
            </div>
          </div>

          {/* Execution Trace Timeline */}
          <div className="space-y-3">
            <label className="text-xs font-bold text-slate-700 uppercase tracking-wider block">2. Agent Steps</label>

            <div className="bg-slate-900 rounded-2xl p-4 text-slate-200 font-mono text-xs space-y-3 min-h-[220px] shadow-inner border border-slate-800">
              {executionLogs.length === 0 && !isExecuting && (
                <div className="h-full flex flex-col items-center justify-center py-12 text-slate-500">
                  <Terminal className="w-8 h-8 mb-2 text-slate-600" />
                  <p>Click &quot;Run Walkthrough&quot; above.</p>
                </div>
              )}

              {executionLogs.map((log, idx) => (
                <div key={idx} className="p-3 rounded-xl bg-slate-800/90 border border-slate-700 space-y-1.5">
                  <div className="flex items-center gap-2 text-slate-300">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    <span className="font-bold text-indigo-300">[{log.agentName}]</span>
                    <span className="text-slate-200 font-semibold">{log.stepName}</span>
                  </div>
                  <p className="text-[11px] text-emerald-400 pl-4 border-l-2 border-indigo-500/50">
                    &gt; {log.outputSnippet}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {done && (
            <div className="p-4 rounded-2xl bg-indigo-50/80 border border-indigo-200 space-y-3">
              <span className="text-xs font-extrabold text-indigo-900 uppercase tracking-wider flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Walkthrough complete</span>
              </span>
              <p className="text-xs text-slate-700 font-medium leading-relaxed">
                In a real run, this is where the Deployer would report deployment eligibility, and the
                Evaluation Dashboard would show the actual Unified Score, RAGAS breakdown, and citations.
              </p>
              <Link
                href="/login"
                onClick={onClose}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-700 hover:text-indigo-900"
              >
                <span>Sign in to run a real pipeline</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-white border-t border-slate-200 flex items-center justify-between">
          <span className="text-xs text-slate-500 font-medium">Illustrative — not connected to live infrastructure</span>
          <button onClick={onClose} className="px-5 py-2 bg-slate-800 hover:bg-slate-900 text-white text-xs font-bold rounded-xl transition-colors">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
