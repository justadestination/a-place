// ShadeNet operations console (/ops/). Talks only to /api/ops/*.
// Everything is rendered with h(), which creates text nodes, so log lines and
// user-supplied strings can't inject markup. Never pass `html:` here.
import { h, clear } from "../core/dom.js";

const app = document.getElementById("app");
let csrf = "";
let me = "";
let tabs = [];
let current = location.hash.slice(1) || "overview";
let refreshTimer = null;

// --- API -------------------------------------------------------------------

class ApiError extends Error {
  constructor(status, body) { super(body?.error || `HTTP ${status}`); this.status = status; this.body = body; }
}

async function api(path, { method = "GET", body, stepUp } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (method !== "GET") headers["X-Ops-CSRF"] = csrf;
  if (stepUp) headers["X-Ops-Step-Up"] = stepUp;
  const res = await fetch(`/api/ops/${path}`, {
    method, headers, credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) { showLogin("Session ended. Sign in again."); throw new ApiError(401, data); }
  if (res.status === 428 && !stepUp) {
    const code = await askStepUp();
    if (!code) throw new ApiError(428, { error: "step-up cancelled" });
    return api(path, { method, body, stepUp: code });
  }
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

// Mutations: run, then report success or the server's error inline.
async function act(statusEl, fn, onDone) {
  statusEl.textContent = "Working…";
  statusEl.className = "ops-muted";
  try {
    const res = await fn();
    statusEl.textContent = "Saved.";
    onDone?.(res);
  } catch (e) {
    if (e.status === 401) return;
    statusEl.textContent = e.status === 501 ? `Not built yet: ${e.message}` : e.message;
    statusEl.className = "ops-error";
  }
}

// --- step-up dialog ------------------------------------------------------------

function askStepUp() {
  return new Promise(resolve => {
    const input = h("input.ops-input.ops-mono", { inputmode: "numeric", autocomplete: "one-time-code", maxlength: "6", required: true });
    const dlg = h("dialog.ops-stepup", {},
      h("form", { method: "dialog", class: "ops-field" },
        h("strong", {}, "Confirm with your authenticator"),
        h("p.ops-muted", {}, "This action is protected. Enter a fresh 6-digit code."),
        input,
        h("div.ops-row", {},
          h("button.nc-button.nc-button--primary", { type: "submit", value: "ok" }, "Confirm"),
          h("button.nc-button.nc-button--ghost", { type: "submit", value: "cancel", formnovalidate: true }, "Cancel"))));
    dlg.addEventListener("close", () => { resolve(dlg.returnValue === "ok" ? input.value.trim() : ""); dlg.remove(); });
    document.body.append(dlg);
    dlg.showModal();
  });
}

// --- login --------------------------------------------------------------------

function showLogin(message = "") {
  clearInterval(refreshTimer);
  const err = h("p.ops-error", { role: "alert" }, message);
  const user = h("input", { name: "username", autocomplete: "username", required: true });
  const pass = h("input", { name: "password", type: "password", autocomplete: "current-password", required: true });
  const totp = h("input.ops-mono", { name: "totp", inputmode: "numeric", autocomplete: "one-time-code", maxlength: "6", required: true });
  const form = h("form.ops-login", {},
    h("h1", {}, "ShadeNet Operations"),
    h("label.ops-field", {}, "Operator", user),
    h("label.ops-field", {}, "Password", pass),
    h("label.ops-field", {}, "Authenticator code", totp),
    err,
    h("button.nc-button.nc-button--primary", { type: "submit" }, "Sign in"));
  form.addEventListener("submit", async e => {
    e.preventDefault();
    err.textContent = "";
    try {
      const res = await fetch("/api/ops/login", {
        method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin",
        body: JSON.stringify({ username: user.value, password: pass.value, totp: totp.value }),
      });
      const data = await res.json().catch(() => ({}));
      pass.value = ""; totp.value = "";
      if (!res.ok) { err.textContent = data.retry_after ? `${data.error} (${Math.ceil(data.retry_after / 60)} min)` : data.error || "Sign-in failed"; return; }
      csrf = data.csrf; me = data.username;
      boot();
    } catch { err.textContent = "Network error"; }
  });
  app.replaceChildren(form);
  user.focus();
}

// --- shell ----------------------------------------------------------------------

async function boot() {
  try {
    const s = await api("session");
    csrf = s.csrf; me = s.username;
  } catch (e) { if (e.status !== 401) showLogin(e.message); return; }
  tabs = (await api("settings")).tabs;
  renderShell();
}

function renderShell() {
  const nav = h("nav.ops-nav", { "aria-label": "Console sections" },
    h("div.ops-nav__brand", {}, "ShadeNet Ops"),
    tabs.map(t => h("button", {
      type: "button", "aria-current": t.id === current ? "page" : null,
      onclick: () => { location.hash = t.id; },
    }, t.label)),
    h("div.ops-nav__foot", {},
      h("span.ops-muted", {}, `Signed in as ${me}`),
      h("button.nc-button.nc-button--ghost", { type: "button", onclick: logout }, "Sign out")));
  const main = h("main.ops-main", { id: "main", tabindex: "-1" });
  app.replaceChildren(h("div.ops-shell", {}, nav, main));
  renderTab(main);
}

async function logout() {
  try { await api("logout", { method: "POST", body: {} }); } catch { /* signing out anyway */ }
  csrf = ""; me = "";
  showLogin("Signed out.");
}

window.addEventListener("hashchange", () => {
  current = location.hash.slice(1) || "overview";
  if (me) renderShell();
});

async function renderTab(main) {
  clearInterval(refreshTimer);
  const tab = tabs.find(t => t.id === current) || tabs[0];
  main.append(h("h1", {}, tab.label));
  const view = VIEWS[tab.id] || settingsView;
  try {
    await view(main, tab.id);
  } catch (e) {
    if (e.status !== 401) main.append(h("p.ops-error", {}, `Couldn't load: ${e.message}`));
  }
}

const panel = (title, ...children) => h("section.ops-panel", {}, title ? h("h2", {}, title) : null, ...children);
const stat = (label, value) => h("div.ops-stat", {}, h("b", {}, String(value)), h("span.ops-muted", {}, label));
const time = iso => (iso ? new Date(iso).toLocaleString() : "—");

function table(cols, rows) {
  return h("table.ops-table", {},
    h("thead", {}, h("tr", {}, cols.map(c => h("th", { scope: "col" }, c.label)))),
    h("tbody", {}, rows.length ? rows.map(r => h("tr", {}, cols.map(c => h("td", { class: c.cls || null }, c.get(r)))))
      : h("tr", {}, h("td", { colspan: String(cols.length), class: "ops-muted" }, "Nothing here yet."))));
}

// --- views ------------------------------------------------------------------------

async function overviewView(main) {
  const d = await api("overview");
  const health = d.operator?.health || {};
  main.append(
    panel("Right now",
      h("div.ops-stats", {},
        stat("Health", health.status || "?"),
        stat("Uptime (min)", Math.round((d.metrics.uptime_seconds || 0) / 60)),
        stat("p95 latency (ms)", d.metrics.latency_ms.p95),
        stat("5xx since start", d.metrics.status["5xx"] || 0),
        stat("Pending recoveries", d.pending_recoveries),
        stat("Audit chain", d.audit_chain.ok ? `intact (${d.audit_chain.entries})` : "BROKEN"))),
    panel("Log source",
      h("p", {}, logSourceText(d.log_source))),
    panel("Recent error groups", errorTable(d.errors)));
}

function logSourceText(src) {
  if (src.kind === "file") return `Reading ${src.path}${src.exists ? "" : " (not created yet)"}.`;
  if (src.kind === "journald") return `Reading journald unit "${src.unit}". Set SHADENET_LOG_FILE for structured search across restarts.`;
  return src.hint || "No log source configured.";
}

function errorTable(groups) {
  return table([
    { label: "Count", get: g => String(g.count) },
    { label: "Error", get: g => g.key, cls: "ops-mono" },
    { label: "Last message", get: g => g.last.message || g.last.error || "", cls: "ops-wrap" },
    { label: "Last seen", get: g => time(g.last.timestamp) },
  ], groups);
}

async function logsView(main) {
  const level = h("select.ops-input", {}, ["", "DEBUG", "INFO", "WARNING", "ERROR"].map(l => h("option", { value: l }, l || "Any level")));
  const q = h("input.ops-input", { type: "search", placeholder: "Text, event, path…" });
  const trace = h("input.ops-input.ops-mono", { placeholder: "trace id" });
  const live = h("input", { type: "checkbox", checked: true });
  const out = h("div");
  const src = h("p.ops-muted");
  const load = async () => {
    const p = new URLSearchParams({ level: level.value, q: q.value, trace: trace.value, limit: "300" });
    const d = await api(`logs?${p}`);
    src.textContent = `${logSourceText(d.source)} ${d.count} lines.`;
    out.replaceChildren(table([
      { label: "Time", get: r => time(r.timestamp) },
      { label: "Level", get: r => h(`span.ops-level--${r.level}`, {}, r.level || "") },
      { label: "Service", get: r => r.service || "" },
      { label: "Event", get: r => r.event || "", cls: "ops-mono" },
      { label: "Detail", get: r => detail(r), cls: "ops-wrap ops-mono" },
      { label: "Trace", get: r => r.trace_id ? h("button.nc-button.nc-button--ghost", { type: "button", onclick: () => { trace.value = r.trace_id; load(); } }, r.trace_id.slice(0, 8)) : "" },
    ], d.records));
  };
  for (const el of [level, q, trace]) el.addEventListener("change", load);
  main.append(panel(null,
    h("div.ops-row", {},
      h("label.ops-field", {}, "Level", level), h("label.ops-field", {}, "Search", q), h("label.ops-field", {}, "Trace", trace),
      h("label", {}, live, " Live (5 s)")),
    src, out));
  await load();
  refreshTimer = setInterval(() => { if (live.checked && document.visibilityState === "visible") load().catch(() => {}); }, 5000);
}

function detail(r) {
  const skip = new Set(["timestamp", "level", "service", "event", "trace_id"]);
  const rest = Object.fromEntries(Object.entries(r).filter(([k]) => !skip.has(k)));
  const s = JSON.stringify(rest);
  return s === "{}" ? "" : s.length > 400 ? `${s.slice(0, 400)}…` : s;
}

async function errorsView(main) {
  const d = await api("errors");
  main.append(panel(null, h("p.ops-muted", {}, logSourceText(d.source)), errorTable(d.groups)));
}

async function metricsView(main) {
  const m = await api("metrics");
  const peak = Math.max(1, ...m.per_minute.map(x => x.count));
  main.append(
    panel("Traffic",
      h("div.ops-stats", {},
        stat("Uptime (min)", Math.round(m.uptime_seconds / 60)),
        ...Object.entries(m.status).map(([k, v]) => stat(k, v)),
        stat("p50 ms", m.latency_ms.p50), stat("p95 ms", m.latency_ms.p95), stat("p99 ms", m.latency_ms.p99)),
      h("p.ops-muted", {}, "Requests per minute, last hour (red = minutes with 5xx):"),
      h("div.ops-bar", { role: "img", "aria-label": `Requests per minute, peak ${peak}` },
        m.per_minute.map(x => h("span", { class: x.errors ? "has-errors" : null, title: `${x.count} req, ${x.errors} errors`, style: { height: `${(x.count / peak) * 100}%` } })))),
    panel("Routes", table([
      { label: "Route", get: r => r.route, cls: "ops-mono" },
      { label: "Requests", get: r => String(r.count) },
      { label: "5xx", get: r => String(r.errors) },
      { label: "Avg ms", get: r => String(r.avg_ms) },
      { label: "Max ms", get: r => String(r.max_ms) },
    ], m.routes)));
  refreshTimer = setInterval(() => { if (document.visibilityState === "visible" && current === "metrics") renderShell(); }, 15000);
}

async function settingsView(main, tabId) {
  const d = await api(`settings?tab=${encodeURIComponent(tabId)}`);
  if (d.settings.length) main.append(panel("Settings", d.settings.map(settingRow)));
  if (tabId === "security") main.append(panel("Environment (read-only, restart to change)", table([
    { label: "Variable", get: ([k]) => k, cls: "ops-mono" },
    { label: "Value", get: ([, v]) => v || "—", cls: "ops-mono ops-wrap" },
  ], Object.entries(d.env))));
  return d;
}

function settingRow(s) {
  const status = h("span.ops-muted", { role: "status" });
  let control;
  if (s.type === "bool") control = h("input", { type: "checkbox", checked: Boolean(s.value) });
  else if (s.type === "choice") control = h("select.ops-input", {}, s.choices.map(c => h("option", { value: c, selected: c === s.value }, c)));
  else control = h("input.ops-input", { type: s.type === "int" ? "number" : "text", value: String(s.value), min: s.min ?? null, max: s.max ?? null });
  const read = () => (s.type === "bool" ? control.checked : s.type === "int" ? Number(control.value) : control.value);
  control.addEventListener("change", () => act(status, () => api("settings", { method: "POST", body: { key: s.key, value: read() } })));
  return h("div.ops-setting", {},
    h("div", {},
      h("label", { for: s.key }, h("strong", {}, s.label)),
      s.dangerous ? h("span.ops-badge.ops-badge--danger", {}, "step-up") : null,
      s.wired ? null : h("span.ops-badge", { title: "Saved, but nothing in the app reads this value yet." }, "stored only"),
      s.help ? h("p.ops-muted", {}, s.help) : null,
      status),
    Object.assign(control, { id: s.key }));
}

async function flagsView(main) {
  const flags = await api("flags");
  main.append(panel(null, Object.entries(flags).map(([name, f]) => {
    const status = h("span.ops-muted", { role: "status" });
    const box = h("input", { type: "checkbox", checked: Boolean(f.enabled), id: `flag-${name}` });
    box.addEventListener("change", () => act(status, () => api("flags", { method: "POST", body: { name, enabled: box.checked } })));
    return h("div.ops-setting", {},
      h("div", {}, h("label", { for: `flag-${name}` }, h("strong.ops-mono", {}, name)),
        h("span.ops-badge", {}, `${f.rollout_percentage ?? 100}%`), h("p.ops-muted", {}, f.description || ""), status),
      box);
  })));
}

async function agegateView(main) {
  await settingsView(main, "agegate");
  const d = await api("agegate");
  const status = h("span.ops-muted", { role: "status" });
  const subject = h("input.ops-input", { placeholder: "account, session or door id", required: true });
  const kind = h("select.ops-input", {}, h("option", { value: "grant" }, "grant (treat as verified)"), h("option", { value: "block" }, "block"));
  const reason = h("input.ops-input", { placeholder: "why (required)", required: true });
  const days = h("input.ops-input", { type: "number", min: "1", max: "90", value: "7" });
  const form = h("form.ops-row", {},
    h("label.ops-field", {}, "Subject", subject), h("label.ops-field", {}, "Kind", kind),
    h("label.ops-field", {}, "Reason", reason), h("label.ops-field", {}, "Days", days),
    h("button.nc-button.nc-button--primary", { type: "submit" }, "Add override"), status);
  form.addEventListener("submit", e => {
    e.preventDefault();
    act(status, () => api("agegate", { method: "POST", body: { subject: subject.value, kind: kind.value, reason: reason.value, days: Number(days.value) } }), () => renderShell());
  });
  main.append(panel("Overrides",
    h("p", {}, h("span.ops-badge.ops-badge--danger", {}, "not enforced yet"), " ", d.note),
    form,
    table([
      { label: "Subject", get: o => o.subject, cls: "ops-mono" },
      { label: "Kind", get: o => o.kind },
      { label: "Reason", get: o => o.reason, cls: "ops-wrap" },
      { label: "Expires", get: o => time(o.expires_at) },
      { label: "", get: o => o.active ? h("button.nc-button.nc-button--ghost", { type: "button", onclick: () => act(status, () => api("agegate", { method: "POST", body: { revoke: o.id } }), () => renderShell()) }, "Revoke") : "inactive" },
    ], d.overrides)));
}

async function accountsView(main) {
  await settingsView(main, "accounts");
  const d = await api("recovery");
  const status = h("span.ops-muted", { role: "status" });
  const account = h("input.ops-input", { placeholder: "account / username", required: true });
  const reason = h("input.ops-input", { placeholder: "what happened", required: true });
  const evKind = h("select.ops-input", {}, d.evidence_kinds.map(k => h("option", { value: k }, k.replaceAll("_", " "))));
  const evNote = h("input.ops-input", { placeholder: "evidence detail" });
  const form = h("form.ops-row", {},
    h("label.ops-field", {}, "Account", account), h("label.ops-field", {}, "Reason", reason),
    h("label.ops-field", {}, "Evidence", evKind), h("label.ops-field", {}, "Detail", evNote),
    h("button.nc-button.nc-button--primary", { type: "submit" }, "Open request"), status);
  form.addEventListener("submit", e => {
    e.preventDefault();
    act(status, () => api("recovery", { method: "POST", body: {
      account: account.value, reason: reason.value,
      evidence: [{ kind: evKind.value, note: evNote.value }] } }), () => renderShell());
  });
  const verb = (r, v, label) => h("button.nc-button.nc-button--ghost", { type: "button",
    onclick: () => act(status, () => api(`recovery/${r.id}/${v}`, { method: "POST", body: {} }), () => renderShell()) }, label);
  main.append(panel("Recovery requests",
    h("p.ops-muted", {}, "Approval starts a waiting period; the owner's existing devices can cancel during it."),
    form,
    table([
      { label: "Account", get: r => r.account, cls: "ops-mono" },
      { label: "Status", get: r => r.status },
      { label: "Evidence", get: r => r.evidence.map(e => `${e.kind}: ${e.note}`).join("; "), cls: "ops-wrap" },
      { label: "Executable after", get: r => time(r.executable_after) },
      { label: "", get: r => r.status === "pending" ? [verb(r, "approve", "Approve"), verb(r, "deny", "Deny")]
        : r.status === "approved" ? [verb(r, "execute", "Execute"), verb(r, "cancel", "Cancel")] : "" },
    ], d.requests)));
}

async function venuesView(main) {
  await settingsView(main, "venues");
  const d = await api("venues");
  const status = h("span.ops-muted", { role: "status" });
  const custodianForm = v => {
    const acct = h("input.ops-input", { placeholder: "account" });
    const role = h("select.ops-input", {}, ["owner", "manager", "staff"].map(r => h("option", { value: r }, r)));
    const f = h("form.ops-row", {}, acct, role, h("button.nc-button.nc-button--ghost", { type: "submit" }, "Add"));
    f.addEventListener("submit", e => {
      e.preventDefault();
      act(status, () => api("venues/custodians", { method: "POST", body: { venue_id: v.venue_id, account: acct.value, role: role.value } }), () => renderShell());
    });
    return f;
  };
  main.append(panel(`Venues (minimum ${d.min_custodians} custodians)`, status, table([
    { label: "Venue", get: v => [v.name, v.at_risk ? h("span.ops-badge.ops-badge--danger", {}, "at risk") : h("span.ops-badge.ops-badge--ok", {}, "ok")] },
    { label: "Custodians", get: v => v.custodians.map(c => `${c.account} (${c.role})`).join(", ") || "none", cls: "ops-wrap" },
    { label: "Add custodian", get: custodianForm },
  ], d.venues)));
  const sVenue = h("select.ops-input", {}, d.venues.map(v => h("option", { value: v.venue_id }, v.name)));
  const sAdd = h("input.ops-input", { placeholder: "new custodian account", required: true });
  const sRemove = h("input.ops-input", { placeholder: "account leaving (optional)" });
  const sReason = h("input.ops-input", { placeholder: "e.g. manager left, venue unreachable", required: true });
  const sForm = h("form.ops-row", {},
    h("label.ops-field", {}, "Venue", sVenue), h("label.ops-field", {}, "Add", sAdd),
    h("label.ops-field", {}, "Remove", sRemove), h("label.ops-field", {}, "Reason", sReason),
    h("button.nc-button.nc-button--primary", { type: "submit" }, "Open succession"));
  sForm.addEventListener("submit", e => {
    e.preventDefault();
    act(status, () => api("venues/succession", { method: "POST", body: {
      action: "open", venue_id: sVenue.value, add: sAdd.value, remove: sRemove.value, reason: sReason.value } }), () => renderShell());
  });
  main.append(panel("Successions",
    h("p.ops-muted", {}, `Takes effect after the waiting period; current custodians can object until then.`),
    sForm, table([
    { label: "Venue", get: s => s.venue_id, cls: "ops-mono" },
    { label: "Add / remove", get: s => `${s.add}${s.remove ? ` / ${s.remove}` : ""}` },
    { label: "Status", get: s => s.status },
    { label: "Effective after", get: s => time(s.effective_after) },
    { label: "", get: s => s.status === "waiting" ? [
      h("button.nc-button.nc-button--ghost", { type: "button", onclick: () => act(status, () => api("venues/succession", { method: "POST", body: { action: "complete", id: s.id } }), () => renderShell()) }, "Complete"),
      h("button.nc-button.nc-button--ghost", { type: "button", onclick: () => act(status, () => api("venues/succession", { method: "POST", body: { action: "cancel", id: s.id } }), () => renderShell()) }, "Cancel")] : "" },
  ], d.successions)));
}

async function securityView(main) {
  await settingsView(main, "security");
  const d = await api("security");
  main.append(
    panel("Operators", h("p.ops-muted", {}, "Add, reset or disable operators from the server shell: python -m shadenet.ops --help"),
      table([{ label: "Operator", get: o => o.username }, { label: "State", get: o => (o.disabled ? "disabled" : "active") }, { label: "Since", get: o => time(o.created_at) }], d.operators)),
    panel("Signed-in sessions", h("p.ops-muted", {}, `Idle timeout ${d.idle_seconds / 60} min, absolute ${d.absolute_seconds / 3600} h. Network allowlist: ${d.allowlist || "none (any network)"}.`),
      table([{ label: "Operator", get: s => s.username }, { label: "IP", get: s => s.ip, cls: "ops-mono" },
        { label: "Since", get: s => new Date(s.created * 1000).toLocaleString() }, { label: "Browser", get: s => s.user_agent, cls: "ops-wrap" }], d.sessions)));
}

async function opstewardView(main) {
  const term = h("div.ops-term", { role: "log", "aria-live": "polite" });
  const input = h("input.ops-input.ops-mono", { placeholder: "type a command — try: help", autocomplete: "off", "aria-label": "Command" });
  const print = (text, cls) => { term.append(h(cls ? `div.${cls}` : "div", {}, text)); term.scrollTop = term.scrollHeight; };
  const form = h("form.ops-row", {}, input, h("button.nc-button.nc-button--primary", { type: "submit" }, "Run"));
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const command = input.value.trim();
    if (!command) return;
    input.value = "";
    print(`> ${command}`, "ops-term__in");
    try {
      let res = await api("steward", { method: "POST", body: { command } });
      if (res.step_up_required) {
        const code = await askStepUp();
        if (code) res = await api("steward", { method: "POST", body: { command }, stepUp: code });
      }
      print(res.text);
    } catch (err) { print(`error: ${err.message}`); }
  });
  main.append(panel(null,
    h("p.ops-muted", {}, "Deterministic command console. Fixed commands only, no AI inference. Same permissions as the buttons."),
    term, form));
  print("Operator Steward ready. Type help for commands.");
  input.focus();
}

async function auditView(main) {
  const d = await api("audit?limit=300");
  main.append(panel(null,
    h("p", {}, d.chain.ok ? h("span.ops-badge.ops-badge--ok", {}, "chain intact") : h("span.ops-badge.ops-badge--danger", {}, `chain broken at line ${d.chain.broken_at_line}`),
      ` ${d.chain.entries} entries`),
    table([
      { label: "Time", get: e => time(e.ts) },
      { label: "Operator", get: e => e.actor },
      { label: "Action", get: e => e.action, cls: "ops-mono" },
      { label: "Target", get: e => e.target, cls: "ops-mono" },
      { label: "OK", get: e => (e.ok ? "yes" : "no") },
      { label: "IP", get: e => e.ip, cls: "ops-mono" },
      { label: "Detail", get: e => JSON.stringify(e.detail), cls: "ops-wrap ops-mono" },
    ], d.entries)));
}

const VIEWS = {
  overview: overviewView, logs: logsView, errors: errorsView, metrics: metricsView,
  flags: flagsView, agegate: agegateView, accounts: accountsView, venues: venuesView,
  security: securityView, opsteward: opstewardView, audit: auditView,
};

boot();
