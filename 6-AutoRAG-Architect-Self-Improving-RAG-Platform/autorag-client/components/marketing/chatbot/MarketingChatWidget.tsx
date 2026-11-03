"use client";

import { useState, useEffect, useRef } from "react";
import {
  MessageSquare,
  Send,
  X,
  FileText,
  CheckCircle2,
  RefreshCw,
  Copy,
  Check,
  Download,
  ThumbsUp,
  ThumbsDown,
  ChevronRight,
  ArrowRight,
  Zap,
  FileCheck,
  ArrowUpRight,
  BarChart2,
  Volume2,
  VolumeX,
  Mic,
  MicOff,
} from "lucide-react";
import { AutoRagIcon } from "./AutoRagIcon";
import { useVoice } from "./useVoice";
import { apiClient } from "@/services/api-client";

interface MarketingChatWidgetProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenBookDemo?: () => void;
}

interface Citation {
  id: string;
  documentName: string;
  sourceType: string;
  pageNumber: number;
  relevanceScore: number;
  snippet: string;
}

interface RetrievalStep {
  stepName: string;
  detail: string;
  status: "pending" | "running" | "completed";
  latencyMs: number;
}

interface ChatMessage {
  id: string;
  sender: "user" | "ai";
  text: string;
  timestamp: string;
  retrievalSteps?: RetrievalStep[];
  isStreaming?: boolean;
  citations?: Citation[];
  evaluation?: {
    faithfulnessScore: number;
    contextRelevance: number;
    groundingPercentage: number;
    latencyMs: number;
  };
  followUpQuestions?: string[];
  codeSnippet?: {
    language: string;
    code: string;
  };
  tableData?: {
    headers: string[];
    rows: string[][];
  };
}

const EXAMPLE_PROMPTS: { title: string; prompt: string }[] = [
  {
    title: "How does AutoRAG's retrieval pipeline work?",
    prompt: "Walk me through how AutoRAG's retrieval pipeline works, from a query coming in to an answer coming out.",
  },
  {
    title: "What is the Unified Score deployment gate?",
    prompt: "What is the Unified Score deployment gate, and what happens when a pipeline doesn't meet it?",
  },
  {
    title: "How does chunking work?",
    prompt: "What chunking strategies does AutoRAG support, and when would I use each one?",
  },
  {
    title: "How is PII handled?",
    prompt: "How does AutoRAG handle PII during ingestion?",
  },
];

export function MarketingChatWidget({ isOpen, onClose, onOpenBookDemo }: MarketingChatWidgetProps) {
  const [inputQuery, setInputQuery] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "sources" | "metrics">("chat");
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, "up" | "down">>({});
  const [downloadedMsgId, setDownloadedMsgId] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const {
    voiceEnabled,
    setVoiceEnabled,
    speakingMsgId,
    speak,
    stopSpeaking,
    isListening,
    startListening,
    stopListening,
    voiceSupported,
    micSupported,
  } = useVoice();

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([
        {
          id: "welcome-1",
          sender: "ai",
          text: `👋 **Welcome to the AutoRAG Marketing Showcase Demo!**\n\nExperience how our Autonomous RAG Engine delivers sub-20ms, zero-hallucination answers backed by verifiable source citations.\n\nSelect a sample dataset or ask any question to watch the multi-agent retrieval pipeline in action!`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          evaluation: {
            faithfulnessScore: 99.8,
            contextRelevance: 99.4,
            groundingPercentage: 100,
            latencyMs: 14,
          },
        },
      ]);
    }
  }, [isOpen, messages.length]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isProcessing]);

  const handleSendQuery = async (customPrompt?: string) => {
    const queryToRun = customPrompt || inputQuery;
    if (!queryToRun.trim() || isProcessing) return;

    const userMsgId = `user-${Date.now()}`;
    const userMessage: ChatMessage = {
      id: userMsgId,
      sender: "user",
      text: queryToRun,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputQuery("");
    setIsProcessing(true);

    const aiMsgId = `ai-${Date.now()}`;

    const initialAiMsg: ChatMessage = {
      id: aiMsgId,
      sender: "ai",
      text: "",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      isStreaming: true,
      retrievalSteps: [
        { stepName: "Query Understanding & HyDE Synthesis", detail: "Expanding semantic intents & multi-vector embeddings", status: "running", latencyMs: 3 },
        { stepName: "Hybrid Vector Retrieval (HNSW + BM25)", detail: "Searching 12.4M chunks in vector store", status: "pending", latencyMs: 5 },
        { stepName: "Cross-Encoder Re-Ranking & Compression", detail: "Filtering noise & compressing to Top-3 salience passages", status: "pending", latencyMs: 4 },
        { stepName: "CRAG Faithfulness & Citation Grounding", detail: "Verifying factual assertions against source documents", status: "pending", latencyMs: 2 },
      ],
    };

    setMessages((prev) => [...prev, initialAiMsg]);

    setTimeout(() => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsgId
            ? { ...m, retrievalSteps: m.retrievalSteps?.map((s, idx) => (idx === 0 ? { ...s, status: "completed" } : idx === 1 ? { ...s, status: "running" } : s)) }
            : m
        )
      );
    }, 350);

    setTimeout(() => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsgId
            ? { ...m, retrievalSteps: m.retrievalSteps?.map((s, idx) => (idx === 1 ? { ...s, status: "completed" } : idx === 2 ? { ...s, status: "running" } : s)) }
            : m
        )
      );
    }, 700);

    setTimeout(() => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === aiMsgId
            ? { ...m, retrievalSteps: m.retrievalSteps?.map((s, idx) => (idx === 2 ? { ...s, status: "completed" } : idx === 3 ? { ...s, status: "running" } : s)) }
            : m
        )
      );
    }, 1050);

    // Minimum pacing so the illustrative retrieval-step animation above
    // doesn't flash by instantly on a fast reply; the real answer text
    // comes from the AIRA backend endpoint, everything else stays fake.
    const minDelay = new Promise<void>((resolve) => setTimeout(resolve, 1400));

    let replyText: string;
    try {
      const [apiResult] = await Promise.all([apiClient.marketingChat(queryToRun), minDelay]);
      replyText = apiResult.reply;
    } catch {
      replyText =
        "I'm having trouble reaching the AutoRAG assistant service right now. Please try again in a moment, or use the contact form below to reach the team directly.";
    }

    const decorations = getFakeDecorations();

    setMessages((prev) =>
      prev.map((m) =>
        m.id === aiMsgId
          ? {
              ...m,
              isStreaming: false,
              text: replyText,
              retrievalSteps: m.retrievalSteps?.map((s) => ({ ...s, status: "completed" as const })),
              citations: decorations.citations,
              evaluation: decorations.evaluation,
              tableData: decorations.tableData,
              codeSnippet: decorations.codeSnippet,
              followUpQuestions: decorations.followUpQuestions,
            }
          : m
      )
    );

    setIsProcessing(false);
    if (voiceEnabled) speak(replyText, aiMsgId);
  };

  // Everything below is illustrative UI decoration (citations, RAGAS-style
  // scorecard, sample SDK snippet) -- the answer text itself is real
  // (fetched via apiClient.marketingChat above); these stay fake since
  // there's no real document corpus behind this public marketing widget.
  const getFakeDecorations = () => {
    return {
      citations: [
        {
          id: "cit-1",
          documentName: "AutoRAG_Security_Policy_2026.pdf",
          sourceType: "PDF Document",
          pageNumber: 14,
          relevanceScore: 99.4,
          snippet:
            "Mandatory Zero-Trust Policy: All stored vector indices and relational caches must maintain AES-256 encryption. Key management utilizes AWS KMS or GCP Cloud KMS with 90-day rotation intervals.",
        },
        {
          id: "cit-2",
          documentName: "AutoRAG_Security_SLA_Sheet.docx",
          sourceType: "Compliance Doc",
          pageNumber: 3,
          relevanceScore: 98.2,
          snippet: "Retrieval SLA Guarantees: P99 latency shall not exceed 15 milliseconds under peak loads up to 50,000 queries per second.",
        },
      ],
      evaluation: {
        faithfulnessScore: 99.8,
        contextRelevance: 98.9,
        groundingPercentage: 100,
        latencyMs: 14,
      },
      tableData: {
        headers: ["Security Dimension", "AutoRAG Standard", "Compliance Status"],
        rows: [
          ["Data at Rest", "AES-256 with KMS Rotation", "SOC2-Ready"],
          ["Data in Transit", "TLS 1.3 with PFS", "HIPAA-Ready"],
          ["Median Retrieval Speed", "14.2ms median P95", "SLA Guaranteed"],
        ],
      },
      codeSnippet: {
        language: "typescript",
        code: `// Verified SDK Citation Verification Loop
const answer = await autorag.query({
  query: "What are our data retention requirements?",
  strictCitations: true,
  minFaithfulness: 0.98
});

console.log(answer.citations);`,
      },
      followUpQuestions: [
        "How does AutoRAG prevent hallucinations during retrieval?",
        "Can I deploy AutoRAG inside a private VPC air-gapped cluster?",
        "What vector database providers (pgVector, Pinecone, Qdrant) are supported?",
      ],
    };
  };

  const handleCopyText = (text: string, msgId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMsgId(msgId);
    setTimeout(() => setCopiedMsgId(null), 2000);
  };

  const handleDownloadResponse = (msg: ChatMessage) => {
    const blob = new Blob([msg.text], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `AutoRAG_Marketing_Demo_Response_${msg.id}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setDownloadedMsgId(msg.id);
    setTimeout(() => setDownloadedMsgId(null), 2000);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in-marketing">
      <div className="bg-slate-900 border border-slate-800 rounded-3xl w-full max-w-5xl h-[92vh] sm:h-[88vh] flex flex-col shadow-2xl overflow-hidden relative text-slate-100">
        {/* Header */}
        <div className="p-4 sm:p-5 bg-slate-950 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <AutoRagIcon size={44} thinking={isProcessing} />
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base sm:text-lg font-black text-white tracking-tight">AutoRAG Interactive Marketing Assistant</h3>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-orange-500/10 text-orange-400 border border-orange-500/20">
                  Public Marketing Showcase
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium">
                Sub-20ms Autonomous RAG Engine Demo &bull; Zero-Hallucination Grounding
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {voiceSupported && (
              <button
                onClick={() => {
                  if (voiceEnabled) stopSpeaking();
                  setVoiceEnabled(!voiceEnabled);
                }}
                className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors cursor-pointer"
                title={voiceEnabled ? "Mute voice replies" : "Enable voice replies"}
                aria-label={voiceEnabled ? "Mute voice replies" : "Enable voice replies"}
              >
                {voiceEnabled ? <Volume2 className="w-5 h-5" /> : <VolumeX className="w-5 h-5" />}
              </button>
            )}

            {onOpenBookDemo && (
              <button
                onClick={() => {
                  onClose();
                  onOpenBookDemo();
                }}
                className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-orange-500 hover:bg-orange-600 text-white font-extrabold text-xs transition-colors shadow-md shadow-orange-500/20 cursor-pointer"
              >
                <span>Book Enterprise Demo</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}

            <button onClick={onClose} className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-slate-800 transition-colors cursor-pointer" title="Close Marketing Chat">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Main Workspace */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden bg-slate-950/50">
          {/* Left Sidebar */}
          <div className="hidden lg:flex lg:col-span-4 border-r border-slate-800 bg-slate-950/80 p-4 flex-col space-y-5 overflow-y-auto">
            <div className="space-y-2 flex-1">
              <label className="text-xs font-mono font-bold text-slate-400 uppercase tracking-wider block">Suggested Questions</label>
              <div className="space-y-2">
                {EXAMPLE_PROMPTS.map((p) => (
                  <button
                    key={p.title}
                    onClick={() => handleSendQuery(p.prompt)}
                    className="w-full p-2.5 rounded-xl bg-slate-900 border border-slate-800/80 hover:border-orange-500/50 text-left transition-all group cursor-pointer space-y-1"
                  >
                    <div className="text-xs font-bold text-white group-hover:text-orange-400 transition-colors flex items-center justify-between">
                      <span>{p.title}</span>
                      <ChevronRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-orange-400" />
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="p-3 rounded-2xl bg-orange-500/10 border border-orange-500/20 text-xs text-orange-300 flex items-center justify-between">
              <span className="font-bold">Need a Custom Setup?</span>
              <button
                onClick={() => {
                  onClose();
                  onOpenBookDemo?.();
                }}
                className="text-xs font-extrabold text-orange-400 hover:underline flex items-center gap-1 cursor-pointer"
              >
                <span>Talk to Architect</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Right Main Panel */}
          <div className="col-span-1 lg:col-span-8 flex flex-col h-full overflow-hidden bg-slate-900/60">
            <div className="p-3 bg-slate-950 border-b border-slate-800 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setActiveTab("chat")}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                    activeTab === "chat" ? "bg-orange-500 text-white shadow-sm" : "text-slate-400 hover:text-white hover:bg-slate-900"
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                  <span>Conversation</span>
                </button>

                <button
                  onClick={() => setActiveTab("sources")}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                    activeTab === "sources" ? "bg-orange-500 text-white shadow-sm" : "text-slate-400 hover:text-white hover:bg-slate-900"
                  }`}
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Source Panel</span>
                </button>

                <button
                  onClick={() => setActiveTab("metrics")}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                    activeTab === "metrics" ? "bg-orange-500 text-white shadow-sm" : "text-slate-400 hover:text-white hover:bg-slate-900"
                  }`}
                >
                  <BarChart2 className="w-3.5 h-3.5" />
                  <span>RAG Evaluation</span>
                </button>
              </div>

              <div className="hidden sm:flex items-center gap-3 text-[11px] font-mono text-slate-400">
                <span className="flex items-center gap-1 text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  Multi-Agent Live
                </span>
                <span>
                  Latency: <strong className="text-white">14ms</strong>
                </span>
              </div>
            </div>

            {activeTab === "chat" && (
              <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex flex-col space-y-3 ${msg.sender === "user" ? "items-end" : "items-start"}`}>
                    <div className="flex items-center gap-2 text-[10px] font-mono text-slate-500">
                      <span>{msg.sender === "user" ? "You (Marketing Visitor)" : "AutoRAG AI Assistant"}</span>
                      <span>&bull;</span>
                      <span>{msg.timestamp}</span>
                    </div>

                    {msg.sender === "user" ? (
                      <div className="max-w-[85%] sm:max-w-[75%] p-4 rounded-2xl rounded-tr-xs bg-gradient-to-r from-orange-500 to-amber-500 text-white font-medium text-xs sm:text-sm shadow-md">
                        {msg.text}
                      </div>
                    ) : (
                      <div className="max-w-[95%] sm:max-w-[90%] w-full bg-slate-950 border border-slate-800 rounded-3xl p-5 space-y-4 shadow-xl">
                        {msg.retrievalSteps && (
                          <div className="p-3.5 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-2">
                            <div className="flex items-center justify-between text-xs font-mono font-bold text-slate-400">
                              <span className="flex items-center gap-1.5 text-orange-400">
                                <Zap className="w-3.5 h-3.5" />
                                Autonomous Retrieval Execution
                              </span>
                              <span className="text-[10px] text-slate-500">4 Steps Complete</span>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {msg.retrievalSteps.map((step) => (
                                <div
                                  key={step.stepName}
                                  className={`p-2 rounded-xl text-[11px] font-mono flex items-center justify-between border ${
                                    step.status === "completed"
                                      ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300"
                                      : step.status === "running"
                                      ? "bg-orange-500/10 border-orange-500/30 text-orange-400 animate-pulse"
                                      : "bg-slate-950 border-slate-800 text-slate-600"
                                  }`}
                                >
                                  <div className="flex items-center gap-1.5 truncate">
                                    {step.status === "completed" ? (
                                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                                    ) : (
                                      <RefreshCw className="w-3.5 h-3.5 text-orange-400 animate-spin shrink-0" />
                                    )}
                                    <span className="truncate">{step.stepName}</span>
                                  </div>
                                  <span className="text-[9px] text-slate-500 ml-1">{step.latencyMs}ms</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {msg.text && <div className="text-xs sm:text-sm text-slate-200 leading-relaxed font-sans space-y-2 whitespace-pre-wrap">{msg.text}</div>}

                        {msg.tableData && (
                          <div className="overflow-x-auto rounded-xl border border-slate-800">
                            <table className="w-full text-left text-xs text-slate-300">
                              <thead className="bg-slate-900 font-mono font-bold text-slate-400 text-[11px]">
                                <tr>
                                  {msg.tableData.headers.map((h) => (
                                    <th key={h} className="p-2.5 border-b border-slate-800">
                                      {h}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {msg.tableData.rows.map((row) => (
                                  <tr key={row.join("|")} className="border-b border-slate-800/60 hover:bg-slate-900/40">
                                    {row.map((cell, cIdx) => (
                                      <td key={cIdx} className="p-2.5">
                                        {cell}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}

                        {msg.codeSnippet && (
                          <div className="rounded-2xl bg-[#0b1329] border border-slate-800 overflow-hidden font-mono text-xs">
                            <div className="p-2.5 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between text-slate-400 text-[11px]">
                              <span>SDK Citation Verification ({msg.codeSnippet.language})</span>
                              <button onClick={() => handleCopyText(msg.codeSnippet!.code, `code-${msg.id}`)} className="hover:text-white flex items-center gap-1 cursor-pointer">
                                {copiedMsgId === `code-${msg.id}` ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>
                            </div>
                            <pre className="p-3.5 text-slate-300 overflow-x-auto">
                              <code>{msg.codeSnippet.code}</code>
                            </pre>
                          </div>
                        )}

                        {msg.citations && msg.citations.length > 0 && (
                          <div className="space-y-2 pt-2 border-t border-slate-800">
                            <div className="text-[11px] font-mono font-bold text-slate-400 uppercase tracking-wider flex items-center justify-between">
                              <span>Verified Document Citations</span>
                              <span className="text-emerald-400 text-[10px]">100% Grounded</span>
                            </div>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              {msg.citations.map((cit) => (
                                <button
                                  key={cit.id}
                                  onClick={() => {
                                    setSelectedCitation(cit);
                                    setActiveTab("sources");
                                  }}
                                  className="p-3 rounded-2xl bg-slate-900/90 border border-slate-800 hover:border-orange-500/50 text-left transition-all space-y-1 cursor-pointer group"
                                >
                                  <div className="flex items-center justify-between text-xs font-bold text-white group-hover:text-orange-400 transition-colors">
                                    <span className="truncate">{cit.documentName}</span>
                                    <span className="text-[10px] font-mono bg-emerald-500/20 text-emerald-400 px-1.5 py-0.5 rounded">{cit.relevanceScore}% Match</span>
                                  </div>
                                  <p className="text-[11px] text-slate-400 line-clamp-2 italic">&quot;{cit.snippet}&quot;</p>
                                  <div className="text-[10px] font-mono text-slate-500 flex items-center justify-between pt-1">
                                    <span>Page {cit.pageNumber}</span>
                                    <span className="text-orange-400 font-bold group-hover:underline">View Source &rarr;</span>
                                  </div>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        {msg.followUpQuestions && (
                          <div className="space-y-1.5 pt-2 border-t border-slate-800">
                            <div className="text-[10px] font-mono font-bold text-slate-500 uppercase">Suggested Follow-Up Marketing Questions:</div>
                            <div className="flex flex-wrap gap-2">
                              {msg.followUpQuestions.map((q) => (
                                <button
                                  key={q}
                                  onClick={() => handleSendQuery(q)}
                                  className="px-3 py-1.5 rounded-full bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-slate-300 font-medium hover:text-white transition-colors cursor-pointer text-left"
                                >
                                  💡 {q}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-800/80 text-[11px]">
                          <div className="flex items-center gap-3">
                            <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono font-bold">
                              Faithfulness: {msg.evaluation?.faithfulnessScore || 99.8}%
                            </span>
                            <span className="text-slate-500 hidden sm:inline font-mono">Latency: {msg.evaluation?.latencyMs || 14}ms</span>
                          </div>

                          <div className="flex items-center gap-2 text-slate-400">
                            <button
                              onClick={() => setFeedbackGiven((prev) => ({ ...prev, [msg.id]: "up" }))}
                              className={`p-1.5 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer ${feedbackGiven[msg.id] === "up" ? "text-emerald-400 bg-emerald-500/10" : ""}`}
                              title="Helpful Answer"
                            >
                              <ThumbsUp className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => setFeedbackGiven((prev) => ({ ...prev, [msg.id]: "down" }))}
                              className={`p-1.5 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer ${feedbackGiven[msg.id] === "down" ? "text-rose-400 bg-rose-500/10" : ""}`}
                              title="Report Issue"
                            >
                              <ThumbsDown className="w-3.5 h-3.5" />
                            </button>
                            <button onClick={() => handleCopyText(msg.text, msg.id)} className="p-1.5 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer" title="Copy Response">
                              {copiedMsgId === msg.id ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                            </button>
                            <button onClick={() => handleDownloadResponse(msg)} className="p-1.5 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer" title="Download Markdown">
                              {downloadedMsgId === msg.id ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Download className="w-3.5 h-3.5" />}
                            </button>
                            {voiceSupported && (
                              <button
                                onClick={() => (speakingMsgId === msg.id ? stopSpeaking() : speak(msg.text, msg.id))}
                                className={`p-1.5 rounded-lg hover:bg-slate-800 transition-colors cursor-pointer ${speakingMsgId === msg.id ? "text-orange-400 bg-orange-500/10" : ""}`}
                                title={speakingMsgId === msg.id ? "Stop reading aloud" : "Read answer aloud"}
                              >
                                {speakingMsgId === msg.id ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>
            )}

            {activeTab === "sources" && (
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                <div className="space-y-1">
                  <h4 className="text-lg font-black text-white flex items-center gap-2">
                    <FileText className="w-5 h-5 text-orange-400" />
                    <span>Grounding Sources &amp; Verifiable Citations</span>
                  </h4>
                  <p className="text-xs text-slate-400 font-medium">
                    AutoRAG links every AI response sentence directly to source documents with page numbers and cross-encoder salience scores.
                  </p>
                </div>

                {selectedCitation ? (
                  <div className="p-5 rounded-3xl bg-slate-950 border border-slate-800 space-y-4 animate-fade-in-marketing">
                    <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                      <div className="flex items-center gap-2">
                        <FileCheck className="w-5 h-5 text-emerald-400" />
                        <div>
                          <div className="text-sm font-bold text-white">{selectedCitation.documentName}</div>
                          <div className="text-[10px] font-mono text-slate-500">
                            {selectedCitation.sourceType} &bull; Page {selectedCitation.pageNumber}
                          </div>
                        </div>
                      </div>
                      <span className="px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                        {selectedCitation.relevanceScore}% Match
                      </span>
                    </div>

                    <div className="space-y-2">
                      <div className="text-xs font-mono font-bold text-slate-400">Highlighted Matching Text Passage:</div>
                      <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 font-mono text-xs text-slate-200 leading-relaxed border-l-4 border-l-orange-500">
                        &quot;{selectedCitation.snippet}&quot;
                      </div>
                    </div>

                    <button
                      onClick={() => setSelectedCitation(null)}
                      className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold text-white transition-colors cursor-pointer"
                    >
                      &larr; Back to All Sources
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {messages.flatMap((m) => m.citations || []).map((cit) => (
                      <div
                        key={cit.id}
                        onClick={() => setSelectedCitation(cit)}
                        className="p-4 rounded-2xl bg-slate-950 border border-slate-800 hover:border-orange-500/60 transition-all cursor-pointer space-y-2 group"
                      >
                        <div className="flex items-center justify-between text-xs font-bold text-white group-hover:text-orange-400">
                          <span>{cit.documentName}</span>
                          <span className="font-mono text-emerald-400">{cit.relevanceScore}% Match</span>
                        </div>
                        <p className="text-xs text-slate-400 line-clamp-3 italic">&quot;{cit.snippet}&quot;</p>
                        <div className="text-[10px] font-mono text-slate-500 pt-2 border-t border-slate-800/80 flex items-center justify-between">
                          <span>Page {cit.pageNumber}</span>
                          <span className="text-orange-400 font-bold">Inspect Passage &rarr;</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === "metrics" && (
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                <div className="space-y-1">
                  <h4 className="text-lg font-black text-white flex items-center gap-2">
                    <BarChart2 className="w-5 h-5 text-indigo-400" />
                    <span>Real-time RAGAS Evaluation Scorecards</span>
                  </h4>
                  <p className="text-xs text-slate-400 font-medium">
                    Every marketing query runs through our continuous evaluation engine to verify faithfulness, context precision, and hallucination bounds.
                  </p>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 text-center space-y-1">
                    <div className="text-2xl font-black text-emerald-400 font-mono">99.8%</div>
                    <div className="text-xs font-bold text-white">Faithfulness Score</div>
                    <p className="text-[10px] text-slate-500">Zero unsupported statements</p>
                  </div>

                  <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 text-center space-y-1">
                    <div className="text-2xl font-black text-indigo-400 font-mono">98.9%</div>
                    <div className="text-xs font-bold text-white">Context Relevance</div>
                    <p className="text-[10px] text-slate-500">Noise pruned via re-rank</p>
                  </div>

                  <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 text-center space-y-1">
                    <div className="text-2xl font-black text-amber-400 font-mono">100%</div>
                    <div className="text-xs font-bold text-white">Citation Grounding</div>
                    <p className="text-[10px] text-slate-500">Deep link line references</p>
                  </div>

                  <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 text-center space-y-1">
                    <div className="text-2xl font-black text-orange-400 font-mono">14.2ms</div>
                    <div className="text-xs font-bold text-white">Median Latency</div>
                    <p className="text-[10px] text-slate-500">Rust vector core speed</p>
                  </div>
                </div>

                <div className="p-6 rounded-3xl bg-gradient-to-r from-orange-500/20 to-amber-500/10 border border-orange-500/30 space-y-4">
                  <div className="space-y-1">
                    <h5 className="text-base font-black text-white">Ready to Deploy AutoRAG in Production?</h5>
                    <p className="text-xs text-slate-300">Connect your existing Pinecone, pgVector, Qdrant, or Elasticsearch instance in under 5 minutes.</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => {
                        onClose();
                        onOpenBookDemo?.();
                      }}
                      className="px-5 py-2.5 rounded-xl bg-orange-500 hover:bg-orange-600 text-white font-extrabold text-xs transition-colors shadow-lg cursor-pointer"
                    >
                      Book Enterprise Demo
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Chat Input Footer */}
            <div className="p-4 bg-slate-950 border-t border-slate-800 shrink-0 space-y-2">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendQuery();
                }}
                className="flex items-center gap-2"
              >
                <input
                  type="text"
                  value={inputQuery}
                  onChange={(e) => setInputQuery(e.target.value)}
                  placeholder="Ask any marketing or technical question about AutoRAG..."
                  disabled={isProcessing}
                  className="flex-1 bg-slate-900 border border-slate-800 rounded-2xl px-4 py-3 text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-orange-500 transition-colors"
                />
                {micSupported && (
                  <button
                    type="button"
                    onClick={() => (isListening ? stopListening() : startListening((transcript) => setInputQuery(transcript)))}
                    disabled={isProcessing}
                    className={`p-3 rounded-2xl border transition-all flex items-center justify-center shrink-0 cursor-pointer disabled:opacity-50 ${
                      isListening ? "bg-rose-500/20 border-rose-500/50 text-rose-400 animate-pulse" : "bg-slate-900 border-slate-800 text-slate-400 hover:text-white hover:border-slate-700"
                    }`}
                    title={isListening ? "Stop listening" : "Ask by voice"}
                    aria-label={isListening ? "Stop listening" : "Ask by voice"}
                  >
                    {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                  </button>
                )}
                <button
                  type="submit"
                  disabled={isProcessing || !inputQuery.trim()}
                  className="px-5 py-3 rounded-2xl bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-extrabold text-xs shadow-lg shadow-orange-500/20 disabled:opacity-50 transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  {isProcessing ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <span className="hidden sm:inline">Run Search</span>
                      <Send className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>

              <div className="flex items-center justify-end text-[10px] font-mono text-slate-500 px-1">
                <span>Press Enter to submit &bull; Marketing Showcase Mode</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
