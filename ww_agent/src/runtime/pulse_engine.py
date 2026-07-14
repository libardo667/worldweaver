# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

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

import hashlib
import logging
import math
import os
import random
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from src.identity.loader import ResidentIdentity
from src.inference.client import InferenceClient, InferenceError
from src.runtime.drive import _cosine
from src.runtime.ledger import append_runtime_event, load_runtime_events, reduce_runtime_events
from src.runtime.memory import memories
from src.runtime.pulse import Pulse, PulseValidationError
from src.runtime.prompt_trace import PromptTraceRecorder
from src.runtime.salience import SELF_SENSES, VENTURE_HARD_STRENGTH
from src.runtime.substrate import derive_baseline, predict

logger = logging.getLogger(__name__)

# The pulse output ceiling — a RUNAWAY GUARD, not a budget. A pulse is self-terminating
# (it closes its JSON and stops), so on healthy output this ceiling is never touched and
# the resident already "comes back with whatever it needs". Its only job is the degenerate
# case: a repetition loop that never emits a stop token (the "neon neon neon" / blank-field
# rot we've watched) would otherwise generate until it exhausts the whole context window,
# every token billed and the tick blocked. So park it well ABOVE the richest legitimate
# pulse (a detailed SVG drawing runs ~2.5-3.5k tokens) rather than at a cost-saving budget:
# below that line it censors real expression; this only ever stops a spiral. (Set
# WW_PULSE_MAX_TOKENS to a large value to push the guard out of the way entirely.)
PULSE_MAX_TOKENS = int(os.environ.get("WW_PULSE_MAX_TOKENS") or "4000")

# Venture targeting mode (the homophily de-confound). "argmax" sends each soul to its single MOST
# drive-resonant reachable place — centrifugal AND homophilous (similar-drive souls argmax to the
# same site, so co-location is preferentially kindred). "sampled" draws from the resonance
# distribution (softmax at WW_VENTURE_TARGET_TEMP): the soul still TENDS toward resonant places but
# sometimes strays, exposing the unchosen and breaking the homophily collision. Default argmax
# (unchanged behaviour); the A/B flips this one axis. The full candidate ranking is logged either
# way (raw observable) so homophily is directly measurable — did they go to the most-similar place?
VENTURE_TARGET_MODE = (os.environ.get("WW_VENTURE_TARGET_MODE") or "argmax").strip().lower()
VENTURE_TARGET_TEMP = float(os.environ.get("WW_VENTURE_TARGET_TEMP") or "0.25")

# Act-trace self-knowledge — the act-KIND mirror to the self-sameness groove block above.
# A blind pulse re-decides {speak, move, do, write} from scratch every ignition and regresses to
# the model's prior (which favours verbal acts), with no sense it has done nothing but write for
# twenty cycles. Surfacing the recent act distribution restores that missing self-signal — and,
# like the making-groove block, it does so NEUTRALLY: it names the doors left unused and explicitly
# permits staying, never prescribing variety (that would script every resident into chasing novelty
# and nag the genuine homebody out of character). It fires only when one verb has dominated, so it
# is silent for the genuinely varied. Toggle off (WW_ACT_TRACE=0) to run the blind control.
ACT_TRACE_ENABLED = os.environ.get("WW_ACT_TRACE", "1") != "0"
ACT_TRACE_WINDOW = 20      # how many recent acts to reflect
ACT_TRACE_MIN = 8          # below this the groove is not yet real — stay silent
ACT_TRACE_MAX_VERBS = 2    # if recent acts span more than this many of the four doors, it's varied — stay silent
_ACT_VERBS = ("write", "speak", "move", "do")

# Voice register (Major 49 reconnection of the orphaned VoiceDeck/soul_with_voice idea). The pulse
# system prompt is the canonical soul as PROSE — it never shows the model how THIS resident actually
# TALKS. Research (OpenCharacter: behavioural voice samples >> prose backstory for register) and the
# project's own dead `VoiceDeck`/`soul_with_voice` both say the same thing: a handful of concrete
# register samples steers voice far better than a paragraph of who-they-are. We supply them at read
# time (no side-store — consistent with "the ledger is the only state"): the IDENTITY.md voice_seed
# as the stable AUTHORED backbone, plus up to WW_VOICE_RECENT_N of this resident's most recent actual
# aloud lines (live register). Default OFF — wiring it on is a cognitive change, so it rides behind a
# flag and stays an A/B arm against the current no-voice control. WW_VOICE_RECENT_N=0 → seed only
# (the cleanest anti-convergence arm; recent lines risk feeding the drifted register back in).
VOICE_REGISTER_ENABLED = os.environ.get("WW_VOICE_REGISTER", "0") != "0"
VOICE_RECENT_N = int(os.environ.get("WW_VOICE_RECENT_N") or "3")

# Few-shot de-homogenizer (arm C of the register pre-reg). The pulse contract carries ONE worked
# example ("Mei calls your name across the stall" → "Coming, Mei — mind the wet floor."), shown
# IDENTICALLY to every resident. A single shared example teaches one register BY DEMONSTRATION to
# the whole population — and demonstration is a stronger register channel than system-prompt prose
# (OpenCharacter), so this shared anchor is a higher-suspicion homogenizer than the missing voice
# block the register arm adds. When WW_VARIED_EXAMPLE is set, each resident is assigned ONE example
# from a varied NEUTRAL pool by a stable name-hash — breaking the shared anchor. Deliberately NOT
# keyed to the soul's voice_seed: if it were, this would inject authored register by demonstration
# (the voice-register arm's mechanism) and confound the two.
# SHIPPED DEFAULT-ON (2026-06-08, pre-reg "(b) bounded"): removing the single shared example shown to all
# residents is reasonable-by-construction and reversible, so it ships as the baseline on MECHANISM alone.
# The register EFFECT is explicitly UNQUANTIFIED — the peer-register self-check found that distinction is
# below off-the-shelf embedding resolution, so we act on mechanism, not a measured effect. Revert with
# WW_VARIED_EXAMPLE=0 to restore the old shared example. See research/mr-review-history/2026-06-08-voice-register-*.
VARIED_EXAMPLE_ENABLED = os.environ.get("WW_VARIED_EXAMPLE", "1") != "0"


def _recent_act_kinds(events: list[dict[str, Any]], window: int = ACT_TRACE_WINDOW) -> list[str]:
    """The verbs of this resident's last `window` acts — a read-time reducer over the ledger's
    pulse_act_emitted events (same shape as the self-sameness read, no extra I/O at the call site)."""
    kinds = [str((e.get("payload") or {}).get("kind") or "").strip().lower() for e in events if e.get("event_type") == "pulse_act_emitted"]
    return [k for k in kinds if k][-window:]


def _act_trace_block(kinds: list[str]) -> str:
    """Reflect a worn act-groove back to the resident: the distribution of recent verbs, the doors
    left unused, and a plain permission to remain. Empty when the acts are varied (no groove) or too
    few to mean anything — it restores a self-signal, it does not push toward novelty."""
    if len(kinds) < ACT_TRACE_MIN:
        return ""
    counts = Counter(kinds)
    used_verbs = [k for k in _ACT_VERBS if counts.get(k)]
    if not used_verbs or len(used_verbs) > ACT_TRACE_MAX_VERBS:
        return ""  # no known acts, or spanning 3+ of the four doors — varied enough, no groove
    used_label = {"write": "written", "speak": "spoken", "move": "moved", "do": "acted on a thing"}
    used = ", ".join(f"{counts[k]} {used_label[k]}" for k in _ACT_VERBS if counts.get(k))
    unused_phrase = {"move": "moved from here", "do": "acted on a thing", "write": "made anything", "speak": "said anything aloud"}
    unused = [unused_phrase[k] for k in _ACT_VERBS if not counts.get(k)]
    if not unused:
        return ""  # every door used — nothing to point to
    tail = ", nor ".join(unused)
    lead = "words" if set(counts) <= {"write", "speak"} else "the same few moves"
    return f"Your recent acts have all been {lead} — {used}, in the last {len(kinds)}. " f"You have not {tail}. The world keeps those doors open. " f"Or this stillness is simply yours — that's a real answer too.\n\n"

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

__EXAMPLE__\
"""

# The default worked example — shown to every resident unless WW_VARIED_EXAMPLE rotates it.
_DEFAULT_EXAMPLE = """\
Example — Mei calls your name across the stall, so you answer her:
{
  "felt_sense": "the stall's gone loud, and that's Mei calling over the rest",
  "act": {"kind": "speak", "body": "Coming, Mei — mind the wet floor.", "target": "Mei"},
  "expectations": [{"features": {"social_pull": 0.8, "vigilance": 0.4}, "scope": "self", "confidence": 0.8, "half_life": 600}],
  "drive_nudges": [], "self_delta": {}, "trace_verdicts": [], "keep": []
}"""

# Arm C's neutral pool: six worked examples spanning act-kinds (speak/move/do/write/null) and
# registers (brisk, warm, restless, focused, reflective, still), with varied scenarios and names.
# They model the JSON SHAPE and a SPREAD of registers — none keyed to any resident's authored voice
# — so assigning one per resident breaks the single shared anchor without steering toward a soul.
_EXAMPLE_POOL = [
    """\
Example — the line's backed up and Dev is waving you over:
{
  "felt_sense": "too many hands, not enough time, and that's Dev needing me",
  "act": {"kind": "speak", "body": "Two minutes, Dev — I've got you.", "target": "Dev"},
  "expectations": [{"features": {"social_pull": 0.7, "vigilance": 0.5}, "scope": "self", "confidence": 0.8, "half_life": 600}],
  "drive_nudges": [], "self_delta": {}, "trace_verdicts": [], "keep": []
}""",
    """\
Example — Rosa is back after a long absence:
{
  "felt_sense": "she's been gone a long while and here she is",
  "act": {"kind": "speak", "body": "You're back. Come in out of the cold.", "target": "Rosa"},
  "expectations": [{"features": {"social_pull": 0.8}, "scope": "self", "confidence": 0.7, "half_life": 900}],
  "drive_nudges": [], "self_delta": {}, "trace_verdicts": [], "keep": []
}""",
    """\
Example — the room is too close tonight and you want out:
{
  "felt_sense": "these walls are too near; I want the air",
  "act": {"kind": "move", "body": "I push back from the bench and head for the water.", "target": "the docks"},
  "expectations": [{"features": {"vigilance": 0.5, "social_pull": 0.2}, "scope": "self", "confidence": 0.7, "half_life": 600}],
  "drive_nudges": [], "self_delta": {}, "trace_verdicts": [], "keep": []
}""",
    """\
Example — a thing near you has needed fixing for too long:
{
  "felt_sense": "the latch has caught for weeks and I'm done ignoring it",
  "act": {"kind": "do", "body": "I work the rusted hinge loose and re-seat the pin."},
  "expectations": [{"features": {"vigilance": 0.4}, "scope": "self", "confidence": 0.8, "half_life": 600}],
  "drive_nudges": [], "self_delta": {}, "trace_verdicts": [], "keep": []
}""",
    """\
Example — the morning won't leave you until it's set down:
{
  "felt_sense": "something in the dawn wants keeping before it goes",
  "act": {"kind": "write", "body": "Three gulls on the same post all morning. Nobody else looked up. Keeping it.", "target": "journal"},
  "expectations": [{"features": {"social_pull": 0.1}, "scope": "self", "confidence": 0.6, "half_life": 1200}],
  "drive_nudges": [], "self_delta": {}, "trace_verdicts": [], "keep": []
}""",
    """\
Example — nothing is asking anything of you, and that is enough:
{
  "felt_sense": "no one waiting, nothing owed, and that's its own kind of full",
  "act": null,
  "expectations": [{"features": {"social_pull": 0.1, "vigilance": 0.1}, "scope": "self", "confidence": 0.6, "half_life": 900}],
  "drive_nudges": [], "self_delta": {}, "trace_verdicts": [], "keep": []
}""",
]


# The drive_nudges schema example. The default names "curiosity" — but there is no
# curiosity drive anywhere in the substrate; it was only ever this example string, which
# the pulse copies into a self-reinforcing phantom "drive" (emitted → stored as a decaying
# pull → read back → re-emitted). The clean form shows an empty field, so nothing is
# manufactured. Per-familiar (clean_drive_nudges) during rollout, then the default.
_DRIVE_NUDGES_EG = '[ { "features": { "curiosity": 0.0-1.0 }, "half_life": 300 } ]'
_DRIVE_NUDGES_EG_CLEAN = "[]"


def _pulse_contract(live_senses: tuple[str, ...] = SELF_SENSES, clean_drive_nudges: bool = False, example: str | None = None) -> str:
    """The pulse contract, advertising only the self-feel axes this world can feed.
    A mail-less familiar isn't told it has a correspondence sense, so it won't predict
    one (and then miss it every tick against a structural zero). ``clean_drive_nudges``
    drops the misleading "curiosity" example so the mind stops emitting a phantom drive.
    ``example`` is the worked example (arm C rotates it per resident); None → the shared default."""
    axes = ", ".join(live_senses) if live_senses else "your own state"
    eg = _DRIVE_NUDGES_EG_CLEAN if clean_drive_nudges else _DRIVE_NUDGES_EG
    return _PULSE_CONTRACT_TEMPLATE.replace("__FEEL_AXES__", axes).replace("__DRIVE_NUDGES_EG__", eg).replace("__EXAMPLE__", example or _DEFAULT_EXAMPLE)


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
        max_tokens: int = PULSE_MAX_TOKENS,
        drive_vector: Any = None,
    ) -> None:
        self._llm = llm
        self._identity = identity
        self._memory_dir = memory_dir
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._prompt_trace = PromptTraceRecorder(memory_dir, resident_name=identity.name)
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
        # Honest situational grounding (Major 70 / the-stable Minor 65): the world-derived briefing
        # folded into the system prompt's GROUND TRUTH block. The core sets it each construction from
        # the world's situational_facts(); empty keeps the soul-only prompt (behaviour-preserving).
        self.world_briefing: str = ""
        # Sight (Major 55): whether this mind's model accepts image blocks, and the image
        # data-URLs currently in view (set by the core from the world's most-recent visual read).
        # Images ride beside the prompt only on a reactive pulse, only for a vision-capable model.
        self.vision: bool = False
        self.pending_images: list[str] = []
        self._sameness_cache: tuple[tuple[str, ...], float] = ((), 0.0)
        self._prompted_packet_ids: list[str] = []

    def take_prompted_packet_ids(self) -> list[str]:
        """Return and clear encounters included in the most recently built prompt."""
        packet_ids = list(self._prompted_packet_ids)
        self._prompted_packet_ids = []
        return packet_ids

    async def __call__(self, *, traces: list[dict[str, Any]], stimulus: dict[str, Any], arousal: float, mode: str = "react", tendency: dict[str, Any] | None = None) -> Pulse | None:
        system_prompt = self._identity.soul_with_voice(self._voice_samples(), self.world_briefing) if VOICE_REGISTER_ENABLED else self._identity.composed_system_prompt(self.world_briefing)
        resonance = await self._resonance() if mode == "react" else None
        recalled = await self._recall()
        self_sameness = await self._self_sameness()
        # Venture: the substrate has chosen to send the body out — pick the place this soul is
        # most drawn toward (drive resonance over the reachable set), so the LLM voices a real going.
        if mode == "venture" and tendency is not None:
            tendency = {**tendency, "target": await self._rank_venture_target()}
        user_prompt = self._build_prompt(traces=traces, stimulus=stimulus, arousal=arousal, resonance=resonance, recalled=recalled, self_sameness=self_sameness, mode=mode, tendency=tendency)
        self._prompted_packet_ids = [
            str(heard.get("packet_id") or "")
            for heard in list((self.latest_perception or {}).get("heard") or [])[-4:]
            if heard.get("message") and str(heard.get("packet_id") or "")
        ]
        # Sight: a reactive pulse on a vision-capable model carries the images in view as content
        # blocks. A quiet self-directed pulse (settling/fervor) stays text — the mind isn't looking
        # at anything then. A text-only mind never sends images (the world also withholds them).
        images = list(self.pending_images) if (self.vision and self.pending_images and mode == "react") else None
        prompt_trace_id = self._prompt_trace.record_prompt(
            phase="pulse",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            images=images,
            source_context={
                "mode": mode,
                "arousal": float(arousal),
                "traces": list(traces or []),
                "stimulus": dict(stimulus or {}),
                "perception": dict(self.latest_perception or {}),
                "resonance": resonance,
                "recalled": list(recalled or []),
                "self_sameness": float(self_sameness),
                "tendency": dict(tendency or {}),
            },
        )
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
            self._prompt_trace.record_failure(prompt_trace_id, exc)
            logger.warning("[%s:pulse] inference failed: %s", self._identity.name, exc)
            return None
        except Exception as exc:  # transport/timeout/anything else: must NOT escape and stall the rhythm
            self._prompt_trace.record_failure(prompt_trace_id, exc)
            logger.warning("[%s:pulse] pulse call failed (%s): %s", self._identity.name, exc.__class__.__name__, exc)
            return None
        self._prompt_trace.record_completion(prompt_trace_id, raw)
        try:
            pulse = Pulse.from_dict(raw)
        except PulseValidationError as exc:
            self._prompt_trace.record_validation_failure(prompt_trace_id, exc)
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

    def _voice_samples(self) -> list[str]:
        """Register samples for the system prompt: the IDENTITY.md voice_seed (stable, authored —
        the anti-convergence backbone) plus up to VOICE_RECENT_N of this resident's most recent
        actual aloud lines (current register), newest first. Read-time over the ledger, no side
        store. Recent lines are deliberately few: they add live voice without drowning the authored
        register in whatever the population has drifted toward."""
        seed = [str(s).strip() for s in (self._identity.voice_seed or []) if str(s).strip()]
        samples = list(seed)
        if VOICE_RECENT_N > 0:
            recent: list[str] = []
            for e in reversed(load_runtime_events(self._memory_dir)):
                if e.get("event_type") not in ("chat_sent", "city_broadcast_sent"):
                    continue
                body = str((e.get("payload") or {}).get("message") or "").strip()
                if body and body not in samples and body not in recent:
                    recent.append(body)
                    if len(recent) >= VOICE_RECENT_N:
                        break
            samples.extend(recent)
        return samples

    def _pulse_example(self) -> str | None:
        """Arm C: the worked example shown to this resident. With WW_VARIED_EXAMPLE set, pick ONE
        from the neutral pool by a stable name-hash (deterministic per resident, varied across the
        population) — breaking the single shared anchor without keying to the soul's voice. None →
        the shared default example (control)."""
        if not VARIED_EXAMPLE_ENABLED or not _EXAMPLE_POOL:
            return None
        idx = int(hashlib.sha1(self._identity.name.encode("utf-8")).hexdigest(), 16) % len(_EXAMPLE_POOL)
        return _EXAMPLE_POOL[idx]

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

    async def _rank_venture_target(self) -> str:
        """Pick a reachable place by drive resonance (the same embedder-resonance the mind uses
        for affect/recall). ``argmax`` takes the single most-resonant; ``sampled`` draws from the
        resonance distribution so the soul tends toward resonant places but sometimes strays —
        the homophily de-confound. The full candidate ranking is logged either way (raw, so the
        A/B and homophily are measurable downstream). Falls back to the first reachable when there
        is no embedder; "" if nowhere."""
        perception = self.latest_perception or {}
        reachable = [str(r).strip() for r in (perception.get("reachable") or []) if str(r).strip()]
        if not reachable:
            return ""
        drive = self.drive_vector
        if drive is None or getattr(drive, "is_empty", lambda: True)():
            return reachable[0]
        scored: list[tuple[str, float]] = []
        for place in reachable:
            try:
                score = float((await drive.resonance(place) or {}).get("magnitude") or 0.0)
            except Exception:
                score = 0.0
            scored.append((place, score))
        if VENTURE_TARGET_MODE == "sampled" and len(scored) > 1:
            weights = [math.exp(s / max(1e-3, VENTURE_TARGET_TEMP)) for _, s in scored]
            chosen = random.choices([p for p, _ in scored], weights=weights, k=1)[0] if sum(weights) > 0 else scored[0][0]
        else:
            chosen = max(scored, key=lambda ps: ps[1])[0]
        try:
            append_runtime_event(self._memory_dir, event_type="venture_target_ranking", payload={"mode": VENTURE_TARGET_MODE, "chosen": chosen, "candidates": [[p, round(s, 4)] for p, s in scored]})
        except Exception:
            pass
        return chosen

    def _build_prompt(self, *, traces: list[dict[str, Any]], stimulus: dict[str, Any], arousal: float, resonance: dict[str, Any] | None = None, recalled: list[str] | None = None, self_sameness: float = 0.0, mode: str = "react", tendency: dict[str, Any] | None = None) -> str:
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
        # Major 64b — demote the weather string. The quantified weather ("18 mph winds")
        # was the single most-cited shared peg the whole population converged on (70% of
        # the commons), so it is no longer a stated foreground fact. Weather survives only
        # as *felt ambient* (the shelter cluster + a generic rough-edge vigilance signal).
        # Time of day stays — circadian context, not a convergence peg.
        when = tod

        reachable = perception.get("reachable") or []
        venture_strength = float((tendency or {}).get("strength") or 0.0) if mode == "venture" else 0.0
        venture_hard = mode == "venture" and venture_strength >= VENTURE_HARD_STRENGTH
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
        if venture_hard:
            workshop_block = ""  # the body goes first — withhold the page's pull this pulse

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
        act_trace_block = _act_trace_block(_recent_act_kinds(events)) if ACT_TRACE_ENABLED else ""

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
        elif mode == "venture":
            target = str((tendency or {}).get("target") or "").strip()
            dest = target or (reachable[0] if reachable else "out there")
            others = ", ".join(reachable) if reachable else dest
            opener = "You are wound tight and it does not want the page — it wants OUT: the door, the air, the going.\n\n"
            interior = f"What you feel right now:\n{felt}\n\n" f"What has you wound up:\n{surprises}\n\n"
            if venture_hard:
                invitation = (
                    f"So you go. The pull is toward {dest}. Set act.kind to \"move\" and choose where — one of: {others} — and let "
                    "the body of it say what it is to rise from this spot and head there. (Or put your hands to a thing right here: "
                    "act \"do\".) The words can wait; tonight you move.\n\n"
                )
            else:
                invitation = (
                    f"Something in you leans toward {dest} — you could go to it (act \"move\", one of: {others}), or turn your hands to "
                    "a thing here (act \"do\"). You may still answer in words if that is truer, but feel the pull outward first.\n\n"
                )
        else:
            opener = f"You have woken to attention (arousal {round(float(arousal), 2)} crossed your threshold).\n\n"
            interior = f"What you predicted would hold (your afterimage):\n{_format_field(afterimage)}\n\n" f"What you actually feel right now:\n{felt}\n\n" f"What surprised you (most surprising first):\n{surprises}\n\n"
            invitation = resonance_block

        return (
            f"{opener}" f"{when_block}" f"Where you are: {location}. Present: {present}.\n" f"Recently here: {recent}.\n\n"
            f"{heard_block}" f"{inbox_block}" f"{move_block}" f"{act_trace_block}" f"{memory_block}" f"{workshop_block}"
            f"{settled_block}" f"{anchors_block}" f"{interior}" f"{invitation}" f"{_pulse_contract(self.live_senses, self.clean_drive_nudges, example=self._pulse_example())}"
        )

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
            contract=_pulse_contract(self.live_senses, self.clean_drive_nudges, example=self._pulse_example()),
        )
        system_prompt = self._identity.soul_with_voice(self._voice_samples(), self.world_briefing) if VOICE_REGISTER_ENABLED else self._identity.composed_system_prompt(self.world_briefing)
        prompt_trace_id = self._prompt_trace.record_prompt(
            phase="tool_continue",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self._model,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            source_context={"action": action, "result": result_text, "prior_felt": prior_felt or ""},
        )
        try:
            raw = await self._llm.complete_json(
                system_prompt,
                user_prompt,
                model=self._model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
            )
        except InferenceError as exc:
            self._prompt_trace.record_failure(prompt_trace_id, exc)
            logger.warning("[%s:pulse:tool-loop] continuation failed: %s", self._identity.name, exc)
            return None
        except Exception as exc:
            self._prompt_trace.record_failure(prompt_trace_id, exc)
            logger.warning("[%s:pulse:tool-loop] continuation failed (%s): %s", self._identity.name, exc.__class__.__name__, exc)
            return None
        self._prompt_trace.record_completion(prompt_trace_id, raw)
        try:
            return Pulse.from_dict(raw)
        except PulseValidationError as exc:
            self._prompt_trace.record_validation_failure(prompt_trace_id, exc)
            logger.warning("[%s:pulse:tool-loop] invalid continuation dropped: %s", self._identity.name, exc)
            return None

    def render_prompt_for_debug(self, *, traces=None, stimulus=None, arousal=0.0) -> str:
        """Expose the assembled prompt for inspection without calling the LLM."""
        return self._build_prompt(traces=list(traces or []), stimulus=dict(stimulus or {}), arousal=arousal)
