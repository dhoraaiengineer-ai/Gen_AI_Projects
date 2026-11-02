import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { readSse } from "../api/client";
import type { SafetyInfo } from "../api/schemas";
import { SafetyBanner } from "../components/Safety";
import { OWNER, jsonResponse, renderApp, sseResponse } from "../test/render";
import { render } from "@testing-library/react";

afterEach(() => vi.unstubAllGlobals());

const STOP: SafetyInfo = {
  safety_critical: true,
  banner_tier: "stop",
  banner_text: "⚠ SAFETY-CRITICAL: Stop safely when it is safe to do so and contact Veloxa service.",
  required_action_quote: {
    chunk_id: "c1",
    source_file: "owner_manual_terra.pdf",
    page: 1,
    section_id: "owner_manual_terra#3.2",
    section_title: "Brake system warning light (red)",
    quote: "If the light stays on after releasing the parking brake, stop safely when it is safe to do so.",
  },
  escalation: "I recommend having this checked by a certified technician.",
};

describe("SafetyBanner", () => {
  it("renders the server text, the cited required action, and escalation", () => {
    render(<SafetyBanner safety={STOP} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("SAFETY-CRITICAL");
    expect(alert).toHaveTextContent("The manual says");
    expect(alert).toHaveTextContent("Brake system warning light (red) · owner_manual_terra.pdf p.1");
    expect(alert).toHaveTextContent("certified technician");
  });

  it("renders nothing for tier none", () => {
    const { container } = render(
      <SafetyBanner safety={{ safety_critical: false, banner_tier: "none", banner_text: null }} />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("readSse", () => {
  it("parses events split across chunks", async () => {
    const resp = sseResponse([
      { event: "token", data: { text: "Hello " } },
      { event: "final", data: { ok: true } },
    ]);
    const events = [];
    for await (const e of readSse(resp.body)) events.push(e);
    expect(events).toEqual([
      { event: "token", data: { text: "Hello " } },
      { event: "final", data: { ok: true } },
    ]);
  });
});

describe("Login", () => {
  it("signs an owner in and lands on the chat", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) =>
        Promise.resolve(
          url.endsWith("/auth/login")
            ? jsonResponse({ access_token: "t", token_type: "bearer", expires_in: 3600, user: OWNER })
            : jsonResponse({ items: [], next_cursor: null }),
        ),
      ),
    );
    renderApp("/login");
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "owner.priya@example.test" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Owner chat" })).toBeInTheDocument();
  });
});

describe("OwnerChat", () => {
  it("streams a reply and shows the safety banner and citation chips", async () => {
    const reply = {
      conversation_id: "conv-1",
      intent: "manual_question",
      reply: "The brake fluid level may be low.",
      citations: [STOP.required_action_quote],
      safety: STOP,
      insufficient_evidence: false,
      options: [],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) =>
        Promise.resolve(
          url.startsWith("/api/v1/chat/messages")
            ? sseResponse([
                { event: "meta", data: { intent: "manual_question" } },
                { event: "token", data: { text: "The brake fluid " } },
                { event: "token", data: { text: "level may be low." } },
                { event: "final", data: { status: "ok", data: reply, error: null, request_id: "r" } },
              ])
            : jsonResponse({
                items: [{ id: "v1", vin_masked: "***100003", model: "Terra", model_year: 2022, plate_masked: null, last_odometer_km: 1 }],
                next_cursor: null,
              }),
        ),
      ),
    );
    renderApp("/chat", OWNER);
    await screen.findByRole("option", { name: /Veloxa Terra 2022/ });
    fireEvent.change(screen.getByLabelText("Message"), { target: { value: "Can I keep driving with the brake light on?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(screen.getByText("The brake fluid level may be low.")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent("SAFETY-CRITICAL");
    expect(screen.getAllByText(/owner_manual_terra.pdf p.1/).length).toBeGreaterThan(0);
    const call = (fetch as unknown as { mock: { calls: [string, RequestInit][] } }).mock.calls.find(([u]) =>
      u.startsWith("/api/v1/chat/messages"),
    );
    expect(JSON.parse(String(call?.[1].body))).toMatchObject({ vehicle_id: "v1" });
  });
});
