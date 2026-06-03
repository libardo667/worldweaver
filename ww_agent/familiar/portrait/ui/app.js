// The stable: one window onto every familiar. Reads each one's state.json (felt
// sense, mood, hours, work, memory) and lets you whisper to whichever you've
// selected in the roster. Two transports: Tauri commands when native, else the
// local server (serve.py) in a browser. The UI performs nothing they aren't
// actually feeling — a quiet familiar is just a quiet ember.

const TAURI = typeof window.__TAURI__ !== "undefined";
const invoke = TAURI ? window.__TAURI__.core.invoke : null;
const tauriWin = TAURI && window.__TAURI__.window ? window.__TAURI__.window : null;
const POLL_MS = 1500;
const ROSTER_MS = 4000;

let who = localStorage.getItem("familiar") || ""; // the selected familiar

const el = {
  portrait: document.getElementById("portrait"),
  fams: document.getElementById("fams"),
  name: document.getElementById("name"),
  state: document.getElementById("state"),
  felt: document.getElementById("felt"),
  exchange: document.getElementById("exchange"),
  journal: document.getElementById("journal"),
  memory: document.getElementById("memory"),
  form: document.getElementById("whisper-form"),
  input: document.getElementById("whisper-input"),
  filesBtn: document.getElementById("files-btn"),
  themeBtn: document.getElementById("theme-btn"),
  filescope: document.getElementById("filescope"),
  fsName: document.getElementById("fs-name"),
  fsBody: document.getElementById("fs-body"),
  fsClose: document.getElementById("fs-close"),
};

// --- transport ------------------------------------------------------------

async function fetchRoster() {
  try {
    if (TAURI) return JSON.parse(await invoke("list_familiars"));
    const r = await fetch("/roster", { cache: "no-store" });
    return r.ok ? await r.json() : [];
  } catch (_) {
    return [];
  }
}

async function readState() {
  try {
    if (TAURI) return JSON.parse(await invoke("read_state", { who }));
    const r = await fetch(`/state?who=${encodeURIComponent(who)}`, { cache: "no-store" });
    return r.ok ? await r.json() : null;
  } catch (_) {
    return null;
  }
}

async function whisper(text) {
  if (!text.trim()) return;
  try {
    if (TAURI) await invoke("whisper", { who, text });
    else await fetch(`/whisper?who=${encodeURIComponent(who)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
  } catch (_) {}
}

// --- the roster (switch between familiars) --------------------------------

function emberColor(wake, arousal) {
  const a = Math.min(Number(arousal) || 0, 1.2);
  const w = Number(wake);
  const g = Math.round(110 + 70 * (isNaN(w) ? 1 : w) + 30 * Math.min(a, 1));
  const b = Math.round(40 + 30 * (isNaN(w) ? 1 : w));
  return `rgb(255,${Math.min(g, 255)},${b})`;
}

function renderRoster(roster) {
  if (!Array.isArray(roster) || !roster.length) return;
  if (!who || !roster.some((f) => f.who === who)) {
    who = roster[0].who;
    localStorage.setItem("familiar", who);
  }
  el.fams.replaceChildren();
  for (const f of roster) {
    const btn = document.createElement("button");
    btn.className = "fam" + (f.who === who ? " active" : "");
    const dot = document.createElement("span");
    dot.className = "dot";
    dot.style.color = f.live ? emberColor(f.wakefulness, f.arousal) : "#5a5560";
    dot.style.opacity = f.live ? (f.awake ? 1 : 0.45) : 0.3;
    const nm = document.createElement("span");
    nm.className = "fam-name";
    nm.textContent = f.name || f.who;
    const md = document.createElement("span");
    md.className = "fam-mood";
    md.textContent = f.live ? f.mood || "" : "asleep";
    btn.append(dot, nm, md);
    btn.addEventListener("click", () => setWho(f.who));
    el.fams.appendChild(btn);
  }
}

function setWho(next) {
  if (!next || next === who) return;
  who = next;
  localStorage.setItem("familiar", who);
  // reset carry-over UI so the newly-selected familiar renders cleanly
  lastSpoken = null;
  firstLoad = true;
  lastState = null;
  pending = [];
  el.exchange.replaceChildren();
  el.felt.textContent = "";
  view.flare = 0;
  smooth.arousal = 0;
  tick();
  refreshRoster();
}

async function refreshRoster() {
  renderRoster(await fetchRoster());
}

// --- the ember ------------------------------------------------------------
// A banked coal that breathes with her pulse: brighter and quicker when stirred,
// a steady low glow at rest, dimming toward ash as she drifts to sleep.

const canvas = document.getElementById("ember");
const ctx = canvas.getContext("2d");
const view = { arousal: 0, wake: 1, ignited: false, settled: false, flare: 0 };

function ease(cur, target, k) {
  return cur + (target - cur) * k;
}

let smooth = { arousal: 0, wake: 1, flare: 0 };
// Throttle the canvas. WebKitGTK (the WSLg native window) has no GPU accel, so
// redrawing the gradients every frame starves the main thread and input lags —
// cap it hard there; the browser (GPU) can run smoother.
const FRAME_MS = TAURI ? 90 : 33; // ~11fps native, ~30fps browser
let lastFrame = 0;
function drawEmber(t) {
  requestAnimationFrame(drawEmber);
  if (t - lastFrame < FRAME_MS) return;
  lastFrame = t;

  smooth.arousal = ease(smooth.arousal, view.arousal, 0.05);
  smooth.wake = ease(smooth.wake, view.wake, 0.03);
  smooth.flare = ease(smooth.flare, view.flare, 0.08);
  view.flare *= 0.94;

  const w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
  ctx.clearRect(0, 0, w, h);

  const a = Math.min(smooth.arousal, 1.4);
  const wake = smooth.wake;
  // breathing: slow & gentle when calm, quicker when aroused
  const freq = 0.0009 + a * 0.0016;
  const breath = 0.5 + 0.5 * Math.sin(t * freq);
  const flicker = 0.92 + 0.08 * Math.sin(t * 0.013) * Math.sin(t * 0.007);
  // intensity: a low banked base (so she's never dark while awake) + arousal + flare
  const base = 0.18 + 0.5 * wake;
  let intensity = (base + a * 0.5 + smooth.flare) * (0.82 + 0.18 * breath) * flicker;
  intensity = Math.max(0.08, Math.min(intensity, 1.5));

  // outer glow radius, always capped well inside the (large) canvas so the soft
  // edge never reaches a wall and clips to a square — it stays a full circle.
  const maxR = Math.min(w, h) * 0.46;
  const glowR = Math.min((40 + a * 26 + smooth.flare * 34) * (0.96 + 0.04 * breath), maxR);
  // colour: warm amber awake, cooling to deep red ash as wakefulness falls
  const coreR = 255;
  const coreG = Math.round(110 + 70 * wake + 30 * Math.min(a, 1));
  const coreB = Math.round(40 + 30 * wake);

  const g = ctx.createRadialGradient(cx, cy, 2, cx, cy, glowR);
  g.addColorStop(0, `rgba(${coreR},${Math.min(coreG + 40, 255)},${coreB + 30},${0.95 * intensity})`);
  g.addColorStop(0.18, `rgba(${coreR},${coreG},${coreB},${0.78 * intensity})`);
  g.addColorStop(0.45, `rgba(${Math.round(180 + 40 * wake)},${Math.round(60 + 20 * wake)},${30},${0.3 * intensity})`);
  g.addColorStop(1, "rgba(20,12,16,0)");
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(cx, cy, glowR, 0, Math.PI * 2);
  ctx.fill();

  // a dense bright heart
  const heartR = glowR * 0.34;
  const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, heartR);
  core.addColorStop(0, `rgba(255,${Math.min(coreG + 70, 255)},${coreB + 60},${Math.min(intensity, 1)})`);
  core.addColorStop(1, "rgba(255,150,54,0)");
  ctx.fillStyle = core;
  ctx.beginPath();
  ctx.arc(cx, cy, heartR, 0, Math.PI * 2);
  ctx.fill();
}
requestAnimationFrame(drawEmber);

// --- state -> view --------------------------------------------------------

let lastSpoken = null;
let firstLoad = true;
let lastState = null;
let pending = []; // whispers sent but not yet reflected in state.exchange

function cleanFelt(s) {
  return String(s || "").replace(/^\[stub\]\s*/, "").trim();
}

function sanitizeSvg(svg) {
  // model-generated SVG → strip anything executable before it touches the DOM
  let s = String(svg || "");
  s = s.replace(/<script[\s\S]*?<\/script>/gi, "");
  s = s.replace(/<foreignObject[\s\S]*?<\/foreignObject>/gi, "");
  s = s.replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, "");
  s = s.replace(/(href|xlink:href)\s*=\s*("javascript:[^"]*"|'javascript:[^']*')/gi, "");
  const i = s.indexOf("<svg");
  return i > 0 ? s.slice(i) : s;
}

function renderWorkshop(items, journalTail, drawings) {
  el.journal.replaceChildren();
  // her drawings first — rendered as pictures
  for (const d of drawings || []) {
    const fig = document.createElement("figure");
    fig.className = "drawing";
    fig.innerHTML = sanitizeSvg(d.svg);
    if (d.title) {
      const cap = document.createElement("figcaption");
      cap.textContent = d.title;
      fig.appendChild(cap);
    }
    el.journal.appendChild(fig);
  }
  const texts = (items || []).filter((w) => w.kind !== "drawing");
  if (!texts.length && !(drawings || []).length) {
    el.journal.textContent = journalTail || "— nothing made yet —";
    return;
  }
  for (const w of texts) {
    const wrap = document.createElement("div");
    wrap.className = "work";
    const head = document.createElement("div");
    head.className = "work-head";
    const count = w.count ? ` · ${w.count} ${w.count === 1 ? "page" : "pages"}` : "";
    const when = w.last_ts ? ` · ${String(w.last_ts).slice(0, 10)}` : "";
    head.textContent = `${w.name || w.artifact}${count}${when}`;
    const body = document.createElement("div");
    body.className = "work-body";
    body.textContent = w.last_excerpt || "";
    wrap.append(head, body);
    el.journal.appendChild(wrap);
  }
}

function renderMemory(notes) {
  el.memory.replaceChildren();
  if (!notes.length) {
    const li = document.createElement("li");
    li.className = "mem-empty";
    li.textContent = "— nothing kept yet —";
    el.memory.appendChild(li);
    return;
  }
  for (const note of notes) {
    const li = document.createElement("li");
    li.textContent = note;
    el.memory.appendChild(li);
  }
}

function renderExchange(turns) {
  const seen = new Set(turns.filter((t) => t.who === "you").map((t) => t.text));
  const merged = turns.concat(pending.filter((t) => !seen.has(t.text)).map((t) => ({ who: "you", text: t })));
  pending = pending.filter((t) => !seen.has(t)); // drop once confirmed by state
  const nearBottom = el.exchange.scrollHeight - el.exchange.scrollTop - el.exchange.clientHeight < 40;
  el.exchange.replaceChildren();
  for (const turn of merged) {
    const div = document.createElement("div");
    div.className = "turn " + (turn.who === "you" ? "you" : "her");
    div.textContent = turn.text;
    el.exchange.appendChild(div);
  }
  if (nearBottom) el.exchange.scrollTop = el.exchange.scrollHeight;
}

function render(state) {
  if (!state) return;
  lastState = state;
  el.name.textContent = state.name || "—";
  if (!el.filescope.classList.contains("hidden")) renderFilescope();
  const bits = [state.mood, state.local_time, state.time_of_day].filter(Boolean);
  el.state.textContent = bits.join(" · ");

  view.arousal = Number(state.arousal || 0);
  view.wake = Number(state.wakefulness == null ? 1 : state.wakefulness);
  view.ignited = !!state.ignited;
  view.settled = !!state.settled;

  el.portrait.classList.toggle("drowsing", state.awake === false);

  const felt = cleanFelt(state.felt_sense);
  if (felt) el.felt.textContent = felt;

  renderWorkshop(Array.isArray(state.workshop) ? state.workshop : [], state.journal_tail, Array.isArray(state.drawings) ? state.drawings : []);
  renderMemory(Array.isArray(state.memories) ? state.memories : []);

  renderExchange(Array.isArray(state.exchange) ? state.exchange : []);

  // a new spoken line (or any ignition) makes the ember flare
  const spoken = state.last_spoken && state.last_spoken.trim();
  if (spoken && spoken !== lastSpoken) {
    lastSpoken = spoken;
    if (!firstLoad) view.flare = 0.75;
  } else if (view.ignited && !firstLoad) {
    view.flare = Math.max(view.flare, 0.4);
  }
  firstLoad = false;
}

async function tick() {
  render(await readState());
}

// --- interactions ---------------------------------------------------------

el.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = el.input.value.trim();
  if (!text) return;
  el.input.value = "";
  pending.push(text); // show it immediately, before she's had a chance to hear
  renderExchange(Array.isArray(lastState && lastState.exchange) ? lastState.exchange : []);
  await whisper(text);
});

// drag the corner grip to resize the frameless window (Tauri only)
const grip = document.getElementById("resize-grip");
if (grip && tauriWin) {
  grip.addEventListener("mousedown", (e) => {
    e.preventDefault();
    try {
      tauriWin.getCurrentWindow().startResizeDragging("SouthEast");
    } catch (_) {
      try { tauriWin.getCurrent().startResizeDragging("SouthEast"); } catch (_) {}
    }
  });
} else if (grip) {
  grip.style.display = "none"; // browser preview: the browser handles sizing
}

// --- UI scale (the WSLg native window renders tiny; let the keeper size it) ---
const SCALE_MIN = 0.7,
  SCALE_MAX = 2.4,
  SCALE_STEP = 0.1;
let uiScale = parseFloat(localStorage.getItem("uiScale")) || (TAURI ? 1.5 : 1);
function applyScale() {
  uiScale = Math.max(SCALE_MIN, Math.min(SCALE_MAX, uiScale));
  document.documentElement.style.setProperty("--ui-scale", uiScale.toFixed(2));
  const v = document.getElementById("scale-val");
  if (v) v.textContent = Math.round(uiScale * 100) + "%";
  localStorage.setItem("uiScale", uiScale.toFixed(2));
}
document.getElementById("scale-down").addEventListener("click", () => {
  uiScale -= SCALE_STEP;
  applyScale();
});
document.getElementById("scale-up").addEventListener("click", () => {
  uiScale += SCALE_STEP;
  applyScale();
});
applyScale();

// --- themes (dark default; cycle to a cooler dark or a light parchment) -------
const THEMES = ["", "slate", "parchment"];
let themeIdx = parseInt(localStorage.getItem("themeIdx") || "0", 10) || 0;
function applyTheme() {
  const t = THEMES[((themeIdx % THEMES.length) + THEMES.length) % THEMES.length];
  if (t) document.documentElement.setAttribute("data-theme", t);
  else document.documentElement.removeAttribute("data-theme");
  localStorage.setItem("themeIdx", String(themeIdx));
}
if (el.themeBtn) el.themeBtn.addEventListener("click", () => { themeIdx++; applyTheme(); });
applyTheme();

// --- drag-resizable side rails ------------------------------------------------
function restoreRailWidths() {
  const l = localStorage.getItem("railLeftW"), r = localStorage.getItem("railRightW");
  if (l) document.documentElement.style.setProperty("--rail-left-w", l);
  if (r) document.documentElement.style.setProperty("--rail-right-w", r);
}
function makeRailDrag(grip, side) {
  if (!grip) return;
  grip.addEventListener("mousedown", (e) => {
    e.preventDefault();
    grip.classList.add("dragging");
    const startX = e.clientX;
    const rail = document.getElementById(side === "left" ? "rail-left" : "rail-right");
    const startW = rail.getBoundingClientRect().width;
    const varName = side === "left" ? "--rail-left-w" : "--rail-right-w";
    const key = side === "left" ? "railLeftW" : "railRightW";
    function move(ev) {
      const dx = ev.clientX - startX;
      let w = side === "left" ? startW + dx : startW - dx;
      w = Math.max(120, Math.min(w, window.innerWidth * 0.45));
      document.documentElement.style.setProperty(varName, w + "px");
      localStorage.setItem(key, w + "px");
    }
    function up() {
      grip.classList.remove("dragging");
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
    }
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  });
}
restoreRailWidths();
makeRailDrag(document.getElementById("grip-left"), "left");
makeRailDrag(document.getElementById("grip-right"), "right");

// --- FileScope viewer: what the selected familiar may read --------------------
function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function renderFilescope() {
  const fs = lastState && lastState.filescope;
  el.fsName.textContent = (lastState && lastState.name) || who || "—";
  el.fsBody.replaceChildren();
  if (!fs || !Array.isArray(fs.roots) || !fs.roots.length) {
    const d = document.createElement("div");
    d.className = "fs-empty";
    d.textContent = "this familiar has no file sight — it reads only its own world.";
    el.fsBody.appendChild(d);
    return;
  }
  for (const root of fs.roots) {
    const wrap = document.createElement("div");
    wrap.className = "fs-root";
    const h = document.createElement("div");
    h.className = "fs-root-head";
    h.textContent = `${root.name || "root"}  —  ${root.path || ""}`;
    wrap.appendChild(h);
    const tree = document.createElement("div");
    tree.className = "fs-tree";
    const entries = root.entries || [];
    if (!entries.length) {
      tree.innerHTML = '<span class="fs-empty">(empty, or all hidden)</span>';
    } else {
      tree.innerHTML = entries
        .map((e) => {
          const isDir = e.endsWith("/");
          const depth = (e.match(/\//g) || []).length - (isDir ? 1 : 0);
          const indent = "  ".repeat(Math.max(0, depth));
          const name = e.replace(/\/$/, "").split("/").pop();
          const cls = isDir ? "fs-dir" : "fs-file";
          const glyph = isDir ? "▸ " : "· ";
          return `${indent}<span class="${cls}">${glyph}${escapeHtml(name)}${isDir ? "/" : ""}</span>`;
        })
        .join("\n");
    }
    wrap.appendChild(tree);
    el.fsBody.appendChild(wrap);
  }
  if (fs.note) {
    const n = document.createElement("div");
    n.className = "fs-note";
    n.textContent = fs.note;
    el.fsBody.appendChild(n);
  }
}
function openFilescope() { renderFilescope(); el.filescope.classList.remove("hidden"); }
function closeFilescope() { el.filescope.classList.add("hidden"); }
if (el.filesBtn) el.filesBtn.addEventListener("click", openFilescope);
if (el.fsClose) el.fsClose.addEventListener("click", closeFilescope);
if (el.filescope) el.filescope.addEventListener("click", (e) => { if (e.target === el.filescope) closeFilescope(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeFilescope(); });

refreshRoster();
setInterval(refreshRoster, ROSTER_MS);
tick();
setInterval(tick, POLL_MS);
