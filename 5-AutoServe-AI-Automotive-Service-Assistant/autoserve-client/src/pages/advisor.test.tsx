import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ADVISOR, jsonResponse, renderApp } from "../test/render";

afterEach(() => vi.unstubAllGlobals());

const ITEM = {
  appointment_id: "a1",
  ro_id: "ro-1",
  ro_ref: "RO-2026-000011",
  ro_status: "BOOKED",
  slot_start: "2026-10-28T09:00:00+00:00",
  vehicle_id: "v1",
  model: "Aria",
  model_year: 2023,
  vin_masked: "***100004",
  owner_display_name: "Kabir (SYNTHETIC)",
  complaint_text: "Clunk from the rear suspension over bumps.",
};

const CONTEXT = {
  vehicle_id: "v1",
  model: "Aria",
  model_year: 2023,
  decoded: { wmi: "VLX", model: "Aria", model_year: 2023, plant: "M", serial: "100004" },
  in_service_date: "2023-03-15",
  service_history: [{ date: "2026-03-20", odometer_km: 27100, op_codes: ["OP-SVC-STD"], dealer_name: "Riverside" }],
  maintenance_due: null,
  open_recalls: [],
  applicable_tsbs: [],
  warranty_coverage: [],
  risk_flags: [
    {
      id: "f1",
      detector_id: "D-01",
      severity: "high",
      evidence: {},
      explanation: "Indicator for review: an odometer reading is lower than an earlier recorded reading.",
      status: "open",
    },
  ],
};

describe("AdvisorBoard", () => {
  it("checks in a booked RO with an Idempotency-Key and shows the D-01 indicator", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        url.includes("/check-in")
          ? jsonResponse({ ro_id: "ro-1", ro_ref: ITEM.ro_ref, status: "CHECKED_IN", vehicle_context: CONTEXT, replayed: false })
          : jsonResponse({ items: [ITEM], next_cursor: null }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderApp("/advisor", ADVISOR);
    fireEvent.click(await screen.findByRole("button", { name: "Start check-in" }));
    fireEvent.change(screen.getByLabelText("Odometer (km)"), { target: { value: "28000" } });
    fireEvent.click(screen.getByLabelText(/complaint confirmed/));
    fireEvent.click(screen.getByRole("button", { name: "Check in" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("D-01 · high — Indicator for review"));

    const call = fetchMock.mock.calls.find((c: unknown[]) => String(c[0]).includes("/check-in"));
    const init = call?.[1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
    expect(JSON.parse(String(init.body))).toEqual({
      odometer_in_km: 28000,
      fuel_or_charge_level: "1/2 tank",
      damage_notes: "",
      complaint_confirmed: true,
    });
  });
});
