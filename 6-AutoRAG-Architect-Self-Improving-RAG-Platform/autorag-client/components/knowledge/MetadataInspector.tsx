"use client";

/**
 * Metadata Inspector — Chapter 32.11. Real DocumentDetail fields only. Spec fields
 * with no backing data (owner beyond uploaded_by, language, pipeline link) are
 * omitted rather than fabricated.
 */

import { Card } from "@/components/ui/card";
import { relativeTime, displayUser } from "@/lib/format";
import { formatBytes } from "@/lib/knowledge";
import type { DocumentDetail } from "@/types";

interface MetadataInspectorProps {
  detail: DocumentDetail | null;
}

export function MetadataInspector({ detail }: MetadataInspectorProps) {
  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Metadata Inspector</h3>

      {!detail ? (
        <p className="text-sm text-text-3">Select a document to inspect its metadata.</p>
      ) : (
        <div className="space-y-4">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
            <Field label="Document" value={detail.file_name} />
            <Field label="Uploaded By" value={displayUser(detail.uploaded_by)} />
            <Field label="Uploaded" value={relativeTime(detail.uploaded_at)} />
            <Field label="Type" value={detail.mime_type} />
            <Field label="Status" value={detail.status} />
            <Field label="Chunks" value={`${detail.indexed_chunks}/${detail.chunk_count} indexed`} />
            <Field label="File Size" value={formatBytes(detail.file_size)} />
            <Field label="Pages" value={detail.page_count !== null ? detail.page_count.toLocaleString() : "—"} />
            <Field label="Embedding Status" value={detail.embedding_status} />
            <Field
              label="PII Redactions"
              value={detail.pii_redaction_count > 0 ? `${detail.pii_redaction_count} masked` : "None found"}
            />
          </dl>

          {(detail.tags?.length || detail.categories?.length) && (
            <div className="flex flex-wrap gap-1.5">
              {detail.categories?.map((c) => (
                <span key={`cat-${c}`} className="rounded-full bg-violet-500/15 px-2 py-0.5 text-xs text-violet-300">
                  {c}
                </span>
              ))}
              {detail.tags?.map((t) => (
                <span key={`tag-${t}`} className="rounded-full bg-accent/5 px-2 py-0.5 text-xs text-text-3">
                  #{t}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-text-3">{label}</dt>
      <dd className="mt-0.5 truncate text-sm text-foreground" title={value}>
        {value}
      </dd>
    </div>
  );
}
