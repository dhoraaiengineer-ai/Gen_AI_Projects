import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { VehicleContextSchema } from "../api/advisor";
import { api } from "../api/client";
import { ApiError } from "../api/envelope";
import { pageSchema, RODetailSchema, ROSummarySchema, type ROSummary } from "../api/schemas";
import {
  DiagnosisResultSchema,
  FindingOutSchema,
  FindingSummarySchema,
  parseDtcs,
  type DiagnosisResult,
} from "../api/tech";
import { AIAssessmentBanner, CitationChip, SafetyBanner } from "../components/Safety";
import { VehicleContextCard } from "../components/VehicleContextCard";

const input = "mt-1 block min-h-tap w-full rounded border border-slate-300 px-2 dark:bg-slate-900";
type TestRow = { name: string; value: string; unit: string };
const errText = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

function DiagnosisPanel({ result }: { result: DiagnosisResult }) {
  return (
    <section aria-label="Diagnosis" className="mt-4 rounded-lg bg-white p-4 shadow dark:bg-slate-800">
      <SafetyBanner safety={result.safety} />
      {result.refusal_reason === "bypass_request" ? (
        <p role="alert" className="font-medium text-red-800">
          Request refused: disabling or bypassing safety or emissions systems is not supported. The refusal was logged.
        </p>
      ) : (
        <>
          <AIAssessmentBanner />
          <h2 className="mt-2 text-lg font-semibold">DTC meanings</h2>
          <ul className="text-sm">
            {result.dtc_meanings.map((m) => (
              <li key={m.code}>
                <strong>{m.code}</strong>{" "}
                {m.not_found || !m.meaning_quote ? (
                  <span className="text-amber-800">— code not found in the DTC reference</span>
                ) : (
                  <>
                    “{m.meaning_quote.quote}” <CitationChip citation={m.meaning_quote} />
                  </>
                )}
              </li>
            ))}
            {result.dtc_meanings.length === 0 && <li className="text-slate-600">No DTCs entered.</li>}
          </ul>

          {result.matched_tsbs.length > 0 && (
            <>
              <h2 className="mt-3 text-lg font-semibold">Matching TSBs</h2>
              <ul className="text-sm">
                {result.matched_tsbs.map((t) => (
                  <li key={t.tsb_code}>
                    <strong>{t.tsb_code}</strong> {t.title} · op {t.op_code ?? "—"} · matched on {t.match_reason}:{" "}
                    {t.matched_terms.join(", ")} {t.source && <CitationChip citation={t.source} />}
                  </li>
                ))}
              </ul>
            </>
          )}

          <h2 className="mt-3 text-lg font-semibold">Ranked hypotheses</h2>
          {result.insufficient_evidence ? (
            <p className="text-sm text-slate-700 dark:text-slate-300">
              {result.refusal_reason === "service_unavailable"
                ? "The AI assessment is unavailable right now. DTC meanings and TSBs above are from the reference data."
                : "Not enough evidence in the service documentation for a cited hypothesis. Follow the DTC reference."}
            </p>
          ) : (
            <ol className="space-y-3">
              {result.hypotheses.map((h) => (
                <li key={h.rank} className="rounded border border-slate-200 p-3 dark:border-slate-700">
                  <p className="font-medium">
                    {h.rank}. {h.cause}{" "}
                    <span className="text-xs text-slate-500">confidence {Math.round(h.confidence * 100)}%</span>
                  </p>
                  <p className="text-sm">{h.evidence}</p>
                  <p className="mt-1 text-xs">
                    Sources:{" "}
                    {h.citations.map((c, i) => (
                      <CitationChip key={`${c.chunk_id}-${i}`} citation={c} />
                    ))}
                  </p>
                  {h.next_test && (
                    <p className="mt-1 text-sm">
                      Next test: “{h.next_test.quote}” <CitationChip citation={h.next_test} />
                    </p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </section>
  );
}

function FindingForm({ roId, result, dtcs }: { roId: string; result: DiagnosisResult | null; dtcs: string[] }) {
  const qc = useQueryClient();
  const [choice, setChoice] = useState("");
  const [other, setOther] = useState("");
  const [ops, setOps] = useState("");
  const [hours, setHours] = useState("");
  const [parts, setParts] = useState("");
  const [notes, setNotes] = useState("");
  const [idemKey, setIdemKey] = useState(() => crypto.randomUUID());
  const confirmed = choice === "__other" ? other.trim() : choice;
  const mutation = useMutation({
    mutationFn: () =>
      api(`/api/v1/repair-orders/${roId}/findings`, FindingOutSchema, {
        idempotencyKey: idemKey,
        body: {
          confirmed_hypothesis: confirmed,
          dtcs,
          op_codes_performed: ops.split(/[\s,;]+/).filter(Boolean),
          actual_hours: hours,
          parts_used: parts
            .split(/[\n,;]+/)
            .map((p) => p.trim())
            .filter(Boolean)
            .map((p) => {
              const m = /^(\S+?)\s*(?:[x×]\s*|\s)(\d+(?:\.\d+)?)$/i.exec(p); // "VLX-AC-RLY-03 x 2" / "VLX-AC-RLY-03 2"
              return m ? { part_number: m[1], qty: m[2] } : { part_number: p, qty: "1" };
            }),
          notes: notes || null,
        },
      }),
    onSuccess: () => {
      setIdemKey(crypto.randomUUID());
      void qc.invalidateQueries({ queryKey: ["findings", roId] });
    },
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }
  return (
    <form onSubmit={submit} aria-label="Record finding" className="mt-4 rounded-lg bg-white p-4 shadow dark:bg-slate-800">
      <h2 className="text-lg font-semibold">Record your finding</h2>
      <p className="text-xs text-slate-500">You decide. The confirmed cause becomes feedback data for evaluation.</p>
      <fieldset className="mt-2 space-y-1 text-sm">
        <legend className="font-medium">Confirmed cause</legend>
        {result?.hypotheses.map((h) => (
          <label key={h.rank} className="flex min-h-tap items-center gap-2">
            <input type="radio" name="confirmed" value={h.cause} checked={choice === h.cause}
              onChange={() => setChoice(h.cause)} className="h-5 w-5" />
            {h.rank}. {h.cause}
          </label>
        ))}
        <label className="flex min-h-tap items-center gap-2">
          <input type="radio" name="confirmed" value="__other" checked={choice === "__other"}
            onChange={() => setChoice("__other")} className="h-5 w-5" />
          Other (describe)
        </label>
        {choice === "__other" && (
          <input aria-label="Other cause" required minLength={3} maxLength={500} value={other}
            onChange={(e) => setOther(e.target.value)} className={input} />
        )}
      </fieldset>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        <label className="text-sm">
          Op codes performed
          <input value={ops} onChange={(e) => setOps(e.target.value.toUpperCase())} placeholder="OP-TSB-AR01"
            className={input} />
        </label>
        <label className="text-sm">
          Actual hours
          <input required inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,2})?" value={hours}
            onChange={(e) => setHours(e.target.value)} className={input} />
        </label>
        <label className="text-sm">
          Parts used (part × qty)
          <input value={parts} onChange={(e) => setParts(e.target.value.toUpperCase())} placeholder="VLX-AC-RLY-03 x 1"
            className={input} />
        </label>
        <label className="text-sm sm:col-span-3">
          Notes
          <input value={notes} maxLength={2000} onChange={(e) => setNotes(e.target.value)} className={input} />
        </label>
      </div>
      {mutation.isError && (
        <p role="alert" className="mt-2 text-sm text-red-700">
          {errText(mutation.error, "Could not record the finding.")}
        </p>
      )}
      {mutation.isSuccess && <p className="mt-2 text-sm text-green-800">Finding recorded.</p>}
      <button type="submit" disabled={mutation.isPending || confirmed.length < 3}
        className="mt-3 min-h-tap rounded bg-blue-700 px-4 font-medium text-white disabled:opacity-60">
        {mutation.isPending ? "Saving…" : "Save finding"}
      </button>
    </form>
  );
}

function Workbench({ ro }: { ro: ROSummary }) {
  const [dtcText, setDtcText] = useState("");
  const [symptoms, setSymptoms] = useState("");
  const [freeze, setFreeze] = useState("");
  const [tests, setTests] = useState<TestRow[]>([]);
  const detail = useQuery({ queryKey: ["ro", ro.id], queryFn: () => api(`/api/v1/repair-orders/${ro.id}`, RODetailSchema) });
  const context = useQuery({
    queryKey: ["context", ro.id],
    queryFn: () => api(`/api/v1/vehicles/${ro.vehicle.id}/context?ro_id=${ro.id}`, VehicleContextSchema),
  });
  const findings = useQuery({
    queryKey: ["findings", ro.id],
    queryFn: () => api(`/api/v1/repair-orders/${ro.id}/findings`, FindingSummarySchema.array()),
  });
  const { codes, invalid } = parseDtcs(dtcText);
  const diagnose = useMutation({
    mutationFn: () =>
      api(`/api/v1/repair-orders/${ro.id}/diagnosis`, DiagnosisResultSchema, {
        body: {
          dtcs: codes,
          symptoms,
          freeze_frame_notes: freeze || null,
          test_results: tests.filter((t) => t.name && t.value).map((t) => ({ ...t, unit: t.unit || null })),
        },
      }),
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    if (invalid.length === 0) diagnose.mutate();
  }
  const setTest = (i: number, patch: Partial<TestRow>) =>
    setTests((rows) => rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <div>
      {detail.data && (
        <div className="mt-4 rounded-lg bg-white p-4 shadow dark:bg-slate-800">
          <h2 className="text-lg font-semibold">
            <Link to={`/ro/${ro.id}`} className="underline">
              {detail.data.ro_ref}
            </Link>{" "}
            · Veloxa {detail.data.vehicle.model} {detail.data.vehicle.model_year} ({detail.data.vehicle.vin_masked})
          </h2>
          {detail.data.complaints.map((c, i) => (
            <blockquote key={i} className="mt-1 border-l-4 border-slate-300 pl-2 text-sm italic">
              “{c.text}”
            </blockquote>
          ))}
        </div>
      )}
      {context.data && <VehicleContextCard ctx={context.data} />}

      <form onSubmit={submit} aria-label="Diagnostic inputs" className="mt-4 rounded-lg bg-white p-4 shadow dark:bg-slate-800">
        <h2 className="text-lg font-semibold">Diagnostic inputs</h2>
        <label className="mt-2 block text-sm">
          DTCs (e.g. P0301, C0035)
          <input value={dtcText} onChange={(e) => setDtcText(e.target.value)} aria-invalid={invalid.length > 0}
            aria-describedby="dtc-help" className={input} />
        </label>
        <p id="dtc-help" className={`text-xs ${invalid.length ? "text-red-700" : "text-slate-500"}`}>
          {invalid.length ? `Invalid format: ${invalid.join(", ")} — use P/B/C/U + 4 characters.` : "P/B/C/U + 4 characters."}
        </p>
        <label className="mt-2 block text-sm">
          Symptoms
          <textarea value={symptoms} onChange={(e) => setSymptoms(e.target.value)} maxLength={2000} rows={3}
            className={`${input} py-1`} />
        </label>
        <label className="mt-2 block text-sm">
          Freeze-frame notes
          <textarea value={freeze} onChange={(e) => setFreeze(e.target.value)} maxLength={2000} rows={2}
            className={`${input} py-1`} />
        </label>
        <fieldset className="mt-2">
          <legend className="text-sm font-medium">Test results</legend>
          {tests.map((t, i) => (
            <div key={i} className="mt-1 grid grid-cols-3 gap-2">
              <input aria-label={`Test ${i + 1} name`} value={t.name} onChange={(e) => setTest(i, { name: e.target.value })}
                placeholder="Glow plug 2 resistance" className={input} />
              <input aria-label={`Test ${i + 1} value`} value={t.value} onChange={(e) => setTest(i, { value: e.target.value })}
                placeholder="2.5" className={input} />
              <input aria-label={`Test ${i + 1} unit`} value={t.unit} onChange={(e) => setTest(i, { unit: e.target.value })}
                placeholder="ohm" className={input} />
            </div>
          ))}
          <button type="button" onClick={() => setTests((rows) => [...rows, { name: "", value: "", unit: "" }])}
            className="mt-2 min-h-tap rounded border border-slate-400 px-3 text-sm">
            Add test result
          </button>
        </fieldset>
        {diagnose.isError && (
          <p role="alert" className="mt-2 text-sm text-red-700">
            {errText(diagnose.error, "Diagnosis failed.")}
          </p>
        )}
        <button type="submit" disabled={diagnose.isPending || invalid.length > 0 || (!codes.length && !symptoms.trim())}
          className="mt-3 min-h-tap rounded bg-blue-700 px-4 font-medium text-white disabled:opacity-60">
          {diagnose.isPending ? "Analysing…" : "Run diagnosis"}
        </button>
      </form>

      {diagnose.data && <DiagnosisPanel result={diagnose.data} />}
      <FindingForm roId={ro.id} result={diagnose.data ?? null} dtcs={codes.filter((c) => !invalid.includes(c))} />
      {findings.data && findings.data.length > 0 && (
        <section aria-label="Recorded findings" className="mt-4 text-sm">
          <h2 className="text-lg font-semibold">Recorded findings</h2>
          <ul>
            {findings.data.map((f) => (
              <li key={f.id}>
                {new Date(f.created_at).toLocaleString()} — {f.confirmed_hypothesis} · {f.op_codes_performed.join(", ") || "no op codes"}
                {" · "}
                {f.actual_hours ?? "—"} h
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/** Technician diagnostic copilot (P3-1). Tablet-first: 48px targets, single column below `sm`. */
export function TechCopilot() {
  const [selected, setSelected] = useState<ROSummary | null>(null);
  const ros = useQuery({
    queryKey: ["ros", "DIAGNOSING"],
    queryFn: () => api("/api/v1/repair-orders?status=DIAGNOSING", pageSchema(ROSummarySchema)),
  });
  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-4xl p-4">
      <h1 id="page-title" className="text-2xl font-semibold">
        Technician copilot
      </h1>
      {ros.isError && <p role="alert">Could not load repair orders.</p>}
      {ros.data && ros.data.items.length === 0 && <p className="mt-4 text-slate-600">No repair orders are being diagnosed.</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {ros.data?.items.map((ro) => (
          <button key={ro.id} type="button" onClick={() => setSelected(ro)} aria-pressed={selected?.id === ro.id}
            className={`min-h-tap rounded border px-3 text-sm ${
              selected?.id === ro.id ? "border-blue-700 bg-blue-50 text-blue-900" : "border-slate-300"
            }`}>
            {ro.ro_ref} · {ro.vehicle.model} {ro.vehicle.model_year}
          </button>
        ))}
      </div>
      {selected && <Workbench key={selected.id} ro={selected} />}
    </section>
  );
}
