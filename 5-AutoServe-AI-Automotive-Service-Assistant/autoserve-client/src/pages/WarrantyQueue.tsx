import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { ClaimRowSchema } from "../api/review";
import { pageSchema } from "../api/schemas";

const STATUSES = ["", "WARRANTY_REVIEW_REQUIRED", "PREPARED", "RETURNED_FOR_INFO", "SUBMITTED_TO_OEM", "REJECTED_BY_DEALER"];
const RISK_STYLE: Record<string, string> = {
  high: "bg-orange-100 text-orange-900",
  medium: "bg-amber-100 text-amber-900",
  low: "bg-slate-100 text-slate-800",
  none: "bg-slate-50 text-slate-600",
};

/** Warranty queue (P3-10): sorted by risk, then age. Risk is an "indicator for review", never an accusation. */
export function WarrantyQueue() {
  const [status, setStatus] = useState("");
  const [model, setModel] = useState("");
  const qs = new URLSearchParams({ sort: "risk_age", ...(status && { status }), ...(model && { model }) });
  const claims = useQuery({
    queryKey: ["claims", status, model],
    queryFn: () => api(`/api/v1/warranty/claims?${qs.toString()}`, pageSchema(ClaimRowSchema)),
  });
  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-5xl p-4">
      <h1 id="page-title" className="text-2xl font-semibold">
        Warranty queue
      </h1>
      <div className="mt-3 flex flex-wrap gap-3 text-sm">
        <label>
          Status{" "}
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="min-h-tap rounded border px-2 dark:bg-slate-900">
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s ? s.replace(/_/g, " ").toLowerCase() : "all"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Model{" "}
          <select value={model} onChange={(e) => setModel(e.target.value)} className="min-h-tap rounded border px-2 dark:bg-slate-900">
            {["", "Aria", "Terra", "Volt"].map((m) => (
              <option key={m} value={m}>
                {m || "all"}
              </option>
            ))}
          </select>
        </label>
      </div>
      {claims.isError && <p role="alert">Could not load claims.</p>}
      {claims.data && claims.data.items.length === 0 && <p className="mt-4 text-slate-600">No claims match.</p>}
      <table className="mt-4 w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-700">
            <th className="py-2">Claim</th>
            <th>RO</th>
            <th>Vehicle</th>
            <th>Status</th>
            <th>Risk indicator</th>
            <th>Age</th>
            <th>Claimed</th>
          </tr>
        </thead>
        <tbody>
          {claims.data?.items.map((c) => (
            <tr key={c.id} className="border-b border-slate-100 dark:border-slate-800">
              <td className="py-2">
                <Link to={`/warranty/${c.id}`} className="font-medium underline">
                  {c.claim_ref}
                </Link>
              </td>
              <td>{c.ro_ref}</td>
              <td>
                Veloxa {c.model} {c.model_year}
              </td>
              <td>{c.status.replace(/_/g, " ").toLowerCase()}</td>
              <td>
                <span className={`rounded px-2 py-0.5 text-xs ${RISK_STYLE[c.risk_level]}`}>{c.risk_level}</span>
              </td>
              <td>{c.age_days} d</td>
              <td>{c.total_claimed ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
