"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider, useTheme } from "next-themes";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/primitives";
import { ApiError } from "@/lib/api";
import { AuthProvider } from "@/lib/auth";
import { AuthGate } from "@/components/auth/auth-gate";

function ThemedToaster() {
  const { resolvedTheme } = useTheme();
  return <Toaster theme={resolvedTheme === "dark" ? "dark" : "light"} position="bottom-right" closeButton richColors={false} toastOptions={{ className: "!rounded-lg !border !shadow-raised" }} />;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            // Retry transient failures with exponential backoff; never retry client errors (4xx).
            retry: (count, err) => (err instanceof ApiError ? err.retryable && count < 2 : count < 2),
            retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
          },
        },
      }),
  );
  return (
    <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider delayDuration={250}>
          <AuthProvider>
            <AuthGate>{children}</AuthGate>
          </AuthProvider>
          <ThemedToaster />
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
