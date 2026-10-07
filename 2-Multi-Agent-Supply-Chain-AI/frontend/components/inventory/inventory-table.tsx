"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, PackageSearch, Search, Sparkles } from "lucide-react";
import type { InventoryItem, InventoryQuery, RiskLevel } from "@/types";
import { useInventory } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/data";
import { Tooltip } from "@/components/ui/primitives";
import { Sparkline, CHART } from "@/components/charts";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import { RiskBadge } from "@/components/shared/status";
import { PRODUCT_CATEGORIES as CATEGORIES } from "@/lib/constants";
import { cn, fmt } from "@/lib/utils";

type SortKey = keyof InventoryItem;

const COLUMNS: { key: SortKey; label: string; align?: "right"; hint?: string }[] = [
  { key: "sku", label: "SKU" },
  { key: "name", label: "Product" },
  { key: "available", label: "Stock", align: "right", hint: "Available = on hand − allocated" },
  { key: "forecast30d", label: "Demand (30d)", align: "right" },
  { key: "safetyStock", label: "Safety stock", align: "right", hint: "95% service level" },
  { key: "daysOfCover", label: "Cover", align: "right", hint: "Days until stock runs out at forecast demand" },
  { key: "risk", label: "Risk" },
  { key: "reorderQty", label: "Recommendation" },
];

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function InventoryTable({ initialSearch = "", initialRisk = "all" }: { initialSearch?: string; initialRisk?: RiskLevel | "all" }) {
  const [search, setSearchRaw] = useState(initialSearch);
  const [risk, setRiskRaw] = useState<RiskLevel | "all">(initialRisk);
  const [category, setCategoryRaw] = useState("all");
  const [sort, setSortRaw] = useState<{ key: SortKey; order: "asc" | "desc" }>({ key: "risk", order: "asc" });
  const [page, setPage] = useState(1);
  // Any filter or sort change returns to the first page.
  const withReset =
    <A,>(fn: (a: A) => void) =>
    (a: A) => {
      fn(a);
      setPage(1);
    };
  const setSearch = withReset(setSearchRaw);
  const setRisk = withReset(setRiskRaw);
  const setCategory = withReset(setCategoryRaw);
  const setSort = withReset(setSortRaw);
  const debounced = useDebounced(search);
  const query: InventoryQuery = { search: debounced, risk, category, sort: sort.key, order: sort.order, page, pageSize: 15 };
  const { data, isLoading, isFetching, error, refetch } = useInventory(query);

  const toggleSort = (key: SortKey) =>
    setSort(sort.key === key ? { key, order: sort.order === "asc" ? "desc" : "asc" } : { key, order: key === "name" || key === "sku" || key === "risk" || key === "daysOfCover" ? "asc" : "desc" });

  const pages = data ? Math.max(1, Math.ceil(data.total / data.pageSize)) : 1;

  return (
    <div>
      <div className="flex flex-col gap-2 border-b px-5 py-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 sm:max-w-xs">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search SKU or product" className="pl-8" aria-label="Search inventory" />
        </div>
        <Select
          label="Filter by risk"
          value={risk}
          onValueChange={(v) => setRisk(v as RiskLevel | "all")}
          className="sm:w-36"
          options={[
            { value: "all", label: "All risk levels" },
            { value: "critical", label: "Critical" },
            { value: "high", label: "High" },
            { value: "medium", label: "Medium" },
            { value: "low", label: "Low" },
          ]}
        />
        <Select
          label="Filter by category"
          value={category}
          onValueChange={setCategory}
          className="sm:w-44"
          options={[{ value: "all", label: "All categories" }, ...CATEGORIES.map((c) => ({ value: c, label: c }))]}
        />
        <p className="text-xs text-muted-foreground sm:ml-auto" aria-live="polite">
          {data ? `${fmt.int(data.total)} products` : ""}
        </p>
      </div>

      {isLoading ? (
        <TableSkeleton rows={10} cols={7} />
      ) : error ? (
        <ErrorState error={error} what="inventory data" onRetry={() => refetch()} />
      ) : !data?.items.length ? (
        <EmptyState icon={PackageSearch} title="No products match these filters" description="Try a different search term or clear the risk and category filters." action={{ label: "Clear filters", onClick: () => { setSearch(""); setRisk("all"); setCategory("all"); } }} />
      ) : (
        <div className={cn("transition-opacity", isFetching && "opacity-60")}>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                {COLUMNS.map((c) => {
                  const active = sort.key === c.key;
                  const Icon = active ? (sort.order === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;
                  const header = (
                    <button
                      type="button"
                      onClick={() => toggleSort(c.key)}
                      className={cn("inline-flex cursor-pointer items-center gap-1 uppercase hover:text-foreground", active && "text-foreground", c.align === "right" && "flex-row-reverse")}
                    >
                      {c.label}
                      <Icon className={cn("size-3", !active && "opacity-40")} aria-hidden />
                    </button>
                  );
                  return (
                    <TableHead key={c.key} className={cn(c.align === "right" && "text-right")} aria-sort={active ? (sort.order === "asc" ? "ascending" : "descending") : "none"}>
                      {c.hint ? <Tooltip content={c.hint}>{header}</Tooltip> : header}
                    </TableHead>
                  );
                })}
                <TableHead className="w-20">
                  <span className="sr-only">Trend</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.items.map((i) => (
                <TableRow key={i.sku}>
                  <TableCell className="font-mono text-xs">{i.sku}</TableCell>
                  <TableCell className="max-w-64">
                    <p className="truncate font-medium">{i.name}</p>
                    <p className="truncate text-[11.5px] text-muted-foreground">
                      {i.category} · {i.warehouse}
                    </p>
                  </TableCell>
                  <TableCell className="text-right tabular">{fmt.int(i.available)}</TableCell>
                  <TableCell className="text-right tabular">{fmt.int(i.forecast30d)}</TableCell>
                  <TableCell className="text-right tabular text-muted-foreground">{fmt.int(i.safetyStock)}</TableCell>
                  <TableCell className={cn("text-right font-medium tabular", i.daysOfCover < i.leadTimeDays && "text-critical")}>{i.daysOfCover >= 999 ? "—" : `${i.daysOfCover}d`}</TableCell>
                  <TableCell>
                    <RiskBadge risk={i.risk} />
                  </TableCell>
                  <TableCell className="max-w-72">
                    {i.reorderQty > 0 ? (
                      <Link
                        href={`/copilot?q=${encodeURIComponent(`Give me a complete recommendation for ${i.sku}`)}`}
                        className="inline-flex items-center gap-1 text-[12.5px] font-medium text-ai hover:underline"
                      >
                        <Sparkles className="size-3.5" aria-hidden />
                        Reorder {fmt.int(i.reorderQty)}
                      </Link>
                    ) : (
                      <span className="text-[12.5px] text-muted-foreground">{i.recommendation}</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Sparkline data={i.trend} className="w-16" height={24} color={i.risk === "critical" ? CHART.critical : CHART.secondary} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between border-t px-5 py-3">
            <p className="text-xs text-muted-foreground tabular">
              Page {page} of {fmt.int(pages)}
            </p>
            <div className="flex gap-1">
              <Button variant="outline" size="icon-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page">
                <ChevronLeft />
              </Button>
              <Button variant="outline" size="icon-sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page">
                <ChevronRight />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
