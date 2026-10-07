// RAG Assistant UI. No framework, no build step.
// Model output is always inserted as text (never innerHTML) so it can't inject markup.
"use strict";

const $ = (id) => document.getElementById(id);

// ---------- Auth (Supabase Auth REST API; tokens kept in sessionStorage for this tab) ----------

const SESSION_KEY = "rag.session";
let authConfig = { enabled: false };

function loadSession() {
  try { return JSON.parse(sessionStorage.getItem(SESSION_KEY)); } catch { return null; }
}

function saveSession(data) {
  const session = {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    expires_at: data.expires_at ?? Math.floor(Date.now() / 1000) + (data.expires_in ?? 3600),
  };
  try { sessionStorage.setItem(SESSION_KEY, JSON.stringify(session)); } catch { /* storage blocked */ }
  return session;
}

function clearSession() {
  try { sessionStorage.removeItem(SESSION_KEY); } catch { /* storage blocked */ }
}

async function supabaseAuth(grantType, body) {
  const res = await fetch(`${authConfig.supabase_url}/auth/v1/token?grant_type=${grantType}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: authConfig.supabase_publishable_key },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error_description || data.msg || data.message || "Sign-in failed.");
  return saveSession(data);
}

let refreshing = null; // share one in-flight refresh between concurrent requests

async function refreshSession() {
  const session = loadSession();
  if (!session?.refresh_token) throw new Error("Session expired. Please sign in again.");
  refreshing ??= supabaseAuth("refresh_token", { refresh_token: session.refresh_token }).finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function accessToken() {
  if (!authConfig.enabled) return null;
  let session = loadSession();
  if (!session) return null;
  if (session.expires_at - 60 < Date.now() / 1000) session = await refreshSession();
  return session.access_token;
}

// ---------- API ----------

async function apiFetch(path, options = {}, retried = false) {
  const headers = { ...(options.headers || {}) };
  const token = await accessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });

  if (res.status === 401 && authConfig.enabled) {
    if (!retried) {
      try {
        await refreshSession();
        return apiFetch(path, options, true);
      } catch { /* fall through to sign-out */ }
    }
    showLogin("Your session expired. Please sign in again.");
    throw new Error("Signed out.");
  }
  return res;
}

async function postJson(path, body) {
  return readJson(await apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }));
}

// multipart/form-data: the browser sets the Content-Type with its boundary itself.
async function postForm(path, form) {
  return readJson(await apiFetch(path, { method: "POST", body: form }));
}

async function readJson(res) {
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON error body */ }
  if (!res.ok) throw new Error(describeError(res.status, data));
  return data;
}

function describeError(status, data) {
  if (status === 403) return "You don't have permission to do that (admin role required).";
  if (status === 413) return data?.detail || "File too large.";
  if (status === 429) {
    // Our own per-user limit says how long to wait; otherwise it's the LLM provider's quota.
    if (typeof data?.detail === "string" && data.detail.startsWith("Too many requests")) return data.detail;
    return "The LLM daily token limit or rate limit was reached. Try again later.";
  }
  if (status === 503) return "The backend can't reach the LLM provider or database right now.";
  if (status === 502) return "The LLM provider returned an error.";
  if (status === 422 && Array.isArray(data?.detail)) {
    return "Invalid input: " + data.detail.map((d) => d.msg).join("; ");
  }
  return data?.detail || `Request failed (HTTP ${status}).`;
}

// ---------- Health indicator ----------

async function refreshStatus() {
  const el = $("status");
  try {
    const res = await fetch("/health/ready");
    const data = await res.json();
    const ok = res.ok && data.status === "ok";
    el.dataset.state = ok ? "ok" : "degraded";
    el.textContent = ok ? "Ready" : "Database unavailable";
  } catch {
    el.dataset.state = "down";
    el.textContent = "Backend offline";
  }
}

// ---------- Chat rendering ----------

let messageCount = 0;

function addMessage(kind, text) {
  $("empty-state")?.remove();
  const el = document.createElement("div");
  el.className = `msg ${kind}`;
  el.textContent = text;
  $("messages").appendChild(el);
  el.scrollIntoView({ behavior: "smooth", block: "end" });
  return el;
}

// Turns "... [1] ... [2]" into text nodes plus clickable citation buttons.
function renderAnswer(el, answer, sources, msgId) {
  el.textContent = "";
  for (const part of answer.split(/(\[\d+\])/)) {
    const m = part.match(/^\[(\d+)\]$/);
    const idx = m ? Number(m[1]) : 0;
    if (m && idx >= 1 && idx <= sources.length) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cite";
      btn.textContent = part;
      btn.title = citationLabel(sources[idx - 1]);
      btn.addEventListener("click", () => revealSource(msgId, idx));
      el.appendChild(btn);
    } else {
      el.appendChild(document.createTextNode(part));
    }
  }
}

function renderSources(el, sources, msgId) {
  if (!sources.length) return;
  const details = document.createElement("details");
  details.className = "sources";
  details.id = `${msgId}-sources`;
  const summary = document.createElement("summary");
  summary.textContent = `${sources.length} source${sources.length > 1 ? "s" : ""}`;
  details.appendChild(summary);

  sources.forEach((s, i) => {
    const item = document.createElement("div");
    item.className = "source";
    item.id = `${msgId}-src-${i + 1}`;

    const head = document.createElement("div");
    head.className = "source-head";
    const name = document.createElement("span");
    name.textContent = `[${i + 1}] ${citationLabel(s)}`;
    const score = document.createElement("span");
    score.textContent = `relevance ${s.score.toFixed(2)}`;
    head.append(name, score);

    const body = document.createElement("div");
    body.className = "source-text";
    body.textContent = s.text;

    item.append(head, body);
    details.appendChild(item);
  });
  el.appendChild(details);
}

// Web pages the research agent read. Only http(s) URLs become links; they open in a new tab without a referrer.
function renderWebSources(el, urls) {
  const safe = urls.filter((u) => /^https?:\/\//i.test(u));
  if (!safe.length) return;
  const details = document.createElement("details");
  details.className = "sources";
  const summary = document.createElement("summary");
  summary.textContent = `${safe.length} web source${safe.length > 1 ? "s" : ""}`;
  details.appendChild(summary);
  for (const url of safe) {
    const item = document.createElement("div");
    item.className = "source";
    const link = document.createElement("a");
    link.href = url;
    link.textContent = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    item.appendChild(link);
    details.appendChild(item);
  }
  el.appendChild(details);
}

function citationLabel(source) {
  return source.location ? `${source.source}, ${source.location}` : source.source;
}

function revealSource(msgId, idx) {
  const details = document.getElementById(`${msgId}-sources`);
  const target = document.getElementById(`${msgId}-src-${idx}`);
  if (!details || !target) return;
  details.open = true;
  target.scrollIntoView({ behavior: "smooth", block: "nearest" });
  target.classList.add("flash");
  setTimeout(() => target.classList.remove("flash"), 1500);
}

function addMeta(el, text) {
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = text;
  el.appendChild(meta);
}

// ---------- Conversation ----------

// One conversation per "New chat": the server keeps its memory, so follow-up questions work.
const newSessionId = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())).replace(/[^A-Za-z0-9_-]/g, "");
let sessionId = newSessionId();

function newChat() {
  sessionId = newSessionId();
  $("messages").replaceChildren();
  const empty = document.createElement("div");
  empty.className = "empty";
  empty.id = "empty-state";
  empty.textContent = "New conversation. Ask a question about your documents.";
  $("messages").appendChild(empty);
  $("question").focus();
}

// ---------- Metadata filters ----------

const splitTags = (value) => value.split(",").map((t) => t.trim()).filter(Boolean);
const selected = (id) => [...$(id).selectedOptions].map((o) => o.value);

function currentFilters() {
  const filters = { sources: selected("filter-sources"), file_types: selected("filter-types"), tags: splitTags($("filter-tags").value) };
  return filters.sources.length || filters.file_types.length || filters.tags.length ? filters : undefined;
}

function updateFilterSummary() {
  const f = currentFilters();
  $("filter-summary").textContent = f
    ? [f.sources.length && `${f.sources.length} document(s)`, f.file_types.join(", "), f.tags.length && `tags: ${f.tags.join(", ")}`]
        .filter(Boolean).join(" · ")
    : "all documents";
}

async function loadSources() {
  try {
    const res = await apiFetch("/api/v1/sources");
    if (!res.ok) return;
    const { sources } = await res.json();
    const fill = (id, values) => {
      const keep = new Set(selected(id));
      $(id).replaceChildren(...values.map((v) => {
        const option = new Option(v, v);
        option.selected = keep.has(v);
        return option;
      }));
    };
    fill("filter-sources", sources.map((s) => s.source));
    fill("filter-types", [...new Set(sources.map((s) => s.file_type))].sort());
  } catch { /* the filter is optional; the chat still works without it */ }
}

// ---------- Guardrails ----------

const GUARDRAIL_TEXT = {
  prompt_injection: "an attempt to override the assistant's instructions",
  jailbreak: "a jailbreak attempt",
  secrets: "a credential or API key",
  blocked_topics: "a topic this assistant doesn't cover",
  length: "a question that is too long",
  pii: "personal data",
  system_prompt_leak: "internal instructions",
  blocked_terms: "a restricted term",
};

function renderGuardrails(el, data) {
  const events = data.guardrails || [];
  if (!events.length) return;
  const note = document.createElement("div");
  note.className = "meta guard";
  const describe = (e) => GUARDRAIL_TEXT[e.check] || e.check.replace("_", " ");
  if (data.blocked) {
    note.textContent = `🛡 Blocked by the usage policy: ${[...new Set(events.filter((e) => e.action === "block").map(describe))].join(", ")}`;
  } else {
    const redacted = events.filter((e) => e.action === "redact").map(describe);
    note.textContent = `🛡 ${redacted.length ? `Removed ${[...new Set(redacted)].join(", ")} before processing` : "Checked by the usage policy"}`;
  }
  el.appendChild(note);
}

// ---------- Ask ----------

async function ask(event) {
  event.preventDefault();
  const input = $("question");
  const question = input.value.trim();
  if (!question) return;

  const mode = document.querySelector('input[name="mode"]:checked').value;
  const btn = $("ask-btn");
  btn.disabled = true;
  input.value = "";

  addMessage("user", question);
  const pending = addMessage("bot pending", mode === "agent" ? "Researching…" : "Thinking…");
  const msgId = `m${++messageCount}`;

  try {
    if (mode === "agent") {
      const data = await postJson("/api/v1/agent", { task: question, session_id: sessionId, filters: currentFilters() });
      pending.className = "msg bot";
      pending.textContent = data.answer;
      renderGuardrails(pending, data);
      renderWebSources(pending, data.web_sources || []);
      addMeta(pending, `${data.tool_calls} search${data.tool_calls === 1 ? "" : "es"} · ${data.model}`);
    } else {
      const data = await postJson("/api/v1/query", { question, session_id: sessionId, filters: currentFilters() });
      pending.className = "msg bot";
      renderAnswer(pending, data.answer, data.sources, msgId);
      renderSources(pending, data.sources, msgId);
      const notes = [data.model];
      if (data.cached) notes.push("cached");
      if (data.standalone_question) notes.push(`understood as: "${data.standalone_question}"`);
      addMeta(pending, notes.join(" · "));
      if (data.grounded === false) {
        // Hallucination guard: the answer has content the passages don't support. Show why.
        const warn = document.createElement("div");
        warn.className = "meta warn";
        warn.textContent = `⚠ Check this answer against the sources: ${data.grounding_issues.join("; ")}`;
        pending.appendChild(warn);
      }
      renderGuardrails(pending, data);
    }
  } catch (err) {
    pending.className = "msg error";
    pending.textContent = err.message;
  } finally {
    btn.disabled = false;
    input.focus();
    pending.scrollIntoView({ behavior: "smooth", block: "end" });
  }
}

// ---------- Ingest ----------

const STATUS_TEXT = {
  added: (r) => `added, ${r.chunks} chunks`,
  updated: (r) => `updated: ${r.added} new chunks embedded, ${r.removed} removed`,
  unchanged: () => "unchanged, skipped",
  empty: () => "no text found",
  failed: (r) => `failed: ${r.error}`,
};

function describeResult(r) {
  const parts = [STATUS_TEXT[r.status](r)];
  if (r.chunking && r.status !== "failed" && r.status !== "unchanged") parts.push(r.chunking.replace("_", "-"));
  if (r.golden_questions) parts.push(`${r.golden_questions} golden Q&A`);
  return `${r.source}: ${parts.join(" · ")}`;
}

async function ingest(event) {
  event.preventDefault();
  const result = $("ingest-result");
  const btn = $("ingest-btn");
  result.className = "result";
  result.textContent = "";

  try {
    const files = $("files").files;
    const text = $("doc-text").value.trim();
    if (!files.length && !text) throw new Error("Paste some text or choose at least one file.");

    btn.disabled = true;
    result.textContent = "Reading, embedding and storing… (new documents also get golden Q&A, which takes a few seconds)";
    const chunking = $("chunking").value || undefined;
    const overlap = $("overlap").value.trim();
    const chunk_overlap_pct = overlap === "" ? undefined : Number(overlap);
    const tags = splitTags($("tags").value);

    const results = [];
    if (files.length) {
      const form = new FormData();
      for (const file of files) form.append("files", file);
      if (chunking) form.append("chunking", chunking);
      if (chunk_overlap_pct !== undefined) form.append("chunk_overlap_pct", String(chunk_overlap_pct));
      if (tags.length) form.append("tags", tags.join(","));
      results.push(...(await postForm("/api/v1/ingest/files", form)).results);
    }
    if (text) {
      const documents = [{ text, source: $("source").value.trim() || "pasted-text" }];
      results.push(...(await postJson("/api/v1/ingest", { documents, chunking, chunk_overlap_pct, tags })).results);
    }

    const failed = results.some((r) => r.status === "failed");
    result.className = failed ? "result err" : "result ok";
    result.textContent = results.map(describeResult).join("\n");
    if (!failed) event.target.reset();
    loadSources(); // new documents become available in the "Search in" filter
  } catch (err) {
    result.className = "result err";
    result.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
}

// ---------- Evaluation ----------

const pct = (value) => (value === null || value === undefined ? "n/a" : `${Math.round(value * 100)}%`);

async function runEvaluation() {
  const out = $("eval-result");
  const btn = $("eval-btn");
  btn.disabled = true;
  out.className = "result";
  const judge = $("eval-judge").checked;
  const limit = Number($("eval-limit").value) || 10;
  out.textContent = judge
    ? `Running ${limit} questions… each is answered, graded by the LLM judge and scored on the 4 RAGAS metrics (about 6 LLM calls per question), so this takes a few minutes.`
    : "Running retrieval checks…";
  try {
    const data = await postJson("/api/v1/eval", { judge, limit });
    if (!data.count) {
      out.textContent = "No golden Q&A yet. Upload a document, or import a golden set (.json).";
      return;
    }
    const lines = [
      `${data.count} questions, top ${data.top_k}`,
      `Evidence retrieved: ${pct(data.evidence_hit_rate)} · right document: ${pct(data.source_hit_rate)} · MRR ${data.mrr ?? "n/a"}`,
    ];
    if (data.judged) {
      lines.push(
        "",
        "LLM as judge",
        `  Answers correct: ${pct(data.answer_accuracy)} · cited the right document: ${pct(data.citation_accuracy)} · passed the hallucination guard: ${pct(data.grounded_rate)}`,
        "",
        "RAGAS",
        `  Faithfulness: ${pct(data.faithfulness)} · answer relevancy: ${pct(data.answer_relevancy)}`,
        `  Context precision: ${pct(data.context_precision)} · context recall: ${pct(data.context_recall)}`,
      );
    }
    const misses = data.items.filter(
      (i) => i.evidence_rank === null || i.correct === false || (i.faithfulness !== null && i.faithfulness < 1),
    );
    if (misses.length) {
      lines.push("", "Needs attention:");
      for (const m of misses.slice(0, 10)) {
        const why = m.evidence_rank === null
          ? "evidence not retrieved"
          : m.correct === false
            ? `answer judged wrong (${m.judge_reason || "no reason"})`
            : `faithfulness ${pct(m.faithfulness)}: some claims aren't supported by the passages`;
        lines.push(`• ${m.question} [${m.source}]: ${why}`);
      }
    }
    out.className = "result ok";
    out.textContent = lines.join("\n");
  } catch (err) {
    out.className = "result err";
    out.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
}

async function importGolden(event) {
  const out = $("eval-result");
  const file = event.target.files[0];
  if (!file) return;
  try {
    const parsed = JSON.parse(await file.text());
    const items = Array.isArray(parsed) ? parsed : parsed.items;
    const data = await postJson("/api/v1/golden", { items });
    out.className = "result ok";
    out.textContent = `Imported ${items.length} golden Q&A from ${file.name}. The golden set now has ${data.count}.`;
  } catch (err) {
    out.className = "result err";
    out.textContent = err instanceof SyntaxError ? `${file.name} is not valid JSON.` : err.message;
  } finally {
    event.target.value = "";
  }
}

// ---------- Screens ----------

function showLogin(message = "") {
  clearSession();
  $("app").hidden = true;
  $("user").hidden = true;
  $("login").hidden = false;
  $("login-error").textContent = message;
  $("email").focus();
}

function showApp(me) {
  $("login").hidden = true;
  $("app").hidden = false;
  const isAdmin = me.role === "admin";
  // The API enforces this too; hiding the panel just avoids offering what would be refused.
  $("knowledge").hidden = !isAdmin;
  loadSources();
  $("app").classList.toggle("chat-only", !isAdmin);
  if (authConfig.enabled) {
    $("user").hidden = false;
    $("user-email").textContent = me.email || "Signed in";
    $("user-role").textContent = me.role;
  }
  $("question").focus();
}

async function loadMe() {
  const res = await apiFetch("/api/v1/me");
  if (!res.ok) throw new Error(describeError(res.status, await res.json().catch(() => null)));
  return res.json();
}

async function signIn(event) {
  event.preventDefault();
  const btn = $("login-btn");
  btn.disabled = true;
  $("login-error").textContent = "";
  try {
    await supabaseAuth("password", { email: $("email").value.trim(), password: $("password").value });
    $("password").value = "";
    showApp(await loadMe());
  } catch (err) {
    $("login-error").textContent = err.message;
  } finally {
    btn.disabled = false;
  }
}

async function signOut() {
  const session = loadSession();
  if (session && authConfig.enabled) {
    // Revokes the refresh token server-side; ignore failures, we clear locally regardless.
    fetch(`${authConfig.supabase_url}/auth/v1/logout`, {
      method: "POST",
      headers: { apikey: authConfig.supabase_publishable_key, Authorization: `Bearer ${session.access_token}` },
    }).catch(() => {});
  }
  showLogin();
}

async function start() {
  try {
    authConfig = await (await fetch("/api/v1/auth/config")).json();
  } catch {
    $("status").dataset.state = "down";
    $("status").textContent = "Backend offline";
    return;
  }
  if (!authConfig.enabled) return showApp({ role: "admin" });
  if (!loadSession()) return showLogin();
  try {
    showApp(await loadMe());
  } catch {
    showLogin();
  }
}

// ---------- Wire up ----------

document.addEventListener("DOMContentLoaded", () => {
  $("login-form").addEventListener("submit", signIn);
  $("signout-btn").addEventListener("click", signOut);
  $("ask-form").addEventListener("submit", ask);
  $("ingest-form").addEventListener("submit", ingest);
  $("eval-btn").addEventListener("click", runEvaluation);
  $("new-chat-btn").addEventListener("click", newChat);
  for (const id of ["filter-sources", "filter-types", "filter-tags"]) $(id).addEventListener("change", updateFilterSummary);
  $("golden-file").addEventListener("change", importGolden);
  start();
  $("question").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("ask-form").requestSubmit();
    }
  });
  refreshStatus();
  setInterval(refreshStatus, 30_000);
});
