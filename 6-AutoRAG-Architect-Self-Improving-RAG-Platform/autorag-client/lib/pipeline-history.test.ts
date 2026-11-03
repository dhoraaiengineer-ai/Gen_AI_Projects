import { describe, expect, it } from "vitest";

import {
  diffConfigs,
  extractConfigView,
  sortVersionsDesc,
} from "@/lib/pipeline-history";
import { makePipeline } from "@/test-utils/fixtures";

describe("sortVersionsDesc", () => {
  it("returns newest version first", () => {
    const versions = [
      makePipeline({ current_version: 1 }),
      makePipeline({ current_version: 3 }),
      makePipeline({ current_version: 2 }),
    ];
    expect(sortVersionsDesc(versions).map((v) => v.current_version)).toEqual([3, 2, 1]);
  });

  it("breaks version ties by created_at (newest first) and does not mutate input", () => {
    const input = [
      makePipeline({ current_version: 1, created_at: "2026-06-01T00:00:00Z" }),
      makePipeline({ current_version: 1, created_at: "2026-06-05T00:00:00Z" }),
    ];
    const sorted = sortVersionsDesc(input);
    expect(sorted[0].created_at).toBe("2026-06-05T00:00:00Z");
    expect(input[0].created_at).toBe("2026-06-01T00:00:00Z"); // original order preserved
  });
});

describe("extractConfigView", () => {
  it("reads chunk_strategy off the pipeline; retrieval knobs use the global defaults", () => {
    const view = extractConfigView(makePipeline({ chunk_strategy: "hierarchical" }));
    expect(view).toMatchObject({
      chunk_strategy: "hierarchical",
      dense_weight: 0.5,
      hybrid_ratio: 0.5,
      reranker_enabled: true,
      retrieval_k: 5,
      weight_recall: 0.25,
      weight_quality: 0.35,
      weight_faithfulness: 0.25,
    });
  });

  it("falls back to semantic when chunk_strategy is null", () => {
    const view = extractConfigView(makePipeline({ chunk_strategy: null }));
    expect(view.chunk_strategy).toBe("semantic");
  });
});

describe("diffConfigs", () => {
  it("flags only the changed fields", () => {
    const a = extractConfigView(makePipeline({ chunk_strategy: "semantic" }));
    const b = extractConfigView(makePipeline({ chunk_strategy: "hierarchical" }));
    const rows = diffConfigs(a, b);

    const changed = rows.filter((r) => r.changed).map((r) => r.key);
    expect(changed).toEqual(["chunk_strategy"]);
    const row = rows.find((r) => r.key === "chunk_strategy");
    expect(row?.aValue).toBe("semantic");
    expect(row?.bValue).toBe("hierarchical");
  });

  it("reports no changes for identical configs", () => {
    const view = extractConfigView(makePipeline());
    expect(diffConfigs(view, view).every((r) => !r.changed)).toBe(true);
  });

  it("formats booleans and ratios readably", () => {
    const view = extractConfigView(makePipeline());
    const rows = diffConfigs(view, view);
    const rerank = rows.find((r) => r.key === "reranker_enabled");
    expect(rerank?.aValue).toBe("Enabled");
    expect(rows.find((r) => r.key === "hybrid_ratio")?.aValue).toBe("0.50");
  });
});
