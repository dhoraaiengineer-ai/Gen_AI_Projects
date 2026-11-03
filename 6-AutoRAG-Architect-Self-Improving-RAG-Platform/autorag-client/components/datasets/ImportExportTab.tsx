"use client";

/**
 * Import / Export tab (Evaluation Center gap-closure, 24-Jul-2026) --
 * bulk-create golden questions from CSV/JSON/JSONL (column-mapped, validated,
 * real per-row apiClient.createGoldenQuestion calls -- no bulk backend
 * endpoint exists, so this loops the existing single-question endpoint
 * rather than inventing a duplicate one) and export the current version's
 * questions as CSV/JSON/XLSX (client-side serialization of already-fetched
 * real data -- no new backend needed for export).
 */

import { useState } from "react";
import Papa from "papaparse";
import * as XLSX from "xlsx";
import { Download, Upload, AlertCircle, CheckCircle2 } from "lucide-react";

import { apiClient } from "@/services/api-client";
import type { GoldenQuestion } from "@/types";

interface ImportExportTabProps {
  datasetName: string;
  datasetVersionId: string;
  versionLabel: string;
  questions: GoldenQuestion[];
  onImported: () => void;
}

type TargetField = "question" | "reference_answer" | "category" | "difficulty" | "metric_focus" | "reference_pages";

const TARGET_FIELDS: { key: TargetField; label: string; required: boolean }[] = [
  { key: "question", label: "Question", required: true },
  { key: "reference_answer", label: "Reference Answer", required: false },
  { key: "category", label: "Category", required: false },
  { key: "difficulty", label: "Difficulty", required: false },
  { key: "metric_focus", label: "Metric Focus", required: false },
  { key: "reference_pages", label: "Reference Pages", required: false },
];

export function ImportExportTab({
  datasetName,
  datasetVersionId,
  versionLabel,
  questions,
  onImported,
}: ImportExportTabProps) {
  const [rows, setRows] = useState<Record<string, string>[] | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Partial<Record<TargetField, string>>>({});
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<{ succeeded: number; failed: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setError(null);
    setResult(null);
    try {
      const ext = file.name.split(".").pop()?.toLowerCase();
      let parsed: Record<string, string>[] = [];

      if (ext === "csv") {
        const text = await file.text();
        const res = Papa.parse<Record<string, string>>(text, { header: true, skipEmptyLines: true });
        parsed = res.data;
      } else if (ext === "json") {
        const text = await file.text();
        const data = JSON.parse(text);
        parsed = Array.isArray(data) ? data : [data];
      } else if (ext === "jsonl") {
        const text = await file.text();
        parsed = text
          .split("\n")
          .map((l) => l.trim())
          .filter(Boolean)
          .map((l) => JSON.parse(l));
      } else {
        setError("Unsupported file type — use .csv, .json, or .jsonl");
        return;
      }

      if (parsed.length === 0) {
        setError("No rows found in file");
        return;
      }

      const detectedColumns = Object.keys(parsed[0]);
      setColumns(detectedColumns);
      setRows(parsed);

      // Auto-map columns whose name matches a target field exactly.
      const autoMapping: Partial<Record<TargetField, string>> = {};
      for (const field of TARGET_FIELDS) {
        if (detectedColumns.includes(field.key)) autoMapping[field.key] = field.key;
      }
      setMapping(autoMapping);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to parse file");
    }
  };

  const handleImport = async () => {
    if (!rows || !mapping.question) return;
    setImporting(true);
    setError(null);
    let succeeded = 0;
    let failed = 0;

    for (const row of rows) {
      const question = mapping.question ? row[mapping.question]?.trim() : "";
      if (!question) {
        failed += 1;
        continue;
      }
      try {
        await apiClient.createGoldenQuestion({
          dataset_version_id: datasetVersionId,
          question,
          reference_answer: mapping.reference_answer ? row[mapping.reference_answer] || undefined : undefined,
          category: mapping.category ? row[mapping.category] || undefined : undefined,
          difficulty: mapping.difficulty ? row[mapping.difficulty] || undefined : undefined,
          metric_focus: mapping.metric_focus ? row[mapping.metric_focus] || undefined : undefined,
          reference_pages: mapping.reference_pages ? row[mapping.reference_pages] || undefined : undefined,
        });
        succeeded += 1;
      } catch {
        failed += 1;
      }
    }

    setResult({ succeeded, failed });
    setImporting(false);
    setRows(null);
    onImported();
  };

  const exportRows = questions.map((q) => ({
    question: q.question,
    reference_answer: q.reference_answer ?? "",
    category: q.category ?? "",
    difficulty: q.difficulty ?? "",
    metric_focus: q.metric_focus ?? "",
    reference_pages: q.reference_pages ?? "",
    review_status: q.review_status,
  }));

  const download = (content: BlobPart, filename: string, type: string) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportCsv = () => {
    const csv = Papa.unparse(exportRows);
    download(csv, `${datasetName}-${versionLabel}.csv`, "text/csv");
  };

  const exportJson = () => {
    download(JSON.stringify(exportRows, null, 2), `${datasetName}-${versionLabel}.json`, "application/json");
  };

  const exportXlsx = () => {
    const sheet = XLSX.utils.json_to_sheet(exportRows);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, sheet, "Golden Questions");
    XLSX.writeFile(workbook, `${datasetName}-${versionLabel}.xlsx`);
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="eyebrow mb-2">Import Golden Questions</h3>
        <p className="mb-3 text-xs text-text-3">
          Bulk-create questions in <strong>{versionLabel}</strong> from CSV, JSON, or JSONL. Each row
          becomes a real question via the same create endpoint the manual form uses.
        </p>

        {error && (
          <div role="alert" className="mb-3 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {error}
          </div>
        )}

        {result && (
          <div role="status" className="mb-3 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            Imported {result.succeeded} question(s){result.failed > 0 ? `, ${result.failed} failed` : ""}.
          </div>
        )}

        {!rows && (
          <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-border bg-[#0F1629] px-4 py-3 text-xs text-text-3 hover:bg-accent/5">
            <Upload className="h-4 w-4" aria-hidden="true" />
            Choose a .csv, .json, or .jsonl file…
            <input
              type="file"
              accept=".csv,.json,.jsonl"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleFile(file);
                e.target.value = "";
              }}
            />
          </label>
        )}

        {rows && (
          <div className="space-y-3 rounded-lg border border-border bg-[#0F1629] p-4">
            <p className="text-xs text-text-3">
              {rows.length} row(s) detected. Map columns to golden-question fields (Question is
              required):
            </p>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {TARGET_FIELDS.map((field) => (
                <div key={field.key} className="flex items-center gap-2">
                  <label className="w-36 shrink-0 text-xs text-text-2">
                    {field.label}
                    {field.required && <span className="text-rose-500"> *</span>}
                  </label>
                  <select
                    value={mapping[field.key] ?? ""}
                    onChange={(e) =>
                      setMapping((prev) => ({ ...prev, [field.key]: e.target.value || undefined }))
                    }
                    className="flex-1 rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground"
                  >
                    <option value="">— none —</option>
                    {columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleImport}
                disabled={!mapping.question || importing}
                className="rounded-lg border border-amber-400/40 bg-amber-500/15 px-4 py-2 text-xs font-semibold text-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {importing ? "Importing…" : `Import ${rows.length} question(s)`}
              </button>
              <button
                type="button"
                onClick={() => setRows(null)}
                disabled={importing}
                className="rounded-lg border border-border px-4 py-2 text-xs font-semibold text-text-3"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      <div>
        <h3 className="eyebrow mb-2">Export</h3>
        <p className="mb-3 text-xs text-text-3">
          Export {versionLabel}&apos;s {questions.length} question(s).
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={exportCsv}
            disabled={questions.length === 0}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-semibold text-text-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" /> CSV
          </button>
          <button
            type="button"
            onClick={exportJson}
            disabled={questions.length === 0}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-semibold text-text-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" /> JSON
          </button>
          <button
            type="button"
            onClick={exportXlsx}
            disabled={questions.length === 0}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs font-semibold text-text-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" /> XLSX
          </button>
        </div>
      </div>
    </div>
  );
}
