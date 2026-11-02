import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { parseDtcs } from "../api/tech";
import { jsonResponse, renderApp, TECH } from "../test/render";

afterEach(() => vi.unstubAllGlobals());

const RO = {
  id: "ro-3",
  ro_ref: "RO-2026-000003",
  status: "DIAGNOSING",
  vehicle: { id: "v3", model: "Aria", model_year: 2023, vin_masked: "***100004" },
  created_at: "2026-10-20T08:00:00Z",
  updated_at: "2026-10-20T09:00:00Z",
};
const DETAIL = {
  id: "ro-3",
  ro_ref: RO.ro_ref,
  status: "DIAGNOSING",
  dealer: { id: "d1", name: "Riverside (SYNTHETIC)" },
  vehicle: RO.vehicle,
  complaints: [{ text: "Rough idle after cold start.", confirmed_by_advisor: true }],
  check_in: null,
  promised_ready_at: null,
  timeline: [],
};
const CONTEXT = {
  vehicle_id: "v3", model: "Aria", model_year: 2023, decoded: null, in_service_date: null, service_history: [],
  maintenance_due: null, open_recalls: [], applicable_tsbs: [], warranty_coverage: [], risk_flags: [],
};
const cite = (section_id: string, quote: string) => ({
  chunk_id: section_id, source_file: "service_manual_aria.pdf", page: 1, section_id, section_title: section_id, quote,
});
const RESULT = {
  dtc_meanings: [
    { code: "P0301", meaning_quote: cite("dtc_reference#P0301", "P0301 Cylinder 1 misfire detected"), not_found: false },
    { code: "P0999", meaning_quote: null, not_found: true },
  ],
  hypotheses: [
    {
      rank: 1,
      cause: "Cylinder 1 coil connector clip not fully engaged",
      evidence: "Cold-start rough idle with P0301 matches the TSB symptom.",
      citations: [cite("TSB-AR-2024-01#TSB-AR-2024-01", "The cylinder 1 ignition coil connector locking clip may not fully engage")],
      confidence: 0.9,
      next_test: cite("TSB-AR-2024-01#TSB-AR-2024-01", "Replace the ignition coil connector clip and apply dielectric grease."),
    },
  ],
  matched_tsbs: [],
  insufficient_evidence: false,
  safety: { safety_critical: false, banner_tier: "none", banner_text: null, required_action_quote: null, escalation: null },
  ai_label: "AI-generated preliminary assessment — not a decision.",
  refusal_reason: null,
  dropped_hypotheses: 0,
};

function mockFetch() {
  return vi.fn().mockImplementation((url: string) => {
    if (url.includes("/diagnosis")) return Promise.resolve(jsonResponse(RESULT));
    if (url.endsWith("/findings") && url.includes("ro-3")) return Promise.resolve(jsonResponse([]));
    if (url.includes("/context")) return Promise.resolve(jsonResponse(CONTEXT));
    if (url.includes("status=DIAGNOSING")) return Promise.resolve(jsonResponse({ items: [RO], next_cursor: null }));
    return Promise.resolve(jsonResponse(DETAIL));
  });
}

describe("parseDtcs", () => {
  it("normalises, de-duplicates and flags invalid codes", () => {
    expect(parseDtcs("p0301, P0301 c0035;P03O1")).toEqual({ codes: ["P0301", "C0035", "P03O1"], invalid: ["P03O1"] });
  });
});

describe("TechCopilot", () => {
  it("blocks invalid DTCs, then shows cited hypotheses, unknown codes and the AI label", async () => {
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    renderApp("/tech", TECH);
    fireEvent.click(await screen.findByRole("button", { name: /RO-2026-000003/ }));
    const dtcs = await screen.findByLabelText(/DTCs/);

    fireEvent.change(dtcs, { target: { value: "P03O1" } });
    expect(screen.getByText(/Invalid format: P03O1/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run diagnosis" })).toBeDisabled();

    fireEvent.change(dtcs, { target: { value: "p0301 P0999" } });
    fireEvent.change(screen.getByLabelText("Symptoms"), { target: { value: "Rough idle when cold" } });
    fireEvent.click(screen.getByRole("button", { name: "Run diagnosis" }));

    expect(await screen.findByText(/Cylinder 1 coil connector clip not fully engaged/, { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText(/code not found in the DTC reference/)).toBeInTheDocument();
    expect(screen.getByText("AI-generated preliminary assessment — not a decision.")).toBeInTheDocument();
    expect(screen.getByText(/Next test: “Replace the ignition coil connector clip/)).toBeInTheDocument();

    const call = fetchMock.mock.calls.find((c: unknown[]) => String(c[0]).includes("/diagnosis"));
    expect(JSON.parse(String((call?.[1] as RequestInit).body))).toMatchObject({
      dtcs: ["P0301", "P0999"],
      symptoms: "Rough idle when cold",
    });
  });

  it("records the confirmed finding with an Idempotency-Key", async () => {
    const fetchMock = mockFetch();
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if (url.endsWith("/findings") && init?.method === "POST")
        return Promise.resolve(jsonResponse({ finding_id: "f1", replayed: false }));
      if (url.includes("/diagnosis")) return Promise.resolve(jsonResponse(RESULT));
      if (url.endsWith("/findings")) return Promise.resolve(jsonResponse([]));
      if (url.includes("/context")) return Promise.resolve(jsonResponse(CONTEXT));
      if (url.includes("status=DIAGNOSING")) return Promise.resolve(jsonResponse({ items: [RO], next_cursor: null }));
      return Promise.resolve(jsonResponse(DETAIL));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp("/tech", TECH);
    fireEvent.click(await screen.findByRole("button", { name: /RO-2026-000003/ }));
    fireEvent.change(await screen.findByLabelText(/DTCs/), { target: { value: "P0301" } });
    fireEvent.click(screen.getByRole("button", { name: "Run diagnosis" }));
    fireEvent.click(await screen.findByRole("radio", { name: /Cylinder 1 coil connector clip/ }));
    fireEvent.change(screen.getByLabelText("Op codes performed"), { target: { value: "op-tsb-ar01" } });
    fireEvent.change(screen.getByLabelText("Actual hours"), { target: { value: "0.6" } });
    fireEvent.change(screen.getByLabelText(/Parts used/), { target: { value: "VLX-IGN-CLIP-01 x 1" } });
    fireEvent.click(screen.getByRole("button", { name: "Save finding" }));
    await waitFor(() => expect(screen.getByText("Finding recorded.")).toBeInTheDocument());

    const call = fetchMock.mock.calls.find(
      (c: unknown[]) => String(c[0]).endsWith("/findings") && (c[1] as RequestInit | undefined)?.method === "POST",
    );
    const init = call?.[1] as RequestInit;
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
    expect(JSON.parse(String(init.body))).toEqual({
      confirmed_hypothesis: "Cylinder 1 coil connector clip not fully engaged",
      dtcs: ["P0301"],
      op_codes_performed: ["OP-TSB-AR01"],
      actual_hours: "0.6",
      parts_used: [{ part_number: "VLX-IGN-CLIP-01", qty: "1" }],
      notes: null,
    });
  });
});
