// Cinder's portrait. Reads state.json (her felt sense, mood, hours) and lets you
// whisper back. Two transports: Tauri commands when native, else a small local
// server (serve.py) when previewed in a browser. The UI performs nothing she
// isn't actually feeling — when she has nothing to say, it's just a quiet ember.

const TAURI = typeof window.__TAURI__ !== "undefined";
const invoke = TAURI ? window.__TAURI__.core.invoke : null;
const tauriWin = TAURI && window.__TAURI__.window ? window.__TAURI__.window : null;
const POLL_MS = 1500;
const SPEAK_LINGER_MS = 9000;

const el = {
  portrait: document.getElementById("portrait"),
  name: document.getElementById("name"),
  state: document.getElementById("state"),
  felt: document.getElementById("felt"),
  exchange: document.getElementById("exchange"),
  journal: document.getElementById("journal"),
  memory: document.getElementById("memory"),
  form: document.getElementById("whisper-form"),
  input: document.getElementById("whisper-input"),
};

// --- transport ------------------------------------------------------------

async function readState() {
  try {
    if (TAURI) return JSON.parse(await invoke("read_state"));
    const r = await fetch("/state", { cache: "no-store" });
    return r.ok ? await r.json() : null;
  } catch (_) {
    return null;
  }
}

async function whisper(text) {
  if (!text.trim()) return;
  try {
    if (TAURI) await invoke("whisper", { text });
    else await fetch("/whisper", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
  } catch (_) {}
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
function drawEmber(t) {
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

  requestAnimationFrame(drawEmber);
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
  el.name.textContent = state.name || "Cinder";
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

tick();
setInterval(tick, POLL_MS);
