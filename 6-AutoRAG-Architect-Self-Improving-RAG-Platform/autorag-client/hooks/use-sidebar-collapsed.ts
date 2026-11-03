"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "autorag-sidebar-collapsed";

/**
 * Persists desktop sidebar collapse state across route changes. There is no
 * shared (dashboard)/layout.tsx -- AppShell is composed fresh in every page
 * file, so plain React state would reset on every navigation. localStorage
 * is the only thing that survives that.
 */
export function useSidebarCollapsed() {
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setCollapsed(window.localStorage.getItem(STORAGE_KEY) === "1");
  }, []);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }, []);

  return { collapsed, toggle };
}
