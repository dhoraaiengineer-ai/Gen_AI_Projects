import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { z } from "zod";

import { api, getToken } from "../api/client";
import { ApiError, envelopeSchema } from "../api/envelope";
import { pageSchema } from "../api/schemas";

const TABS = ["Overview", "Users", "Knowledge", "Audit"] as const;
type Tab = (typeof TABS)[number];
const ROLES = ["vehicle_owner", "service_advisor", "technician", "warranty_admin", "admin"] as const;
const STAFF = ["service_advisor", "technician", "warranty_admin"];
const input = "mt-1 block min-h-tap w-full rounded border border-slate-300 px-2 dark:bg-slate-900";
const err = (e: unknown, fallback: string) => (e instanceof ApiError ? e.message : fallback);

const OverviewSchema = z.object({
  users_by_role: z.record(z.number()),
  repair_orders_by_status: z.record(z.number()),
  claims_by_status: z.record(z.number()),
  open_risk_flags: z.number(),
  knowledge_documents: z.number(),
  knowledge_chunks: z.number(),
  llm_calls_24h: z.record(z.number()),
  llm_calls_24h_by_provider: z.record(z.number()),
});
const UserSchema = z.object({ id: z.string(), email: z.string(), display_name: z.string(), role: z.string(), dealer_id: z.string().nullable() });
const DealerSchema = z.object({ id: z.string(), code: z.string(), name: z.string() });
const KnowledgeSchema = z.object({
  id: z.string(),
  source_file: z.string(),
  doc_type: z.string(),
  model: z.string().nullable(),
  version: z.string(),
  visibility: z.string(),
  chunk_count: z.number(),
  ingested_at: z.string().nullable(),
});
const AuditSchema = z.object({ intact: z.boolean(), checked: z.number(), first_broken_seq: z.number().nullable() });
const IngestSchema = z.object({ document_id: z.string(), chunks_added: z.number(), chunks_skipped_duplicate: z.number(), unchanged: z.boolean() });

function Counts({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data);
  return (
    <div className="rounded border border-slate-200 p-3 dark:border-slate-700">
      <h3 className="font-semibold">{title}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-500">none</p>
      ) : (
        <ul className="text-sm">
          {entries.map(([k, v]) => (
            <li key={k}>
              {k.replace(/_/g, " ").toLowerCase()}: <strong>{v}</strong>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function OverviewTab() {
  const o = useQuery({ queryKey: ["admin-overview"], queryFn: () => api("/api/v1/admin/overview", OverviewSchema) });
  if (o.isLoading) return <p>Loading…</p>;
  if (!o.data) return <p role="alert">Could not load the overview.</p>;
  const d = o.data;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Counts title="Users by role" data={d.users_by_role} />
      <Counts title="Repair orders by status" data={d.repair_orders_by_status} />
      <Counts title="Warranty claims by status" data={d.claims_by_status} />
      <Counts title="AI calls in the last 24 h (outcome)" data={d.llm_calls_24h} />
      <Counts title="AI calls in the last 24 h (provider)" data={d.llm_calls_24h_by_provider} />
      <div className="rounded border border-slate-200 p-3 text-sm dark:border-slate-700">
        <h3 className="font-semibold">Knowledge &amp; risk</h3>
        <p>Documents: <strong>{d.knowledge_documents}</strong> · chunks: <strong>{d.knowledge_chunks}</strong></p>
        <p>Open risk indicators: <strong>{d.open_risk_flags}</strong></p>
      </div>
    </div>
  );
}

function UsersTab() {
  const qc = useQueryClient();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => api("/api/v1/admin/users", pageSchema(UserSchema)) });
  const dealers = useQuery({ queryKey: ["admin-dealers"], queryFn: () => api("/api/v1/admin/dealers", pageSchema(DealerSchema)) });
  const [form, setForm] = useState({ email: "", display_name: "", role: "vehicle_owner", dealer_id: "", password: "" });
  const dealerName = (id: string | null) => dealers.data?.items.find((d) => d.id === id)?.code ?? "—";
  const create = useMutation({
    mutationFn: () =>
      api("/api/v1/admin/users", UserSchema, {
        body: {
          email: form.email.trim(),
          display_name: form.display_name.trim(),
          role: form.role,
          dealer_id: STAFF.includes(form.role) ? form.dealer_id || null : null,
          password: form.password || null,
        },
      }),
    onSuccess: () => {
      setForm({ email: "", display_name: "", role: "vehicle_owner", dealer_id: "", password: "" });
      void qc.invalidateQueries({ queryKey: ["admin-users"] });
      void qc.invalidateQueries({ queryKey: ["admin-overview"] });
    },
  });
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }
  return (
    <div>
      <form onSubmit={submit} aria-label="Create user" className="grid gap-2 rounded border border-slate-200 p-3 sm:grid-cols-2 dark:border-slate-700">
        <h3 className="font-semibold sm:col-span-2">Create a DEMO user</h3>
        <label className="text-sm">Email<input required type="email" value={form.email} onChange={set("email")} className={input} /></label>
        <label className="text-sm">Display name<input required value={form.display_name} onChange={set("display_name")} className={input} /></label>
        <label className="text-sm">
          Role
          <select value={form.role} onChange={set("role")} className={input}>
            {ROLES.map((r) => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
          </select>
        </label>
        {STAFF.includes(form.role) && (
          <label className="text-sm">
            Dealer
            <select required value={form.dealer_id} onChange={set("dealer_id")} className={input}>
              <option value="">choose…</option>
              {dealers.data?.items.map((d) => <option key={d.id} value={d.id}>{d.code} — {d.name}</option>)}
            </select>
          </label>
        )}
        <label className="text-sm">
          Password (min 12 characters)
          <input type="password" minLength={12} value={form.password} onChange={set("password")} className={input} />
        </label>
        {create.isError && <p role="alert" className="text-sm text-red-700 sm:col-span-2">{err(create.error, "Could not create the user.")}</p>}
        {create.isSuccess && <p className="text-sm text-green-800 sm:col-span-2">User created.</p>}
        <button type="submit" disabled={create.isPending} className="min-h-tap rounded bg-blue-700 px-4 font-medium text-white disabled:opacity-60 sm:col-span-2">
          Create user
        </button>
      </form>
      <table className="mt-4 w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-700"><th className="py-1">Email</th><th>Name</th><th>Role</th><th>Dealer</th></tr>
        </thead>
        <tbody>
          {users.data?.items.map((u) => (
            <tr key={u.id} className="border-b border-slate-100 dark:border-slate-800">
              <td className="py-1">{u.email}</td><td>{u.display_name}</td><td>{u.role.replace(/_/g, " ")}</td><td>{dealerName(u.dealer_id)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

async function uploadKnowledge(form: FormData) {
  const resp = await fetch("/api/v1/admin/knowledge", { method: "POST", body: form, headers: { Authorization: `Bearer ${getToken() ?? ""}` } });
  const env = envelopeSchema(IngestSchema).parse(await resp.json());
  if (env.status === "error" || !env.data) throw new ApiError(env.error?.code ?? "INTERNAL_ERROR", env.error?.message ?? "Upload failed", env.request_id, resp.status);
  return env.data;
}

function KnowledgeTab() {
  const qc = useQueryClient();
  const docs = useQuery({ queryKey: ["admin-knowledge"], queryFn: () => api("/api/v1/admin/knowledge", pageSchema(KnowledgeSchema)) });
  const [meta, setMeta] = useState({ doc_id: "", doc_type: "owner_manual", visibility: "owner", version: "2026.1", model: "all" });
  const [file, setFile] = useState<File | null>(null);
  const upload = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      Object.entries(meta).forEach(([k, v]) => fd.append(k, v));
      if (file) fd.append("file", file);
      return uploadKnowledge(fd);
    },
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["admin-knowledge"] }),
  });
  const set = (k: keyof typeof meta) => (e: { target: { value: string } }) => setMeta((m) => ({ ...m, [k]: e.target.value }));
  return (
    <div>
      <form aria-label="Upload knowledge" className="grid gap-2 rounded border border-slate-200 p-3 sm:grid-cols-3 dark:border-slate-700"
        onSubmit={(e) => { e.preventDefault(); upload.mutate(); }}>
        <h3 className="font-semibold sm:col-span-3">Add a document to the knowledge base (PDF, max 10 MB)</h3>
        <label className="text-sm">Document id<input required pattern="[A-Za-z0-9_.\-]{3,64}" value={meta.doc_id} onChange={set("doc_id")} className={input} /></label>
        <label className="text-sm">Type
          <select value={meta.doc_type} onChange={set("doc_type")} className={input}>
            {["owner_manual", "service_manual", "tsb", "recall", "warranty", "dtc"].map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <label className="text-sm">Visibility
          <select value={meta.visibility} onChange={set("visibility")} className={input}><option>owner</option><option>staff</option></select>
        </label>
        <label className="text-sm">Model
          <select value={meta.model} onChange={set("model")} className={input}>{["all", "Aria", "Terra", "Volt"].map((m) => <option key={m}>{m}</option>)}</select>
        </label>
        <label className="text-sm">Version<input required value={meta.version} onChange={set("version")} className={input} /></label>
        <label className="text-sm">PDF file<input required type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="mt-1 block text-sm" /></label>
        {upload.isError && <p role="alert" className="text-sm text-red-700 sm:col-span-3">{err(upload.error, "Upload failed.")}</p>}
        {upload.data && (
          <p className="text-sm text-green-800 sm:col-span-3">
            {upload.data.unchanged ? "Unchanged — this exact document is already indexed." : `Indexed: ${upload.data.chunks_added} new chunk(s), ${upload.data.chunks_skipped_duplicate} duplicate(s) skipped.`}
          </p>
        )}
        <button type="submit" disabled={upload.isPending || !file} className="min-h-tap rounded bg-blue-700 px-4 font-medium text-white disabled:opacity-60 sm:col-span-3">
          {upload.isPending ? "Indexing…" : "Upload and index"}
        </button>
      </form>
      <table className="mt-4 w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 dark:border-slate-700"><th className="py-1">Source</th><th>Type</th><th>Model</th><th>Visibility</th><th>Version</th><th>Chunks</th></tr>
        </thead>
        <tbody>
          {docs.data?.items.map((d) => (
            <tr key={d.id} className="border-b border-slate-100 dark:border-slate-800">
              <td className="py-1">{d.source_file}</td><td>{d.doc_type}</td><td>{d.model ?? "all"}</td><td>{d.visibility}</td><td>{d.version}</td><td>{d.chunk_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditTab() {
  const check = useMutation({ mutationFn: () => api("/api/v1/admin/audit/verify", AuditSchema) });
  return (
    <div className="text-sm">
      <p>The audit log is append-only and hash-chained. This check recomputes every hash to prove no entry was changed or removed.</p>
      <button type="button" onClick={() => check.mutate()} disabled={check.isPending}
        className="mt-2 min-h-tap rounded bg-blue-700 px-4 font-medium text-white disabled:opacity-60">
        {check.isPending ? "Verifying…" : "Verify audit chain"}
      </button>
      {check.data && (
        <p role="status" className={`mt-2 font-medium ${check.data.intact ? "text-green-800" : "text-red-800"}`}>
          {check.data.intact
            ? `Intact — ${check.data.checked} entries verified.`
            : `BROKEN at entry #${check.data.first_broken_seq} (${check.data.checked} checked).`}
        </p>
      )}
      {check.isError && <p role="alert" className="mt-2 text-red-700">{err(check.error, "Verification failed.")}</p>}
    </div>
  );
}

/** Admin console: overview counts, users, knowledge base, audit integrity. Admin never decides claims. */
export function Admin() {
  const [tab, setTab] = useState<Tab>("Overview");
  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-5xl p-4">
      <h1 id="page-title" className="text-2xl font-semibold">Admin</h1>
      <div role="tablist" aria-label="Admin" className="mt-3 flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button key={t} role="tab" type="button" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`min-h-tap rounded px-3 text-sm ${tab === t ? "bg-slate-800 text-white" : "bg-slate-100 dark:bg-slate-700"}`}>
            {t}
          </button>
        ))}
      </div>
      <div role="tabpanel" aria-label={tab} className="mt-3 rounded-lg bg-white p-4 shadow dark:bg-slate-800">
        {tab === "Overview" && <OverviewTab />}
        {tab === "Users" && <UsersTab />}
        {tab === "Knowledge" && <KnowledgeTab />}
        {tab === "Audit" && <AuditTab />}
      </div>
    </section>
  );
}
