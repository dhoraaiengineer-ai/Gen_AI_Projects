import { beforeEach, describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { useSidebarCollapsed } from "./use-sidebar-collapsed";

beforeEach(() => {
  window.localStorage.clear();
});

describe("useSidebarCollapsed", () => {
  it("defaults to expanded when nothing is stored", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    expect(result.current.collapsed).toBe(false);
  });

  it("reads a previously persisted collapsed state on mount", () => {
    window.localStorage.setItem("autorag-sidebar-collapsed", "1");
    const { result } = renderHook(() => useSidebarCollapsed());
    expect(result.current.collapsed).toBe(true);
  });

  it("toggle flips state and persists it", () => {
    const { result } = renderHook(() => useSidebarCollapsed());

    act(() => result.current.toggle());
    expect(result.current.collapsed).toBe(true);
    expect(window.localStorage.getItem("autorag-sidebar-collapsed")).toBe("1");

    act(() => result.current.toggle());
    expect(result.current.collapsed).toBe(false);
    expect(window.localStorage.getItem("autorag-sidebar-collapsed")).toBe("0");
  });
});
