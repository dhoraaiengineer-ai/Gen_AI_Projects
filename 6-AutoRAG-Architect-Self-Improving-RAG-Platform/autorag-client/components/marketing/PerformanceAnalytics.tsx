"use client";

import { useState, useEffect } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { Activity, Zap, TrendingUp, ShieldCheck, Clock, ArrowDownRight, ArrowUpRight, Play, Pause } from "lucide-react";

// Illustrative benchmark data (simulated, not live production telemetry) —
// ported verbatim from the provided design source, including the live-tick
// jitter simulation below.
interface ChartPoint {
  time: string;
  naiveLatency: number;
  autoRagLatency: number;
  accuracy: number;
  recall: number;
  cost: number;
}

const historicalData: Record<"60s" | "24h" | "7d" | "30d", ChartPoint[]> = {
  "60s": [
    { time: "00:50", naiveLatency: 380, autoRagLatency: 28, accuracy: 99.2, recall: 98.5, cost: 0.0024 },
    { time: "00:40", naiveLatency: 410, autoRagLatency: 24, accuracy: 99.4, recall: 98.7, cost: 0.0021 },
    { time: "00:30", naiveLatency: 395, autoRagLatency: 22, accuracy: 99.1, recall: 98.2, cost: 0.0019 },
    { time: "00:20", naiveLatency: 420, autoRagLatency: 19, accuracy: 99.5, recall: 98.9, cost: 0.0018 },
    { time: "00:10", naiveLatency: 390, autoRagLatency: 16, accuracy: 99.6, recall: 99.1, cost: 0.0016 },
    { time: "NOW", naiveLatency: 405, autoRagLatency: 14, accuracy: 99.8, recall: 99.4, cost: 0.0014 },
  ],
  "24h": [
    { time: "00:00", naiveLatency: 450, autoRagLatency: 32, accuracy: 94.2, recall: 91.0, cost: 0.0050 },
    { time: "04:00", naiveLatency: 430, autoRagLatency: 28, accuracy: 96.0, recall: 93.5, cost: 0.0042 },
    { time: "08:00", naiveLatency: 420, autoRagLatency: 22, accuracy: 97.8, recall: 95.8, cost: 0.0031 },
    { time: "12:00", naiveLatency: 410, autoRagLatency: 18, accuracy: 98.9, recall: 97.4, cost: 0.0022 },
    { time: "16:00", naiveLatency: 390, autoRagLatency: 15, accuracy: 99.4, recall: 98.8, cost: 0.0018 },
    { time: "20:00", naiveLatency: 385, autoRagLatency: 14, accuracy: 99.7, recall: 99.2, cost: 0.0015 },
  ],
  "7d": [
    { time: "Mon", naiveLatency: 520, autoRagLatency: 45, accuracy: 92.1, recall: 88.5, cost: 0.0075 },
    { time: "Tue", naiveLatency: 490, autoRagLatency: 38, accuracy: 94.5, recall: 91.2, cost: 0.0062 },
    { time: "Wed", naiveLatency: 460, autoRagLatency: 29, accuracy: 96.8, recall: 94.0, cost: 0.0048 },
    { time: "Thu", naiveLatency: 430, autoRagLatency: 22, accuracy: 98.2, recall: 96.5, cost: 0.0032 },
    { time: "Fri", naiveLatency: 400, autoRagLatency: 18, accuracy: 99.1, recall: 98.1, cost: 0.0021 },
    { time: "Sat", naiveLatency: 390, autoRagLatency: 15, accuracy: 99.5, recall: 98.9, cost: 0.0016 },
    { time: "Sun", naiveLatency: 380, autoRagLatency: 14, accuracy: 99.7, recall: 99.3, cost: 0.0014 },
  ],
  "30d": [
    { time: "W1", naiveLatency: 610, autoRagLatency: 68, accuracy: 89.4, recall: 85.0, cost: 0.0120 },
    { time: "W2", naiveLatency: 530, autoRagLatency: 42, accuracy: 93.8, recall: 90.2, cost: 0.0080 },
    { time: "W3", naiveLatency: 440, autoRagLatency: 24, accuracy: 97.5, recall: 95.6, cost: 0.0038 },
    { time: "W4", naiveLatency: 385, autoRagLatency: 14, accuracy: 99.6, recall: 99.2, cost: 0.0015 },
  ],
};

export function PerformanceAnalytics() {
  const [activeTab, setActiveTab] = useState<"latency" | "accuracy" | "cost">("latency");
  const [timeHorizon, setTimeHorizon] = useState<"60s" | "24h" | "7d" | "30d">("60s");
  const [isLiveStreaming, setIsLiveStreaming] = useState<boolean>(true);
  const [chartData, setChartData] = useState<ChartPoint[]>(historicalData["60s"]);

  useEffect(() => {
    setChartData(historicalData[timeHorizon]);
  }, [timeHorizon]);

  // Live streaming tick generator for '60s' mode
  useEffect(() => {
    if (!isLiveStreaming || timeHorizon !== "60s") return;

    const interval = setInterval(() => {
      setChartData((prevData) => {
        const last = prevData[prevData.length - 1];
        const now = new Date();
        const timeStr = `${now.getMinutes().toString().padStart(2, "0")}:${now.getSeconds().toString().padStart(2, "0")}`;

        const newAutoLatency = Math.max(11, Math.min(22, Math.round(last.autoRagLatency + (Math.random() * 4 - 2))));
        const newNaiveLatency = Math.max(360, Math.min(440, Math.round(last.naiveLatency + (Math.random() * 20 - 10))));
        const newAccuracy = Number(Math.min(99.9, Math.max(98.5, last.accuracy + (Math.random() * 0.2 - 0.1))).toFixed(1));
        const newRecall = Number(Math.min(99.8, Math.max(97.8, last.recall + (Math.random() * 0.2 - 0.1))).toFixed(1));
        const newCost = Number(Math.max(0.0010, Math.min(0.0025, last.cost + (Math.random() * 0.0002 - 0.0001))).toFixed(4));

        const newItem: ChartPoint = {
          time: timeStr,
          naiveLatency: newNaiveLatency,
          autoRagLatency: newAutoLatency,
          accuracy: newAccuracy,
          recall: newRecall,
          cost: newCost,
        };

        return [...prevData.slice(1), newItem];
      });
    }, 2000);

    return () => clearInterval(interval);
  }, [isLiveStreaming, timeHorizon]);

  return (
    <div className="w-full bg-[#0b1120] rounded-3xl border border-slate-800/90 p-6 sm:p-8 shadow-2xl text-slate-100 relative overflow-hidden">
      {/* Background Decorative Glow */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-96 h-96 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Header Bar */}
      <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800/80">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-500/10 border border-orange-500/30 text-orange-400 text-xs font-mono font-bold mb-2">
            <Activity className="w-3.5 h-3.5 animate-pulse" />
            <span>REAL-TIME PERFORMANCE ENGINE</span>
          </div>
          <h3 className="text-2xl sm:text-3xl font-black text-white tracking-tight flex items-center gap-2">
            <span>RAG Query Analytics</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-mono font-bold border border-emerald-500/30">
              Auto-Tuned
            </span>
          </h3>
          <p className="text-xs text-slate-400 font-medium mt-1">
            Continuous autonomous benchmarking against standard naive RAG pipelines.
          </p>
        </div>

        {/* Controls & Time Horizon */}
        <div className="flex flex-wrap items-center gap-2">
          {timeHorizon === "60s" && (
            <button
              onClick={() => setIsLiveStreaming(!isLiveStreaming)}
              className={`px-3 py-1.5 rounded-xl text-xs font-mono font-bold flex items-center gap-1.5 transition-all border cursor-pointer ${
                isLiveStreaming
                  ? "bg-emerald-950/80 text-emerald-400 border-emerald-800 hover:bg-emerald-900/80"
                  : "bg-slate-800 text-slate-400 border-slate-700 hover:text-white"
              }`}
            >
              {isLiveStreaming ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              <span>{isLiveStreaming ? "LIVE TICKING" : "PAUSED"}</span>
            </button>
          )}

          <div className="inline-flex rounded-xl bg-slate-900 p-1 border border-slate-800">
            {(["60s", "24h", "7d", "30d"] as const).map((th) => (
              <button
                key={th}
                onClick={() => setTimeHorizon(th)}
                className={`px-3 py-1 text-xs font-mono font-bold rounded-lg transition-colors cursor-pointer ${
                  timeHorizon === th ? "bg-orange-500 text-white shadow-sm" : "text-slate-400 hover:text-white"
                }`}
              >
                {th.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* KPI Summary Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 my-6 relative z-10">
        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800/90 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-bold">
            <span>AVG LATENCY</span>
            <Clock className="w-4 h-4 text-orange-400" />
          </div>
          <div className="my-2">
            <span className="text-2xl sm:text-3xl font-black text-white font-mono">14ms</span>
            <span className="ml-2 text-xs font-bold text-emerald-400 inline-flex items-center">
              <ArrowDownRight className="w-3.5 h-3.5" /> -96.5%
            </span>
          </div>
          <span className="text-[10px] text-slate-400 font-medium">vs. 395ms Naive RAG</span>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800/90 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-bold">
            <span>FAITHFULNESS SCORE</span>
            <ShieldCheck className="w-4 h-4 text-sky-400" />
          </div>
          <div className="my-2">
            <span className="text-2xl sm:text-3xl font-black text-white font-mono">99.8%</span>
            <span className="ml-2 text-xs font-bold text-emerald-400 inline-flex items-center">
              <ArrowUpRight className="w-3.5 h-3.5" /> +28.4%
            </span>
          </div>
          <span className="text-[10px] text-slate-400 font-medium">Zero Hallucination Guard</span>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800/90 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-bold">
            <span>CONTEXT RECALL</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="my-2">
            <span className="text-2xl sm:text-3xl font-black text-white font-mono">99.4%</span>
            <span className="ml-2 text-xs font-bold text-emerald-400 inline-flex items-center">
              <ArrowUpRight className="w-3.5 h-3.5" /> +34.1%
            </span>
          </div>
          <span className="text-[10px] text-slate-400 font-medium">Dense + Sparse Hybrid</span>
        </div>

        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800/90 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-bold">
            <span>COST PER 1K REQS</span>
            <Zap className="w-4 h-4 text-amber-400" />
          </div>
          <div className="my-2">
            <span className="text-2xl sm:text-3xl font-black text-white font-mono">$0.0014</span>
            <span className="ml-2 text-xs font-bold text-emerald-400 inline-flex items-center">
              <ArrowDownRight className="w-3.5 h-3.5" /> -78%
            </span>
          </div>
          <span className="text-[10px] text-slate-400 font-medium">Speculative Cache Enabled</span>
        </div>
      </div>

      {/* Mode Switcher Tabs */}
      <div className="flex items-center gap-2 mb-4 relative z-10 border-b border-slate-800 pb-3">
        <button
          onClick={() => setActiveTab("latency")}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === "latency" ? "bg-orange-500 text-white shadow-lg shadow-orange-500/20" : "bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800"
          }`}
        >
          Query Latency Benchmark (ms)
        </button>
        <button
          onClick={() => setActiveTab("accuracy")}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === "accuracy" ? "bg-sky-500 text-white shadow-lg shadow-sky-500/20" : "bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800"
          }`}
        >
          Retrieval Accuracy &amp; Recall (%)
        </button>
        <button
          onClick={() => setActiveTab("cost")}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === "cost" ? "bg-emerald-500 text-white shadow-lg shadow-emerald-500/20" : "bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800"
          }`}
        >
          Token Cost Efficiency ($)
        </button>
      </div>

      {/* Main Chart Canvas */}
      <div className="h-72 w-full relative z-10 pt-2">
        <ResponsiveContainer width="100%" height="100%">
          {activeTab === "latency" ? (
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorAutoRag" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f97316" stopOpacity={0.5} />
                  <stop offset="95%" stopColor="#f97316" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="colorNaive" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#64748b" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#64748b" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" stroke="#64748b" fontSize={11} tickLine={false} />
              <YAxis stroke="#64748b" fontSize={11} tickLine={false} unit="ms" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  borderRadius: "12px",
                  color: "#fff",
                  fontSize: "12px",
                }}
              />
              <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "10px" }} />
              <Area
                type="monotone"
                dataKey="naiveLatency"
                name="Traditional Naive RAG (ms)"
                stroke="#64748b"
                fillOpacity={1}
                fill="url(#colorNaive)"
                strokeWidth={2}
                strokeDasharray="4 4"
              />
              <Area
                type="monotone"
                dataKey="autoRagLatency"
                name="AutoRAG Autonomous Optimization (ms)"
                stroke="#f97316"
                fillOpacity={1}
                fill="url(#colorAutoRag)"
                strokeWidth={3}
              />
            </AreaChart>
          ) : activeTab === "accuracy" ? (
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" stroke="#64748b" fontSize={11} tickLine={false} />
              <YAxis stroke="#64748b" fontSize={11} tickLine={false} domain={[80, 100]} unit="%" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  borderRadius: "12px",
                  color: "#fff",
                  fontSize: "12px",
                }}
              />
              <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "10px" }} />
              <Line type="monotone" dataKey="accuracy" name="Faithfulness Score (%)" stroke="#38bdf8" strokeWidth={3} dot={{ r: 4, fill: "#38bdf8" }} />
              <Line type="monotone" dataKey="recall" name="Context Recall (%)" stroke="#10b981" strokeWidth={3} dot={{ r: 4, fill: "#10b981" }} />
            </LineChart>
          ) : (
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" stroke="#64748b" fontSize={11} tickLine={false} />
              <YAxis stroke="#64748b" fontSize={11} tickLine={false} unit="$" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  borderRadius: "12px",
                  color: "#fff",
                  fontSize: "12px",
                }}
              />
              <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "10px" }} />
              <Bar dataKey="cost" name="Token Cost / 1k Queries ($)" fill="#10b981" radius={[6, 6, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>

      <div className="mt-6 pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-400 gap-2 relative z-10">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-mono">Autonomous Optimization Loop: Active (6 Auto-Tuning Agents Operating)</span>
        </div>
        <div className="font-mono text-slate-400">
          Source: AutoRAG Evaluation Benchmark v3.2
        </div>
      </div>
    </div>
  );
}
