// Cinder's portrait. Reads state.json (her felt sense, mood, hours) and lets you
// whisper back. Two transports: Tauri commands when native, else a small local
// server (serve.py) when previewed in a browser. The UI performs nothing she
// isn't actually feeling — when she has nothing to say, it's just a quiet ember.

const TAURI = typeof window.__TAURI__ !== "undefined";
const invoke = TAURI ? window.__TAURI__.core.invoke : null;
const POLL_MS = 1500;
const SPEAK_LINGER_MS = 9000;

const el = {
  portrait: document.getElementById("portrait"),
  name: document.getElementById("name"),
  state: document.getElementById("state"),
  felt: document.getElementById("felt"),
  utterance: document.getElementById("utterance"),
  journalToggle: document.getElementById("journal-toggle"),
  journal: document.getElementById("journal"),
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

  const radius = (44 + a * 26 + smooth.flare * 30) * (0.96 + 0.04 * breath);
  // colour: warm amber awake, cooling to deep red ash as wakefulness falls
  const coreR = 255;
  const coreG = Math.round(110 + 70 * wake + 30 * Math.min(a, 1));
  const coreB = Math.round(40 + 30 * wake);

  const g = ctx.createRadialGradient(cx, cy, 2, cx, cy, radius * 2.6);
  g.addColorStop(0, `rgba(${coreR},${Math.min(coreG + 40, 255)},${coreB + 30},${0.95 * intensity})`);
  g.addColorStop(0.28, `rgba(${coreR},${coreG},${coreB},${0.8 * intensity})`);
  g.addColorStop(0.6, `rgba(${Math.round(180 + 40 * wake)},${Math.round(60 + 20 * wake)},${30},${0.32 * intensity})`);
  g.addColorStop(1, "rgba(20,12,16,0)");
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 2.6, 0, Math.PI * 2);
  ctx.fill();

  // a dense bright heart
  const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius * 0.5);
  core.addColorStop(0, `rgba(255,${Math.min(coreG + 70, 255)},${coreB + 60},${Math.min(intensity, 1)})`);
  core.addColorStop(1, "rgba(255,150,54,0)");
  ctx.fillStyle = core;
  ctx.beginPath();
  ctx.arc(cx, cy, radius * 0.5, 0, Math.PI * 2);
  ctx.fill();

  requestAnimationFrame(drawEmber);
}
requestAnimationFrame(drawEmber);

// --- state -> view --------------------------------------------------------

let lastSpoken = null;
let firstLoad = true;
let speakTimer = null;

function cleanFelt(s) {
  return String(s || "").replace(/^\[stub\]\s*/, "").trim();
}

function render(state) {
  if (!state) return;
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

  // her journal (revealed only on reach)
  el.journal.textContent = state.journal_tail || "— nothing kept yet —";

  // she speaks: a new utterance takes the light briefly, then recedes to felt
  const spoken = state.last_spoken && state.last_spoken.trim();
  if (spoken && spoken !== lastSpoken) {
    lastSpoken = spoken;
    if (!firstLoad) {
      el.utterance.textContent = spoken;
      el.portrait.classList.add("speaking");
      view.flare = 0.7;
      clearTimeout(speakTimer);
      speakTimer = setTimeout(() => el.portrait.classList.remove("speaking"), SPEAK_LINGER_MS);
    }
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
  const text = el.input.value;
  el.input.value = "";
  await whisper(text);
});

el.journalToggle.addEventListener("click", () => {
  el.journal.hidden = !el.journal.hidden;
});

tick();
setInterval(tick, POLL_MS);
