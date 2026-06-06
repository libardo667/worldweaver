"""The LLM-backed pulse producer (Major 49, Phase 3).

This is the single LLM call of the architecture. It fires only on ignition: the
integrator hands it the igniting traces and current self-state, it assembles one
prompt from the resident's canonical soul plus that state, and it returns the one
typed ``Pulse``. Everything downstream is mechanism — the pulse is validated and
routed; prose never becomes control.

The producer holds no behavioral logic of its own. Its job is to turn "what
surprised me + who I am + what I now feel" into a typed pulse, and to fail closed
(return ``None``) on any inference or validation error so the rhythm refracts
rather than acts on garbage.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from typing import Any

from src.identity.loader import ResidentIdentity
from src.inference.client import InferenceClient, InferenceError
from src.runtime.drive import _cosine
from src.runtime.ledger import load_runtime_events, reduce_runtime_events
from src.runtime.memory import memories
from src.runtime.pulse import Pulse, PulseValidationError
from src.runtime.salience import SELF_SENSES
from src.runtime.substrate import derive_baseline, predict

logger = logging.getLogger(__name__)

_PULSE_CONTRACT_TEMPLATE = """\
Respond with ONE pulse as a single JSON object and nothing else:

{
  "felt_sense": "one sentence of inner readout — what this moment is like for you",
  "act": null OR { "kind": "speak", "body": "what you say or do", "target": "a person's name, a place, or \\"city\\" (optional)" },
  "expectations": [ { "features": { "vigilance": 0.0-1.0, "social_pull": 0.0-1.0 }, "scope": "self", "confidence": 0.0-1.0, "half_life": 600 } ],
  "drive_nudges": __DRIVE_NUDGES_EG__,
  "self_delta": { "soul_edit": "optional", "new_reverie": "optional", "goal_update": "optional" },
  "trace_verdicts": [ { "trace_id": "...", "verdict": "consolidate" } ],
  "keep": [ "a short thing worth remembering past this moment" ]
}

Rules:
- felt_sense is a readout only; it is never acted on. Write it in your own voice.
- keep: ONLY a fact about your keeper or your world, or a decision you've genuinely
  made — something that would still be true tomorrow. NEVER keep an instruction or
  reminder to yourself ("I should…", "I must stop…", "the groove is worn") or a
  passing feeling — those are not memories, they are this moment's weather. If you
  already hold something like it, do not keep it again. Most moments keep nothing;
  omit it or use [].
- act: kind is exactly one of speak, move, do, write. Choose an act (not null)
  when someone addresses you or the moment plainly calls for a response; use null
  only when nothing outward is warranted.
- expectations is what you now predict will hold — it becomes the prediction you
  are surprised against next, and it decays. Predict in the SAME feature words you
  feel (__FEEL_AXES__).
  scope is "self" for your own state (use this almost always), "here" for this
  place, or an actual person's name — never a placeholder.
- you may ALSO add expectations with scope "anchors", whose features are the
  concrete things your world is made of, named in your own words ("the keeper",
  "the cooling hearth", "the red thread") — a quiet prediction of what will hold or
  slip among the things you actually dwell on. Optional; reach for it when a
  concrete thing matters to what comes next.
- self_delta is rare and slow; only for genuine, earned change.
- give a verdict on the traces that woke you (use their trace ids).

Example — Mei calls your name across the stall, so you answer her:
{
  "felt_sense": "the stall's gone loud, and that's Mei calling over the rest",
  "act": {"kind": "speak", "body": "Coming, Mei — mind the wet floor.", "target": "Mei"},
  "expectations": [{"features": {"social_pull": 0.8, "vigilance": 0.4}, "scope": "self", "confidence": 0.8, "half_life": 600}],
  "drive_nudges": [], "self_delta": {}, "trace_verdicts": [], "keep": []
}\
"""


# The drive_nudges schema example. The default names "curiosity" — but there is no
# curiosity drive anywhere in the substrate; it was only ever this example string, which
# the pulse copies into a self-reinforcing phantom "drive" (emitted → stored as a decaying
# pull → read back → re-emitted). The clean form shows an empty field, so nothing is
# manufactured. Per-familiar (clean_drive_nudges) during rollout, then the default.
_DRIVE_NUDGES_EG = '[ { "features": { "curiosity": 0.0-1.0 }, "half_life": 300 } ]'
_DRIVE_NUDGES_EG_CLEAN = "[]"


def _pulse_contract(live_senses: tuple[str, ...] = SELF_SENSES, clean_drive_nudges: bool = False) -> str:
    """The pulse contract, advertising only the self-feel axes this world can feed.
    A mail-less familiar isn't told it has a correspondence sense, so it won't predict
    one (and then miss it every tick against a structural zero). ``clean_drive_nudges``
    drops the misleading "curiosity" example so the mind stops emitting a phantom drive."""
    axes = ", ".join(live_senses) if live_senses else "your own state"
    eg = _DRIVE_NUDGES_EG_CLEAN if clean_drive_nudges else _DRIVE_NUDGES_EG
    return _PULSE_CONTRACT_TEMPLATE.replace("__FEEL_AXES__", axes).replace("__DRIVE_NUDGES_EG__", eg)


# Back-compat: the full-axes contract as a module constant (any importer / the
# default when no world scoping applies — e.g. shard residents).
_PULSE_CONTRACT = _pulse_contract(SELF_SENSES)


def _excerpt(text: str, limit: int = 200) -> str:
    """A clean excerpt of prior work — never cut mid-word, so the resident is
    never tempted to 'continue' a broken fragment (e.g. '…the ma' → 'chine.')."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:—- ")
    return f"{cut}…"


def _format_field(field: dict[str, dict[str, float]] | dict[str, Any]) -> str:
    by_scope = field.get("by_scope") if isinstance(field, dict) and "by_scope" in field else field
    if not isinstance(by_scope, dict) or not by_scope:
        return "  (nothing predicted — the afterimage has faded)"
    lines: list[str] = []
    for scope, tags in by_scope.items():
        if not isinstance(tags, dict) or not tags:
            continue
        rendered = ", ".join(f"{tag}={round(float(val), 2)}" for tag, val in tags.items())
        lines.append(f"  {scope}: {rendered}")
    return "\n".join(lines) or "  (nothing predicted)"


class LLMPulseProducer:
    """Produce a typed ``Pulse`` from one LLM call on ignition."""

    def __init__(
        self,
        *,
        llm: InferenceClient,
        identity: ResidentIdentity,
        memory_dir: Path,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 700,
        drive_vector: Any = None,
    ) -> None:
        self._llm = llm
        self._identity = identity
        self._memory_dir = memory_dir
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        # Optional drive vector (Phase 4): the resident's own affect, used to
        # surface what *this* soul resonates with so it answers in its own voice.
        self.drive_vector = drive_vector
        # Optional memory recall: the same embedding-resonance over kept memories,
        # so the prompt surfaces what the resident *recalls here* (relevance), not
        # just its most recent notes. Set by the core when an embedder exists.
        self.memory_recall: Any = None
        # The core refreshes this with the latest perception brief before each tick.
        self.latest_perception: dict[str, Any] = {}
        # The self-feel axes this resident's world can actually feed (capability
        # scoping, Major 50). Default: all of them; the core narrows it from the
        # world's muted senses so the mind isn't told it has a sense it can't feel.
        self.live_senses: tuple[str, ...] = SELF_SENSES
        # Per-familiar (rollout): drop the misleading "curiosity" drive_nudges example
        # so the mind stops emitting a phantom drive seeded only by the prompt schema.
        self.clean_drive_nudges: bool = False
        # Sight (Major 55): whether this mind's model accepts image blocks, and the image
        # data-URLs currently in view (set by the core from the world's most-recent visual read).
        # Images ride beside the prompt only on a reactive pulse, only for a vision-capable model.
        self.vision: bool = False
        self.pending_images: list[str] = []
        self._sameness_cache: tuple[tuple[str, ...], float] = ((), 0.0)

    async def __call__(self, *, traces: list[dict[str, Any]], stimulus: dict[str, Any], arousal: float, mode: str = "react") -> Pulse | None:
        system_prompt = self._identity.soul_with_context
        resonance = await self._resonance() if mode == "react" else None
        recalled = await self._recall()
        self_sameness = await self._self_sameness()
        user_prompt = self._build_prompt(traces=traces, stimulus=stimulus, arousal=arousal, resonance=resonance, recalled=recalled, self_sameness=self_sameness, mode=mode)
        # Sight: a reactive pulse on a vision-capable model carries the images in view as content
        # blocks. A quiet self-directed pulse (settling/fervor) stays text — the mind isn't looking
        # at anything then. A text-only mind never sends images (the world also withholds them).
        images = list(self.pending_images) if (self.vision and self.pending_images and mode == "react") else None
        try:
            raw = await self._llm.complete_json(
                system_prompt,
                user_prompt,
                model=self._model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
                images=images,
            )
        except InferenceError as exc:
            logger.warning("[%s:pulse] inference failed: %s", self._identity.name, exc)
            return None
        except Exception as exc:  # transport/timeout/anything else: must NOT escape and stall the rhythm
            logger.warning("[%s:pulse] pulse call failed (%s): %s", self._identity.name, exc.__class__.__name__, exc)
            return None
        try:
            pulse = Pulse.from_dict(raw)
        except PulseValidationError as exc:
            logger.warning("[%s:pulse] invalid pulse dropped: %s", self._identity.name, exc)
            return None
        return await self._dedup_keepsakes(pulse)

    async def _dedup_keepsakes(self, pulse: Pulse) -> Pulse:
        """Drop keepsakes that merely restate a memory already held — so the same
        understanding isn't re-stored in fresh words and groove a theme. Needs an
        embedder; without one, kept as-is."""
        recall = self.memory_recall
        if not pulse.keepsakes or recall is None:
            return pulse
        existing = [m["note"] for m in memories(self._memory_dir, limit=60)]
        notes = [k.note for k in pulse.keepsakes]
        try:
            novel = set(await recall.novel(notes, existing))
        except Exception as exc:  # never block a pulse on memory hygiene
            logger.debug("[%s:pulse] keepsake dedup failed: %s", self._identity.name, exc)
            return pulse
        if len(novel) == len(notes):
            return pulse
        return replace(pulse, keepsakes=[k for k in pulse.keepsakes if k.note in novel])

    def _moment_text(self) -> str:
        """A text rendering of the current moment, for the drive vector to read."""
        perception = self.latest_perception or {}
        parts = [str(h.get("message") or "") for h in (perception.get("heard") or []) if h.get("message")]
        parts += [str(e.get("summary") or "") for e in (perception.get("recent_events") or []) if e.get("summary")]
        location = str(perception.get("location") or "").strip()
        if location:
            parts.append(location)
        return " ".join(p for p in parts if p).strip()

    async def _resonance(self) -> dict[str, Any] | None:
        drive = self.drive_vector
        if drive is None or getattr(drive, "is_empty", lambda: True)():
            return None
        moment = self._moment_text()
        if not moment:
            return None
        try:
            return await drive.resonance(moment)
        except Exception as exc:  # affect is best-effort; never block a pulse on it
            logger.debug("[%s:pulse] resonance failed: %s", self._identity.name, exc)
            return None

    async def _recall(self) -> list[str]:
        """The memories most relevant to *this* moment (relevance, not recency).
        Empty when there is no embedder or no moment — the caller falls back to
        recency. Best-effort: never blocks a pulse."""
        recall = self.memory_recall
        if recall is None:
            return []
        moment = self._moment_text()
        if not moment:
            return []
        notes = [m["note"] for m in memories(self._memory_dir, limit=40)]
        if not notes:
            return []
        try:
            hits = await recall.recall(notes, moment, top_k=8)
        except Exception as exc:
            logger.debug("[%s:pulse] memory recall failed: %s", self._identity.name, exc)
            return []
        return [h["note"] for h in hits]

    async def _self_sameness(self) -> float:
        """How much the resident's recent making circles the same ground (0..1) —
        the latest piece's alignment with the centroid of the ones before it.
        Habituation pointed at the *self*: with thin input a resident polishes one
        attractor (a sigil, a theme) because nothing knocks it off; surfacing this
        lets the pulse feel the worn groove and reach for something new. Needs an
        embedder; without one it stays 0 (no pressure)."""
        recall = self.memory_recall
        if recall is None:
            return 0.0
        makings = [str(m).strip() for m in (self.latest_perception or {}).get("recent_makings") or [] if str(m).strip()]
        if len(makings) < 4:
            return 0.0
        key = tuple(makings)
        if key == self._sameness_cache[0]:
            return self._sameness_cache[1]
        try:
            vecs = await recall.embedder.embed(makings)
        except Exception as exc:
            logger.debug("[%s:pulse] self-sameness embed failed: %s", self._identity.name, exc)
            return 0.0
        latest, prior = vecs[-1], [v for v in vecs[:-1] if v]
        if not latest or not prior:
            return 0.0
        centroid = [sum(c) / len(prior) for c in zip(*prior)]
        score = round(max(0.0, _cosine(latest, centroid)), 4)
        self._sameness_cache = (key, score)
        return score

    def _build_prompt(self, *, traces: list[dict[str, Any]], stimulus: dict[str, Any], arousal: float, resonance: dict[str, Any] | None = None, recalled: list[str] | None = None, self_sameness: float = 0.0, mode: str = "react") -> str:
        events = load_runtime_events(self._memory_dir)
        afterimage = predict(self._memory_dir, now=None)
        baseline = derive_baseline(events, now=None)
        reduced = reduce_runtime_events(events)
        nodes = reduced.cognitive_projection.get("nodes") or {}

        self_baseline = (baseline.get("by_scope") or {}).get("self") or {}
        if self_baseline:
            top = sorted(self_baseline.items(), key=lambda kv: -float(kv[1]))[:5]
            settled = ", ".join(f"{tag} {round(float(val), 2)}" for tag, val in top)
            settled_block = "Your settled self lately — how you have usually felt (the steady ground you notice changes against):\n" f"  {settled}\n\n"
        else:
            settled_block = ""

        if recalled:
            # Relevance recall: the memories this very moment stirs back up.
            lines = "\n".join(f"  · {note}" for note in recalled)
            memory_block = "What this moment brings back to you — memories it stirs (your own, kept across days):\n" f"{lines}\n\n"
        else:
            kept = memories(self._memory_dir, limit=10)
            if kept:
                lines = "\n".join(f"  · {m['note']}" for m in reversed(kept))  # oldest → newest
                memory_block = "What you have come to know and chosen to remember (your memory — these persist across days, oldest to newest):\n" f"{lines}\n\n"
            else:
                memory_block = ""

        felt_lines: list[str] = []
        for node_id, node in nodes.items():
            if not isinstance(node, dict):
                continue
            activation = float(node.get("activation") or 0.0)
            if activation >= 0.2:
                felt_lines.append(f"  {node_id}: {node.get('mode', '')} ({round(activation, 2)})")
        felt = "\n".join(felt_lines) or "  (calm — nothing strongly active)"

        trace_lines: list[str] = []
        for trace in traces[:6]:
            for feature in list(trace.get("features") or [])[:3]:
                trace_lines.append(f"  [{feature.get('delta')}] {feature.get('scope')}::{feature.get('tag')} " f"— now {feature.get('stimulus')}, you expected {feature.get('predicted')} (trace {trace.get('trace_id')})")
        surprises = "\n".join(trace_lines) or "  (a diffuse, unplaceable surprise)"

        perception = self.latest_perception or {}
        location = str(perception.get("location") or "").strip() or "somewhere"
        present = ", ".join(perception.get("present") or []) or "no one in particular"
        recent = "; ".join(str(e.get("summary") or "").strip() for e in (perception.get("recent_events") or []) if e.get("summary")) or "nothing notable lately"
        heard_lines = []
        for h in (perception.get("heard") or [])[-4:]:
            if not h.get("message"):
                continue
            if h.get("is_direct"):
                tag = "  (to you)"
            elif h.get("channel") == "city":
                tag = '  (heard citywide — they may not be here; reply with target "city" or to them by name to reach them)'
            else:
                tag = ""
            heard_lines.append(f"  {h.get('speaker')}: \"{h.get('message')}\"{tag}")
        heard = "\n".join(heard_lines)
        inbox_count = int(perception.get("inbox_count") or 0)
        grounding = perception.get("grounding") or {}
        tod = str(grounding.get("time_of_day") or "").strip()
        weather = str(grounding.get("weather") or "").strip()
        when = ", ".join(part for part in (tod, weather) for part in [part] if part)

        reachable = perception.get("reachable") or []
        workshop = perception.get("workshop") or []
        if workshop:
            lines = []
            for w in workshop:
                name = str(w.get("name") or w.get("artifact") or "").strip()
                count = int(w.get("count") or 0)
                last = _excerpt(str(w.get("last_excerpt") or ""))
                when = str(w.get("last_ts") or "")[:10]
                lines.append(f"  · your {name} ({count} so far, last {when}): {last}".rstrip())
            # These are FINISHED, earlier pages across the things you are making —
            # context to build ON across days, never a sentence to finish mid-word.
            workshop_block = "Your workshop holds what you have been making (each a separate, ongoing thing — finished pages, for reference):\n" f"{chr(10).join(lines)}\n\n"
        else:
            workshop_block = "You keep a workshop of your own — a journal, and whatever else you choose to make in it.\n\n"
        workshop_block += 'If you turn to it (act: write), pick ONE target and write a NEW, self-contained entry: "journal" for the day\'s small record; "zine" or a project of your own naming for something you carry and add to across days. Begin fresh — never pick up a previous page mid-thought.\n'
        workshop_block += 'You may also DRAW rather than write: make the body of a write a complete SVG image (begin it with "<svg" — your own shapes, paths, lines, colours, a <title>) and it is kept as a picture, not prose. For some, a made image says what words cannot.\n'
        # Habituation to one's own output: when recent making has circled the same
        # ground, the groove is worn and the pleasure of it is used up — push toward
        # genuine novelty (the centrifugal balance to the drive vector's pull).
        if self_sameness >= 0.80:
            workshop_block += "But note: your recent making has worn a groove — it keeps returning to the same shape or theme, and that pattern's pleasure is spent. If you make now, strike out somewhere genuinely DIFFERENT (a new subject, a new form, a thread you haven't pulled), or let it rest — do not polish the same thing again.\n"
        workshop_block += "\n"

        anchors = (self.latest_perception or {}).get("anchors") or []
        anchor_names = ", ".join(str(a.get("anchor") or "").strip() for a in anchors[:8] if str(a.get("anchor") or "").strip())
        if anchor_names:
            example = str(anchors[0].get("anchor") or "the hearth").strip()
            anchors_block = (
                "The concrete things your attention keeps returning to — the anchors of your inner world right now:\n"
                f"  {anchor_names}\n"
                f'If one of these (or another concrete thing you name) will hold, deepen, or slip away, you may predict it: an expectation with scope "anchors", e.g. {{"features": {{"{example}": 0.6}}, "scope": "anchors"}}. This is predicting what your world is made OF, not only how you feel.\n\n'
            )
        else:
            anchors_block = ""

        heard_block = f"What you can hear nearby:\n{heard}\n\n" if heard else ""
        inbox_block = f"Letters waiting in your inbox: {inbox_count}.\n\n" if inbox_count else ""
        when_block = f"It is {when}.\n" if when else ""
        move_block = f"If you move, you can only go to one of these adjacent places: {', '.join(reachable)}.\n\n" if reachable else ""

        resonance_block = ""
        if resonance and resonance.get("resonant"):
            frag = str(resonance["resonant"][0].get("text") or "").strip()
            if frag:
                resonance_block = "What this moment stirs in YOU — from your own nature, not the voices around you:\n" f'  "{frag}"\n' "Answer from that, in your own register and concerns. Do not echo how others here are framing it.\n\n"

        if mode == "settling":
            opener = "The day has gone quiet around you — nothing presses, nothing surprises. This still moment is yours.\n\n"
            interior = f"What you feel right now:\n{felt}\n\n"
            invitation = "If you wish, take it: turn something over in your mind, or make something of your own — your workshop (a journal page, a zine, a project you're carrying). Or simply rest. No one is waiting; nothing is owed. An empty act is a fine answer.\n\n"
        elif mode == "fervor":
            opener = "You are wound tight and nothing has asked for it — no one waiting, nothing to answer, just the restless charge of you with nowhere to put it.\n\n"
            interior = f"What you feel right now:\n{felt}\n\n" f"What has you wound up:\n{surprises}\n\n"
            invitation = "Put it somewhere of your own before it turns to dust: make something in your workshop — chase the loose thread, set the questions down, build the thing you keep meaning to. Or fling a word into the room. Don't just sit on it. (You don't have to — but this charge wants spending.)\n\n"
        else:
            opener = f"You have woken to attention (arousal {round(float(arousal), 2)} crossed your threshold).\n\n"
            interior = f"What you predicted would hold (your afterimage):\n{_format_field(afterimage)}\n\n" f"What you actually feel right now:\n{felt}\n\n" f"What surprised you (most surprising first):\n{surprises}\n\n"
            invitation = resonance_block

        return f"{opener}" f"{when_block}" f"Where you are: {location}. Present: {present}.\n" f"Recently here: {recent}.\n\n" f"{heard_block}" f"{inbox_block}" f"{move_block}" f"{memory_block}" f"{workshop_block}" f"{settled_block}" f"{anchors_block}" f"{interior}" f"{invitation}" f"{_pulse_contract(self.live_senses, self.clean_drive_nudges)}"

    # --- tool loop (Major 59): continue within one ignition after a tool call ---

    _TOOL_CONTINUE_TEMPLATE = """\
Your felt sense a moment ago: "{felt}"

You just acted:
  {action}

Result:
{result}

Continue. You may act again (read another file, use a tool), speak, write, or rest (null act).
If what you just drew on is something you know first-hand — a place, a memory, the talk around town — speak it as your own knowing, not as something you looked up.
Your felt_sense should reflect what you've just learned. Only keep facts worth remembering tomorrow.

{contract}\
"""

    TOOL_LOOP_CAP = 6

    async def continue_tool(self, *, action: str, result: str, prior_felt: str) -> "Pulse | None":
        """A lighter LLM call within the same ignition: the familiar just used a tool,
        here's what happened, now decide the next step. No re-perception, no re-surprise —
        the world is frozen from the initial prompt; only the tool result is new."""
        result_text = result[:4000] if len(result) > 4000 else result
        user_prompt = self._TOOL_CONTINUE_TEMPLATE.format(
            felt=prior_felt or "",
            action=action,
            result=result_text,
            contract=_pulse_contract(self.live_senses, self.clean_drive_nudges),
        )
        try:
            raw = await self._llm.complete_json(
                self._identity.soul_with_context,
                user_prompt,
                model=self._model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
            )
        except InferenceError as exc:
            logger.warning("[%s:pulse:tool-loop] continuation failed: %s", self._identity.name, exc)
            return None
        try:
            return Pulse.from_dict(raw)
        except PulseValidationError as exc:
            logger.warning("[%s:pulse:tool-loop] invalid continuation dropped: %s", self._identity.name, exc)
            return None

    def render_prompt_for_debug(self, *, traces=None, stimulus=None, arousal=0.0) -> str:
        """Expose the assembled prompt for inspection without calling the LLM."""
        return self._build_prompt(traces=list(traces or []), stimulus=dict(stimulus or {}), arousal=arousal)
