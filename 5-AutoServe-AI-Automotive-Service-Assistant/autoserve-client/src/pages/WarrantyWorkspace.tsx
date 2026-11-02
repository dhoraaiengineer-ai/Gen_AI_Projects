import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { z } from "zod";

import { api } from "../api/client";
import { ApiError } from "../api/envelope";
import { ClaimDecisionOutSchema, DraftSchema, FlagRowSchema, WorkspaceSchema, type FieldRow, type Workspace } from "../api/review";
import { useAuth } from "../auth/AuthContext";
import { AIAssessmentBanner, CitationChip } from "../components/Safety";
import { VehicleContextCard } from "../components/VehicleContextCard";

const TABS = ["Summary", "Vehicle Context", "Diagnosis", "Extracted Fields", "Warranty Rules", "Estimate", "Risk Indicators", "Audit Trail"] as const;
type Tab = (typeof TABS)[number];
const err = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);
const input = "mt-1 block min-h-tap w-full rounded border border-slate-300 px-2 dark:bg-slate-900";
const RESULT_STYLE: Record<string, string> = { pass: "text-green-800", fail: "text-red-800", unknown: "text-amber-800" };

function FieldEditor({ field, onSaved }: { field: FieldRow; onSaved: () => void }) {
  const [value, setValue] = useState(field.value ?? "");
  const [reason, setReason] = useState("");
  const save = useMutation({
    mutationFn: () =>
      api(`/api/v1/documents/${field.document_id}/fields/${field.id}`, z.record(z.unknown()), {
        method: "PATCH",
        body: { value, reason },
      }),
    onSuccess: onSaved,
  });
  return (
    <form aria-label={`Correct ${field.name}`} className="mt-1 flex flex-wrap items-end gap-2"
      onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <label className="text-xs">
        New value
        <input value={value} onChange={(e) => setValue(e.target.value)} className={input} />
      </label>
      <label className="text-xs">
        Reason
        <input value={reason} onChange={(e) => setReason(e.target.value)} className={input} />
      </label>
      <button type="submit" disabled={reason.trim().length < 3 || save.isPending}
        className="min-h-tap rounded border border-blue-700 px-3 text-sm disabled:opacity-60">
        Save correction
      </button>
      {save.isError && <span role="alert" className="text-xs text-red-700">{err(save.error, "Save failed")}</span>}
    </form>
  );
}

function Decision({ claimId, ws, onDone }: { claimId: string; ws: Workspace; onDone: () => void }) {
  const [rationale, setRationale] = useState("");
  const [message, setMessage] = useState("");
  const [idemKey] = useState(() => crypto.randomUUID());
  const [partNo, setPartNo] = useState(String(ws.summary.failed_part_number ?? ""));
  const [partReason, setPartReason] = useState("");
  const draft = useMutation({
    mutationFn: () => api(`/api/v1/warranty/claims/${claimId}/return-message/draft`, DraftSchema, { body: {} }),
    onSuccess: (d) => setMessage(d.draft),
  });
  const correct = useMutation({
    mutationFn: () =>
      api(`/api/v1/warranty/claims/${claimId}`, z.record(z.string()), {
        method: "PATCH",
        body: { field: "failed_part_number", value: partNo, reason: partReason },
      }),
    onSuccess: onDone,
  });
  const decide = useMutation({
    mutationFn: (decision: string) =>
      api(`/api/v1/warranty/claims/${claimId}/decision`, ClaimDecisionOutSchema, {
        idempotencyKey: `${idemKey}-${decision.replace(/_/g, "")}`.slice(0, 64), // keys allow [A-Za-z0-9-] only
        body: { decision, rationale, approved_message: decision === "return_for_info" ? message : undefined },
      }),
    onSuccess: onDone,
  });
  if (ws.allowed_decisions.length === 0) return null;
  return (
    <section aria-label="Decision" className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:bg-slate-800">
      <h2 className="text-lg font-semibold">Your decision</h2>
      <p className="text-xs text-slate-600">AI findings above are preliminary. You decide; a rationale is required.</p>
      <form aria-label="Correct claim part" className="mt-2 flex flex-wrap items-end gap-2"
        onSubmit={(e) => { e.preventDefault(); correct.mutate(); }}>
        <label className="text-sm">
          Failed part number
          <input value={partNo} onChange={(e) => setPartNo(e.target.value.toUpperCase())} className={input} />
        </label>
        <label className="text-sm">
          Correction reason
          <input value={partReason} onChange={(e) => setPartReason(e.target.value)} className={input} />
        </label>
        <button type="submit" disabled={partReason.trim().length < 3 || correct.isPending}
          className="min-h-tap rounded border border-blue-700 px-3 text-sm disabled:opacity-60">
          Correct field
        </button>
        {correct.isSuccess && <span className="text-sm text-green-800">Field corrected.</span>}
      </form>
      <label className="mt-3 block text-sm">
        Rationale
        <textarea value={rationale} onChange={(e) => setRationale(e.target.value)} rows={2} maxLength={2000} className={`${input} py-1`} />
      </label>
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" disabled={!rationale.trim() || decide.isPending} onClick={() => decide.mutate("submit_to_oem")}
          className="min-h-tap rounded bg-blue-700 px-4 font-medium text-white disabled:opacity-60">
          Submit to OEM (DEMO)
        </button>
        <button type="button" disabled={!rationale.trim() || decide.isPending} onClick={() => decide.mutate("reject_by_dealer")}
          className="min-h-tap rounded border border-red-700 px-4 text-red-800 disabled:opacity-60">
          Reject (dealer)
        </button>
        <button type="button" disabled={draft.isPending} onClick={() => draft.mutate()}
          className="min-h-tap rounded border border-slate-500 px-4 disabled:opacity-60">
          Draft "return for info" message
        </button>
      </div>
      {message && (
        <div className="mt-3">
          <AIAssessmentBanner />
          <label className="block text-sm">
            Message to the dealer (edit and approve — never sent automatically)
            <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={3} className={`${input} py-1`} />
          </label>
          <button type="button" disabled={!rationale.trim() || !message.trim() || decide.isPending}
            onClick={() => decide.mutate("return_for_info")}
            className="mt-2 min-h-tap rounded border border-amber-700 px-4 text-amber-900 disabled:opacity-60">
            Approve message and return for info
          </button>
        </div>
      )}
      {(decide.isError || draft.isError || correct.isError) && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {err(decide.error ?? draft.error ?? correct.error, "The action failed.")}
        </p>
      )}
    </section>
  );
}

function FlagReview({ flagId, onDone }: { flagId: string; onDone: () => void }) {
  const [note, setNote] = useState("");
  const review = useMutation({
    mutationFn: (status: string) => api(`/api/v1/risk-flags/${flagId}/review`, FlagRowSchema, { body: { status, note } }),
    onSuccess: onDone,
  });
  return (
    <div className="mt-1 flex flex-wrap items-end gap-2">
      <label className="text-xs">
        Review note
        <input value={note} onChange={(e) => setNote(e.target.value)} className={input} />
      </label>
      {["reviewed", "dismissed"].map((s) => (
        <button key={s} type="button" disabled={note.trim().length < 3} onClick={() => review.mutate(s)}
          className="min-h-tap rounded border px-3 text-sm disabled:opacity-60">
          Mark {s}
        </button>
      ))}
    </div>
  );
}

export function WarrantyWorkspace() {
  const { id } = useParams();
  const { me } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("Summary");
  const ws = useQuery({ queryKey: ["claim", id], queryFn: () => api(`/api/v1/warranty/claims/${id}`, WorkspaceSchema) });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["claim", id] });
  if (ws.isLoading) return <p className="p-6">Loading…</p>;
  if (ws.isError || !ws.data) return <p className="p-6">Claim not found.</p>;
  const d = ws.data;
  const s = d.summary;
  const isAdmin = me?.role === "warranty_admin";
  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-5xl p-4">
      <h1 id="page-title" className="text-2xl font-semibold">
        Claim {String(s.claim_ref)} · <span className="text-base">{String(s.status).replace(/_/g, " ").toLowerCase()}</span>
      </h1>
      <p className="text-sm">
        RO <Link to={`/ro/${String(s.ro_id)}`} className="underline">{String(s.ro_ref)}</Link> · {String(s.component_group ?? "—")} ·
        part {String(s.failed_part_number ?? "—")} · claimed {String(s.total_claimed ?? "—")}
      </p>
      <div role="tablist" aria-label="Claim workspace" className="mt-3 flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`min-h-tap rounded px-3 text-sm ${tab === t ? "bg-slate-800 text-white" : "bg-slate-100 dark:bg-slate-700"}`}>
            {t}
          </button>
        ))}
      </div>
      <div role="tabpanel" aria-label={tab} className="mt-3 rounded-lg bg-white p-4 shadow dark:bg-slate-800">
        {tab === "Summary" && (
          <div className="text-sm">
            <p>Complaint: “{String(s.complaint)}”</p>
            <p>RO status: {String(s.ro_status).replace(/_/g, " ").toLowerCase()}</p>
            <p>Open risk indicators: {d.risk_indicators.filter((f) => f.status === "open").map((f) => f.detector_id).join(", ") || "none"}</p>
            <p>Checklist: {Object.entries(d.checklist).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(" · ") || "—"}</p>
            {s.oem_ack ? <p>OEM acknowledgement (DEMO): {JSON.stringify(s.oem_ack)}</p> : null}
          </div>
        )}
        {tab === "Vehicle Context" && <VehicleContextCard ctx={d.vehicle_context} />}
        {tab === "Diagnosis" && (
          <div className="text-sm">
            <p>Technician confirmation: {String(d.diagnosis.technician_confirmation ?? "—")}</p>
            <p>Op codes: {(d.diagnosis.op_codes as string[]).join(", ") || "—"} · actual hours {String(d.diagnosis.actual_hours ?? "—")}</p>
            <p>DTCs: {(d.diagnosis.dtcs as string[]).join(", ") || "none"}</p>
          </div>
        )}
        {tab === "Extracted Fields" && (
          <ul className="space-y-3 text-sm">
            {d.extracted_fields.length === 0 && <li>No extracted fields.</li>}
            {d.extracted_fields.map((f) => (
              <li key={f.id}>
                <strong>{f.name}</strong> ({f.doc_class}, p.{f.source_page}): {f.value ?? "—"}{" "}
                <span className="text-xs text-slate-500">confidence {Math.round(f.confidence * 100)}% · {f.validation_status}</span>
                {f.needs_human_verification && <span className="ml-1 rounded bg-amber-100 px-1 text-xs">verify</span>}
                {f.previous_value != null && <span className="block text-xs">was “{f.previous_value}” — {f.edit_reason}</span>}
                {isAdmin && <FieldEditor field={f} onSaved={refresh} />}
              </li>
            ))}
          </ul>
        )}
        {tab === "Warranty Rules" && (
          <>
            <AIAssessmentBanner />
            <p className="text-xs text-slate-500">Preliminary assessment — deterministic rules with the booklet clause each one cites.</p>
            <ul className="mt-2 space-y-2 text-sm">
              {d.warranty_rules.map((r) => (
                <li key={r.rule_id}>
                  <strong>{r.rule_id}</strong> <span className={RESULT_STYLE[r.result]}>{r.result}</span>{" "}
                  <span className="text-xs text-slate-500">{JSON.stringify(r.inputs)}</span>
                  {r.clause && <CitationChip citation={r.clause} />}
                </li>
              ))}
            </ul>
          </>
        )}
        {tab === "Estimate" && (
          <ul className="text-sm">
            {d.estimate.map((l, i) => (
              <li key={i}>
                {l.kind} {l.code ?? ""} — {l.description}: {l.amount} ({l.pay_type}
                {l.owner_decision ? `, owner ${l.owner_decision}` : ""})
              </li>
            ))}
          </ul>
        )}
        {tab === "Risk Indicators" && (
          <ul className="space-y-3 text-sm">
            {d.risk_indicators.length === 0 && <li>No indicators for review.</li>}
            {d.risk_indicators.map((f) => (
              <li key={f.id}>
                <strong>{f.detector_id}</strong> · {f.severity} · {f.status}
                <p>{f.explanation}</p>
                <p className="text-xs text-slate-500">{JSON.stringify(f.evidence)}</p>
                {f.status === "open" && <FlagReview flagId={f.id} onDone={refresh} />}
              </li>
            ))}
          </ul>
        )}
        {tab === "Audit Trail" && (
          <ol className="text-sm">
            {d.audit_trail.map((a) => (
              <li key={a.seq}>
                #{a.seq} {new Date(a.occurred_at).toLocaleString()} · {a.actor_role.replace(/_/g, " ")} · {a.action}
                {a.summary ? ` — ${a.summary}` : ""}
              </li>
            ))}
          </ol>
        )}
      </div>
      {isAdmin && <Decision claimId={id ?? ""} ws={d} onDone={refresh} />}
    </section>
  );
}
