"use client";

import { useEffect, useState } from "react";

interface AgentStatusProps {
  jobId: string;
}

type NodeStatus = "idle" | "running" | "complete" | "error";

interface AgentNode {
  key: string;
  label: string;
  status: NodeStatus;
}

const AGENT_KEYS: Array<{ key: string; label: string }> = [
  { key: "ingestion",     label: "Ingestion" },
  { key: "query_rewriter", label: "Query Rewriter" },
  { key: "builder",       label: "Builder" },
  { key: "compressor",    label: "Compressor" },
  { key: "evaluator",     label: "Evaluator" },
  { key: "observer",      label: "Observer" },
  { key: "diagnoser",     label: "Diagnoser" },
  { key: "improver",      label: "Improver" },
  { key: "deployer",      label: "Deployer" },
];

const STATUS_RING: Record<NodeStatus, string> = {
  idle:     "bg-gray-800 border border-gray-700 text-text-3",
  running:  "bg-blue-600 text-foreground border border-blue-500",
  complete: "bg-emerald-600 text-foreground border border-emerald-500",
  error:    "bg-red-600 text-foreground border border-red-500",
};

const STATUS_LABEL: Record<NodeStatus, string> = {
  idle:     "",
  running:  "Running…",
  complete: "Done",
  error:    "Error",
};

export function AgentStatus({ jobId }: AgentStatusProps): JSX.Element {
  const [nodes, setNodes] = useState<AgentNode[]>(
    AGENT_KEYS.map((k) => ({ ...k, status: "idle" as NodeStatus }))
  );
  const [jobDone, setJobDone] = useState(false);

  useEffect(() => {
    if (!jobId || jobDone) return;
    let active = true;

    const poll = async () => {
      while (active) {
        try {
          const res = await fetch(`/api/v1/jobs/${jobId}`, {
            headers: { "X-Organization-ID": process.env.NEXT_PUBLIC_DEFAULT_ORG_ID ?? "" },
          });
          if (!res.ok) break;

          const json = await res.json();
          const data: {
            status?: string;
            node_statuses?: Record<string, NodeStatus>;
          } = json?.data ?? {};

          const nodeStatuses = data.node_statuses ?? {};
          setNodes((prev) =>
            prev.map((n) => ({
              ...n,
              status: nodeStatuses[n.key] ?? n.status,
            }))
          );

          if (
            data.status === "completed" ||
            data.status === "failed" ||
            data.status === "cancelled"
          ) {
            setJobDone(true);
            break;
          }
        } catch {
          break;
        }

        await new Promise<void>((r) => setTimeout(r, 2000));
      }
    };

    poll();
    return () => {
      active = false;
    };
  }, [jobId, jobDone]);

  return (
    <div className="flex flex-col gap-2">
      {nodes.map((node, idx) => (
        <div key={node.key} className="flex items-center gap-3">
          {/* Step badge */}
          <div
            className={[
              "w-7 h-7 rounded-full text-[11px] font-bold flex items-center justify-center shrink-0",
              node.status === "running" ? "animate-pulse" : "",
              STATUS_RING[node.status],
            ].join(" ")}
          >
            {idx + 1}
          </div>

          {/* Label */}
          <span className="text-sm text-gray-300 flex-1 min-w-0 truncate">
            {node.label}
          </span>

          {/* Status chip */}
          {STATUS_LABEL[node.status] && (
            <span
              className={`text-xs shrink-0 ${
                node.status === "running"
                  ? "text-blue-400"
                  : node.status === "complete"
                  ? "text-emerald-400"
                  : "text-red-400"
              }`}
            >
              {STATUS_LABEL[node.status]}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
