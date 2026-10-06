// RAG Assistant UI. No framework, no build step.
// Model output is always inserted as text (never innerHTML) so it can't inject markup.
"use strict";

const MAX_FILE_CHARS = 1_000_000; // matches DocumentIn.text max_length on the API
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
  const res = await apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON error body */ }
  if (!res.ok) throw new Error(describeError(res.status, data));
  return data;
}

function describeError(status, data) {
  if (status === 403) return "You don't have permission to do that (admin role required).";
  if (status === 429) return "The LLM daily token limit or rate limit was reached. Try again later.";
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
      btn.title = sources[idx - 1].source;
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
    name.textContent = `[${i + 1}] ${s.source}`;
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
      const data = await postJson("/api/v1/agent", { task: question });
      pending.className = "msg bot";
      pending.textContent = data.answer;
      addMeta(pending, `${data.tool_calls} search${data.tool_calls === 1 ? "" : "es"} · ${data.model}`);
    } else {
      const data = await postJson("/api/v1/query", { question });
      pending.className = "msg bot";
      renderAnswer(pending, data.answer, data.sources, msgId);
      renderSources(pending, data.sources, msgId);
      addMeta(pending, data.model);
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

async function readFiles(fileList) {
  const docs = [];
  for (const file of fileList) {
    const text = await file.text();
    if (text.length > MAX_FILE_CHARS) throw new Error(`${file.name} is too large (max ${MAX_FILE_CHARS.toLocaleString()} characters).`);
    if (text.trim()) docs.push({ text, source: file.name });
  }
  return docs;
}

async function ingest(event) {
  event.preventDefault();
  const result = $("ingest-result");
  const btn = $("ingest-btn");
  result.className = "result";
  result.textContent = "";

  try {
    const documents = await readFiles($("files").files);
    const text = $("doc-text").value.trim();
    if (text) documents.push({ text, source: $("source").value.trim() || "pasted-text" });
    if (!documents.length) throw new Error("Paste some text or choose at least one file.");

    btn.disabled = true;
    result.textContent = "Embedding and storing…";
    const data = await postJson("/api/v1/ingest", { documents });

    result.className = "result ok";
    result.textContent = `Added ${data.documents} document${data.documents > 1 ? "s" : ""} (${data.chunks} chunk${data.chunks === 1 ? "" : "s"}).`;
    event.target.reset();
  } catch (err) {
    result.className = "result err";
    result.textContent = err.message;
  } finally {
    btn.disabled = false;
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
