"use client";

/**
 * Storage Analytics — Chapter 32.14. Shows real source storage (summed file_size)
 * and the document status distribution. Vector storage, compression ratio, and
 * growth trend are not exposed by any endpoint and are intentionally omitted.
 */

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card } from "@/components/ui/card";
import { formatBytes, type StatusSlice } from "@/lib/knowledge";

interface StorageAnalyticsProps {
  storageBytes: number;
  distribution: StatusSlice[];
}

const TOOLTIP_STYLE = {
  backgroundColor: "hsl(var(--card))",
  borderColor: "rgba(15,23,42,0.1)",
  borderRadius: "6px",
  fontSize: "12px",
  color: "var(--text-1)",
};

const STATUS_COLOR: Record<string, string> = {
  indexed: "#22c55e",
  embedding: "#06b6d4",
  chunking: "#38bdf8",
  validating: "#818cf8",
  uploaded: "#a78bfa",
  failed: "#ef4444",
  archived: "#64748b",
};

export function StorageAnalytics({ storageBytes, distribution }: StorageAnalyticsProps) {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">Storage Analytics</h3>
        <span className="font-mono text-sm text-text-2">{formatBytes(storageBytes)}</span>
      </div>

      {distribution.length === 0 ? (
        <p className="py-8 text-center text-sm text-text-3">No documents to analyze.</p>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={distribution} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.1)" vertical={false} />
            <XAxis dataKey="status" stroke="var(--text-3)" tick={{ fontSize: 10, fill: "var(--text-3)" }} />
            <YAxis allowDecimals={false} stroke="var(--text-3)" tick={{ fontSize: 11, fill: "var(--text-3)" }} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "rgba(15,23,42,0.06)" }} />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {distribution.map((slice) => (
                <Cell key={slice.status} fill={STATUS_COLOR[slice.status] ?? "#7c3aed"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
