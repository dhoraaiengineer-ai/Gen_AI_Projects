import { describe, expect, it } from "vitest";

import { pipelineDisplayName, relativeTime } from "@/lib/format";

const base = {
  id: "0192abcd-ef01-7000-8000-000000000000",
  current_version: 2,
};

describe("pipelineDisplayName", () => {
  it("prefers an explicit pipeline name", () => {
    expect(pipelineDisplayName({ ...base, name: "Support RAG" })).toBe("Support RAG · v2");
  });

  it("falls back to a short id when name is empty", () => {
    expect(pipelineDisplayName({ ...base, name: "" })).toBe("Pipeline 0192abcd · v2");
  });
});

describe("relativeTime", () => {
  const now = new Date("2026-06-20T12:00:00Z").getTime();

  it("renders seconds, minutes, hours, and days", () => {
    expect(relativeTime("2026-06-20T11:59:30Z", now)).toBe("30s ago");
    expect(relativeTime("2026-06-20T11:30:00Z", now)).toBe("30m ago");
    expect(relativeTime("2026-06-20T09:00:00Z", now)).toBe("3h ago");
    expect(relativeTime("2026-06-18T12:00:00Z", now)).toBe("2d ago");
  });

  it("renders an em dash for missing or invalid input", () => {
    expect(relativeTime(null, now)).toBe("—");
    expect(relativeTime("not-a-date", now)).toBe("—");
  });
});
