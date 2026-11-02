import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, useRoutes } from "react-router-dom";

import type { Me } from "../api/schemas";
import { AuthProvider } from "../auth/AuthContext";
import { routes } from "../routes";

function AppRoutes() {
  return useRoutes(routes);
}

export const OWNER: Me = { id: "u1", display_name: "Priya (SYNTHETIC)", role: "vehicle_owner", dealer_id: null };
export const ADVISOR: Me = { id: "u2", display_name: "Marco (SYNTHETIC)", role: "service_advisor", dealer_id: "d1" };
export const TECH: Me = { id: "u3", display_name: "Sam (SYNTHETIC)", role: "technician", dealer_id: "d1" };
export const WADMIN: Me = { id: "u4", display_name: "Lena (SYNTHETIC)", role: "warranty_admin", dealer_id: "d1" };

export function renderApp(path: string, user: Me | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider initialUser={user}>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

/** Minimal fetch Response stand-in for vi.stubGlobal("fetch", ...). */
export function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status < 400,
    status,
    json: async () => ({ status: status < 400 ? "ok" : "error", data, error: null, request_id: "t" }),
  };
}

export function sseResponse(events: { event: string; data: unknown }[]) {
  const text = events.map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`).join("");
  const bytes = new TextEncoder().encode(text);
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(bytes.slice(0, 7)); // split mid-event to exercise buffering
      controller.enqueue(bytes.slice(7));
      controller.close();
    },
  });
  return { ok: true, status: 200, body, json: async () => null };
}
