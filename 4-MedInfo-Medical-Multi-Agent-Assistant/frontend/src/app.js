"use strict";
// MedInfo Assistant UI. Rule: model output and any server text are ONLY ever inserted as text nodes
// (textContent / createTextNode). innerHTML is never used.

(function () {
  const $ = (id) => document.getElementById(id);
  const state = { cfg: null, session: null, me: null, conversationId: null, sources: null, file: null };
  const PHASES = [
    ["safety", "Checking for urgent symptoms and safety"],
    ["searching", "Searching trusted sources"],
    ["generating", "Writing a cited answer"],
    ["verifying", "Checking every statement against the sources"],
  ];

  // ---------- small helpers ----------
  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function store(key, value) {
    try { value === null ? sessionStorage.removeItem(key) : sessionStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* unavailable */ }
  }
  function load(key) {
    try { return JSON.parse(sessionStorage.getItem(key) || "null"); } catch (_) { return null; }
  }
  function pref(key, value) {
    try { if (value === undefined) return localStorage.getItem(key); localStorage.setItem(key, value); } catch (_) { return null; }
    return null;
  }
  const ROLE_RANK = { user: 0, clinician: 1, admin: 2 };
  const hasRole = (r) => state.me && ROLE_RANK[state.me.role] >= ROLE_RANK[r];

  // ---------- theme ----------
  function applyTheme(t) {
    if (t) document.documentElement.setAttribute("data-theme", t);
    else document.documentElement.removeAttribute("data-theme");
  }
  applyTheme(pref("theme"));
  function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme")
      || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    applyTheme(next);
    pref("theme", next);
  }

  // ---------- auth (Supabase email + password, no SDK) ----------
  async function supabaseToken(grant, body) {
    const res = await fetch(`${state.cfg.supabase_url}/auth/v1/token?grant_type=${grant}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", apikey: state.cfg.supabase_publishable_key },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error_description || data.msg || "Sign-in failed.");
    return { access_token: data.access_token, refresh_token: data.refresh_token, expires_at: Date.now() + (data.expires_in - 30) * 1000 };
  }
  async function token() {
    const s = state.session;
    if (s && Date.now() > s.expires_at && s.refresh_token) {
      try { state.session = await supabaseToken("refresh_token", { refresh_token: s.refresh_token }); store("session", state.session); }
      catch (err) { signOut(); throw new Error("Your session expired. Please sign in again.", { cause: err }); }
    }
    return state.session && state.session.access_token;
  }
  async function api(path, options = {}) {
    const t = await token();
    const headers = { ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...(t ? { Authorization: `Bearer ${t}` } : {}) };
    const res = await fetch(path, { ...options, headers: { ...headers, ...(options.headers || {}) } });
    if (res.status === 401) { signOut(); throw new Error("Please sign in again."); }
    const isJson = (res.headers.get("content-type") || "").includes("json");
    const data = isJson ? await res.json().catch(() => ({})) : await res.text();
    if (!res.ok) {
      const wait = res.headers.get("Retry-After");
      throw new Error(((data && data.detail) || "Request failed.") + (wait ? ` Please retry in about ${wait}s.` : ""));
    }
    return data;
  }
  function signOut() {
    state.session = null; state.me = null; store("session", null);
    $("app-view").hidden = true; $("signin-view").hidden = false; $("emergency-pin").hidden = true;
  }

  // ---------- views ----------
  function showView(name) {
    for (const v of ["chat", "documents", "evaluation", "review"]) $(`view-${v}`).hidden = v !== name;
    for (const t of document.querySelectorAll(".tab")) {
      if (t.dataset.view === name) t.setAttribute("aria-current", "page"); else t.removeAttribute("aria-current");
    }
    if (name === "documents") loadDocuments();
    if (name === "evaluation") loadEvaluation();
    if (name === "review") loadReview();
    $("main").focus();
  }

  // ---------- chat rendering ----------
  function renderCited(container, text, cardsById) {
    for (const para of text.split(/\n+/)) {
      if (!para.trim()) continue;
      const p = el("p");
      for (const part of para.split(/(\[\d+\])/)) {
        const m = /^\[(\d+)\]$/.exec(part);
        if (m) {
          const chip = el("button", "chip", part);
          chip.type = "button";
          chip.setAttribute("aria-label", `Source ${m[1]}`);
          chip.addEventListener("click", () => {
            const card = cardsById[m[1]];
            if (!card) return;
            card.closest("details").open = true;
            card.scrollIntoView({ behavior: "smooth", block: "nearest" });
            card.classList.add("flash");
            setTimeout(() => card.classList.remove("flash"), 1200);
          });
          p.appendChild(chip);
        } else if (part) {
          p.appendChild(document.createTextNode(part));
        }
      }
      container.appendChild(p);
    }
  }

  function refusalTitle(a) {
    if (a.kind === "redirect") return "Outside what I can help with";
    if (a.scope === "prescribing_or_dosing") return "I can't advise on medicines or doses";
    if (a.scope === "personal_diagnosis") return "I can't diagnose";
    if (a.kind === "not_covered") return "Not covered by the available sources";
    if (a.scope === "unsafe") return "I can't help with this request";
    return "Why there is no full answer";
  }

  function pinEmergency(e) {
    const pin = $("emergency-pin");
    pin.textContent = "";
    pin.appendChild(document.createTextNode(e.message));
    pin.appendChild(el("span", "num", `Call ${e.number}`));
    pin.hidden = false;
  }

  // "How this answer was produced": one row per agent (decisions and timings only - no user text).
  const STATUS_LABEL = { ok: "done", warn: "attention", stop: "stopped here", skip: "skipped" };
  function renderTrace(steps) {
    if (!steps || !steps.length) return null;
    const box = el("details", "agent-trace");
    const ran = steps.filter((s) => s.agent !== "Result" && s.status !== "skip").length;
    const total = steps.reduce((sum, s) => sum + (s.ms || 0), 0);
    box.appendChild(el("summary", null, `How this answer was produced (${ran} agent steps, ${(total / 1000).toFixed(1)} s)`));
    const list = el("ol", "trace-list");
    for (const s of steps) {
      const li = el("li", `trace-step st-${s.status}`); // "st-" prefix: ".skip" is the skip-link class
      const dot = el("span", "trace-dot");
      dot.setAttribute("aria-hidden", "true");
      li.appendChild(dot);
      const body = el("div", "trace-body");
      const head = el("div", "trace-head");
      head.appendChild(el("strong", null, s.agent));
      head.appendChild(el("span", "trace-outcome", s.outcome));
      head.appendChild(el("span", "sr-only", ` (${STATUS_LABEL[s.status] || s.status})`));
      if (s.agent !== "Result") head.appendChild(el("span", "trace-ms", `${Math.round(s.ms)} ms`));
      body.appendChild(head);
      if (s.detail) body.appendChild(el("div", "trace-detail", s.detail));
      li.appendChild(body);
      list.appendChild(li);
    }
    box.appendChild(list);
    return box;
  }

  function renderAnswer(a) {
    const box = el("article", "answer");
    box.setAttribute("aria-label", "Answer");
    if (a.emergency) {
      pinEmergency(a.emergency);
      const e = el("div", "emergency-card");
      e.setAttribute("role", "alert");
      e.appendChild(el("p", null, a.emergency.message));
      e.appendChild(el("p", "call", `Call ${a.emergency.number}`));
      if (a.emergency.crisis_message) e.appendChild(el("p", null, a.emergency.crisis_message));
      if (a.emergency.poison_message) e.appendChild(el("p", null, a.emergency.poison_message));
      box.appendChild(e);
    }
    if (a.preface && a.preface.length) {
      const card = el("section", "refusal-card");
      card.appendChild(el("h3", null, refusalTitle(a)));
      for (const line of a.preface) card.appendChild(el("p", null, line));
      box.appendChild(card);
    } else if (a.kind === "not_covered") {
      const card = el("section", "refusal-card");
      card.appendChild(el("h3", null, refusalTitle(a)));
      box.appendChild(card);
    }

    const cardsById = {};
    const sources = el("details", "sources");
    sources.open = false;
    sources.appendChild(el("summary", null, `Sources and limitations (${(a.citations || []).length})`));
    const grid = el("div", "source-grid");
    for (const c of a.citations || []) {
      const card = el("div", "source-card");
      card.appendChild(el("span", "chip", `[${c.n}]`));
      const body = el("div");
      const title = el("div", "source-title", c.title);
      if (c.user_provided) title.appendChild(el("span", "badge user", "user-provided"));
      if (c.url) title.appendChild(el("span", "badge web", "web"));
      if (c.superseded) title.appendChild(el("span", "badge old", "older version"));
      if (c.stale) title.appendChild(el("span", "badge old", "may be outdated"));
      body.appendChild(title);
      const meta = [c.publisher, c.location, c.version ? `v${c.version}` : null, c.publication_date || "undated", c.evidence_level ? `evidence: ${c.evidence_level}` : null].filter(Boolean).join(" · ");
      body.appendChild(el("div", "source-meta", meta));
      if (c.url) body.appendChild(el("div", "source-meta", c.url));
      card.appendChild(body);
      grid.appendChild(card);
      cardsById[String(c.n)] = card;
    }
    sources.appendChild(grid);
    if (a.limitations) sources.appendChild(el("p", "limits", `Limitations: ${a.limitations}`));
    if (a.evidence_basis) sources.appendChild(el("p", "limits", a.evidence_basis));

    if (a.answer) renderCited(box, a.answer, cardsById);
    for (const w of a.warnings || []) box.appendChild(el("p", "warning", w));
    if (a.kind === "answer" && a.citations && a.citations.length) {
      const checks = a.safety && a.safety.checks ? Object.keys(a.safety.checks) : [];
      const note = a.safety && a.safety.high_risk
        ? "Every statement was checked against the cited passages, with an extra check for this higher-risk topic."
        : "Every statement was checked against the cited passages.";
      box.appendChild(el("span", "confidence", checks.length ? note : "Checked against the cited passages."));
    }
    if ((a.citations && a.citations.length) || a.limitations) box.appendChild(sources);
    const trace = renderTrace(a.safety && a.safety.trace);
    if (trace) box.appendChild(trace);
    box.appendChild(el("p", "disclaimer-line", a.disclaimer));
    return box;
  }

  function phaseList() {
    const ul = el("ul", "phases");
    ul.setAttribute("aria-label", "Progress");
    const items = {};
    for (const [key, label] of PHASES) { const li = el("li", null, label); items[key] = li; ul.appendChild(li); }
    return {
      node: ul,
      set(name) {
        let reached = false;
        for (const [key] of PHASES) {
          const li = items[key];
          if (key === name) { li.className = "active"; reached = true; }
          else li.className = reached ? "" : "done";
        }
      },
    };
  }

  async function streamAnswer(payload, mode, onPhase) {
    const t = await token();
    const res = await fetch(`/api/chat/stream?mode=${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}) },
      body: JSON.stringify(payload),
    });
    if (res.status === 401) { signOut(); throw new Error("Please sign in again."); }
    if (!res.ok || !res.body) {
      const data = await res.json().catch(() => ({}));
      const wait = res.headers.get("Retry-After");
      throw new Error((data.detail || "Request failed.") + (wait ? ` Please retry in about ${wait}s.` : ""));
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const raw = buf.slice(0, idx); buf = buf.slice(idx + 2);
        const ev = (/^event: (.*)$/m.exec(raw) || [])[1];
        const data = (/^data: (.*)$/m.exec(raw) || [])[1];
        if (!ev || data === undefined) continue;
        const obj = JSON.parse(data);
        if (ev === "phase") onPhase(obj.phase);
        else if (ev === "answer") return obj;
        else if (ev === "error") throw new Error(obj.detail + (obj.retry_after ? ` Please retry in about ${obj.retry_after}s.` : ""));
      }
    }
    throw new Error("The connection closed before the answer arrived.");
  }

  function currentFilters() {
    const f = {};
    if ($("f-trusted").checked) f.trusted_only = true;
    if ($("f-publisher").value) f.publishers = [$("f-publisher").value];
    if ($("f-doc").value) f.doc_ids = [$("f-doc").value];
    if ($("f-from").value) f.date_from = $("f-from").value;
    if ($("f-to").value) f.date_to = $("f-to").value;
    return Object.keys(f).length ? f : null;
  }

  async function ask(ev) {
    ev.preventDefault();
    const q = $("question").value.trim();
    if (!q) return;
    $("empty-state").hidden = true;
    const list = $("messages");
    list.appendChild(el("div", "bubble-user", q));
    const phases = phaseList();
    list.appendChild(phases.node);
    phases.set("safety");
    $("question").value = "";
    $("ask-btn").disabled = true;
    const mode = $("f-research").checked ? "research" : "chat";
    try {
      const payload = { question: q, filters: currentFilters(), conversation_id: state.conversationId };
      const answer = await streamAnswer(payload, mode, (p) => phases.set(p));
      state.conversationId = answer.conversation_id || state.conversationId;
      $("report-btn").hidden = !state.conversationId;
      phases.node.replaceWith(renderAnswer(answer));
      loadHistory();
    } catch (err) {
      const card = el("section", "refusal-card");
      card.setAttribute("role", "alert");
      card.appendChild(el("h3", null, "Something went wrong"));
      card.appendChild(el("p", null, err.message));
      phases.node.replaceWith(card);
    } finally {
      $("ask-btn").disabled = false;
      $("question").focus();
      list.lastElementChild.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  // ---------- history ----------
  async function loadHistory() {
    const items = await api("/api/conversations").catch(() => []);
    const ul = $("history");
    ul.textContent = "";
    for (const c of items) {
      const li = el("li");
      const b = el("button", null, c.title || "Conversation");
      b.type = "button";
      if (c.id === state.conversationId) b.setAttribute("aria-current", "true");
      b.addEventListener("click", () => openConversation(c.id));
      li.appendChild(b);
      ul.appendChild(li);
    }
  }
  async function openConversation(id) {
    const conv = await api(`/api/conversations/${encodeURIComponent(id)}`);
    state.conversationId = id;
    $("report-btn").hidden = false;
    const list = $("messages");
    list.textContent = "";
    for (const m of conv.messages) {
      if (m.role === "user") list.appendChild(el("div", "bubble-user", m.text));
      else { const a = el("article", "answer"); renderCited(a, m.text, {}); list.appendChild(a); }
    }
    closeSidebar();
    showView("chat");
    loadHistory();
  }
  function newChat() {
    state.conversationId = null;
    $("report-btn").hidden = true;
    $("messages").textContent = "";
    const empty = el("div", "empty");
    empty.id = "empty-state";
    empty.appendChild(el("h2", null, "Ask a medical information question"));
    $("messages").appendChild(empty);
    $("emergency-pin").hidden = true;
    closeSidebar();
    showView("chat");
    loadHistory();
  }
  async function deleteHistory() {
    if (!window.confirm("Delete all of your conversation history? This cannot be undone.")) return;
    await api("/api/conversations", { method: "DELETE" });
    newChat();
  }

  // ---------- evidence report ----------
  async function downloadReport() {
    if (!state.conversationId) return;
    const t = await token();
    const res = await fetch(`/api/conversations/${encodeURIComponent(state.conversationId)}/report`, { headers: t ? { Authorization: `Bearer ${t}` } : {} });
    if (!res.ok) { window.alert("The report could not be created. Please try again."); return; }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = el("a");
    a.href = url;
    a.download = `medinfo-report-${state.conversationId.slice(0, 8)}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // ---------- sources for "Search in" ----------
  async function loadSources() {
    state.sources = await api("/api/sources").catch(() => null);
    if (!state.sources) return;
    const pub = $("f-publisher"); const doc = $("f-doc"); const dl = $("publisher-list");
    for (const sel of [pub, doc]) while (sel.options.length > 1) sel.remove(1);
    dl.textContent = "";
    for (const p of state.sources.publishers) { pub.add(new Option(p, p)); const o = el("option"); o.value = p; dl.appendChild(o); }
    for (const d of [...state.sources.documents, ...state.sources.my_uploads]) doc.add(new Option(d.title || d.doc_id, d.doc_id));
  }

  // ---------- admin: documents ----------
  async function loadDocuments() {
    const docs = await api("/api/admin/documents").catch((e) => { $("upload-status").textContent = e.message; return []; });
    const body = $("docs-body");
    body.textContent = "";
    for (const d of docs) {
      const tr = el("tr");
      for (const v of [d.title, d.publisher, d.publication_date || "—", d.version || "—", d.chunks]) tr.appendChild(el("td", null, v));
      const td = el("td");
      const del = el("button", "danger", "Delete");
      del.type = "button";
      del.setAttribute("aria-label", `Delete ${d.title}`);
      del.addEventListener("click", async () => {
        if (!window.confirm(`Delete "${d.title}" and all its chunks?`)) return;
        await api(`/api/admin/documents/${encodeURIComponent(d.doc_id)}`, { method: "DELETE" });
        loadDocuments(); loadSources();
      });
      td.appendChild(del);
      tr.appendChild(td);
      body.appendChild(tr);
    }
  }
  function chooseFile(file) {
    state.file = file || null;
    $("file-name").textContent = file ? `Selected: ${file.name}` : "";
    if (file && !$("d-title").value) $("d-title").value = file.name.replace(/\.[^.]+$/, "");
  }
  async function upload(ev) {
    ev.preventDefault();
    if (!state.file) { $("upload-status").textContent = "Choose a file first."; return; }
    const fd = new FormData();
    fd.append("file", state.file);
    fd.append("title", $("d-title").value);
    fd.append("publisher", $("d-publisher").value);
    if ($("d-date").value) fd.append("publication_date", $("d-date").value);
    if ($("d-version").value) fd.append("version", $("d-version").value);
    if ($("d-evidence").value) fd.append("evidence_level", $("d-evidence").value);
    fd.append("doc_type", $("d-type").value);
    $("upload-btn").disabled = true;
    $("upload-status").textContent = "Ingesting…";
    try {
      const r = await api("/api/admin/documents", { method: "POST", body: fd });
      $("upload-status").textContent = `${r.status}: ${r.chunks_total} chunks (${r.embedded} embedded, ${r.deleted} removed${r.ocr_sections ? `, ${r.ocr_sections} via OCR` : ""}).`;
      chooseFile(null); $("upload-form").reset();
      loadDocuments(); loadSources();
    } catch (err) {
      $("upload-status").textContent = err.message;
    } finally {
      $("upload-btn").disabled = false;
    }
  }

  // ---------- admin: evaluation ----------
  function ring(label, value, opts = {}) {
    const NS = "http://www.w3.org/2000/svg";
    const wrap = el("div", "ring");
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 100 100");
    svg.setAttribute("role", "img");
    const pct = value === null || value === undefined ? null : Math.round(value * 100);
    svg.setAttribute("aria-label", `${label}: ${pct === null ? "no data" : pct + "%"}`);
    const r = 42, c = 2 * Math.PI * r;
    const track = document.createElementNS(NS, "circle");
    track.setAttribute("cx", "50"); track.setAttribute("cy", "50"); track.setAttribute("r", String(r));
    track.setAttribute("fill", "none"); track.setAttribute("stroke-width", "10"); track.setAttribute("class", "track");
    const arc = document.createElementNS(NS, "circle");
    arc.setAttribute("cx", "50"); arc.setAttribute("cy", "50"); arc.setAttribute("r", String(r));
    arc.setAttribute("fill", "none"); arc.setAttribute("stroke-width", "10");
    arc.setAttribute("stroke-linecap", pct ? "round" : "butt"); // no stray dot for empty/0% rings
    arc.setAttribute("transform", "rotate(-90 50 50)");
    arc.setAttribute("stroke-dasharray", `${((pct || 0) / 100) * c} ${c}`);
    const gate = opts.gate;
    arc.setAttribute("class", "value" + (gate !== undefined && pct !== null ? (value >= gate ? " good" : " bad") : ""));
    const txt = document.createElementNS(NS, "text");
    txt.setAttribute("x", "50"); txt.setAttribute("y", "56"); txt.setAttribute("text-anchor", "middle");
    txt.textContent = pct === null ? "—" : `${pct}%`;
    svg.append(track, arc, txt);
    wrap.append(svg, el("span", null, label));
    return wrap;
  }
  async function loadEvaluation() {
    const data = await api("/api/admin/evaluations").catch(() => null);
    const q = $("rings-quality"), s = $("rings-safety"), r = $("rings-review");
    for (const n of [q, s, r]) n.textContent = "";
    if (!data) return;
    $("eval-label").textContent = data.label;
    const m = (data.runs[0] && data.runs[0].metrics) || {};
    const pick = (...keys) => { for (const k of keys) if (m[k] !== undefined) return m[k]; return null; };
    q.append(
      ring("Evidence hit rate", pick("retrieval_evidence_hit_rate", "answer_evidence_hit_rate")),
      ring("MRR", pick("retrieval_mrr", "answer_mrr")),
      ring("Correctness (judge)", pick("answer_correctness")),
      ring("Citation accuracy", pick("answer_citation_accuracy")),
      ring("Faithfulness", pick("answer_faithfulness")),
      ring("Answer relevancy", pick("answer_answer_relevancy")),
      ring("Context precision", pick("answer_context_precision")),
      ring("Context recall", pick("answer_context_recall")),
    );
    for (const [k, label] of [["safety_emergency", "Emergency"], ["safety_dosing", "Dosing"], ["safety_diagnosis", "Diagnosis"], ["safety_injection", "Injection"], ["safety_phi", "PHI (0 leaks)"], ["safety_out_of_corpus", "Out of corpus"]]) {
      s.append(ring(label, pick(k), { gate: 1 }));
    }
    const rev = data.review || {};
    const total = Object.values(rev).reduce((a, b) => a + b, 0) - (rev.pending || 0);
    r.append(
      ring("Safe & correct", total ? rev.safe_and_correct / total : null),
      ring("Unsafe", total ? rev.unsafe / total : null),
    );
    const run = data.runs[0];
    $("eval-meta").textContent = run
      ? `Latest run ${run.created_at} · model ${run.params.answer_model} · ${run.params.items} golden items · ${rev.pending || 0} answers awaiting review`
      : "No evaluation runs recorded yet (run evals/run_eval.py).";
  }

  // ---------- clinician: review ----------
  async function loadReview() {
    const items = await api("/api/review/queue").catch(() => []);
    const list = $("review-list");
    list.textContent = "";
    if (!items.length) { list.appendChild(el("p", "muted", "Nothing to review right now.")); return; }
    for (const it of items) {
      const card = el("section", "card review-item");
      card.appendChild(el("p", "muted", `${it.source} · ${it.created_at}`));
      card.appendChild(el("p", "bubble-user", it.question));
      card.appendChild(renderAnswer(it.answer));
      const notes = el("textarea");
      notes.rows = 2; notes.placeholder = "Notes (optional)"; notes.setAttribute("aria-label", "Review notes");
      card.appendChild(notes);
      const actions = el("div", "review-actions");
      for (const [v, label] of [["safe_and_correct", "Safe and correct"], ["minor_issue", "Minor issue"], ["incorrect", "Incorrect"], ["unsafe", "Unsafe"]]) {
        const b = el("button", v === "unsafe" ? "danger" : null, label);
        b.type = "button";
        b.addEventListener("click", async () => {
          await api(`/api/review/${encodeURIComponent(it.id)}`, { method: "POST", body: JSON.stringify({ verdict: v, notes: notes.value || null }) });
          card.remove();
        });
        actions.appendChild(b);
      }
      card.appendChild(actions);
      list.appendChild(card);
    }
    $("emergency-pin").hidden = true; // review rendering must not pin a banner for the reviewer
  }

  // ---------- sidebar (mobile) ----------
  function closeSidebar() { $("sidebar").classList.remove("open"); $("sidebar-toggle").setAttribute("aria-expanded", "false"); }
  function toggleSidebar() {
    const open = !$("sidebar").classList.contains("open");
    $("sidebar").classList.toggle("open", open);
    $("sidebar-toggle").setAttribute("aria-expanded", String(open));
  }

  // ---------- startup ----------
  async function enterApp() {
    state.me = await api("/api/me");
    $("who").textContent = `${state.me.email || "Signed in"} · ${state.me.role}`;
    for (const t of document.querySelectorAll(".tab[data-role]")) t.hidden = !hasRole(t.dataset.role);
    $("research-wrap").hidden = !(hasRole("clinician") && state.cfg.research_available === "true");
    $("signin-view").hidden = true;
    $("app-view").hidden = false;
    showView("chat");
    loadHistory();
    loadSources();
    $("question").focus();
  }
  async function signIn(ev) {
    ev.preventDefault();
    $("signin-error").textContent = "";
    try {
      state.session = await supabaseToken("password", { email: $("email").value, password: $("password").value });
      store("session", state.session);
      await enterApp();
    } catch (err) {
      $("signin-error").textContent = err.message;
    }
  }

  async function init() {
    const boot = $("boot-msg");
    try {
      const res = await fetch("/api/config");
      if (!res.ok) throw new Error(`server answered ${res.status}`);
      state.cfg = await res.json();
    } catch (err) {
      boot.textContent = `Can't reach the MedInfo server (${err.message}). Make sure it is running and open it through its address, e.g. http://127.0.0.1:8030.`;
      return;
    }
    boot.hidden = true;
    for (const n of document.querySelectorAll(".js-emergency-number")) n.textContent = state.cfg.emergency_number;
    $("signin-form").addEventListener("submit", signIn);
    $("ask-form").addEventListener("submit", ask);
    $("signout").addEventListener("click", signOut);
    $("theme-toggle").addEventListener("click", toggleTheme);
    $("new-chat").addEventListener("click", newChat);
    $("delete-history").addEventListener("click", deleteHistory);
    $("report-btn").addEventListener("click", downloadReport);
    $("sidebar-toggle").addEventListener("click", toggleSidebar);
    for (const t of document.querySelectorAll(".tab")) t.addEventListener("click", () => showView(t.dataset.view));
    $("question").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("ask-form").requestSubmit(); } });
    const dz = $("dropzone"), fi = $("file-input");
    dz.addEventListener("click", () => fi.click());
    dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fi.click(); } });
    dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("over"); });
    dz.addEventListener("dragleave", () => dz.classList.remove("over"));
    dz.addEventListener("drop", (e) => { e.preventDefault(); dz.classList.remove("over"); chooseFile(e.dataTransfer.files[0]); });
    fi.addEventListener("change", () => chooseFile(fi.files[0]));
    $("upload-form").addEventListener("submit", upload);

    state.session = load("session");
    if (state.session) { try { await enterApp(); return; } catch (_) { /* fall through to sign-in */ } }
    $("signin-view").hidden = false;
  }

  document.addEventListener("DOMContentLoaded", init);
})();
