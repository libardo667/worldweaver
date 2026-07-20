# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""The cognitive core: the resident's mind as substrate + pulse (Major 49, Phase 3).

This is what replaces the loop-era mind. On each tick the core:

  1. perceives the world  → emits substrate perturbations (perception.py),
  2. runs one integrator tick → surprise vs afterimage, decaying call pressure,
     and possibly a model activation with elective-read continuations,
  3. routes the final typed pulse back into the substrate and lets the effector carry
     the one act to the world (effectors.py).

The core is the orchestration seam between derived state, scheduling and prompt
policy, the model, and the world. It also owns behavioral controls such as mode,
incubation, action tendency, refractory timing, and the host read limit. The old
fast / slow / mail / ground / wander loops are gone.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from src.identity.loader import (
    ResidentIdentity,
    render_situational_briefing,
    unregistered_fact_keys,
)
from src.inference.client import InferenceClient
from src.runtime import integrator
from src.runtime.anchors import extract_anchors, record_anchors
from src.runtime.drive import DriveVector, RemoteEmbedder, _cosine
from src.runtime.effectors import WorldEffector
from src.runtime.incubation import is_incubating
from src.runtime.information import InformationAccess
from src.runtime.ledger import append_runtime_event, load_runtime_events
from src.runtime.memory import MemoryRecall
from src.runtime.perception import perceive
from src.runtime.prediction import tag_mattering
from src.runtime.pulse_engine import LLMPulseProducer
from src.runtime.relations import utterance_perceived_fields
from src.runtime.salience import SELF_SENSES
from src.runtime.signals import StimulusPacketQueue
from src.runtime.substrate import predict
from src.runtime.workshop import Workshop
from src.runtime.world import WorldWeaverClient

logger = logging.getLogger(__name__)

# An anchor must resonate at least this much with the resident's soul to be allowed
# to drive arousal when anchor-gating is on — the price on boring, in the gate: only
# concrete things it cares about (the keeper) can wake it, never the furniture.
# Back to 0.5 (2026-06-04): the 0.5→0.65 raise was a flood mitigation, and it made the
# flood WORSE — the real cause was disappearance-surprise (a predicted anchor dropping
# off the gated top-k scored a full delta), and a higher bar shrinks the realized set,
# manufacturing MORE absences. That's now fixed at the source: anchor-scope surprise is
# appearance-weighted (salience.measure_surprise), so absence is free and only a
# cared-about thing showing up fires. With the flood gone, a higher bar only suppresses
# legitimate appearances, so the original calibrated 0.5 stands.
ANCHOR_GATE_MATTERING = 0.5

# Concept-space match threshold (minor 46): a realized anchor whose embedding is at least
# this cosine-close to a PREDICTED anchor is treated as the same thing and renamed to the
# predicted key, so a rephrasing ("question itself" ≈ "the question") stops manufacturing
# phantom exact-string surprise. Genuinely-new anchors stay distinct and still fire.
# Calibrated empirically on nomic-embed-text short phrases: rephrasings land ~0.68-0.87,
# distinct concepts ~0.41-0.56 — 0.65 sits in the valley between them.
ANCHOR_MATCH_THRESHOLD = 0.65
DEFAULT_HOST_REACH_CONTINUATION_MAX = 2
ABSOLUTE_REACH_CONTINUATION_MAX = 8


def resolve_reach_continuation_limit(requested: int | None = None) -> int:
    """Resolve a run's read limit without letting it exceed the host's maximum."""
    try:
        host_max = int(
            os.environ.get(
                "WW_REACH_CONTINUATION_MAX", DEFAULT_HOST_REACH_CONTINUATION_MAX
            )
        )
    except (TypeError, ValueError):
        host_max = DEFAULT_HOST_REACH_CONTINUATION_MAX
    host_max = max(0, min(host_max, ABSOLUTE_REACH_CONTINUATION_MAX))
    if requested is None:
        return host_max
    return min(max(0, int(requested)), host_max)


def _information_freshness_seconds() -> float:
    try:
        value = float(os.environ.get("WW_INFORMATION_FRESHNESS_SECONDS", "30"))
    except (TypeError, ValueError):
        value = 30.0
    return max(0.0, min(value, 300.0))


def _embedder_from_env() -> Any:
    """A drive-vector embedder from WW_EMBEDDING_* (any OpenAI-compatible
    /v1/embeddings endpoint, e.g. a local Ollama nomic-embed-text). Absent → the
    drive vector is disabled and affect stays neutral."""
    url = os.environ.get("WW_EMBEDDING_URL", "").strip()
    if not url:
        return None
    return RemoteEmbedder(
        base_url=url,
        api_key=os.environ.get("WW_EMBEDDING_KEY", "ollama").strip() or "ollama",
        model=os.environ.get("WW_EMBEDDING_MODEL", "nomic-embed-text").strip()
        or "nomic-embed-text",
    )


class CognitiveCore:
    """One resident mind: perceive → integrate → pulse → act, on a cadence."""

    def __init__(
        self,
        *,
        identity: ResidentIdentity,
        resident_dir: Path,
        ww_client: WorldWeaverClient,
        llm: InferenceClient,
        session_id: str,
        tick_seconds: float = 20.0,
        pulse_model: str | None = None,
        pulse_temperature: float | None = 0.7,
        embedder: Any = None,
        writes_to_workshop_only: bool = False,
        anchor_gating: bool = False,
        clean_drive_nudges: bool = False,
        ignition_refractory_seconds: float | None = None,
        pulse_vision: bool = False,
        incubation: bool = False,
        action_tendency: bool | None = None,
        reach_continuation_limit: int | None = None,
    ) -> None:
        self._identity = identity
        self._memory_dir = resident_dir / "memory"
        self._ww = ww_client
        self._session_id = session_id
        self._tick_seconds = max(2.0, float(tick_seconds))
        # Anchor-gating (Major 51 Phase 4b.6, experimental, per-resident): let
        # drive-resonant concrete anchors drive arousal. Off = scored-but-quiet.
        self._anchor_gating = bool(anchor_gating)
        # Incubation (arrival quarantine, experimental, opt-in): seal a self-less new
        # arrival from the citywide current until it has built enough of a self to resist
        # being swept onto the loudest shared thing. Off here keeps behaviour unchanged.
        self._incubation = bool(incubation)
        # A run-scoped override for the existing venture tendency. None retains
        # the shard environment default; True/False is explicit for this host.
        self._action_tendency = action_tendency
        self._reach_continuation_limit = resolve_reach_continuation_limit(
            reach_continuation_limit
        )
        # Min gap between arousal-driven ignitions (None = substrate default). A direct
        # address always bypasses it; this only stops a hot talker echoing itself a
        # paraphrase every tick into the gap before the keeper replies. Per-familiar.
        self._refractory_seconds = ignition_refractory_seconds
        # Drive vector (Phase 4): built lazily on the first tick from the embedder.
        self._embedder = embedder if embedder is not None else _embedder_from_env()
        self._drive_built = False

        # Capability scoping (Major 50): a world declares the self-senses it cannot
        # feed (a mail-less LocalWorld → correspondence_pull). The real WorldWeaver
        # client declares none, so shard residents keep all five axes unchanged.
        self._muted_senses = tuple(getattr(ww_client, "muted_self_senses", ()) or ())

        self._producer = LLMPulseProducer(
            llm=llm,
            identity=identity,
            memory_dir=self._memory_dir,
            model=pulse_model,
            temperature=pulse_temperature,
        )
        self._producer.live_senses = tuple(
            s for s in SELF_SENSES if s not in self._muted_senses
        )
        self._producer.can_mark_world = callable(
            getattr(ww_client, "post_world_trace", None)
        )
        # Rollout flag: drop the phantom "curiosity" drive_nudges example for this familiar.
        self._producer.clean_drive_nudges = bool(clean_drive_nudges)
        # Sight (Major 55): does this mind's model accept images? The world only renders/holds
        # images for a vision-capable familiar, and the producer only sends them when this is set.
        self._producer.vision = bool(pulse_vision)
        # Honest situational grounding (Major 70 / the-stable Minor 65): the world reports VERIFIABLE
        # facts about this resident's circumstances; render_situational_briefing turns them into a
        # briefing that states what is true and withholds every verdict about what it means. It folds
        # into the system prompt's GROUND TRUTH block, replacing the deleted false _WORLD_CONTEXT story.
        # A world that reports none yields no situational claims at all — silence beats a false story.
        facts: dict[str, Any] = {}
        _facts_fn = getattr(ww_client, "situational_facts", None)
        if callable(_facts_fn):
            try:
                facts = dict(_facts_fn() or {})
            except Exception as exc:
                logger.warning(
                    "[%s] situational_facts failed — no world briefing: %s",
                    identity.name,
                    exc,
                )
                facts = {}
        # Drift-catcher (runtime half): a fact the renderer does not know is dropped silently — exactly
        # the drift that produced the old false story. Log it LOUDLY so a new affordance can't slip a fact
        # past the briefing unnoticed. The test half forbids it outright; this is the running tripwire.
        _unknown = unregistered_fact_keys(facts)
        if _unknown:
            logger.warning(
                "[%s] situational_facts reported unrendered key(s) %s — add a briefing line + register in BRIEFING_FACT_KEYS (drift)",
                identity.name,
                _unknown,
            )
        self._producer.world_briefing = render_situational_briefing(facts)
        # The resident's own, capability-scoped workshop (Major 50) — a real place
        # it authors its life into, sandboxed to this directory.
        self._workshop = Workshop(resident_dir / "workshop")
        self._effector = WorldEffector(
            ww_client=ww_client,
            session_id=session_id,
            identity=identity,
            memory_dir=self._memory_dir,
            workshop=self._workshop,
            all_writes_to_workshop=writes_to_workshop_only,
        )
        self._information_access = InformationAccess(
            ww_client=ww_client,
            memory_dir=self._memory_dir,
            freshness_seconds=_information_freshness_seconds(),
        )

    @property
    def name(self) -> str:
        return self._identity.name

    @property
    def tick_seconds(self) -> float:
        """Cadence owned by this core instance."""
        return self._tick_seconds

    async def run(self) -> None:
        logger.info("[%s] cognitive core starting", self.name)
        while True:
            try:
                await self.tick_once()
            except asyncio.CancelledError:
                logger.info("[%s] cognitive core cancelled", self.name)
                raise
            except Exception as exc:
                logger.exception("[%s] cognitive tick error: %s", self.name, exc)
                await asyncio.sleep(10.0)
            await asyncio.sleep(self._tick_seconds)

    async def _ensure_drive_vector(self) -> None:
        if self._drive_built or self._embedder is None:
            return
        self._drive_built = True  # one attempt; never retry-storm on a bad endpoint
        # The same embedder powers relevance recall over kept memories — one
        # mechanism, two stores: "what stirs you" (soul) and "what you recall here"
        # (memory). With no embedder both stay off and memory falls back to recency.
        self._producer.memory_recall = MemoryRecall(self._embedder)
        try:
            self._producer.drive_vector = await DriveVector.build(
                embedder=self._embedder,
                constitution=self._identity.canonical_soul,
                growth=self._identity.growth_soul,
            )
            logger.info(
                "[%s] drive vector built (%d constitution fragments)",
                self.name,
                len(self._producer.drive_vector.slices.get("constitution", [])),
            )
            # Major 60: lend the same affect to the citywide `chatter` pull so it ranks
            # the feed by soul-resonance (curiosity rationing focus). No-op for worlds
            # without a source registry; the pull falls back to recency until/without this.
            bind = getattr(self._ww, "bind_source_drive", None)
            if callable(bind):
                bind(self._producer.drive_vector)
        except Exception as exc:
            logger.warning(
                "[%s] drive vector build failed — affect stays neutral: %s",
                self.name,
                exc,
            )

    async def tick_once(
        self,
        *,
        now: Any = None,
        force_ignite: bool = False,
    ) -> dict[str, Any]:
        """Run one full perceive → integrate → (pulse → act) cycle."""
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        await self._ensure_drive_vector()
        # Incubation keeps a new arrival from deliberately listening to or broadcasting
        # on the citywide channel until it has built some private history. Exact-place
        # perception remains available. CityWorld reads this flag before building tools.
        events = load_runtime_events(self._memory_dir)
        incubating = self._incubation and is_incubating(events, now=now)
        self._effector.incubating = incubating
        setattr(self._ww, "incubating", incubating)
        brief = await perceive(
            ww_client=self._ww,
            session_id=self._session_id,
            memory_dir=self._memory_dir,
            identity=self._identity,
        )
        reactivity = 1.0
        anchor_stimulus = None
        if brief:
            brief["workshop"] = self._workshop.summary()
            # The recent sequence of its OWN makings, for self-output novelty: the
            # last journal entries + drawing titles, newest last.
            makings = [str(e.get("body") or "") for e in self._workshop.recent(6)]
            makings += [
                str(d.get("title") or "") for d in self._workshop.drawings(limit=6)
            ]
            brief["recent_makings"] = [m for m in makings if m.strip()][-8:]
            # Concrete anchors (Major 51 granularity): the things THIS resident's
            # inner world is actually about, lifted from its own recent felt sense
            # plus the entities perceived. Surfaced to the pulse so it can predict
            # them by name; snapshotted as the realized field for offline scoring.
            # Scored-but-quiet: anchors never touch the arousal/ignition rhythm.
            prose = [
                str((e.get("payload") or {}).get("felt_sense") or "")
                for e in events
                if str(e.get("event_type") or "") == "felt_sense_logged"
            ][-10:]
            structured = list(brief.get("present") or [])
            structured += [
                str(e.get("who") or "") for e in (brief.get("recent_events") or [])
            ]
            structured += [
                str(h.get("speaker") or "") for h in (brief.get("heard") or [])
            ]
            anchors = extract_anchors(prose, structured=structured, top_k=8)
            brief["anchors"] = anchors
            record_anchors(self._memory_dir, anchors, now=now, events=events)
            self._producer.latest_perception = brief
            # Sight: the images in view (the most-recent visual read), pulled off the world by its
            # duck-typed surface. A WorldClient without it (the city shard) simply offers none.
            _pending = getattr(self._ww, "pending_images", None)
            self._producer.pending_images = (
                list(_pending() or []) if callable(_pending) else []
            )
            anchor_stimulus = await self._anchor_stimulus(anchors)
            self._effector.present = list(brief.get("present") or [])
            self._effector.co_present = [
                dict(item)
                for item in brief.get("co_present") or []
                if isinstance(item, dict)
            ]
            self._effector.heard = list(
                brief.get("heard") or []
            )  # Major 66: read-from reply-edge source
            location = str(brief.get("location") or "").strip()
            if location:
                self._effector.location = location
            # Circadian wakefulness scales the rhythm: the town quiets after dark.
            reactivity = float(
                brief.get("wakefulness")
                if brief.get("wakefulness") is not None
                else 1.0
            )
        else:
            # A failed scene read must not make a later act claim yesterday's
            # co-presence or speech as if it were still current.
            self._effector.present = []
            self._effector.co_present = []
            self._effector.heard = []

        # Discard anything stale if a prior tick was interrupted after prompt
        # construction but before the lifecycle update below.
        self._producer.take_prompted_packet_ids()
        result = await integrator.tick(
            self._memory_dir,
            pulse_producer=self._producer,
            effector=self._effector,
            information_access=self._information_access,
            now=now,
            reactivity=reactivity,
            force_ignite=force_ignite,
            anchor_stimulus=anchor_stimulus,
            gate_anchors=anchor_stimulus is not None,
            muted_senses=self._muted_senses,
            refractory_seconds=self._refractory_seconds,
            action_tendency=self._action_tendency,
            reach_continuation_limit=self._reach_continuation_limit,
        )
        if bool((result.get("act_executed") or {}).get("identity_growth_adopted")):
            # The shared ResidentIdentity already gives the next prompt the adopted
            # text. Rebuild the optional semantic drive on the next tick as well.
            self._producer.drive_vector = None
            self._drive_built = False
        # A local chat/trace packet becomes observed only after it was actually
        # assembled into the LLM prompt. This does not yet cover mail: the current
        # engine inbox endpoint marks letters read during the HTTP poll itself.
        prompted_packet_ids = self._producer.take_prompted_packet_ids()
        if prompted_packet_ids:
            packet_queue = StimulusPacketQueue(
                self._memory_dir / "stimulus_packets.json"
            )
            for packet_id in prompted_packet_ids:
                packet = packet_queue.mark_status(packet_id, "observed")
                perceived = (
                    utterance_perceived_fields(
                        packet=packet,
                        recipient_actor_id=str(self._identity.actor_id or ""),
                        recipient_session_id=self._session_id,
                        co_present=self._effector.co_present,
                    )
                    if packet is not None
                    else None
                )
                if perceived is not None:
                    append_runtime_event(
                        self._memory_dir,
                        event_type="utterance_perceived",
                        payload=perceived,
                    )
        return result

    async def _anchor_stimulus(
        self, anchors: list[dict[str, Any]]
    ) -> dict[str, dict[str, float]] | None:
        """The realized anchor field that may drive arousal — only when this resident
        has anchor-gating on, and only the anchors whose soul-resonance clears
        ``ANCHOR_GATE_MATTERING`` (the price on boring, in the gate). Needs the drive
        vector; without it the gate stays shut (never an un-weighted, dark-room gate).
        """
        if not self._anchor_gating or not anchors:
            return None
        drive = self._producer.drive_vector
        if drive is None or getattr(drive, "is_empty", lambda: True)():
            return None
        try:
            weights = await tag_mattering(
                drive, [str(a.get("anchor") or "") for a in anchors]
            )
        except Exception as exc:
            logger.debug("[%s] anchor gating weights failed: %s", self.name, exc)
            return None
        field = {
            str(a["anchor"]): float(a.get("salience") or 0.0)
            for a in anchors
            if str(a.get("anchor") or "")
            and weights.get(str(a.get("anchor") or ""), 0.0) >= ANCHOR_GATE_MATTERING
        }
        if not field:
            return None
        # Concept-space matching (minor 46): rename realized anchors to the predicted
        # anchor they semantically *are*, so surprise measures real change, not phrasing
        # noise. This is what lets a low-string-hit-rate resident gate without flooding.
        field = await self._align_anchor_field(field)
        return {"anchors": field} if field else None

    async def _align_anchor_field(self, field: dict[str, float]) -> dict[str, float]:
        """Align realized anchor keys to the current afterimage's predicted-anchor keys by
        embedding cosine. A realized anchor within ``ANCHOR_MATCH_THRESHOLD`` of a predicted
        one is renamed to the predicted key (so exact-tag surprise downstream sees a match,
        not a rephrasing); anchors with no close prediction keep their own key (genuine
        novelty still surprises). Best-effort — on any embedder failure, return as-is.
        """
        embedder = self._embedder
        predicted = list(
            (predict(self._memory_dir).get("by_scope") or {}).get("anchors", {}).keys()
        )
        if embedder is None or not predicted:
            return field
        realized = list(field.keys())
        try:
            vecs = await embedder.embed(realized + predicted)
        except Exception as exc:
            logger.debug("[%s] anchor alignment embed failed: %s", self.name, exc)
            return field
        vmap = {t: v for t, v in zip(realized + predicted, vecs) if v}
        aligned: dict[str, float] = {}
        for r in realized:
            best_key, best_cos = r, ANCHOR_MATCH_THRESHOLD
            rv = vmap.get(r)
            if rv:
                for p in predicted:
                    pv = vmap.get(p)
                    if pv:
                        c = _cosine(rv, pv)
                        if c >= best_cos:
                            best_key, best_cos = p, c
            aligned[best_key] = max(
                aligned.get(best_key, 0.0), field[r]
            )  # merge if two realized map to one
        return aligned
