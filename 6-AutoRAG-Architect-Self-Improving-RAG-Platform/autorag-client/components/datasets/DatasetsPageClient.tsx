"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Database,
  Plus,
  Tag,
  CheckCircle2,
  XCircle,
  History,
  ListChecks,
  ClipboardList,
  GitCompare,
  ChevronsDownUp,
  ChevronsUpDown,
  Download,
  Search,
} from "lucide-react";

import { apiClient } from "@/services/api-client";
import type {
  BatchEvaluation,
  BatchRun,
  DatasetStatistics,
  EvaluationDataset,
  EvaluationDatasetVersion,
  GoldenQuestion,
  QuestionReviewStatus,
} from "@/types";

import { SectionCard } from "@/components/ui/section-card";
import { StatCard } from "@/components/ui/stat-card";
import { EmptyState } from "@/components/ui/empty-state";
import { ImportExportTab } from "@/components/datasets/ImportExportTab";
import { QuestionCard } from "@/components/datasets/QuestionCard";
import { ResultDetailDrawer } from "@/components/evaluation/golden/ResultDetailDrawer";

type Tab = "overview" | "questions" | "versions" | "statistics" | "import";

export function DatasetsPageClient() {
  const [datasets, setDatasets] = useState<EvaluationDataset[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await apiClient.listDatasets();
      setDatasets(items);
      setSelectedId((prev) => prev ?? items[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load datasets");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    try {
      const { dataset } = await apiClient.createDataset({ name });
      setNewName("");
      await refresh();
      setSelectedId(dataset.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create dataset");
    } finally {
      setCreating(false);
    }
  };

  const selected = datasets.find((d) => d.id === selectedId) ?? null;

  return (
    <div className="space-y-6">
      {/* Hero / intro */}
      <div className="rounded-2xl border border-stone-200/90 bg-white px-6 py-5">
        <h2 className="font-head text-sm font-bold text-foreground">Evaluation Dataset</h2>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-text-3">
          A versioned collection of benchmark questions, expected answers, and expected context
          used to objectively evaluate every pipeline version.
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        {/* Dataset list */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="eyebrow">Datasets ({datasets.length})</span>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              placeholder="New dataset name…"
              aria-label="New dataset name"
              className="flex-1 rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground placeholder-muted-foreground outline-none focus:ring-2 focus:ring-amber-500/30"
            />
            <button
              type="button"
              onClick={handleCreate}
              disabled={creating || !newName.trim()}
              className="flex items-center gap-1 rounded-lg border border-amber-400/40 bg-amber-500/15 px-3 py-2 text-xs font-semibold text-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add
            </button>
          </div>

          {loading && (
            <div className="space-y-2" aria-hidden="true">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-14 motion-safe:animate-pulse rounded-lg bg-accent/5" />
              ))}
            </div>
          )}

          {!loading && datasets.length === 0 && (
            <EmptyState
              icon={Database}
              title="No evaluation datasets yet"
              description="Create one above to start building a golden-question benchmark."
            />
          )}

          {datasets.map((d) => (
            <button
              key={d.id}
              onClick={() => setSelectedId(d.id)}
              className={`flex w-full items-center gap-3 rounded-lg border px-3 py-3 text-left ${
                d.id === selectedId
                  ? "border-amber-400/40 bg-amber-500/10"
                  : "border-border bg-card hover:bg-accent/5"
              }`}
            >
              <Database className="h-4 w-4 shrink-0 text-amber-700" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-foreground">{d.name}</div>
                <div className="truncate text-[11px] text-text-3">
                  {d.domain ?? "No domain"} · {d.status}
                </div>
              </div>
            </button>
          ))}
        </div>

        {/* Dataset detail */}
        {selected ? (
          <DatasetDetail key={selected.id} dataset={selected} />
        ) : (
          !loading && (
            <SectionCard>
              <p className="py-8 text-center text-sm text-text-3">
                Select a dataset on the left, or create one to get started.
              </p>
            </SectionCard>
          )
        )}
      </div>
    </div>
  );
}

function DatasetDetail({ dataset }: { dataset: EvaluationDataset }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [versions, setVersions] = useState<EvaluationDatasetVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<GoldenQuestion[]>([]);
  const [stats, setStats] = useState<DatasetStatistics | null>(null);
  const [loadingVersions, setLoadingVersions] = useState(true);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [newQuestion, setNewQuestion] = useState("");
  const [newAnswer, setNewAnswer] = useState("");
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Search/filter toolbar state — wired to listGoldenQuestions's existing
  // server-side filters (already supported, previously unused by this page).
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [difficultyFilter, setDifficultyFilter] = useState("");
  const [metricFilter, setMetricFilter] = useState("");
  const [reviewFilter, setReviewFilter] = useState<QuestionReviewStatus | "">("");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  // Pipelines-using-this-dataset + latest batch run (for the KPI row and the
  // per-question Evaluation Results section). Derived client-side from
  // listBatchRuns -- no new backend aggregation endpoint needed.
  const [batchRuns, setBatchRuns] = useState<BatchRun[]>([]);
  const [latestResults, setLatestResults] = useState<BatchEvaluation[]>([]);
  const [documentNames, setDocumentNames] = useState<Record<string, string>>({});
  const [drawerBatchEvaluationId, setDrawerBatchEvaluationId] = useState<string | null>(null);

  // Compare Versions state
  const [compareA, setCompareA] = useState<string>("");
  const [compareB, setCompareB] = useState<string>("");
  const [compareQuestionsA, setCompareQuestionsA] = useState<GoldenQuestion[] | null>(null);
  const [compareQuestionsB, setCompareQuestionsB] = useState<GoldenQuestion[] | null>(null);
  const [comparing, setComparing] = useState(false);

  const loadVersions = useCallback(async () => {
    setLoadingVersions(true);
    try {
      const items = await apiClient.listDatasetVersions(dataset.id);
      setVersions(items);
      setSelectedVersionId((prev) => prev ?? items[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load versions");
    } finally {
      setLoadingVersions(false);
    }
  }, [dataset.id]);

  useEffect(() => {
    void loadVersions();
  }, [loadVersions]);

  const loadQuestions = useCallback(async () => {
    if (!selectedVersionId) return;
    setLoadingQuestions(true);
    try {
      const items = await apiClient.listGoldenQuestions(selectedVersionId, {
        search: search || undefined,
        category: categoryFilter || undefined,
        difficulty: difficultyFilter || undefined,
        metric_focus: metricFilter || undefined,
        review_status: reviewFilter || undefined,
      });
      setQuestions(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load questions");
    } finally {
      setLoadingQuestions(false);
    }
  }, [selectedVersionId, search, categoryFilter, difficultyFilter, metricFilter, reviewFilter]);

  useEffect(() => {
    void loadQuestions();
  }, [loadQuestions]);

  useEffect(() => {
    apiClient
      .getDatasetStatistics(dataset.id)
      .then(setStats)
      .catch(() => setStats(null));
  }, [dataset.id, questions.length]);

  // Batch runs for this dataset (KPI: Pipelines Using; also source for the
  // most recent run's per-question results shown in each accordion card).
  useEffect(() => {
    apiClient
      .listBatchRuns({ datasetId: dataset.id })
      .then(setBatchRuns)
      .catch(() => setBatchRuns([]));
  }, [dataset.id]);

  const latestBatchRun = useMemo(
    () =>
      batchRuns
        .slice()
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0] ??
      null,
    [batchRuns],
  );

  useEffect(() => {
    if (!latestBatchRun) {
      setLatestResults([]);
      return;
    }
    apiClient
      .listBatchRunResults(latestBatchRun.id)
      .then(setLatestResults)
      .catch(() => setLatestResults([]));
  }, [latestBatchRun]);

  const resultByQuestionId = useMemo(() => {
    const map = new Map<string, BatchEvaluation>();
    for (const r of latestResults) map.set(r.golden_question_id, r);
    return map;
  }, [latestResults]);

  const pipelinesUsingCount = useMemo(
    () => new Set(batchRuns.map((r) => r.pipeline_id)).size,
    [batchRuns],
  );

  // Resolve reference_document_id -> file name, deduplicated across
  // questions (avoids one fetch per question — fetch each distinct
  // document exactly once).
  useEffect(() => {
    const ids = Array.from(
      new Set(questions.map((q) => q.reference_document_id).filter((id): id is string => !!id)),
    ).filter((id) => !(id in documentNames));
    if (ids.length === 0) return;
    void Promise.all(
      ids.map(async (id) => {
        try {
          const doc = await apiClient.getDocument(id);
          return [id, doc.file_name] as const;
        } catch {
          return [id, ""] as const;
        }
      }),
    ).then((pairs) => {
      setDocumentNames((prev) => {
        const next = { ...prev };
        for (const [id, name] of pairs) if (name) next[id] = name;
        return next;
      });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [questions]);

  const selectedVersion = versions.find((v) => v.id === selectedVersionId) ?? null;
  const isPublished = selectedVersion?.lifecycle_status === "published";

  const handleAddQuestion = async () => {
    const question = newQuestion.trim();
    if (!question || !selectedVersionId) return;
    try {
      await apiClient.createGoldenQuestion({
        dataset_version_id: selectedVersionId,
        question,
        reference_answer: newAnswer.trim() || undefined,
      });
      setNewQuestion("");
      setNewAnswer("");
      await loadQuestions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add question");
    }
  };

  const handleReview = async (questionId: string, reviewStatus: QuestionReviewStatus) => {
    try {
      await apiClient.reviewGoldenQuestion(questionId, reviewStatus);
      await loadQuestions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to review question");
    }
  };

  const handlePublish = async () => {
    setPublishing(true);
    try {
      const v = await apiClient.publishDatasetVersion(dataset.id, { copy_from_latest: true });
      await loadVersions();
      setSelectedVersionId(v.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish new version");
    } finally {
      setPublishing(false);
    }
  };

  const handleSetLifecycle = async (status: "published" | "archived") => {
    if (!selectedVersionId) return;
    try {
      await apiClient.updateDatasetVersionStatus(selectedVersionId, status);
      await loadVersions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update version status");
    }
  };

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const expandAll = () => setExpandedIds(new Set(questions.map((q) => q.id)));
  const collapseAll = () => setExpandedIds(new Set());

  // Validation — computed client-side from the already-fetched question list.
  const validation = useMemo(() => {
    const total = questions.length;
    const missingAnswer = questions.filter((q) => !q.reference_answer);
    const missingContext = questions.filter((q) => !q.expected_context);
    return {
      total,
      withAnswer: total - missingAnswer.length,
      withContext: total - missingContext.length,
      missingAnswer,
      missingContext,
      ready: total > 0 && missingAnswer.length === 0 && missingContext.length === 0,
    };
  }, [questions]);

  // Statistics — computed client-side from the already-fetched question list.
  const computedStats = useMemo(() => {
    const withAnswers = questions.filter((q) => q.reference_answer);
    const avgAnswerWords =
      withAnswers.length > 0
        ? Math.round(
            withAnswers.reduce((sum, q) => sum + (q.reference_answer?.split(/\s+/).length ?? 0), 0) /
              withAnswers.length,
          )
        : 0;
    const chunkCounts = questions.map((q) => q.relevant_chunk_ids?.length ?? 0);
    const avgChunks =
      chunkCounts.length > 0
        ? (chunkCounts.reduce((sum, n) => sum + n, 0) / chunkCounts.length).toFixed(1)
        : "0";
    const byCategory = new Map<string, number>();
    for (const q of questions) {
      const cat = q.category ?? "Uncategorized";
      byCategory.set(cat, (byCategory.get(cat) ?? 0) + 1);
    }
    const total = questions.length || 1;
    const coverage = Array.from(byCategory.entries()).map(([category, count]) => ({
      category,
      pct: Math.round((count / total) * 100),
    }));
    return { avgAnswerWords, avgChunks, coverage };
  }, [questions]);

  const handleCompare = async () => {
    if (!compareA || !compareB) return;
    setComparing(true);
    try {
      const [a, b] = await Promise.all([
        apiClient.listGoldenQuestions(compareA),
        apiClient.listGoldenQuestions(compareB),
      ]);
      setCompareQuestionsA(a);
      setCompareQuestionsB(b);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to compare versions");
    } finally {
      setComparing(false);
    }
  };

  const compareDiff = useMemo(() => {
    if (!compareQuestionsA || !compareQuestionsB) return null;
    const textsA = new Set(compareQuestionsA.map((q) => q.question));
    const textsB = new Set(compareQuestionsB.map((q) => q.question));
    const added = compareQuestionsB.filter((q) => !textsA.has(q.question));
    const removed = compareQuestionsA.filter((q) => !textsB.has(q.question));
    return { added, removed };
  }, [compareQuestionsA, compareQuestionsB]);

  return (
    <div className="space-y-4">
      <SectionCard
        title={dataset.name}
        description={dataset.description ?? undefined}
        actions={
          <div className="flex items-center gap-2">
            {selectedVersion && (
              <select
                value={selectedVersionId ?? ""}
                onChange={(e) => setSelectedVersionId(e.target.value)}
                aria-label="Dataset version"
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-xs text-foreground"
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.version_label} — {v.lifecycle_status}
                  </option>
                ))}
              </select>
            )}
            <button
              type="button"
              onClick={handlePublish}
              disabled={publishing}
              className="flex items-center gap-1 rounded-lg border border-border bg-accent/5 px-3 py-1.5 text-xs font-semibold text-text-2 disabled:opacity-50"
            >
              <History className="h-3.5 w-3.5" aria-hidden="true" />
              {publishing ? "Publishing…" : "Publish new version"}
            </button>
          </div>
        }
      >
        {error && (
          <div role="alert" className="mb-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-700">
            {error}
          </div>
        )}

        {selectedVersion && (
          <div className="mb-4 flex items-center gap-3 text-xs text-text-3">
            <span
              className={`rounded-full border px-2.5 py-0.5 font-semibold ${
                isPublished
                  ? "border-emerald-200 bg-emerald-50 text-emerald-600"
                  : "border-border bg-white/5 text-text-3"
              }`}
            >
              {selectedVersion.lifecycle_status}
            </span>
            {selectedVersion.lifecycle_status === "draft" && (
              <button
                type="button"
                onClick={() => handleSetLifecycle("published")}
                className="font-semibold text-amber-700 hover:underline"
              >
                Mark published
              </button>
            )}
            {selectedVersion.lifecycle_status === "published" && (
              <button
                type="button"
                onClick={() => handleSetLifecycle("archived")}
                className="font-semibold text-text-3 hover:underline"
              >
                Archive
              </button>
            )}
            <span className="text-text-3">
              Only <strong>published</strong> versions are selectable for a batch run.
            </span>
          </div>
        )}

        {/* Tabs */}
        <div className="mb-4 flex gap-1 border-b border-border text-xs">
          {(
            [
              ["overview", "Overview"],
              ["questions", "Golden Questions"],
              ["versions", "Versions"],
              ["statistics", "Statistics"],
              ["import", "Import / Export"],
            ] as [Tab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`border-b-[3px] px-3 py-2 transition-colors motion-safe:duration-150 ${
                tab === key ? "border-accent font-bold text-foreground" : "border-transparent font-medium text-text-3 hover:text-foreground"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "overview" && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Questions" value={questions.length} icon={ClipboardList} />
              <StatCard
                label="Latest Version"
                value={stats?.latest_version_label ?? "—"}
                icon={History}
              />
              <StatCard
                label="Last Updated"
                value={new Date(dataset.updated_at).toLocaleDateString()}
                icon={Tag}
              />
              <StatCard label="Pipelines Using" value={pipelinesUsingCount} icon={GitCompare} />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-border bg-card px-4 py-3">
                <h4 className="eyebrow mb-2">Coverage</h4>
                <dl className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <dt className="text-text-3">Expected Answers</dt>
                    <dd className="font-mono text-foreground">
                      {validation.withAnswer} / {validation.total}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-text-3">Expected Context</dt>
                    <dd className="font-mono text-foreground">
                      {validation.withContext} / {validation.total}
                    </dd>
                  </div>
                </dl>
              </div>

              <div className="rounded-lg border border-border bg-card px-4 py-3">
                <h4 className="eyebrow mb-2 flex items-center gap-1.5">
                  <ListChecks className="h-3.5 w-3.5" aria-hidden="true" /> Validation
                </h4>
                {validation.ready ? (
                  <p className="flex items-center gap-1.5 text-emerald-600">
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" /> Ready for evaluation
                  </p>
                ) : validation.total === 0 ? (
                  <p className="text-text-3">No questions in this version yet.</p>
                ) : (
                  <div className="space-y-1 text-text-3">
                    {validation.missingAnswer.length > 0 && (
                      <p>{validation.missingAnswer.length} question(s) missing an expected answer</p>
                    )}
                    {validation.missingContext.length > 0 && (
                      <p>{validation.missingContext.length} question(s) missing expected context</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {tab === "questions" && (
          <div className="space-y-3">
            {!isPublished && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                This version is {selectedVersion?.lifecycle_status ?? "unpublished"} — questions can
                still be edited, but a batch run requires the version to be published.
              </div>
            )}

            <div className="flex flex-col gap-2 rounded-lg border border-border bg-accent/5 p-3">
              <input
                type="text"
                value={newQuestion}
                onChange={(e) => setNewQuestion(e.target.value)}
                placeholder="New golden question…"
                className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground placeholder-muted-foreground outline-none focus:ring-2 focus:ring-amber-500/30"
              />
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newAnswer}
                  onChange={(e) => setNewAnswer(e.target.value)}
                  placeholder="Reference answer (optional — feeds answer_correctness + recall metrics)"
                  className="flex-1 rounded-lg border border-border bg-card px-3 py-2 text-xs text-foreground placeholder-muted-foreground outline-none focus:ring-2 focus:ring-amber-500/30"
                />
                <button
                  type="button"
                  onClick={handleAddQuestion}
                  disabled={!newQuestion.trim()}
                  className="flex items-center gap-1 rounded-lg border border-amber-400/40 bg-amber-500/15 px-3 py-2 text-xs font-semibold text-amber-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add
                </button>
              </div>
            </div>

            {/* Search / filter toolbar — wired to real server-side filters */}
            <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card px-3 py-2">
              <div className="relative flex-1 min-w-[160px]">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-3" aria-hidden="true" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search questions…"
                  aria-label="Search questions"
                  className="w-full rounded-lg border border-border bg-background py-1.5 pl-8 pr-2 text-xs text-foreground outline-none focus:ring-2 focus:ring-amber-500/30"
                />
              </div>
              <input
                type="text"
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                placeholder="Category"
                aria-label="Filter by category"
                className="w-28 rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground outline-none"
              />
              <select
                value={difficultyFilter}
                onChange={(e) => setDifficultyFilter(e.target.value)}
                aria-label="Filter by difficulty"
                className="rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground"
              >
                <option value="">Any difficulty</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
                <option value="expert">Expert</option>
              </select>
              <input
                type="text"
                value={metricFilter}
                onChange={(e) => setMetricFilter(e.target.value)}
                placeholder="Metric focus"
                aria-label="Filter by metric focus"
                className="w-32 rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground outline-none"
              />
              <select
                value={reviewFilter}
                onChange={(e) => setReviewFilter(e.target.value as QuestionReviewStatus | "")}
                aria-label="Filter by review status"
                className="rounded-lg border border-border bg-background px-2 py-1.5 text-xs text-foreground"
              >
                <option value="">Any status</option>
                <option value="draft">Draft</option>
                <option value="under_review">Under review</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="archived">Archived</option>
              </select>
              <div className="ml-auto flex items-center gap-1">
                <button
                  type="button"
                  onClick={expandAll}
                  className="flex items-center gap-1 rounded-lg border border-border bg-background px-2 py-1.5 text-[11px] font-semibold text-text-2 hover:bg-accent/5"
                >
                  <ChevronsUpDown className="h-3.5 w-3.5" aria-hidden="true" /> Expand All
                </button>
                <button
                  type="button"
                  onClick={collapseAll}
                  className="flex items-center gap-1 rounded-lg border border-border bg-background px-2 py-1.5 text-[11px] font-semibold text-text-2 hover:bg-accent/5"
                >
                  <ChevronsDownUp className="h-3.5 w-3.5" aria-hidden="true" /> Collapse All
                </button>
              </div>
            </div>

            {loadingQuestions && (
              <div className="h-24 motion-safe:animate-pulse rounded-lg bg-accent/5" aria-hidden="true" />
            )}

            {!loadingQuestions && questions.length === 0 && (
              <EmptyState
                icon={ClipboardList}
                title="No golden questions match"
                description="Add a question above, or adjust your search and filters."
              />
            )}

            <div className="space-y-2">
              {questions.map((q) => (
                <QuestionCard
                  key={q.id}
                  question={q}
                  expanded={expandedIds.has(q.id)}
                  onToggle={() => toggleExpanded(q.id)}
                  batchEvaluation={resultByQuestionId.get(q.id)}
                  documentName={q.reference_document_id ? documentNames[q.reference_document_id] : null}
                  onViewResult={setDrawerBatchEvaluationId}
                />
              ))}
            </div>

            {questions.some((q) => q.review_status !== "approved" && q.review_status !== "rejected") && (
              <p className="pt-1 text-[11px] text-text-3">
                Approve or reject questions inline via the review workflow below each card.
              </p>
            )}
            {/* Inline review actions kept per-question for now — approve/reject still work
                the same way as before, just inside the accordion's collapsed header area. */}
            <div className="space-y-2">
              {questions
                .filter((q) => q.review_status !== "approved" && q.review_status !== "rejected")
                .map((q) => (
                  <div key={`review-${q.id}`} className="flex items-center gap-3 pl-3 text-[11px]">
                    <span className="truncate text-text-3">{q.question}</span>
                    <button
                      onClick={() => handleReview(q.id, "approved")}
                      className="flex shrink-0 items-center gap-1 font-semibold text-emerald-500 hover:underline"
                    >
                      <CheckCircle2 className="h-3 w-3" aria-hidden="true" /> Approve
                    </button>
                    <button
                      onClick={() => handleReview(q.id, "rejected")}
                      className="flex shrink-0 items-center gap-1 font-semibold text-rose-500 hover:underline"
                    >
                      <XCircle className="h-3 w-3" aria-hidden="true" /> Reject
                    </button>
                  </div>
                ))}
            </div>
          </div>
        )}

        {tab === "versions" && (
          <div className="space-y-4">
            <div className="space-y-2">
              {loadingVersions && (
                <div className="h-24 motion-safe:animate-pulse rounded-lg bg-accent/5" aria-hidden="true" />
              )}
              {versions.map((v) => (
                <div
                  key={v.id}
                  className={`flex items-center gap-3 rounded-lg border px-3 py-2 text-xs ${
                    v.id === selectedVersionId
                      ? "border-amber-400/40 bg-amber-500/10"
                      : "border-border bg-card"
                  }`}
                >
                  <span className="w-14 font-mono font-bold text-foreground">{v.version_label}</span>
                  <span className="w-24 text-text-3">{v.lifecycle_status}</span>
                  <span className="flex-1 text-text-3">{v.notes ?? "—"}</span>
                  <span className="text-text-3">
                    {v.created_at ? new Date(v.created_at).toLocaleDateString() : ""}
                  </span>
                </div>
              ))}
              <p className="pt-2 text-[11px] text-text-3">
                Per Rule 55: publishing a new version never mutates a past version&apos;s questions —
                each version is an immutable snapshot.
              </p>
            </div>

            <div className="rounded-lg border border-border bg-card px-4 py-3">
              <h4 className="eyebrow mb-2 flex items-center gap-1.5">
                <GitCompare className="h-3.5 w-3.5" aria-hidden="true" /> Compare Versions
              </h4>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <select
                  value={compareA}
                  onChange={(e) => setCompareA(e.target.value)}
                  aria-label="Compare version A"
                  className="rounded-lg border border-border bg-background px-2 py-1.5 text-foreground"
                >
                  <option value="">Version A…</option>
                  {versions.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.version_label}
                    </option>
                  ))}
                </select>
                <span className="text-text-3">vs</span>
                <select
                  value={compareB}
                  onChange={(e) => setCompareB(e.target.value)}
                  aria-label="Compare version B"
                  className="rounded-lg border border-border bg-background px-2 py-1.5 text-foreground"
                >
                  <option value="">Version B…</option>
                  {versions.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.version_label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={handleCompare}
                  disabled={!compareA || !compareB || comparing}
                  className="rounded-lg border border-amber-400/40 bg-amber-500/15 px-3 py-1.5 font-semibold text-amber-700 disabled:opacity-50"
                >
                  {comparing ? "Comparing…" : "Compare"}
                </button>
              </div>

              {compareDiff && (
                <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <h5 className="mb-1 text-[11px] font-semibold text-emerald-600">
                      Added ({compareDiff.added.length})
                    </h5>
                    <ul className="space-y-1 text-[11px] text-text-2">
                      {compareDiff.added.map((q) => (
                        <li key={q.id} className="truncate">
                          + {q.question}
                        </li>
                      ))}
                      {compareDiff.added.length === 0 && <li className="text-text-3">None</li>}
                    </ul>
                  </div>
                  <div>
                    <h5 className="mb-1 text-[11px] font-semibold text-rose-600">
                      Removed ({compareDiff.removed.length})
                    </h5>
                    <ul className="space-y-1 text-[11px] text-text-2">
                      {compareDiff.removed.map((q) => (
                        <li key={q.id} className="truncate">
                          − {q.question}
                        </li>
                      ))}
                      {compareDiff.removed.length === 0 && <li className="text-text-3">None</li>}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "statistics" && (
          <div className="space-y-3">
            {!stats && (
              <EmptyState
                icon={ClipboardList}
                title="No statistics yet"
                description="Statistics appear once this dataset has published questions or a batch run."
              />
            )}
            {stats && (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {(Object.entries(stats.question_counts) as [string, number][]).map(([status, count]) => (
                    <div key={status} className="rounded-lg border border-border bg-card px-3 py-3">
                      <div className="eyebrow mb-1">{status.replace("_", " ")}</div>
                      <div className="text-xl font-bold text-foreground">{count}</div>
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="rounded-lg border border-border bg-card px-3 py-3 text-xs">
                    <div className="mb-2 text-text-3">Average Answer Length</div>
                    <div className="font-mono text-lg font-bold text-foreground">
                      {computedStats.avgAnswerWords} words
                    </div>
                  </div>
                  <div className="rounded-lg border border-border bg-card px-3 py-3 text-xs">
                    <div className="mb-2 text-text-3">Average Expected Context</div>
                    <div className="font-mono text-lg font-bold text-foreground">
                      {computedStats.avgChunks} chunks
                    </div>
                  </div>
                </div>

                {computedStats.coverage.length > 0 && (
                  <div className="rounded-lg border border-border bg-card px-3 py-3 text-xs">
                    <div className="mb-2 text-text-3">Category Coverage</div>
                    <div className="space-y-1.5">
                      {computedStats.coverage.map(({ category, pct }) => (
                        <div key={category} className="flex items-center gap-2">
                          <span className="w-28 truncate text-text-2">{category}</span>
                          <div className="h-1.5 flex-1 rounded-full bg-accent/10">
                            <div
                              className="h-1.5 rounded-full bg-amber-500"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="w-10 text-right font-mono text-text-3">{pct}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="rounded-lg border border-border bg-card px-3 py-3 text-xs">
                  <div className="mb-2 flex items-center gap-2 text-text-3">
                    <Tag className="h-3.5 w-3.5" aria-hidden="true" /> Last Batch Run
                  </div>
                  {stats.last_batch_run ? (
                    <p className="text-foreground">
                      Average Unified Score:{" "}
                      {stats.last_batch_run.average_unified_score !== null
                        ? stats.last_batch_run.average_unified_score.toFixed(3)
                        : "—"}{" "}
                      · {stats.last_batch_run.low_score_count} question(s) below 0.70
                    </p>
                  ) : (
                    <p className="text-text-3">No batch run for this dataset yet.</p>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {tab === "import" && selectedVersionId && selectedVersion && (
          <div className="space-y-3">
            <div className="flex justify-end">
              <span className="flex items-center gap-1 text-[11px] text-text-3">
                <Download className="h-3.5 w-3.5" aria-hidden="true" /> Export is also available
                below
              </span>
            </div>
            <ImportExportTab
              datasetName={dataset.name}
              datasetVersionId={selectedVersionId}
              versionLabel={selectedVersion.version_label}
              questions={questions}
              onImported={loadQuestions}
            />
          </div>
        )}
      </SectionCard>

      <ResultDetailDrawer
        batchEvaluationId={drawerBatchEvaluationId}
        onClose={() => setDrawerBatchEvaluationId(null)}
      />
    </div>
  );
}
