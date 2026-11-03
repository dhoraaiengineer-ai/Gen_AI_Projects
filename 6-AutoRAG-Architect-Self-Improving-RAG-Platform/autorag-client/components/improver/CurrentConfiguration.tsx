import { CONFIG_FIELDS, formatConfigValue } from "@/lib/variant";
import type { PipelineConfig } from "@/lib/variant";
import type { ScoreResult } from "@/types";

interface CurrentConfigurationProps {
  version: string;
  config: PipelineConfig;
  score: ScoreResult | null;
}

/**
 * §29.7 Current Configuration — real, persisted pipeline values only.
 * Embedding model / prompt template from the original spec are intentionally
 * omitted: the frozen Pipeline schema does not carry them, so showing them would
 * mean fabricating data (CLAUDE.md Rule 45 / Forbidden Pattern #2).
 */
export function CurrentConfiguration({ version, config, score }: CurrentConfigurationProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
        <Row label="Pipeline Version" value={`v${version}`} />
        {CONFIG_FIELDS.map((field) => (
          <Row key={field.key} label={field.label} value={formatConfigValue(field.key, config[field.key])} />
        ))}
        <Row
          label="Unified Score"
          value={score && score.unified_score !== null ? score.unified_score.toFixed(2) : "Not collected"}
        />
        <Row
          label="Latency p95"
          value={score && score.latency_p95_ms !== null ? `${score.latency_p95_ms} ms` : "Not collected"}
        />
      </dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-text-3">{label}</dt>
      <dd className="mt-1 font-mono text-sm text-foreground">{value}</dd>
    </div>
  );
}
