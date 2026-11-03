"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * TanStack Query provider — required by components/documents/* (F-17), which
 * calls useQuery/useMutation/useQueryClient without any provider ever having
 * been wired up (a pre-existing gap, not introduced by this change).
 * One QueryClient per browser session (useState lazy-init, not per-render).
 */
export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => new QueryClient());
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
