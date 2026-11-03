"use client";

import { useEffect, useState } from "react";
import { ArrowUp } from "lucide-react";

/** Floating scroll-to-top button — appears once the page has scrolled past
 * one viewport height, hidden otherwise. Shared shell component (AppShell),
 * so it applies to every page without per-page wiring. */
export function ScrollToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    function onScroll() {
      setVisible(window.scrollY > window.innerHeight * 0.6);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (!visible) return null;

  return (
    <button
      type="button"
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      aria-label="Scroll to top"
      className="fixed bottom-6 right-6 z-40 flex h-10 w-10 items-center justify-center rounded-full border border-border bg-card text-text-2 shadow-lg transition-all motion-safe:duration-150 hover:border-accent hover:text-amber-600 motion-safe:hover:-translate-y-0.5"
    >
      <ArrowUp className="h-4 w-4" aria-hidden="true" />
    </button>
  );
}
