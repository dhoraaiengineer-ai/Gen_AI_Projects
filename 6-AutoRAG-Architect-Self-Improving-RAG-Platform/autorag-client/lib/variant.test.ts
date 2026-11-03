import { describe, expect, it } from "vitest";

import {
  CONFIG_FIELDS,
  deriveProposedConfig,
  extractConfig,
  formatConfigValue,
  type PipelineConfig,
} from "@/lib/variant";
import { makePipeline } from "@/test-utils/fixtures";

const BASE: PipelineConfig = {
  chunk_strategy: "semantic",
  dense_weight: 0.5,
  hybrid_ratio: 0.5,
  reranker_enabled: true,
  retrieval_k: 5,
};

describe("extractConfig", () => {
  it("uses wizard defaults for retrieval knobs (no per-pipeline retrieval_config on the backend)", () => {
    const config = extractConfig(makePipeline({ chunk_strategy: "semantic" }));
    expect(config).toEqual(BASE);
  });

  it("reads the real persisted chunk_strategy", () => {
    const config = extractConfig(makePipeline({ chunk_strategy: "hierarchical" }));
    expect(config).toEqual({ ...BASE, chunk_strategy: "hierarchical" });
  });

  it("falls back to semantic when chunk_strategy is null", () => {
    const config = extractConfig(makePipeline({ chunk_strategy: null }));
    expect(config.chunk_strategy).toBe("semantic");
  });
});

describe("deriveProposedConfig", () => {
  it("returns an unchanged config with no recommendations when there are no failures", () => {
    const result = deriveProposedConfig(BASE, []);
    expect(result.proposed).toEqual(BASE);
    expect(result.changedKeys).toEqual([]);
    expect(result.recommendations).toEqual([]);
  });

  it("ignores unrecognized failure codes", () => {
    const result = deriveProposedConfig(BASE, ["F-99", "not-a-code"]);
    expect(result.changedKeys).toEqual([]);
    expect(result.recommendations).toEqual([]);
  });

  it("F-01 shifts toward hybrid and forces the reranker on", () => {
    const start: PipelineConfig = { ...BASE, hybrid_ratio: 0.3, reranker_enabled: false };
    const { proposed, changedKeys } = deriveProposedConfig(start, ["F-01"]);
    expect(proposed.hybrid_ratio).toBe(0.6);
    expect(proposed.reranker_enabled).toBe(true);
    expect(changedKeys).toEqual(["hybrid_ratio", "reranker_enabled"]);
  });

  it("F-02 lowers retrieval_k to fit the token budget", () => {
    const { proposed, changedKeys } = deriveProposedConfig(BASE, ["F-02"]);
    expect(proposed.retrieval_k).toBe(3);
    expect(changedKeys).toEqual(["retrieval_k"]);
  });

  it("F-03 raises retrieval_k and enables reranking", () => {
    const { proposed } = deriveProposedConfig({ ...BASE, reranker_enabled: false }, ["F-03"]);
    expect(proposed.retrieval_k).toBe(8);
    expect(proposed.reranker_enabled).toBe(true);
  });

  it("clamps retrieval_k to the 1..50 integer range", () => {
    expect(deriveProposedConfig({ ...BASE, retrieval_k: 1 }, ["F-02"]).proposed.retrieval_k).toBe(1);
    expect(deriveProposedConfig({ ...BASE, retrieval_k: 49 }, ["F-03"]).proposed.retrieval_k).toBe(50);
  });

  it("applies overlapping codes in canonical F-01..F-06 order deterministically", () => {
    // F-03 (+3) then F-05 (-1) starting from k=5 → 8 → 7, regardless of input order.
    const a = deriveProposedConfig(BASE, ["F-05", "F-03"]);
    const b = deriveProposedConfig(BASE, ["F-03", "F-05"]);
    expect(a.proposed).toEqual(b.proposed);
    expect(a.proposed.retrieval_k).toBe(7);
    expect(a.recommendations.map((r) => r.code)).toEqual(["F-03", "F-05"]);
  });

  it("collapses duplicate codes", () => {
    const { recommendations } = deriveProposedConfig(BASE, ["F-02", "F-02"]);
    expect(recommendations).toHaveLength(1);
  });

  it("attaches a label and rationale to every recommendation", () => {
    const { recommendations } = deriveProposedConfig(BASE, ["F-01"]);
    expect(recommendations[0].label).toBe("Retrieval Miss");
    expect(recommendations[0].rationale).toMatch(/hybrid/i);
  });
});

describe("formatConfigValue", () => {
  it("renders booleans, integers, ratios, and strings distinctly", () => {
    expect(formatConfigValue("reranker_enabled", true)).toBe("Enabled");
    expect(formatConfigValue("reranker_enabled", false)).toBe("Disabled");
    expect(formatConfigValue("retrieval_k", 5)).toBe("5");
    expect(formatConfigValue("hybrid_ratio", 0.5)).toBe("0.50");
    expect(formatConfigValue("chunk_strategy", "semantic")).toBe("semantic");
  });
});

describe("CONFIG_FIELDS", () => {
  it("covers every key of PipelineConfig exactly once", () => {
    const keys = CONFIG_FIELDS.map((f) => f.key).sort();
    expect(keys).toEqual(
      (["chunk_strategy", "dense_weight", "hybrid_ratio", "reranker_enabled", "retrieval_k"] as const)
        .slice()
        .sort(),
    );
  });
});
