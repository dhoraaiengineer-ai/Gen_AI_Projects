// Formatting helpers shared by the views (numbers come from the API; the UI never computes them).

export const pct = (v: number | null | undefined, digits = 1) =>
  v === null || v === undefined || Number.isNaN(v) ? "–" : `${(v * 100).toFixed(digits)}%`;

export const money = (v: number | null | undefined) => {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const abs = Math.abs(v);
  if (abs >= 1e9) return `$${(v / 1e9).toFixed(2)}bn`;
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(v / 1e3).toFixed(1)}k`;
  return `$${v.toFixed(0)}`;
};

export const num = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? "–" : v.toFixed(digits);

export const when = (iso: string | null | undefined) => {
  if (!iso) return "–";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
};

export const label = (s: string | null | undefined) => (s ? s.replaceAll("_", " ") : "–");
