import { describe, expect, it } from "vitest";

import {
  activeAlerts,
  deriveOverallStatus,
  formatLatency,
  formatUptime,
  latencyClass,
  sessionUptime,
} from "@/lib/health";

describe("deriveOverallStatus", () => {
  it("is healthy when online with a clean streak", () => {
    expect(deriveOverallStatus(true, 0)).toBe("healthy");
  });

  it("is warning when online but flapping (1-2 fails)", () => {
    expect(deriveOverallStatus(true, 1)).toBe("warning");
    expect(deriveOverallStatus(true, 2)).toBe("warning");
  });

  it("is critical at 3+ consecutive fails even if the latest probe recovered", () => {
    expect(deriveOverallStatus(true, 3)).toBe("critical");
  });

  it("is critical whenever offline", () => {
    expect(deriveOverallStatus(false, 0)).toBe("critical");
  });
});

describe("sessionUptime", () => {
  it("returns the success ratio", () => {
    expect(sessionUptime(9, 10)).toBeCloseTo(0.9);
  });

  it("guards against divide-by-zero before the first probe", () => {
    expect(sessionUptime(0, 0)).toBe(0);
  });
});

describe("latencyClass", () => {
  it("buckets latency into good / fair / poor", () => {
    expect(latencyClass(120)).toBe("good");
    expect(latencyClass(500)).toBe("fair");
    expect(latencyClass(1500)).toBe("poor");
  });

  it("treats a null (failed) probe as poor", () => {
    expect(latencyClass(null)).toBe("poor");
  });
});

describe("activeAlerts", () => {
  it("raises one alert only when critical", () => {
    expect(activeAlerts(true, 0)).toBe(0);
    expect(activeAlerts(true, 1)).toBe(0); // warning is not an alert
    expect(activeAlerts(false, 0)).toBe(1);
    expect(activeAlerts(true, 3)).toBe(1);
  });
});

describe("formatters", () => {
  it("formats uptime as a percentage", () => {
    expect(formatUptime(0.998)).toBe("99.8%");
    expect(formatUptime(1)).toBe("100.0%");
  });

  it("formats latency, using an em dash for a failed probe", () => {
    expect(formatLatency(42.6)).toBe("43 ms");
    expect(formatLatency(null)).toBe("—");
  });
});
