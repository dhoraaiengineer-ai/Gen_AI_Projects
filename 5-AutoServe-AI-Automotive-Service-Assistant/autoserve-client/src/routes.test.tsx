import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ROUTES } from "./routeTable";
import { ADVISOR, OWNER, jsonResponse, renderApp } from "./test/render";

afterEach(() => vi.unstubAllGlobals());

describe("routes and guards", () => {
  it("keeps every route from the contract", () => {
    expect(ROUTES.map((r) => r.path)).toEqual([
      "/login", "/chat", "/vehicles", "/ro/:id", "/advisor", "/tech", "/warranty", "/warranty/:id", "/admin",
    ]);
  });

  it("redirects / and protected pages to sign-in when logged out", () => {
    renderApp("/chat");
    expect(screen.getByRole("heading", { level: 1, name: "Sign in" })).toBeInTheDocument();
  });

  it("shows the owner chat to an owner", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ items: [], next_cursor: null })));
    renderApp("/chat", OWNER);
    expect(screen.getByRole("heading", { level: 1, name: "Owner chat" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Chat" })).toBeInTheDocument();
  });

  it("blocks staff from owner pages (navigation only; the API enforces too)", () => {
    renderApp("/chat", ADVISOR);
    expect(screen.getByRole("alert")).toHaveTextContent("cannot open this page");
  });

  it("shows the synthetic-data DEMO label everywhere", () => {
    renderApp("/login");
    expect(screen.getByText(/SYNTHETIC DATA — DEMO/)).toBeInTheDocument();
  });

  it("renders a not-found page", () => {
    renderApp("/nope", OWNER);
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
  });
});
