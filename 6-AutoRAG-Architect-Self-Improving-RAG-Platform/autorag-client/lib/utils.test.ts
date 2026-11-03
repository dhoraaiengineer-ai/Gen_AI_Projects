import { describe, it, expect } from "vitest";
import { cn } from "./utils";

describe("cn", () => {
  it("should merge class names correctly", () => {
    expect(cn("a", "b")).toBe("a b");
    expect(cn("a", { b: true, c: false })).toBe("a b");
    expect(cn("a", "b", "c")).toBe("a b c");
  });

  it("should handle conflicting class names correctly", () => {
    expect(cn("p-4", "p-2")).toBe("p-2");
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
  });
});