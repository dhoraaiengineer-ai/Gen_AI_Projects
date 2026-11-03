"use client";

/**
 * Light/dark toggle (ADR-010, 24-Jul-2026) -- the first working theme
 * switch in this app; `darkMode: "class"` existed in tailwind.config.ts
 * long before this, but nothing ever flipped the class.
 *
 * Renders nothing until mounted -- next-themes' `resolvedTheme` is
 * undefined on the server (theme lives in localStorage, unknown pre-hydration),
 * so rendering a fixed icon before mount would flash the wrong one.
 */

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div className="h-8 w-8" aria-hidden="true" />;
  }

  const isDark = resolvedTheme === "dark";

  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      className="flex h-8 w-8 items-center justify-center rounded-lg border border-border text-text-2 transition-colors motion-safe:transition-colors hover:bg-accent/10"
    >
      {isDark ? (
        <Sun className="h-4 w-4" aria-hidden="true" />
      ) : (
        <Moon className="h-4 w-4" aria-hidden="true" />
      )}
    </button>
  );
}
