"use client";
// Presenter: portfolio list + selected portfolio detail and risk, formatted for the views.
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { PortfolioListItem, PortfolioView, RiskView } from "@/types";

export { money, pct } from "@/lib/format";

interface Loaded {
  id: string;
  detail: PortfolioView;
  risk: RiskView;
}

export function usePortfolios(token: string | null) {
  const [list, setList] = useState<PortfolioListItem[]>([]);
  const [chosen, setChosen] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api
      .portfolios(token)
      .then((items) => {
        if (!cancelled) setList(items);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  // Derived: the explicit choice, else the first portfolio.
  const selected = chosen ?? list[0]?.portfolioId ?? null;

  useEffect(() => {
    if (!token || !selected) return;
    let cancelled = false;
    Promise.all([api.portfolio(token, selected), api.risk(token, selected)])
      .then(([detail, risk]) => {
        if (!cancelled) setLoaded({ id: selected, detail, risk });
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [token, selected]);

  // Only show data that belongs to the current selection (no stale panel while loading).
  const current = loaded && loaded.id === selected ? loaded : null;
  return {
    list,
    selected,
    select: setChosen,
    detail: current?.detail ?? null,
    risk: current?.risk ?? null,
    error,
  };
}
