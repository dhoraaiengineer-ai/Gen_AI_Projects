"use client";

/**
 * Theme provider (ADR-010, 24-Jul-2026) -- thin next-themes wrapper.
 *
 * defaultTheme="light" + enableSystem={false} is deliberate: ADR-008 (the
 * only accepted theme ADR) mandates light as the explicit platform default,
 * not "match the visitor's OS preference." attribute="class" matches
 * tailwind.config.ts's pre-existing `darkMode: "class"` setting, which was
 * configured but never wired to an actual toggle until this change.
 */

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

export function ThemeProvider({
  children,
  ...props
}: ComponentProps<typeof NextThemesProvider>) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
