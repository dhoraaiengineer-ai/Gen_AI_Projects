import { describe, expect, it } from "vitest";

import {
  formatScore,
  isHardBlock,
  isHitlPending,
  scoreBand,
  scoreColorClasses,
} from "@/lib/score";

describe("scoreBand", () => {
  it("classifies the deploy band at and above 0.85", () => {
    expect(scoreBand(0.85)).toBe("deploy");
    expect(scoreBand(0.99)).toBe("deploy");
  });

  it("classifies the HITL band in [0.70, 0.85)", () => {
    expect(scoreBand(0.7)).toBe("hitl");
    expect(scoreBand(0.84)).toBe("hitl");
  });

  it("classifies the retry band below 0.70", () => {
    expect(scoreBand(0.699)).toBe("retry");
    expect(scoreBand(0)).toBe("retry");
  });
});

describe("scoreColorClasses (light-first palette, frontend_design.md §2/§18)", () => {
  it("returns emerald classes for deploy-eligible scores", () => {
    expect(scoreColorClasses(0.9)).toBe("text-emerald-700 bg-emerald-50");
  });

  it("returns amber classes for HITL scores", () => {
    expect(scoreColorClasses(0.75)).toBe("text-amber-700 bg-amber-50");
  });

  it("returns rose classes for retry scores", () => {
    expect(scoreColorClasses(0.5)).toBe("text-rose-700 bg-rose-50");
  });
});

describe("isHardBlock", () => {
  it("blocks when faithfulness < 0.50", () => {
    expect(isHardBlock(0.49)).toBe(true);
    expect(isHardBlock(0)).toBe(true);
  });

  it("does not block at or above 0.50", () => {
    expect(isHardBlock(0.5)).toBe(false);
    expect(isHardBlock(0.92)).toBe(false);
  });
});

describe("isHitlPending", () => {
  it("is true within the borderline band", () => {
    expect(isHitlPending({ unified_score: 0.8 })).toBe(true);
    expect(isHitlPending({ unified_score: 0.7 })).toBe(true);
  });

  it("is false at the deploy gate or below the retry floor", () => {
    expect(isHitlPending({ unified_score: 0.85 })).toBe(false);
    expect(isHitlPending({ unified_score: 0.69 })).toBe(false);
  });

  it("is false when run is absent", () => {
    expect(isHitlPending(null)).toBe(false);
  });
});

describe("formatScore", () => {
  it("formats numbers to 2 decimals", () => {
    expect(formatScore(0.876)).toBe("0.88");
  });

  it("renders an em dash for missing values", () => {
    expect(formatScore(null)).toBe("—");
    expect(formatScore(undefined)).toBe("—");
    expect(formatScore(Number.NaN)).toBe("—");
  });
});
