import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { jsonResponse, OWNER, renderApp, WADMIN } from "../test/render";

afterEach(() => vi.unstubAllGlobals());

const RO = {
  id: "ro-9",
  ro_ref: "RO-2026-000099",
  status: "AWAITING_OWNER_APPROVAL",
  dealer: { id: "d1", name: "Northgate (SYNTHETIC)" },
  vehicle: { id: "v9", model: "Terra", model_year: 2021, vin_masked: "***100002" },
  complaints: [{ text: "Grinding noise when braking.", confirmed_by_advisor: true }],
  check_in: null,
  promised_ready_at: null,
  timeline: [],
};
const line = (id: string, kind: string, code: string, pay: string, status: string, amount: string) => ({
  id, kind, op_code: kind === "labour" ? code : null, part_number: kind === "part" ? code : null,
  description: `${code} (SYNTHETIC)`, qty: "1", hours: kind === "labour" ? "1.40" : null, unit_price: amount,
  amount, pay_type: pay, display_status: status, owner_decision: null,
});
const ESTIMATE = {
  estimable: true,
  lines: [
    line("l1", "labour", "OP-BRK-PAD-FR", "customer", "decision_needed", "3360.00"),
    line("l2", "part", "VLX-BRK-PAD-TR", "customer", "decision_needed", "5600.00"),
    line("l3", "part", "VLX-FL-CLIP-02", "recall", "recall", "240.00"),
  ],
  totals: { warranty: "0.00", recall: "240.00", customer: "8960.00", tax: "1612.80", grand: "10812.80" },
  ro_status: "AWAITING_OWNER_APPROVAL",
  ai_label: "AI-generated preliminary assessment — not a decision.",
};

describe("Owner estimate approval", () => {
  it("decides customer-pay lines only and sends line decisions with an Idempotency-Key", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.endsWith("/estimate/decision")) return Promise.resolve(jsonResponse({ status: "APPROVED", decision_id: "d", replayed: false }));
      if (url.endsWith("/estimate")) return Promise.resolve(jsonResponse(ESTIMATE));
      return Promise.resolve(jsonResponse(RO));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp("/ro/ro-9", OWNER);
    expect(await screen.findByText("AI-generated preliminary assessment — not a decision.")).toBeInTheDocument();
    expect(screen.getByText("Recall — no charge")).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "Submit my decision" });
    expect(submit).toBeDisabled(); // every customer line needs a decision
    const groups = screen.getAllByRole("group", { name: /Decision for/ });
    expect(groups).toHaveLength(2);
    fireEvent.click(screen.getAllByLabelText("Approve")[0]);
    fireEvent.click(screen.getAllByLabelText("Decline")[1]);
    fireEvent.click(submit);
    await waitFor(() => expect(fetchMock.mock.calls.some((c: unknown[]) => String(c[0]).endsWith("/estimate/decision"))).toBe(true));
    const call = fetchMock.mock.calls.find((c: unknown[]) => String(c[0]).endsWith("/estimate/decision"));
    const init = call?.[1] as RequestInit;
    expect((init.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
    expect(JSON.parse(String(init.body)).line_decisions).toEqual([
      { line_id: "l1", decision: "approved" },
      { line_id: "l2", decision: "declined" },
    ]);
  });
});

const WORKSPACE = {
  summary: { claim_ref: "WC-2026-000002", status: "WARRANTY_REVIEW_REQUIRED", ro_id: "ro-5", ro_ref: "RO-2026-000016",
             ro_status: "ESTIMATE_READY", component_group: "engine", failed_part_number: "VLX-IGN-COIL-AR",
             total_claimed: "4760.00", complaint: "Misfire (SYNTHETIC)", oem_ack: null },
  vehicle_context: { vehicle_id: "v3", model: "Aria", model_year: 2023, decoded: null, in_service_date: null,
                     service_history: [], maintenance_due: null, open_recalls: [], applicable_tsbs: [],
                     warranty_coverage: [], risk_flags: [] },
  diagnosis: { technician_confirmation: "Ignition coil cylinder 1 faulty", dtcs: [], op_codes: ["OP-IGN-COIL"], actual_hours: "2.00", parts: [] },
  extracted_fields: [],
  checklist: { repair_order: "present" },
  warranty_rules: [{ rule_id: "W-PT-AGE", result: "pass", inputs: {}, clause: null }],
  estimate: [],
  risk_indicators: [{ id: "f1", detector_id: "D-04", severity: "medium", evidence: {}, status: "open",
                      explanation: "Indicator for review: labour claimed (2.00 h) is more than 10% above the flat-rate time (0.40 h)." }],
  audit_trail: [{ seq: 1, occurred_at: "2026-10-28T10:00:00Z", actor_role: "system", action: "warranty_claim.transition",
                  entity_type: "warranty_claim", summary: "PREPARED → WARRANTY_REVIEW_REQUIRED" }],
  allowed_decisions: ["submit_to_oem", "return_for_info", "reject_by_dealer"],
  ai_label: "AI-generated preliminary assessment — not a decision.",
};

describe("Warranty workspace", () => {
  it("requires a rationale and sends a valid Idempotency-Key for the decision", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        url.endsWith("/decision")
          ? jsonResponse({ status: "SUBMITTED_TO_OEM", decision_id: "x", oem_ack: { adapter: "DEMO" }, replayed: false })
          : jsonResponse(WORKSPACE),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderApp("/warranty/c1", WADMIN);
    fireEvent.click(await screen.findByRole("tab", { name: "Risk Indicators" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Indicator for review");
    const submit = screen.getByRole("button", { name: "Submit to OEM (DEMO)" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Rationale"), { target: { value: "Coverage confirmed (SYNTHETIC)." } });
    fireEvent.click(submit);
    await waitFor(() => expect(fetchMock.mock.calls.some((c: unknown[]) => String(c[0]).endsWith("/decision"))).toBe(true));
    const call = fetchMock.mock.calls.find((c: unknown[]) => String(c[0]).endsWith("/decision"));
    const key = ((call?.[1] as RequestInit).headers as Record<string, string>)["Idempotency-Key"];
    expect(key).toMatch(/^[A-Za-z0-9-]{8,64}$/);
    expect(JSON.parse(String((call?.[1] as RequestInit).body))).toMatchObject({ decision: "submit_to_oem" });
  });
});
