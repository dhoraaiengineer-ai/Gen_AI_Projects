import type { VehicleContext } from "../api/advisor";
import { CitationChip } from "./Safety";

const nf = (n: number | null | undefined) => (n == null ? "—" : n.toLocaleString());

/** Deterministic vehicle facts; every item links to its cited source (P2-2). */
export function VehicleContextCard({ ctx }: { ctx: VehicleContext }) {
  const m = ctx.maintenance_due;
  return (
    <section aria-label="Vehicle context" className="mt-4 rounded-lg bg-white p-4 shadow dark:bg-slate-800">
      <h2 className="text-lg font-semibold">
        Vehicle context — Veloxa {ctx.model} {ctx.model_year}
      </h2>
      {ctx.decoded && (
        <p className="text-sm text-slate-600 dark:text-slate-400">
          VIN decode: {ctx.decoded.wmi} · {ctx.decoded.model} · {ctx.decoded.model_year} · plant {ctx.decoded.plant} · serial{" "}
          {ctx.decoded.serial}
        </p>
      )}

      {ctx.risk_flags.map((f) => (
        <div key={f.id} role="alert" className="mt-3 rounded border-l-4 border-orange-600 bg-orange-50 p-2 text-sm text-orange-900">
          <p className="font-semibold">
            {f.detector_id} · {f.severity} — {f.explanation}
          </p>
        </div>
      ))}

      {ctx.open_recalls.length > 0 && (
        <div className="mt-3">
          <h3 className="font-semibold">Open recalls</h3>
          <ul className="text-sm">
            {ctx.open_recalls.map((r) => (
              <li key={r.campaign_code}>
                {r.campaign_code} — {r.title} {r.notice && <CitationChip citation={r.notice} />}
              </li>
            ))}
          </ul>
        </div>
      )}

      {ctx.applicable_tsbs.length > 0 && (
        <div className="mt-3">
          <h3 className="font-semibold">Matching TSBs</h3>
          <ul className="text-sm">
            {ctx.applicable_tsbs.map((t) => (
              <li key={t.tsb_code}>
                {t.tsb_code} — {t.title} (matched {t.match_reason}: {t.matched_terms.join(", ")}; op {t.op_code ?? "—"})
                {t.source && <CitationChip citation={t.source} />}
              </li>
            ))}
          </ul>
        </div>
      )}

      {m && (
        <div className="mt-3 text-sm">
          <h3 className="font-semibold">Maintenance</h3>
          <p>
            Status: <strong>{m.status}</strong> · due at {nf(m.due_at_km)} km or {m.due_at_date ?? "—"} · current {nf(m.current_km)} km
            {m.overdue_by_km != null && ` · overdue by ${nf(m.overdue_by_km)} km`}
            {m.overdue_by_days != null && ` · overdue by ${m.overdue_by_days} days`}
            {m.source && <CitationChip citation={m.source} />}
          </p>
        </div>
      )}

      <div className="mt-3 text-sm">
        <h3 className="font-semibold">Warranty coverage (preliminary — not a decision)</h3>
        <ul>
          {ctx.warranty_coverage.map((c) => (
            <li key={c.coverage}>
              {c.coverage}: <strong>{c.status}</strong> · until {c.end_date ?? "—"} · {nf(c.km_remaining)} km remaining
              {c.source && <CitationChip citation={c.source} />}
            </li>
          ))}
        </ul>
      </div>

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer font-semibold">Service history ({ctx.service_history.length})</summary>
        <ul>
          {ctx.service_history.map((h, i) => (
            <li key={i}>
              {h.date} · {nf(h.odometer_km)} km · {h.op_codes.join(", ") || "—"} · {h.dealer_name}
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
