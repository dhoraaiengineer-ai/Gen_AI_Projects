// Knowledge Copilot UI. No framework, no build step.
// Security: model output and user data are only ever inserted as text nodes (never innerHTML), so
// nothing they contain can become markup or script. The page's CSP allows only same-origin assets.
"use strict";

const $ = (id) => document.getElementById(id);

/** Build an element: el("div", { class: "x", text: "hi", title: "t" }, [children]) */
function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of [].concat(children)) if (child) node.append(child);
  return node;
}

function icon(name, cls = "icon") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", cls);
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}

const storage = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, value); } catch { /* storage blocked */ } },
};

// ---------- Theme ----------

function applyTheme(theme) {
  if (theme) document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
  const dark = theme ? theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  $("theme-btn").replaceChildren(icon(dark ? "sun" : "moon"));
}

function toggleTheme() {
  const dark = document.documentElement.dataset.theme
    ? document.documentElement.dataset.theme === "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches;
  const next = dark ? "light" : "dark";
  storage.set("rag.theme", next);
  applyTheme(next);
}

// ---------- Toasts ----------

function toast(message, kind = "info") {
  const node = el("div", { class: `toast ${kind}`, role: "status" }, [
    icon(kind === "err" ? "alert" : kind === "ok" ? "check" : "logo"),
    el("div", { text: message }),
  ]);
  $("toasts").append(node);
  setTimeout(() => node.remove(), 4500);
}

// ---------- Auth (Supabase Auth REST API; tokens kept in sessionStorage for this tab) ----------

const SESSION_KEY = "rag.session";
let authConfig = { enabled: false };
let me = { role: "user", email: null };

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

async function getJson(path) {
  return readJson(await apiFetch(path));
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
  if (status === 404) return data?.detail || "Not found.";
  if (status === 413) return data?.detail || "File too large.";
  if (status === 429) {
    // Our own per-user limit says how long to wait; otherwise it's the LLM provider's quota.
    if (typeof data?.detail === "string" && data.detail.startsWith("Too many requests")) return data.detail;
    return "The AI provider's usage limit was reached. Please try again in a little while.";
  }
  if (status === 503) return "The AI service is temporarily unavailable. Please try again in a minute.";
  if (status === 502) return "The AI provider returned an error. Please try again.";
  if (status === 422 && Array.isArray(data?.detail)) {
    return "Invalid input: " + data.detail.map((d) => d.msg).join("; ");
  }
  return data?.detail || `Request failed (HTTP ${status}).`;
}

// ---------- Status ----------

async function refreshStatus() {
  const pill = $("status");
  try {
    const res = await fetch("/health/ready");
    const data = await res.json();
    const ok = res.ok && data.status === "ok";
    pill.dataset.state = ok ? "ok" : "degraded";
    $("status-text").textContent = ok ? "Online" : "Degraded";
  } catch {
    pill.dataset.state = "down";
    $("status-text").textContent = "Offline";
  }
}

// ---------- Navigation ----------

const VIEWS = { chat: "Chat", knowledge: "Knowledge base", eval: "Evaluation" };
let currentView = "chat";

function setView(name) {
  if (name !== "chat" && me.role !== "admin") name = "chat";
  currentView = name;
  for (const key of Object.keys(VIEWS)) $(`view-${key}`).hidden = key !== name;
  for (const item of document.querySelectorAll(".nav-item")) {
    if (item.dataset.view === name) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  }
  $("view-title").textContent = VIEWS[name];
  $("mode-switch").hidden = name !== "chat";
  closeNav();
  if (name === "knowledge") loadDocuments();
  if (name === "chat") $("question").focus();
}

function openNav() { $("app").classList.add("nav-open"); $("scrim").hidden = false; }
function closeNav() { $("app").classList.remove("nav-open"); $("scrim").hidden = true; }

// ---------- Markdown (safe: builds DOM nodes, never HTML strings) ----------

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[\d+(?:\s*,\s*\d+)*\]|(?<![\w*])\*[^*\s][^*]*\*(?!\*))/g;

function renderInline(parent, text, ctx) {
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    if (match.index > last) parent.append(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("**")) parent.append(el("strong", { text: token.slice(2, -2) }));
    else if (token.startsWith("`")) parent.append(el("code", { text: token.slice(1, -1) }));
    else if (token.startsWith("[")) {
      for (const n of token.slice(1, -1).split(",").map((s) => Number(s.trim()))) parent.append(citeChip(n, ctx));
    } else parent.append(el("em", { text: token.slice(1, -1) }));
    last = match.index + token.length;
  }
  if (last < text.length) parent.append(text.slice(last));
}

function renderMarkdown(text, ctx = {}) {
  const root = document.createDocumentFragment();
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  let list = null;
  let para = [];
  const flushPara = () => {
    if (!para.length) return;
    const p = el("p");
    para.forEach((line, i) => {
      if (i) p.append(el("br"));
      renderInline(p, line, ctx);
    });
    root.append(p);
    para = [];
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const ordered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    if (bullet || ordered) {
      flushPara();
      const tag = bullet ? "ul" : "ol";
      if (!list || list.tagName.toLowerCase() !== tag) { list = el(tag); root.append(list); }
      const li = el("li");
      renderInline(li, (bullet || ordered)[1], ctx);
      list.append(li);
    } else if (heading) {
      flushPara(); list = null;
      const h = el("h4");
      renderInline(h, heading[1], ctx);
      root.append(h);
    } else if (!line.trim()) {
      flushPara(); list = null;
    } else {
      list = null;
      para.push(line);
    }
  }
  flushPara();
  return root;
}

function citeChip(n, ctx) {
  const source = ctx.sources?.[n - 1];
  if (!source) return document.createTextNode(`[${n}]`);
  return el("button", {
    type: "button",
    class: "cite",
    text: String(n),
    title: `${source.source}${source.location ? ` · ${source.location}` : ""}`,
    "aria-label": `Source ${n}: ${source.source}`,
    onclick: () => revealSource(ctx.msgId, n),
  });
}

// ---------- Chat ----------

let sessionId = newSessionId();
let messageCount = 0;
let knownSources = [];

function newSessionId() {
  return (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())).replace(/[^A-Za-z0-9_-]/g, "");
}

function mode() {
  return document.querySelector('input[name="mode"]:checked')?.value || "query";
}

function scrollToBottom() {
  const box = $("chat-scroll");
  box.scrollTop = box.scrollHeight;
}

function fileType(name) {
  const ext = (name.split(".").pop() || "").toLowerCase();
  return name.includes(".") ? ext : "other";
}

function typeBadge(type) {
  const known = ["pdf", "xlsx", "csv", "tsv", "docx", "pptx", "png", "jpg", "jpeg", "tif", "tiff", "webp", "bmp", "md", "txt", "json", "web"];
  return el("span", { class: `ftype ft-${known.includes(type) ? type : "other"}`, text: type.slice(0, 4).toUpperCase(), "aria-hidden": "true" });
}

function renderWelcome({ animate = true } = {}) {
  const docs = knownSources.slice(0, 2).map((s) => s.source);
  const suggestions = [
    ...docs.map((d) => ({ icon: "doc", title: `Summarise ${d}`, sub: "Key points, with citations", q: `Summarise the key points of ${d}.` })),
    { icon: "search", title: "What are the main results?", sub: "Numbers and findings across documents", q: "What are the main results and the most important numbers?" },
    { icon: "layers", title: "List key dates and identifiers", sub: "Dates, IDs, versions, references", q: "List the key dates, identifiers and reference numbers mentioned in the documents." },
    { icon: "globe", title: "Explain a concept, with the web", sub: "Uses Research mode", q: "Explain the main technical concept in these documents and how it is used.", research: true },
  ].slice(0, 4);

  const welcome = el("div", { class: animate ? "welcome" : "welcome no-anim", id: "welcome" }, [
    el("div", { class: "welcome-mark" }, icon("logo")),
    el("h2", {}, [document.createTextNode("Ask your "), el("span", { class: "gradient-text", text: "knowledge base" })]),
    el("p", { text: "Answers come only from your documents, with a citation on every fact. Click a citation to see the exact passage." }),
    el("div", { class: "suggestions" }, suggestions.map((s) => el("button", {
      type: "button",
      class: "suggestion",
      onclick: () => {
        if (s.research) document.querySelector('input[name="mode"][value="agent"]').checked = true;
        $("question").value = s.q;
        $("ask-form").requestSubmit();
      },
    }, [el("span", { class: "s-icon" }, icon(s.icon)), el("span", {}, [el("strong", { text: s.title }), el("span", { text: s.sub })])]))),
  ]);
  $("messages").replaceChildren(welcome);
}

function addUserMessage(text) {
  $("welcome")?.remove();
  const node = el("div", { class: "msg user" }, el("div", { class: "bubble", text }));
  $("messages").append(node);
  scrollToBottom();
}

const PHASES = {
  query: ["Checking your question", "Searching your documents", "Ranking the best passages", "Writing a cited answer"],
  agent: ["Planning the research", "Searching your documents", "Checking the web where needed", "Combining the findings"],
};

function addThinking(kind) {
  const label = el("span", { text: PHASES[kind][0] });
  const body = el("div", { class: "answer" }, [
    el("div", { class: "thinking" }, [el("span", { class: "dots" }, [el("i"), el("i"), el("i")]), label]),
    el("div", { class: "skeleton w80" }),
    el("div", { class: "skeleton w60" }),
  ]);
  const node = el("div", { class: "msg bot" }, [el("div", { class: "msg-avatar" }, icon("logo")), el("div", { class: "msg-body" }, body)]);
  $("messages").append(node);
  scrollToBottom();
  let i = 0;
  const timer = setInterval(() => {
    i = Math.min(i + 1, PHASES[kind].length - 1);
    label.textContent = PHASES[kind][i];
  }, 1600);
  return { node, stop: () => clearInterval(timer) };
}

function botMessage(node, { answer, sources = [], webSources = [], meta = [], notices = [], msgId, error = false }) {
  const body = el("div", { class: "answer" });
  body.append(renderMarkdown(answer, { sources, msgId }));
  const actions = el("span", { class: "msg-actions" }, [
    el("button", {
      type: "button", class: "btn btn-ghost btn-icon btn-sm", title: "Copy answer", "aria-label": "Copy answer",
      onclick: async (e) => {
        try {
          await navigator.clipboard.writeText(answer);
          e.currentTarget.replaceChildren(icon("check"));
          toast("Answer copied", "ok");
        } catch { toast("Copy isn't available in this browser", "err"); }
      },
    }, icon("copy")),
  ]);
  const children = [body, ...notices];
  if (!error) children.push(el("div", { class: "msg-meta" }, [...meta, actions]));
  if (sources.length) children.push(renderSources(sources, msgId));
  if (webSources.length) children.push(renderWebSources(webSources));
  node.className = `msg bot${error ? " error" : ""}`;
  node.replaceChildren(el("div", { class: "msg-avatar" }, icon(error ? "alert" : "logo")), el("div", { class: "msg-body" }, children));
}

function renderSources(sources, msgId) {
  const grid = el("div", { class: "source-grid" });
  sources.forEach((s, i) => {
    const bar = el("i");
    bar.style.width = `${Math.round(Math.max(0, Math.min(1, s.score)) * 100)}%`;
    const card = el("button", {
      type: "button", class: "source-card", id: `${msgId}-src-${i + 1}`, title: "Show the full passage",
      onclick: () => card.classList.toggle("open"),
    }, [
      el("div", { class: "source-top" }, [
        el("span", { class: "source-num", text: String(i + 1) }),
        typeBadge(fileType(s.source)),
        el("span", { class: "source-name", text: s.source }),
      ]),
      s.location ? el("span", { class: "source-loc", text: s.location }) : null,
      el("div", { class: "relevance", title: `Relevance ${Math.round(s.score * 100)}%` }, bar),
      el("div", { class: "source-text", text: s.text }),
    ]);
    grid.append(card);
  });
  const head = el("div", { class: "sources-head" }, [icon("cite"), document.createTextNode(`${sources.length} source${sources.length > 1 ? "s" : ""}`)]);
  return el("div", { class: "sources" }, [head, grid]);
}

function renderWebSources(urls) {
  const safe = urls.filter((u) => /^https?:\/\//i.test(u));
  if (!safe.length) return null;
  return el("div", { class: "sources web-sources" }, [
    el("div", { class: "sources-head" }, [icon("globe"), document.createTextNode(`${safe.length} web source${safe.length > 1 ? "s" : ""}`)]),
    el("div", { class: "source-grid" }, safe.map((url) => el("a", {
      class: "source-card", href: url, target: "_blank", rel: "noopener noreferrer",
    }, [el("div", { class: "source-top" }, [typeBadge("web"), el("span", { class: "source-name", text: new URL(url).hostname })]),
      el("span", { class: "source-loc", text: url })]))),
  ]);
}

function revealSource(msgId, n) {
  const card = document.getElementById(`${msgId}-src-${n}`);
  if (!card) return;
  card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  card.classList.add("flash", "open");
  setTimeout(() => card.classList.remove("flash"), 1600);
}

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

function notices(data) {
  const out = [];
  const events = data.guardrails || [];
  const describe = (e) => GUARDRAIL_TEXT[e.check] || e.check.replace(/_/g, " ");
  if (data.blocked) {
    const why = [...new Set(events.filter((e) => e.action === "block").map(describe))].join(", ");
    out.push(el("div", { class: "notice blocked" }, [icon("shield"), el("span", { text: `Stopped by the usage policy${why ? `: ${why}` : ""}.` })]));
  } else {
    const removed = [...new Set(events.filter((e) => e.action === "redact").map(describe))];
    if (removed.length) {
      out.push(el("div", { class: "notice guard" }, [icon("shield"), el("span", { text: `Protected: ${removed.join(", ")} removed before processing.` })]));
    }
  }
  if (data.grounded === false) {
    out.push(el("div", { class: "notice warn" }, [icon("alert"), el("span", { text: `Double-check this answer against the sources: ${data.grounding_issues.join("; ")}.` })]));
  }
  return out;
}

function metaBadges(data, ms) {
  const badges = [];
  if (data.model && data.model !== "guardrails") badges.push(el("span", { class: "badge", text: data.model }));
  if (data.cached) badges.push(el("span", { class: "badge badge-ok" }, [icon("bolt"), document.createTextNode("Instant · cached")]));
  if (data.grounded === true) badges.push(el("span", { class: "badge badge-ok" }, [icon("check"), document.createTextNode("Grounded")]));
  if (data.tool_calls !== undefined) badges.push(el("span", { class: "badge", text: `${data.tool_calls} search${data.tool_calls === 1 ? "" : "es"}` }));
  if (ms) badges.push(el("span", { class: "badge", text: `${(ms / 1000).toFixed(1)}s` }));
  if (data.standalone_question) badges.push(el("span", { class: "badge badge-brand", title: "How the follow-up was understood", text: `Understood as: ${data.standalone_question}` }));
  return badges;
}

async function ask(event) {
  event.preventDefault();
  const input = $("question");
  const question = input.value.trim();
  if (!question) return;
  const kind = mode();
  const btn = $("ask-btn");
  btn.disabled = true;
  input.value = "";
  autosize();

  addUserMessage(question);
  const thinking = addThinking(kind);
  const msgId = `m${++messageCount}`;
  const started = performance.now();
  try {
    const filters = currentFilters();
    const data = kind === "agent"
      ? await postJson("/api/v1/agent", { task: question, session_id: sessionId, filters })
      : await postJson("/api/v1/query", { question, session_id: sessionId, filters });
    thinking.stop();
    botMessage(thinking.node, {
      answer: data.answer,
      sources: data.sources || [],
      webSources: data.web_sources || [],
      meta: metaBadges(data, performance.now() - started),
      notices: notices(data),
      msgId,
    });
    loadHistory();
  } catch (err) {
    thinking.stop();
    botMessage(thinking.node, { answer: err.message, msgId, error: true });
  } finally {
    btn.disabled = false;
    input.focus();
    scrollToBottom();
  }
}

function newChat() {
  sessionId = newSessionId();
  renderWelcome();
  markActiveHistory();
  setView("chat");
}

function autosize() {
  const box = $("question");
  box.style.height = "auto";
  box.style.height = `${Math.min(box.scrollHeight, 200)}px`;
}

// ---------- Conversation history (long-term memory) ----------

async function loadHistory() {
  try {
    const { sessions } = await getJson("/api/v1/conversations");
    const list = $("history");
    if (!sessions.length) {
      list.replaceChildren(el("li", { class: "history-empty", text: "Your conversations appear here." }));
      return;
    }
    list.replaceChildren(...sessions.slice(0, 30).map((s) => el("li", {}, el("button", {
      type: "button", class: "history-item", "data-session": s.session_id, title: s.title, text: s.title || "Untitled conversation",
      onclick: () => openConversation(s.session_id),
    }))));
    markActiveHistory();
  } catch { /* history is optional */ }
}

function markActiveHistory() {
  for (const item of document.querySelectorAll(".history-item")) item.classList.toggle("active", item.dataset.session === sessionId);
}

async function openConversation(id) {
  try {
    const { messages } = await getJson(`/api/v1/conversations/${encodeURIComponent(id)}`);
    sessionId = id;
    setView("chat");
    $("messages").replaceChildren();
    for (const m of messages) {
      if (m.role === "user") addUserMessage(m.content);
      else {
        const node = el("div", { class: "msg bot" });
        $("messages").append(node);
        botMessage(node, { answer: m.content, msgId: `h${++messageCount}`, meta: [el("span", { class: "badge", text: "From history" })] });
      }
    }
    markActiveHistory();
    scrollToBottom();
  } catch (err) {
    toast(err.message, "err");
  }
}

// ---------- Metadata filters ----------

const filterState = { sources: new Set(), types: new Set() };

async function loadSources() {
  try {
    const { sources } = await getJson("/api/v1/sources");
    knownSources = sources;
    const list = $("filter-sources");
    list.replaceChildren(...(sources.length ? sources.map((s) => {
      const box = el("input", { type: "checkbox", value: s.source });
      box.checked = filterState.sources.has(s.source);
      box.addEventListener("change", () => { box.checked ? filterState.sources.add(s.source) : filterState.sources.delete(s.source); renderChips(); });
      return el("label", {}, [box, typeBadge(s.file_type), el("span", { text: s.source })]);
    }) : [el("span", { class: "hint", text: "No documents yet" })]));
    const types = [...new Set(sources.map((s) => s.file_type))].sort();
    $("filter-types").replaceChildren(...types.map((t) => {
      const box = el("input", { type: "checkbox", value: t });
      box.checked = filterState.types.has(t);
      box.addEventListener("change", () => { box.checked ? filterState.types.add(t) : filterState.types.delete(t); renderChips(); });
      return el("label", { class: "toggle-chip" }, [box, el("span", { text: t.toUpperCase() })]);
    }));
    if ($("welcome")) renderWelcome({ animate: false }); // add document-specific suggestions without a flicker
  } catch { /* the filter is optional */ }
}

const splitTags = (value) => value.split(",").map((t) => t.trim()).filter(Boolean);

function currentFilters() {
  const f = { sources: [...filterState.sources], file_types: [...filterState.types], tags: splitTags($("filter-tags").value) };
  return f.sources.length || f.file_types.length || f.tags.length ? f : undefined;
}

function renderChips() {
  const chips = [];
  const chip = (label, remove) => el("span", { class: "chip" }, [
    document.createTextNode(label),
    el("button", { type: "button", "aria-label": `Remove filter ${label}`, onclick: () => { remove(); syncFilterInputs(); renderChips(); } }, icon("x")),
  ]);
  for (const s of filterState.sources) chips.push(chip(s, () => filterState.sources.delete(s)));
  for (const t of filterState.types) chips.push(chip(t.toUpperCase(), () => filterState.types.delete(t)));
  const tags = splitTags($("filter-tags").value);
  for (const t of tags) chips.push(chip(`#${t}`, () => { $("filter-tags").value = tags.filter((x) => x !== t).join(", "); }));
  $("filter-chips").replaceChildren(...chips);
}

function syncFilterInputs() {
  for (const box of $("filter-sources").querySelectorAll("input")) box.checked = filterState.sources.has(box.value);
  for (const box of $("filter-types").querySelectorAll("input")) box.checked = filterState.types.has(box.value);
}

function toggleFilterPanel(open) {
  const panel = $("filter-panel");
  const show = open ?? panel.hidden;
  panel.hidden = !show;
  $("filter-btn").setAttribute("aria-expanded", String(show));
  if (show) loadSources();
}

// ---------- Knowledge base ----------

let pendingFiles = [];

function setPendingFiles(files) {
  pendingFiles = [...files];
  $("file-list").replaceChildren(...pendingFiles.map((f, i) => el("span", { class: "file-chip" }, [
    typeBadge(fileType(f.name)),
    el("span", { text: `${f.name} · ${(f.size / 1024).toFixed(0)} KB` }),
    el("button", { type: "button", class: "btn btn-ghost btn-icon btn-sm", "aria-label": `Remove ${f.name}`,
      onclick: () => setPendingFiles(pendingFiles.filter((_, j) => j !== i)) }, icon("x")),
  ])));
}

const STATUS = {
  added: ["badge-ok", "Added"],
  updated: ["badge-brand", "Updated"],
  unchanged: ["badge", "Unchanged"],
  empty: ["badge-warn", "No text"],
  failed: ["badge-err", "Failed"],
};

function resultRow(r) {
  const [cls, label] = STATUS[r.status] || ["badge", r.status];
  let detail = "";
  if (r.status === "added") detail = `${r.chunks} chunks`;
  else if (r.status === "updated") detail = `${r.added} new, ${r.removed} removed`;
  else if (r.status === "unchanged") detail = "already up to date";
  else if (r.status === "failed") detail = r.error || "";
  if (r.golden_questions) detail += ` · ${r.golden_questions} test questions`;
  if (r.guardrail_flags?.length) detail += ` · flagged: ${r.guardrail_flags.join(", ").replace(/_/g, " ")}`;
  return el("li", {}, [typeBadge(fileType(r.source)), el("span", { class: "r-name", text: r.source }),
    el("span", { class: "r-detail", text: detail }), el("span", { class: `badge ${cls}`, text: label })]);
}

async function ingest(event) {
  event.preventDefault();
  const text = $("doc-text").value.trim();
  if (!pendingFiles.length && !text) { toast("Choose files or paste some text first.", "err"); return; }
  const chunking = $("chunking").value || undefined;
  const overlap = $("overlap").value.trim();
  const chunk_overlap_pct = overlap === "" ? undefined : Number(overlap);
  const tags = splitTags($("tags").value);
  $("ingest-btn").disabled = true;
  $("ingest-progress").hidden = false;
  $("ingest-results").replaceChildren();
  try {
    const results = [];
    if (pendingFiles.length) {
      const form = new FormData();
      for (const file of pendingFiles) form.append("files", file);
      if (chunking) form.append("chunking", chunking);
      if (chunk_overlap_pct !== undefined) form.append("chunk_overlap_pct", String(chunk_overlap_pct));
      if (tags.length) form.append("tags", tags.join(","));
      results.push(...(await postForm("/api/v1/ingest/files", form)).results);
    }
    if (text) {
      const documents = [{ text, source: $("source").value.trim() || "pasted-text" }];
      results.push(...(await postJson("/api/v1/ingest", { documents, chunking, chunk_overlap_pct, tags })).results);
    }
    $("ingest-results").replaceChildren(...results.map(resultRow));
    const failed = results.filter((r) => r.status === "failed").length;
    toast(failed ? `${failed} file(s) failed. See details below.` : `${results.length} document(s) processed`, failed ? "err" : "ok");
    if (!failed) { setPendingFiles([]); $("ingest-form").reset(); }
    loadDocuments();
    loadSources();
  } catch (err) {
    toast(err.message, "err");
  } finally {
    $("ingest-btn").disabled = false;
    $("ingest-progress").hidden = true;
  }
}

async function loadDocuments() {
  try {
    const { documents } = await getJson("/api/v1/documents");
    $("stat-docs").textContent = documents.length;
    $("stat-chunks").textContent = documents.reduce((n, d) => n + d.chunks, 0).toLocaleString();
    $("stat-types").textContent = new Set(documents.map((d) => fileType(d.source))).size;
    $("docs-empty").hidden = documents.length > 0;
    $("doc-rows").replaceChildren(...documents.map((d) => el("tr", {}, [
      el("td", {}, el("div", { class: "doc-name" }, [typeBadge(fileType(d.source)), el("span", { text: d.source, title: d.source })])),
      el("td", { text: String(d.chunks) }),
      el("td", {}, el("span", { class: "badge", text: d.chunking.replace("_", "-") })),
      el("td", {}, el("button", {
        type: "button", class: "btn btn-ghost btn-icon btn-sm btn-danger", title: `Delete ${d.source}`, "aria-label": `Delete ${d.source}`,
        onclick: () => deleteDocument(d.source),
      }, icon("trash"))),
    ])));
  } catch (err) {
    if (me.role === "admin") toast(err.message, "err");
  }
}

async function deleteDocument(source) {
  if (!confirm(`Delete "${source}" from the knowledge base?\nIts chunks and test questions are removed too.`)) return;
  try {
    const res = await apiFetch(`/api/v1/documents?source=${encodeURIComponent(source)}`, { method: "DELETE" });
    const data = await readJson(res);
    toast(`Deleted ${source} (${data.chunks_deleted} chunks)`, "ok");
    loadDocuments();
    loadSources();
  } catch (err) {
    toast(err.message, "err");
  }
}

// ---------- Evaluation ----------

const METRIC_GROUPS = [
  ["Retrieval", [
    ["evidence_hit_rate", "Evidence found", "The supporting passage was retrieved"],
    ["source_hit_rate", "Right document", "Retrieved from the correct file"],
    ["mrr", "Ranking (MRR)", "How high the right passage ranks"],
  ]],
  ["LLM as judge", [
    ["answer_accuracy", "Correct answers", "Matches the reference answer"],
    ["citation_accuracy", "Correct citations", "Cites the right document"],
    ["grounded_rate", "Grounded", "Passed the hallucination guard"],
  ]],
  ["RAGAS", [
    ["faithfulness", "Faithfulness", "Claims supported by the passages"],
    ["answer_relevancy", "Answer relevancy", "Answers the question asked"],
    ["context_precision", "Context precision", "Useful passages ranked first"],
    ["context_recall", "Context recall", "Reference facts were retrieved"],
  ]],
];

function metricCard(value, name, desc) {
  const ring = el("div", { class: "ring", "data-label": value == null ? "n/a" : `${Math.round(value * 100)}%` });
  ring.style.setProperty("--p", value == null ? 0 : Math.round(value * 100));
  ring.classList.add(value == null ? "na" : value >= 0.85 ? "good" : value >= 0.6 ? "mid" : "bad");
  return el("div", { class: "card metric" }, [ring, el("div", {}, [el("div", { class: "m-name", text: name }), el("div", { class: "m-desc", text: desc })])]);
}

async function runEvaluation() {
  const judge = $("eval-judge").checked;
  const limit = Number($("eval-limit").value) || 10;
  $("eval-btn").disabled = true;
  $("eval-progress").hidden = false;
  $("eval-status").textContent = judge
    ? `Answering and grading ${limit} questions. This takes a few minutes…`
    : "Checking retrieval…";
  try {
    const data = await postJson("/api/v1/eval", { judge, limit });
    if (!data.count) {
      $("eval-status").textContent = "No test questions yet. Upload documents (they generate some) or import a golden set.";
      return;
    }
    $("eval-status").textContent = `${data.count} questions · top ${data.top_k} passages · ${data.judged ? "answers graded" : "retrieval only"}`;
    $("eval-metrics").hidden = false;
    $("eval-metrics").replaceChildren(...METRIC_GROUPS
      .filter(([group]) => data.judged || group === "Retrieval")
      .map(([group, metrics]) => el("div", { class: "metric-group" }, [
        el("h3", { text: group }),
        el("div", { class: "metrics" }, metrics.map(([key, name, desc]) => metricCard(data[key], name, desc))),
      ])));
    const misses = data.items.filter((i) => i.evidence_rank === null || i.correct === false || (i.faithfulness !== null && i.faithfulness < 1));
    $("eval-attention-card").hidden = misses.length === 0;
    $("eval-attention").replaceChildren(...misses.slice(0, 20).map((m) => el("li", {}, [
      el("div", { text: m.question }),
      el("div", { class: "why", text: m.evidence_rank === null
        ? `Evidence not retrieved from ${m.source}`
        : m.correct === false
          ? `Answer judged wrong: ${m.judge_reason || "no reason given"}`
          : `Faithfulness ${Math.round(m.faithfulness * 100)}%: some claims aren't supported by the passages` }),
    ])));
    toast("Evaluation finished", "ok");
  } catch (err) {
    $("eval-status").textContent = err.message;
    toast(err.message, "err");
  } finally {
    $("eval-btn").disabled = false;
    $("eval-progress").hidden = true;
  }
}

async function importGolden(event) {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const parsed = JSON.parse(await file.text());
    const items = Array.isArray(parsed) ? parsed : parsed.items;
    const data = await postJson("/api/v1/golden", { items });
    toast(`Imported ${items.length} test questions. The set now has ${data.count}.`, "ok");
  } catch (err) {
    toast(err instanceof SyntaxError ? `${file.name} is not valid JSON.` : err.message, "err");
  } finally {
    event.target.value = "";
  }
}

// ---------- Screens ----------

function showLogin(message = "") {
  clearSession();
  $("app").hidden = true;
  $("login").hidden = false;
  $("login-error").textContent = message;
  $("email").focus();
}

function initials(email) {
  if (!email) return "U";
  const name = email.split("@")[0].replace(/[^A-Za-z]/g, " ").trim().split(/\s+/);
  return ((name[0]?.[0] || "U") + (name[1]?.[0] || "")).toUpperCase();
}

function showApp(user) {
  me = user;
  $("login").hidden = true;
  $("app").hidden = false;
  const isAdmin = me.role === "admin";
  for (const item of document.querySelectorAll(".admin-only")) item.hidden = !isAdmin;
  $("user-email").textContent = me.email || (authConfig.enabled ? "Signed in" : "Local developer");
  $("user-role").textContent = isAdmin ? "Admin" : "User";
  $("user-avatar").textContent = initials(me.email);
  $("signout-btn").hidden = !authConfig.enabled;
  renderWelcome();
  setView("chat");
  loadSources();
  loadHistory();
}

async function loadMe() {
  return getJson("/api/v1/me");
}

async function signIn(event) {
  event.preventDefault();
  const btn = $("login-btn");
  btn.disabled = true;
  btn.textContent = "Signing in…";
  $("login-error").textContent = "";
  try {
    await supabaseAuth("password", { email: $("email").value.trim(), password: $("password").value });
    $("password").value = "";
    showApp(await loadMe());
  } catch (err) {
    $("login-error").textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Sign in";
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
    $("status-text").textContent = "Offline";
    showLogin("The service is unreachable. Please try again shortly.");
    return;
  }
  if (!authConfig.enabled) return showApp({ role: "admin", email: null });
  if (!loadSession()) return showLogin();
  try {
    showApp(await loadMe());
  } catch {
    showLogin();
  }
}

// ---------- Wire up ----------

document.addEventListener("DOMContentLoaded", () => {
  applyTheme(storage.get("rag.theme"));
  $("theme-btn").addEventListener("click", toggleTheme);
  $("login-form").addEventListener("submit", signIn);
  $("signout-btn").addEventListener("click", signOut);
  $("ask-form").addEventListener("submit", ask);
  $("new-chat-btn").addEventListener("click", newChat);
  $("menu-btn").addEventListener("click", openNav);
  $("scrim").addEventListener("click", closeNav);
  for (const item of document.querySelectorAll(".nav-item")) item.addEventListener("click", () => setView(item.dataset.view));

  const question = $("question");
  question.addEventListener("input", autosize);
  question.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("ask-form").requestSubmit();
    }
  });

  $("filter-btn").addEventListener("click", () => toggleFilterPanel());
  $("filter-done").addEventListener("click", () => toggleFilterPanel(false));
  $("filter-clear").addEventListener("click", () => {
    filterState.sources.clear();
    filterState.types.clear();
    $("filter-tags").value = "";
    syncFilterInputs();
    renderChips();
  });
  $("filter-tags").addEventListener("input", renderChips);
  document.addEventListener("click", (e) => {
    if (!$("filter-panel").hidden && !e.target.closest(".popover")) toggleFilterPanel(false);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { toggleFilterPanel(false); closeNav(); }
  });

  const drop = $("dropzone");
  drop.addEventListener("click", () => $("files").click());
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("files").click(); } });
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("drag"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("drag"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("drag");
    setPendingFiles([...pendingFiles, ...e.dataTransfer.files]);
  });
  $("files").addEventListener("change", (e) => { setPendingFiles([...pendingFiles, ...e.target.files]); e.target.value = ""; });
  $("ingest-form").addEventListener("submit", ingest);
  $("docs-refresh").addEventListener("click", loadDocuments);
  $("eval-btn").addEventListener("click", runEvaluation);
  $("golden-file").addEventListener("change", importGolden);

  start();
  refreshStatus();
  setInterval(refreshStatus, 30_000);
});
