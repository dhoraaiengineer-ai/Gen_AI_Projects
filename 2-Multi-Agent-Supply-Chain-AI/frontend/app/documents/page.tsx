"use client";

import { useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Eye, FileSpreadsheet, FileText, FileType2, Image as ImageIcon, Loader2, MoreHorizontal, Presentation, RefreshCw, ScanText, Search, Sparkles, Trash2, Upload } from "lucide-react";
import { toast } from "sonner";
import type { DocumentItem, DocumentSearchResult } from "@/types";
import { useDocumentMutations, useDocumentStats, useDocuments } from "@/hooks/use-api";
import { getApi } from "@/lib/api";
import { PageHeader } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/data";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger, Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/overlays";
import { Skeleton } from "@/components/ui/primitives";
import { CitedText } from "@/components/copilot/report-card";
import { Stat } from "@/components/shared/stat";
import { EmptyState, ErrorState, TableSkeleton } from "@/components/shared/states";
import { cn, formatDate, timeAgo } from "@/lib/utils";

const FORMAT_ICON: Record<DocumentItem["format"], typeof FileText> = {
  pdf: FileText,
  docx: FileType2,
  md: FileType2,
  txt: FileType2,
  xlsx: FileSpreadsheet,
  csv: FileSpreadsheet,
  pptx: Presentation,
  png: ImageIcon,
};

const TYPE_LABEL: Record<DocumentItem["type"], string> = {
  procurement_policy: "Procurement policy",
  supplier_contract: "Supplier contract",
  inventory_policy: "Inventory policy",
  shipping_policy: "Shipping policy",
  sop: "SOP",
};

function StatusCell({ doc }: { doc: DocumentItem }) {
  if (doc.status === "indexed")
    return (
      <span className="inline-flex items-center gap-1 text-[12.5px] text-success">
        <CheckCircle2 className="size-3.5" aria-hidden /> Indexed
      </span>
    );
  if (doc.status === "processing")
    return (
      <span className="inline-flex items-center gap-1 text-[12.5px] text-ai">
        <Loader2 className="size-3.5 animate-spin" aria-hidden /> Processing
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-[12.5px] text-critical" title={doc.error}>
      <AlertTriangle className="size-3.5" aria-hidden /> Failed
    </span>
  );
}

/** Knowledge-base search: grounded answer with numbered source references. */
function KnowledgeSearch() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<DocumentSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const run = async (q = query) => {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await (await getApi()).searchDocuments(q));
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle className="flex items-center gap-1.5">
            <Sparkles className="size-4 text-ai" aria-hidden /> Ask your documents
          </CardTitle>
          <CardDescription>Hybrid search over policies, contracts and SOPs. Every answer cites its sources.</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run();
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. What is the PO approval threshold?" className="pl-8" aria-label="Search documents" />
          </div>
          <Button type="submit" disabled={loading || !query.trim()}>
            {loading ? <Loader2 className="animate-spin" /> : <Search />} Search
          </Button>
        </form>
        {!result && !loading && !error && (
          <div className="flex flex-wrap gap-2">
            {["What is the PO approval threshold?", "When are expedited orders allowed?", "Nordvolt late delivery credit", "Lithium battery air shipping rules"].map((q) => (
              <button
                key={q}
                onClick={() => {
                  setQuery(q);
                  void run(q);
                }}
                className="cursor-pointer rounded-full border px-3 py-1 text-[12.5px] text-muted-foreground transition-colors hover:border-ai/40 hover:text-foreground"
              >
                {q}
              </button>
            ))}
          </div>
        )}
        {loading && (
          <div className="space-y-2 rounded-md border p-4" role="status" aria-label="Searching documents">
            <p className="text-xs text-ai">Retrieving passages · reranking · generating grounded answer…</p>
            <Skeleton className="h-3.5 w-full" />
            <Skeleton className="h-3.5 w-5/6" />
            <Skeleton className="h-3.5 w-2/3" />
          </div>
        )}
        {error ? <ErrorState error={error} what="search results" onRetry={() => run()} /> : null}
        {result && !loading && (
          <div className="rounded-md border">
            <div className="p-4">
              <CitedText text={result.answer} className="text-[14px] leading-relaxed" />
              <p className={cn("mt-2 text-[11.5px] font-medium", result.guard.status === "grounded" ? "text-success" : "text-muted-foreground")}>
                {result.guard.status === "grounded" ? "✓ Grounded in retrieved passages" : result.guard.reasons.join(", ")} · {(result.latencyMs / 1000).toFixed(1)}s
              </p>
            </div>
            {result.citations.length > 0 && (
              <ol className="divide-y border-t">
                {result.citations.map((c) => (
                  <li key={c.n} id={`source-${c.n}`} className="flex gap-3 px-4 py-3 text-[12.5px]">
                    <span className="flex h-5 min-w-5 items-center justify-center rounded bg-ai-soft text-[11px] font-semibold text-ai">{c.n}</span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">
                        {c.source} <span className="font-normal text-muted-foreground">· {c.location}</span>
                      </p>
                      <p className="mt-0.5 text-muted-foreground">“{c.snippet}”</p>
                    </div>
                    <span className="shrink-0 text-[11px] text-muted-foreground tabular">{(c.score * 100).toFixed(0)}% match</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function DocumentsPage() {
  const docs = useDocuments();
  const stats = useDocumentStats();
  const { upload, remove, reindex } = useDocumentMutations();
  const [filter, setFilter] = useState("");
  const [preview, setPreview] = useState<DocumentItem | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<DocumentItem | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const onFiles = (files: FileList | null) => {
    if (!files?.length) return;
    upload.mutate(Array.from(files), {
      onSuccess: (results) => {
        const ok = results.filter((r) => r.status !== "failed").length;
        const failed = results.filter((r) => r.status === "failed");
        if (ok) toast.success(`${ok} ${ok === 1 ? "document" : "documents"} indexed`);
        failed.forEach((f) => toast.error(`${f.name} couldn't be indexed`, { description: f.error }));
      },
      onError: () => toast.error("Upload failed. Please try again."),
    });
  };

  const visible = (docs.data ?? []).filter((d) => !filter || d.name.toLowerCase().includes(filter.toLowerCase()) || TYPE_LABEL[d.type].toLowerCase().includes(filter.toLowerCase()));
  const s = stats.data;

  return (
    <>
      <PageHeader
        title="Document intelligence"
        description="The knowledge base behind the Knowledge Agent: policies, contracts and SOPs, chunked, embedded and searchable."
        actions={
          <>
            <input ref={fileInput} type="file" multiple hidden accept=".pdf,.docx,.xlsx,.pptx,.csv,.md,.txt,.png,.jpg,.jpeg" onChange={(e) => onFiles(e.target.files)} />
            <Button onClick={() => fileInput.current?.click()} disabled={upload.isPending}>
              {upload.isPending ? <Loader2 className="animate-spin" /> : <Upload />} Upload documents
            </Button>
          </>
        }
      />

      <section aria-label="Document summary" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Documents" value={s && String(s.total)} hint={s && `${s.chunks.toLocaleString()} searchable chunks`} icon={FileText} loading={stats.isLoading} />
        <Stat label="Indexed" value={s && String(s.indexed)} hint="Ready for retrieval" icon={CheckCircle2} tone="success" loading={stats.isLoading} />
        <Stat label="Processing" value={s && String(s.processing)} hint="Parsing and embedding" icon={Loader2} tone="ai" loading={stats.isLoading} />
        <Stat label="Failed" value={s && String(s.failed)} hint={s?.failed ? "Needs attention" : "No failures"} icon={AlertTriangle} tone={s?.failed ? "critical" : "neutral"} loading={stats.isLoading} />
      </section>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr_1.15fr]">
        <KnowledgeSearch />
        <Card
          className="flex flex-col items-center justify-center border-dashed p-8 text-center"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            onFiles(e.dataTransfer.files);
          }}
        >
          <span className="flex size-11 items-center justify-center rounded-full bg-secondary text-primary dark:text-foreground">
            <Upload className="size-5" aria-hidden />
          </span>
          <p className="mt-3 text-sm font-semibold">Drop files to add them to the knowledge base</p>
          <p className="mt-1 max-w-sm text-[13px] text-muted-foreground">PDF, Word, Excel, PowerPoint, CSV, Markdown and text. Scanned PDFs and images are read with OCR. Up to 20 MB per file.</p>
          <div className="mt-4 flex flex-wrap justify-center gap-1.5 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1 rounded border px-1.5 py-0.5">
              <ScanText className="size-3" aria-hidden /> OCR
            </span>
            <span className="rounded border px-1.5 py-0.5">Incremental re-indexing</span>
            <span className="rounded border px-1.5 py-0.5">Metadata filters</span>
            <span className="rounded border px-1.5 py-0.5">Role-based access</span>
          </div>
          <Button variant="outline" size="sm" className="mt-4" onClick={() => fileInput.current?.click()}>
            Browse files
          </Button>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader className="pb-3">
          <div>
            <CardTitle>Documents</CardTitle>
            <CardDescription>Access is filtered by classification and your role</CardDescription>
          </div>
          <div className="relative w-56">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter documents" className="h-8 pl-8 text-[13px]" aria-label="Filter documents" />
          </div>
        </CardHeader>
        {docs.isLoading ? (
          <TableSkeleton rows={8} cols={5} />
        ) : docs.error ? (
          <ErrorState error={docs.error} what="documents" onRetry={() => docs.refetch()} />
        ) : !visible.length ? (
          <EmptyState icon={FileText} title={filter ? "No documents match" : "No documents yet"} description={filter ? "Try a different name or type." : "Upload your procurement, inventory and shipping policies to ground the Copilot's answers."} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Document</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Access</TableHead>
                <TableHead>Updated</TableHead>
                <TableHead className="text-right">Chunks</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-10">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.map((d) => {
                const Icon = FORMAT_ICON[d.format];
                return (
                  <TableRow key={d.id}>
                    <TableCell className="max-w-96">
                      <div className="flex items-center gap-2.5">
                        <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                        <div className="min-w-0">
                          <button onClick={() => setPreview(d)} className="block max-w-full cursor-pointer truncate text-left font-medium hover:underline">
                            {d.name}
                          </button>
                          <p className="text-[11px] text-muted-foreground">
                            {d.format.toUpperCase()} · {d.sizeKb.toLocaleString()} KB{d.ocr ? " · OCR" : ""}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-[12.5px]">{TYPE_LABEL[d.type]}</TableCell>
                    <TableCell>
                      <span className={cn("rounded px-1.5 py-0.5 text-[11px] font-medium capitalize", d.classification === "restricted" ? "bg-warning/10 text-warning-foreground" : d.classification === "public" ? "bg-success/10 text-success" : "bg-muted text-muted-foreground")}>
                        {d.classification}
                      </span>
                    </TableCell>
                    <TableCell className="text-[12.5px] text-muted-foreground">{timeAgo(d.updatedAt)}</TableCell>
                    <TableCell className="text-right tabular">{d.chunks || "—"}</TableCell>
                    <TableCell>
                      <StatusCell doc={d} />
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${d.name}`}>
                            <MoreHorizontal />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onSelect={() => setPreview(d)}>
                            <Eye /> Preview
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onSelect={() =>
                              reindex.mutate(d.id, {
                                onSuccess: () => toast.success(`${d.name} re-indexed`),
                                onError: () => toast.error("Re-index failed"),
                              })
                            }
                          >
                            <RefreshCw /> Re-index
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem className="text-critical [&_svg]:!text-critical" onSelect={() => setConfirmDelete(d)}>
                            <Trash2 /> Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>

      <Sheet open={!!preview} onOpenChange={(o) => !o && setPreview(null)}>
        <SheetContent>
          {preview && (
            <div className="flex h-full flex-col">
              <div className="border-b p-6 pr-12">
                <SheetTitle>{preview.name}</SheetTitle>
                <SheetDescription>
                  {TYPE_LABEL[preview.type]} · updated {formatDate(preview.updatedAt, { month: "short", day: "numeric", year: "numeric" })} by {preview.uploadedBy}
                </SheetDescription>
              </div>
              <dl className="grid grid-cols-2 gap-4 border-b p-6 text-[13px]">
                {[
                  ["Status", preview.status],
                  ["Chunks", preview.chunks || "—"],
                  ["Classification", preview.classification],
                  ["Size", `${preview.sizeKb.toLocaleString()} KB`],
                  ["Format", preview.format.toUpperCase()],
                  ["OCR", preview.ocr ? "Yes" : "No"],
                ].map(([k, v]) => (
                  <div key={String(k)}>
                    <dt className="text-[11.5px] text-muted-foreground">{k}</dt>
                    <dd className="mt-0.5 font-medium capitalize">{String(v)}</dd>
                  </div>
                ))}
              </dl>
              {preview.error && (
                <div className="m-6 rounded-md border border-critical/30 bg-critical/5 p-3 text-[13px]">
                  <p className="font-medium text-critical">Indexing failed</p>
                  <p className="mt-0.5 text-muted-foreground">{preview.error}</p>
                </div>
              )}
              <div className="p-6 text-[13px] text-muted-foreground">
                <p className="font-medium text-foreground">Metadata used for filtering</p>
                <p className="mt-1">Document type, classification, supplier, SKUs, region and effective dates are stored on every chunk and applied as pre-filters during retrieval.</p>
              </div>
            </div>
          )}
        </SheetContent>
      </Sheet>

      <Dialog open={!!confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(null)}>
        <DialogContent>
          <DialogTitle>Delete document?</DialogTitle>
          <DialogDescription>
            {confirmDelete?.name} and its {confirmDelete?.chunks} chunks will be removed from the knowledge base. The Copilot will no longer cite it.
          </DialogDescription>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirmDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={remove.isPending}
              onClick={() =>
                confirmDelete &&
                remove.mutate(confirmDelete.id, {
                  onSuccess: () => {
                    toast.success(`${confirmDelete.name} deleted`);
                    setConfirmDelete(null);
                  },
                })
              }
            >
              Delete
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
