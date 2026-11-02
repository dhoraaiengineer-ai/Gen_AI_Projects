import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/client";
import { ApiError } from "../api/envelope";
import {
  DecisionOutSchema,
  EstimateViewSchema,
  SendOutSchema,
  TransitionOutSchema,
  WorkflowRunSchema,
  type EstimateLine,
} from "../api/review";
import type { Me } from "../api/schemas";
import { AIAssessmentBanner } from "./Safety";

const STATUS_TEXT: Record<EstimateLine["display_status"], string> = {
  decision_needed: "Your decision",
  pending_warranty_review: "Pending warranty review",
  recall: "Recall — no charge",
  tax: "Tax",
};
const err = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const key = () => crypto.randomUUID();

/** Estimate + the actions each role may take on it (P3-9). Owners decide customer-pay lines only (OD-03). */
export function EstimatePanel({ roId, roStatus, role }: { roId: string; roStatus: string; role: Me["role"] }) {
  const qc = useQueryClient();
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["estimate", roId] });
    void qc.invalidateQueries({ queryKey: ["repair-order", roId] });
  };
  const est = useQuery({
    queryKey: ["estimate", roId],
    queryFn: () => api(`/api/v1/repair-orders/${roId}/estimate`, EstimateViewSchema),
  });
  const [choices, setChoices] = useState<Record<string, "approved" | "declined">>({});
  const [consent, setConsent] = useState("");
  const [runKey] = useState(key);
  const [decisionKey, setDecisionKey] = useState(key);

  const run = useMutation({
    mutationFn: () => api(`/api/v1/repair-orders/${roId}/workflow/run`, WorkflowRunSchema, { body: {}, idempotencyKey: runKey }),
    onSuccess: refresh,
  });
  const send = useMutation({
    mutationFn: () => api(`/api/v1/repair-orders/${roId}/estimate/send`, SendOutSchema, { body: {}, idempotencyKey: key() }),
    onSuccess: refresh,
  });
  const decide = useMutation({
    mutationFn: () =>
      api(`/api/v1/repair-orders/${roId}/estimate/decision`, DecisionOutSchema, {
        idempotencyKey: decisionKey,
        body: {
          line_decisions: Object.entries(choices).map(([line_id, decision]) => ({ line_id, decision })),
          consent_note: role === "service_advisor" ? consent : undefined,
        },
      }),
    onSuccess: () => {
      setDecisionKey(key());
      refresh();
    },
  });
  const startRepair = useMutation({
    mutationFn: () =>
      api(`/api/v1/repair-orders/${roId}/transition`, TransitionOutSchema, {
        body: { to: "IN_REPAIR", note: "Repair started" },
        idempotencyKey: key(),
      }),
    onSuccess: refresh,
  });

  const lines = est.data?.lines ?? [];
  const customer = lines.filter((l) => l.display_status === "decision_needed");
  const canDecide =
    roStatus === "AWAITING_OWNER_APPROVAL" && (role === "vehicle_owner" || role === "service_advisor") && customer.length > 0;
  const allChosen = customer.every((l) => choices[l.id]);
  const busy = run.isPending || send.isPending || decide.isPending || startRepair.isPending;
  const failure = [run, send, decide, startRepair].find((m) => m.isError)?.error;

  return (
    <section aria-label="Estimate" className="mt-6 rounded-lg bg-white p-4 shadow dark:bg-slate-800">
      <h2 className="text-lg font-semibold">Estimate</h2>
      {role === "service_advisor" && ["DIAGNOSING", "INFO_PENDING", "ESTIMATE_READY"].includes(roStatus) && (
        <button type="button" disabled={busy} onClick={() => run.mutate()}
          className="mt-2 min-h-tap rounded border border-blue-700 px-3 text-sm text-blue-800 dark:text-blue-200">
          {run.isPending ? "Running workflow…" : "Run warranty & estimate workflow"}
        </button>
      )}
      {run.data && (
        <p className="mt-2 text-sm">
          Route: <strong>{run.data.route?.replace(/_/g, " ")}</strong> — {run.data.reasons.join("; ")}
          {run.data.claim ? ` · claim ${run.data.claim.claim_ref} (${run.data.claim.status.replace(/_/g, " ").toLowerCase()})` : ""}
        </p>
      )}
      {lines.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          {role === "vehicle_owner" ? "Your service advisor has not sent an estimate yet." : "No estimate lines yet."}
        </p>
      ) : (
        <>
          <AIAssessmentBanner />
          <table className="mt-2 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700">
                <th className="py-1">Item</th>
                <th>Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((l) => (
                <tr key={l.id} className="border-b border-slate-100 align-top dark:border-slate-700">
                  <td className="py-2">
                    {l.description}
                    <span className="block text-xs text-slate-500">
                      {l.op_code ?? l.part_number ?? ""} {l.hours ? `· ${l.hours} h` : `· qty ${l.qty}`}
                    </span>
                  </td>
                  <td>{l.amount}</td>
                  <td>
                    {l.display_status === "decision_needed" && canDecide ? (
                      <fieldset aria-label={`Decision for ${l.description}`} className="flex gap-2">
                        {(["approved", "declined"] as const).map((d) => (
                          <label key={d} className="flex min-h-tap items-center gap-1">
                            <input type="radio" name={`line-${l.id}`} checked={choices[l.id] === d}
                              onChange={() => setChoices((c) => ({ ...c, [l.id]: d }))} className="h-5 w-5" />
                            {d === "approved" ? "Approve" : "Decline"}
                          </label>
                        ))}
                      </fieldset>
                    ) : (
                      <span>{l.owner_decision ? l.owner_decision : STATUS_TEXT[l.display_status]}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-sm">
            Customer-pay {est.data?.totals.customer} + tax {est.data?.totals.tax} · warranty (pending review){" "}
            {est.data?.totals.warranty} · recall {est.data?.totals.recall} · total {est.data?.totals.grand}
          </p>
        </>
      )}
      {canDecide && role === "service_advisor" && (
        <label className="mt-2 block text-sm">
          Consent note (required — e.g. "Owner approved by phone at 10:42")
          <input value={consent} onChange={(e) => setConsent(e.target.value)} maxLength={2000}
            className="mt-1 block min-h-tap w-full rounded border border-slate-300 px-2 dark:bg-slate-900" />
        </label>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {role === "service_advisor" && roStatus === "ESTIMATE_READY" && lines.length > 0 && (
          <button type="button" disabled={busy} onClick={() => send.mutate()}
            className="min-h-tap rounded bg-blue-700 px-4 font-medium text-white disabled:opacity-60">
            Send estimate to owner
          </button>
        )}
        {canDecide && (
          <button type="button" disabled={busy || !allChosen || (role === "service_advisor" && !consent.trim())}
            onClick={() => decide.mutate()}
            className="min-h-tap rounded bg-blue-700 px-4 font-medium text-white disabled:opacity-60">
            {role === "service_advisor" ? "Record owner's decision" : "Submit my decision"}
          </button>
        )}
        {(role === "service_advisor" || role === "technician") && roStatus === "APPROVED" && (
          <button type="button" disabled={busy} onClick={() => startRepair.mutate()}
            className="min-h-tap rounded bg-green-700 px-4 font-medium text-white disabled:opacity-60">
            Start repair
          </button>
        )}
      </div>
      {failure && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {err(failure, "The action failed.")}
        </p>
      )}
    </section>
  );
}
