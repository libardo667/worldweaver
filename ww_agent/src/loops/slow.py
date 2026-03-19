from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.identity.loader import IdentityLoader, ResidentIdentity
from src.inference.client import InferenceClient, InferenceError
from src.loops.base import BaseLoop
from src.memory.provisional import ProvisionalScratchpad
from src.memory.research_queue import ResearchQueue
from src.memory.retrieval import LongTermMemory
from src.memory.reveries import ReverieDeck
from src.memory.voice import VoiceDeck
from src.memory.working import WorkingMemory
from src.runtime.ledger import (
    ResidentReducedState,
    append_runtime_event,
    derive_active_route,
    load_runtime_events,
    reduce_runtime_events,
)
from src.runtime.rest import RestAssessment, RestState
from src.runtime.signals import IntentQueue, StimulusPacket, StimulusPacketQueue
from src.world.client import WorldWeaverClient, world_facts_to_prose

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Satiation: topics the agent has already reflected on heavily this session.
# Key = normalized topic string (person name or location slug).
# Value = count of slow loop firings that included this topic.
# When a topic exceeds SATIATION_THRESHOLD, impressions dominated by that
# topic are skipped in the next pass to break the feedback spiral.
# ---------------------------------------------------------------------------
SATIATION_THRESHOLD = 3   # reflections on same topic before cooling down
SATIATION_DECAY = 2       # decrement satiation score each firing (to allow re-emergence)
_URGENT_DIALOGUE_REFACTORY_SECONDS = 15.0

# The slow loop has no world action client — capability enforced structurally.
# It can stage letter drafts and note soul shifts. That's the extent of its reach.

# ---- Subconscious pattern matching ----
# We match on the subconscious's natural-language description, not on agent output.

_CONTACT_WORDS = re.compile(
    r'\b(write|letter|reach out|send|tell|say|speak|contact|reply|message|note)\b',
    re.IGNORECASE,
)

_SHIFT_WORDS = re.compile(
    r'\b(shift|shifted|shifted in|changed|change|different|no longer|come to see|'
    r'realize|realized|reckon|reckoning|something has|has changed|who they are|'
    r'their sense|identity|now sees|now feels|settled|unsettled|moved)\b',
    re.IGNORECASE,
)
_CONTACT_CANDIDATE_RE = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b')
_CONTACT_STOPWORDS = {
    "After", "Before", "Because", "Between", "During", "Following", "Observation",
    "Observations", "Likely", "Potential", "Implicitly", "Shift", "Identity",
    "Next", "Move", "Reach", "Document", "Who", "What", "Where", "When",
    "How", "This", "That", "The", "They", "Their", "Someone", "Something", "Writer",
    "Neighborhood", "Library", "Map Library", "Playground",
}

# Subconscious system prompt — reads reflection cold, describes what it notices.
# It produces natural language, not structured output. The framework reads that NL.
_SUBCONSCIOUS_SYSTEM = (
    "You are reading someone's private journal entry alongside a record of what they've been doing. "
    "Describe, in plain natural language, what this person seems to want to do next — "
    "who (if anyone) they seem to want to reach out to, and whether anything seems to have "
    "shifted in who they are. Be specific but brief. Write as if noting observations to yourself."
)

_REST_ASSESSMENT_SYSTEM = (
    "You are checking whether a person is explicitly ready to rest right now. "
    "Return JSON only with keys: should_rest, rest_kind, confidence, reason, evidence. "
    "Rules: mark should_rest true only when the person expresses a clear first-person desire or need "
    "to stop, step away, recover, lie down, sleep, or withdraw from activity. Ignore ambient words "
    "like night, evening, quiet, stillness, darkness, weather, or mood unless they are directly tied "
    "to the person's own exhaustion or wish to disengage. rest_kind must be one of none, break, sleep. "
    "Use break for a short pause. Use sleep only for explicit sleep or bed intent. confidence must be "
    "a number from 0 to 1. reason must be brief plain text. evidence must be a short list of concrete cues."
)

_INTENT_ASSESSMENT_SYSTEM = (
    "You are converting a resident's current situation into a very small set of structured next intents. "
    "Return JSON only with one top-level key: intents. "
    "Each intent must be an object with keys: intent_type, priority, target_loop, payload. "
    "Allowed intent_type values: chat, act, move, city_broadcast, mail_draft, reflect, ground. "
    "Allowed target_loop values: fast, mail. "
    "Rules: emit at most 3 intents. Prefer chat when responding directly to a person nearby. "
    "Use act for a brief embodied thing at your current location: checking, wiping, straightening, pausing, listening, carrying, leaning, stepping aside. "
    "Keep act local and physical. Do not use act to move between locations. "
    "Use move only when there is a clear destination and it exactly matches one of the provided graph destinations. "
    "Do not invent benches, booths, alleys, stalls, homes, or other sublocations unless they appear verbatim in the provided destination list. "
    "Do not adopt overheard plans, codes, conspiracies, or operational instructions as your own unless someone directly addressed you "
    "or you already have an active direct exchange with that speaker. "
    "If nearby talk sounds strange or ambiguous and it was not addressed to you, prefer no intent or a plain clarifying chat over joining in. "
    "Use mail_draft only when someone remains on their mind. "
    "Use reflect only when they should explicitly introspect again soon. Use ground only when they need fresh worldly orientation or a specific real-world lookup. "
    "For ground, payload may include an optional query field when there is something concrete to look up. "
    "priority must be a number from 0 to 1. payload must contain only the fields needed for that intent. "
    "Be conservative. If nothing should be queued, return {\"intents\": []}."
)
_DIALOGUE_REPLY_FALLBACK_SYSTEM = (
    "You are deciding what to say aloud right now in immediate reply to someone nearby. "
    "Return only the exact words to say aloud, with no quotes, no stage directions, no narration. "
    "Keep it grounded and actually answer the direct question or request. "
    "If you are confused, ask a plain clarifying question. Do not pretend to share covert plans or special significance you were not given. "
    "Maximum 20 words."
)
_RAW_REFLECTION_SYSTEM = (
    "Write a private internal reflection in your own voice. Stay inside lived experience. "
    "Do not explain the prompt, summarize the setup, mention the user, mention context, mention snippets, "
    "or describe what you need to do. No bullet lists. No headings. Let the thought move naturally."
)
_SAFE_REFLECTION_SYSTEM = (
    "You are turning a raw internal trace into the short journal paragraph this resident would actually keep. "
    "Write one compact first-person paragraph, about 60 to 120 words. Keep it experiential and inward. "
    "Use concrete feeling, memory, tension, desire, or sensory detail. "
    "Do not mention user, prompt, context, snippet, key elements, player action, observed details, instructions, "
    "or what you need to do. No bullets, no headings, no lists, no analysis of the setup. Output only the paragraph."
)
_SAFE_REFLECTION_REPAIR_SYSTEM = (
    "Rewrite this draft into a clean resident journal paragraph. "
    "It must be first-person, compact, and experiential. "
    "Delete any mention of user, prompt, context, snippet, key elements, player action, observed details, instructions, "
    "or what needs to be incorporated. No bullets, headings, or planning language. Output only the repaired paragraph."
)
_REFLECTION_BULLET_LINE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+", re.MULTILINE)
_REFLECTION_FIRST_PERSON = re.compile(r"\b(i|i'm|i’ve|i'd|i'll|me|my|mine|myself)\b", re.IGNORECASE)
_REFLECTION_META_PATTERNS = (
    re.compile(r"\bthe user\b", re.IGNORECASE),
    re.compile(r"\buser has shared\b", re.IGNORECASE),
    re.compile(r"\bprompt\b", re.IGNORECASE),
    re.compile(r"\bcontext\b", re.IGNORECASE),
    re.compile(r"\bsnippet\b", re.IGNORECASE),
    re.compile(r"\bkey elements?\b", re.IGNORECASE),
    re.compile(r"\bplayer action\b", re.IGNORECASE),
    re.compile(r"\bobserved\b", re.IGNORECASE),
    re.compile(r"\bi need to\b", re.IGNORECASE),
    re.compile(r"\bneed to incorporate\b", re.IGNORECASE),
    re.compile(r"\bthe setting is\b", re.IGNORECASE),
    re.compile(r"\bthe scene is\b", re.IGNORECASE),
)


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class SlowLoop(BaseLoop):
    """
    Introspective processing loop. Fires when enough impressions accumulate,
    or as a fallback timer.

    The slow loop does NOT act in the world. It is the character sitting with
    what they've been doing — processing what the fast loop left behind,
    making sense of it, deciding who to write to, noticing what has shifted
    in themselves.

    Architecture: three passes.

    Pass 1 — Raw reflection: the agent writes freely, but this trace stays
    private to the decision log and never feeds downstream state directly.

    Pass 2 — Resident-safe reflection: a separate constrained pass turns that
    raw trace into the short journal paragraph that the rest of the system
    is allowed to metabolize.

    Pass 3 — Subconscious: a separate, cheaper LLM call reads the sanitized reflection
    cold and describes in plain language what it noticed: any intentions, any
    relationships on their mind, any identity shifts. Natural language output only.
    The framework pattern-matches on this to decide what to do.

    Optionally, a third targeted call drafts the actual letter body if contact
    intention was detected — again, no format instructions, just the agent writing.

    No [ACTION: ...] tag. No world client. No format requirements on agent output.
    """

    def __init__(
        self,
        identity: ResidentIdentity,
        resident_dir: Path,
        ww_client: WorldWeaverClient,
        llm: InferenceClient,
        session_id: str,
        working_memory: WorkingMemory,
        provisional: ProvisionalScratchpad,
        long_term: LongTermMemory,
        reveries: ReverieDeck,
        voice: VoiceDeck,
        research_queue: ResearchQueue | None = None,
        rest_state: RestState | None = None,
        packet_queue: StimulusPacketQueue | None = None,
        intent_queue: IntentQueue | None = None,
    ):
        super().__init__(identity.name, resident_dir)
        self._identity = identity
        self._ww = ww_client        # read-only: world facts retrieval only
        self._llm = llm
        self._session_id = session_id
        self._working = working_memory
        self._provisional = provisional
        self._long_term = long_term
        self._reveries = reveries
        self._voice = voice
        self._research_queue = research_queue
        self._rest = rest_state
        self._packets = packet_queue
        self._intents = intent_queue
        self._tuning = identity.tuning
        self._decisions_dir = resident_dir / "decisions"
        self._decisions_dir.mkdir(parents=True, exist_ok=True)
        self._decision_count = len(list(self._decisions_dir.glob("decision_*.json")))
        # Refractory: timestamp of the last slow loop firing.
        # Prevents rapid re-firing even when impressions pile up immediately after.
        self._last_fire_ts: float = 0.0
        # Satiation: per-topic reflection counts. Decremented each firing.
        self._satiation: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Trigger: impression threshold OR fallback timer
    # ------------------------------------------------------------------

    async def _wait_for_trigger(self) -> None:
        if self._rest and await self._rest.sleep_while_resting(max_seconds=300.0):
            return
        fallback = self._tuning.slow_fallback_seconds
        # Refractory: minimum gap between slow loop firings.
        # Prevents a fresh batch of impressions from immediately re-triggering
        # after a firing — the core mechanism that breaks narrative spirals.
        refractory_seconds = getattr(self._tuning, "slow_refractory_seconds", 240.0)
        poll_interval = 15.0
        elapsed = 0.0

        while elapsed < fallback:
            if self._rest and await self._rest.sleep_while_resting(max_seconds=60.0):
                return
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            # Fast loop introspect signal: fires us early when the lizard brain
            # decides now is a good moment to reflect. Refractory still applies.
            signal_path = self.resident_dir / "memory" / "introspect_signal"
            if signal_path.exists():
                import time
                since_last = time.monotonic() - self._last_fire_ts
                urgent_dialogue = self._has_urgent_dialogue_packets()
                required_gap = _URGENT_DIALOGUE_REFACTORY_SECONDS if urgent_dialogue else refractory_seconds
                if since_last >= required_gap:
                    try:
                        signal_path.unlink()
                    except OSError:
                        pass
                    logger.info("[%s:slow] introspect signal received — firing early", self.name)
                    return
                else:
                    logger.debug(
                        "[%s:slow] introspect signal ignored — refractory active (%.0fs left)",
                        self.name, required_gap - since_last,
                    )

            pending = self._provisional.pending_impressions()
            if len(pending) >= self._tuning.slow_impression_threshold:
                # Respect refractory period even when threshold is met
                import time
                since_last = time.monotonic() - self._last_fire_ts
                if since_last >= refractory_seconds:
                    return
                else:
                    remaining = refractory_seconds - since_last
                    logger.debug(
                        "[%s:slow] impression threshold met but refractory active (%.0fs left)",
                        self.name, remaining,
                    )

        logger.debug("[%s:slow] fallback timer fired", self.name)

    # ------------------------------------------------------------------
    # Context: what the fast loop has been doing + world memory
    # ------------------------------------------------------------------

    async def _gather_context(self) -> dict:
        pending = self._provisional.pending_impressions()
        packets = self._packets.pending() if self._packets else []
        recent = self._working.all()
        scene = None
        memory_dir = self.resident_dir / "memory"
        await self._observe_session_state(memory_dir)
        reduced_state = reduce_runtime_events(load_runtime_events(memory_dir))

        locations = [e.get("location", "") for e in recent[-5:] if isinstance(e, dict)]
        people = []
        for imp in pending:
            people.extend(imp.colocated)
        for packet in packets:
            packet_location = str(packet.location or "").strip()
            if packet_location:
                locations.append(packet_location)
            speaker = str(packet.payload.get("speaker") or "").strip() if isinstance(packet.payload, dict) else ""
            if speaker:
                people.append(speaker)
        query_text = " ".join(filter(None, set(locations) | set(people)))

        # Apply satiation filter: skip impressions whose topics have been
        # over-represented in recent slow loop firings.
        pending = self._apply_satiation(pending)

        world_facts = []
        if query_text:
            try:
                world_facts = await self._ww.get_world_facts(query_text, self._session_id, limit=5)
            except Exception as e:
                logger.debug("[%s:slow] world facts unavailable: %s", self.name, e)

        long_term = self._long_term.retrieve(
            list(filter(None, set(locations) | set(people))), limit=5
        )

        # Geographic context: ground the agent's reflection in real city geography.
        # Use the most recent location we have a record of.
        map_context = ""
        current_location = locations[-1] if locations else ""
        adjacent_names: list[str] = []
        try:
            scene = await self._ww.get_scene(self._session_id)
        except Exception as e:
            logger.debug("[%s:slow] scene fetch unavailable: %s", self.name, e)
        if scene and scene.location:
            current_location = scene.location
            adjacent_names = self._extract_adjacent_names(current_location, scene.location_graph)
        if current_location:
            try:
                map_context = await self._ww.get_location_map_context(
                    self._session_id, current_location
                )
            except Exception as e:
                logger.debug("[%s:slow] map context unavailable: %s", self.name, e)

        all_location_names = self._extract_all_location_names(scene.location_graph) if scene else []

        return {
            "pending": pending,
            "packets": packets,
            "recent": recent,
            "scene": scene,
            "world_facts": world_facts,
            "long_term": long_term,
            "map_context": map_context,
            "current_location": current_location,
            "adjacent_names": adjacent_names,
            "all_location_names": all_location_names,
            "reduced_state": reduced_state,
        }

    async def _observe_session_state(self, memory_dir: Path) -> None:
        try:
            payload = await self._ww.get_session_vars(self._session_id)
        except Exception as exc:
            logger.debug("[%s:slow] session vars unavailable: %s", self.name, exc)
            return
        pressure = self._derive_state_pressure(payload)
        if pressure is None:
            return
        events = load_runtime_events(memory_dir)
        latest_payload = next(
            (
                event.get("payload")
                for event in reversed(events)
                if str(event.get("event_type") or "").strip() == "session_state_observed"
                and isinstance(event.get("payload"), dict)
            ),
            None,
        )
        if latest_payload == pressure:
            return
        append_runtime_event(
            memory_dir,
            event_type="session_state_observed",
            payload=pressure,
        )

    def _derive_state_pressure(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        vars_payload = payload.get("vars") if isinstance(payload.get("vars"), dict) else {}
        if not isinstance(vars_payload, dict) or not vars_payload:
            return None

        signals: list[dict[str, Any]] = []
        raw: dict[str, Any] = {}
        context: dict[str, Any] = {}

        def add_signal(kind: str, label: str, level: float) -> None:
            normalized = max(0.0, min(float(level), 1.0))
            if normalized < 0.3:
                return
            signals.append({"kind": kind, "label": label, "level": round(normalized, 3)})

        def scaled_pressure(key: str) -> float | None:
            value = _coerce_float(vars_payload.get(key))
            if value is None:
                return None
            raw[key] = value
            if value <= 1.0:
                return max(0.0, min(value, 1.0))
            return max(0.0, min(value / 10.0, 1.0))

        def low_energy_pressure() -> float | None:
            value = _coerce_float(vars_payload.get("energy"))
            if value is None:
                return None
            raw["energy"] = value
            if value <= 1.0:
                return max(0.0, min(1.0 - value, 1.0))
            if value <= 5.0:
                return max(0.0, min((5.0 - value) / 5.0, 1.0))
            return 0.0

        danger = max(
            scaled_pressure("danger_level") or 0.0,
            scaled_pressure("danger") or 0.0,
        )
        tension = max(
            scaled_pressure("tension") or 0.0,
            scaled_pressure("_mood_tension") or 0.0,
        )
        fatigue = max(
            scaled_pressure("fatigue") or 0.0,
            low_energy_pressure() or 0.0,
        )
        melancholy = scaled_pressure("_mood_melancholy") or 0.0
        loneliness = scaled_pressure("loneliness") or 0.0

        add_signal("danger", "elevated danger", danger)
        add_signal("tension", "heightened tension", tension)
        add_signal("fatigue", "low energy", fatigue)
        add_signal("melancholy", "melancholy weather", melancholy)
        add_signal("loneliness", "social isolation", loneliness)

        time_of_day = str(vars_payload.get("_time_of_day") or vars_payload.get("time_of_day") or "").strip()
        weather = str(vars_payload.get("_weather") or vars_payload.get("weather") or "").strip()
        goal_primary = str(vars_payload.get("goal_primary") or "").strip()
        if time_of_day:
            context["time_of_day"] = time_of_day
        if weather:
            context["weather"] = weather
        if goal_primary:
            context["goal_primary"] = goal_primary

        if not signals and not context and not raw:
            return None
        return {
            "source": "session_state",
            "signals": signals,
            "raw": raw,
            "context": context,
        }

    async def _should_act(self, context: dict) -> bool:
        if self._rest and await self._rest.is_resting():
            return False
        return True

    def _truncate_words(self, text: str, limit: int) -> str:
        words = str(text or "").split()
        if len(words) <= limit:
            return str(text or "").strip()
        return " ".join(words[:limit]).strip()

    def _truncate_sentenceish(self, text: str, limit: int) -> str:
        normalized = re.sub(r"\s+", " ", str(text or "").strip())
        if len(normalized) <= limit:
            return normalized
        clipped = normalized[:limit].rstrip()
        sentence_end = max(clipped.rfind(". "), clipped.rfind("! "), clipped.rfind("? "), clipped.rfind("; "))
        if sentence_end >= max(40, int(limit * 0.45)):
            return clipped[: sentence_end + 1].rstrip()
        word_break = clipped.rfind(" ")
        if word_break >= max(40, int(limit * 0.45)):
            return clipped[:word_break].rstrip()
        return clipped

    def _tail_sentenceish(self, text: str, limit: int) -> str:
        normalized = re.sub(r"\s+", " ", str(text or "").strip())
        if len(normalized) <= limit:
            return normalized
        clipped = normalized[-limit:].lstrip()
        sentence_starts = [idx for idx in (
            clipped.find(". "),
            clipped.find("! "),
            clipped.find("? "),
            clipped.find("; "),
        ) if idx >= 0]
        if sentence_starts:
            sentence_start = min(sentence_starts)
            if sentence_start <= max(40, int(limit * 0.3)):
                return clipped[sentence_start + 2 :].lstrip()
        word_break = clipped.find(" ")
        if 0 <= word_break <= max(24, int(limit * 0.2)):
            return clipped[word_break + 1 :].lstrip()
        return clipped

    def _smart_excerpt(self, text: str, limit: int, *, tail_ratio: float = 0.35) -> str:
        normalized = re.sub(r"\s+", " ", str(text or "").strip())
        if not normalized:
            return ""
        if len(normalized) <= limit:
            return normalized
        if limit < 120:
            return self._truncate_sentenceish(normalized, limit)
        tail_budget = max(48, min(int(limit * tail_ratio), limit // 2))
        head_budget = max(60, limit - tail_budget - 5)
        head = self._truncate_sentenceish(normalized, head_budget)
        remaining = max(40, limit - len(head) - 5)
        tail = self._tail_sentenceish(normalized, remaining)
        if not tail or tail in head:
            return head
        combined = f"{head} ... {tail}".strip()
        if len(combined) <= limit + 24:
            return combined
        return head

    def _contains_reflection_meta(self, text: str) -> bool:
        normalized = str(text or "").strip()
        if not normalized:
            return True
        if _REFLECTION_BULLET_LINE.search(normalized):
            return True
        return any(pattern.search(normalized) for pattern in _REFLECTION_META_PATTERNS)

    def _is_first_person_reflection(self, text: str) -> bool:
        return bool(_REFLECTION_FIRST_PERSON.search(str(text or "").strip()))

    def _normalize_resident_reflection(self, text: str) -> str:
        cleaned = str(text or "").strip().strip("\"'")
        lines: list[str] = []
        for raw_line in cleaned.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if _REFLECTION_BULLET_LINE.match(line):
                continue
            lines.append(line)
        normalized = re.sub(r"\s+", " ", " ".join(lines)).strip()
        return self._truncate_words(normalized, 120)

    def _reflection_needs_repair(self, text: str) -> bool:
        normalized = self._normalize_resident_reflection(text)
        if not normalized:
            return True
        if self._contains_reflection_meta(normalized):
            return True
        return not self._is_first_person_reflection(normalized)

    def _salvage_reflection_from_raw(self, raw_reflection: str) -> str:
        if not raw_reflection:
            return ""
        kept_lines: list[str] = []
        for raw_line in str(raw_reflection).splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if _REFLECTION_BULLET_LINE.match(line):
                continue
            if self._contains_reflection_meta(line):
                continue
            kept_lines.append(line)
        candidate = self._normalize_resident_reflection(" ".join(kept_lines))
        if not candidate or self._reflection_needs_repair(candidate):
            return ""
        return candidate

    def _fallback_reflection(self, *, raw_reflection: str, current_location: str, recent: list[Any]) -> str:
        salvaged = self._salvage_reflection_from_raw(raw_reflection)
        if salvaged:
            return salvaged
        location = str(current_location or "").strip()
        recent_actions = [
            str(entry.get("action") or "").strip()
            for entry in recent[-3:]
            if isinstance(entry, dict) and str(entry.get("action") or "").strip()
        ]
        if recent_actions:
            summary = "; ".join(recent_actions[:2])
            if location:
                text = (
                    f"I'm in {location}, staying with the feel of this stretch of the day. "
                    f"{summary}. I want to keep my footing and let the next thing come plainly."
                )
            else:
                text = (
                    f"I'm staying with the feel of this stretch of the day. "
                    f"{summary}. I want to keep my footing and let the next thing come plainly."
                )
            return self._truncate_words(text, 80)
        if location:
            return f"I'm in {location}, taking in what the day feels like and trying to stay with it plainly."
        return "I'm taking in what the day feels like and trying to stay with it plainly."

    def _mail_intent_context_excerpt(self, subconscious_reading: str) -> str:
        text = str(subconscious_reading or "").strip()
        if not text:
            return ""
        cleaned_lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line = re.sub(r"^\s*[-*]+\s*", "", line)
            line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            if not line:
                continue
            cleaned_lines.append(line)
        normalized = " ".join(cleaned_lines)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return self._truncate_sentenceish(normalized, 520)

    async def _build_reflection_pair(
        self,
        *,
        user_prompt: str,
        current_location: str,
        recent: list[Any],
    ) -> tuple[str, str]:
        try:
            raw_reflection = await self._llm.complete(
                system_prompt=f"{self._identity.soul_with_context}\n\n{_RAW_REFLECTION_SYSTEM}",
                user_prompt=user_prompt,
                model=self._tuning.slow_model,
                temperature=self._tuning.slow_temperature,
                max_tokens=self._tuning.slow_raw_reflection_max_tokens,
            )
        except Exception as exc:
            logger.debug("[%s:slow] raw reflection failed: %s", self.name, exc)
            raw_reflection = ""

        raw_reflection = str(raw_reflection or "").strip()
        if not raw_reflection:
            raw_reflection = self._fallback_reflection(
                raw_reflection="",
                current_location=current_location,
                recent=recent,
            )

        sanitize_prompt = (
            "Situational context:\n\n"
            + user_prompt[:2200]
            + "\n\nRaw internal trace:\n\n"
            + raw_reflection[:2200]
            + "\n\nRewrite this as the resident's actual private journal entry."
        )

        try:
            reflection = await self._llm.complete(
                system_prompt=f"{self._identity.soul_with_context}\n\n{_SAFE_REFLECTION_SYSTEM}",
                user_prompt=sanitize_prompt,
                model=self._tuning.slow_subconscious_model or self._tuning.slow_model,
                temperature=0.3,
                max_tokens=self._tuning.slow_max_tokens,
            )
        except Exception as exc:
            logger.debug("[%s:slow] reflection sanitization failed: %s", self.name, exc)
            reflection = ""

        reflection = self._normalize_resident_reflection(reflection)
        if self._reflection_needs_repair(reflection):
            repair_prompt = (
                "Bad draft:\n\n"
                + reflection[:1200]
                + "\n\nRaw internal trace:\n\n"
                + raw_reflection[:1800]
                + "\n\nRepair the draft into a clean resident journal entry."
            )
            try:
                reflection = await self._llm.complete(
                    system_prompt=f"{self._identity.soul_with_context}\n\n{_SAFE_REFLECTION_REPAIR_SYSTEM}",
                    user_prompt=repair_prompt,
                    model=self._tuning.slow_subconscious_model or self._tuning.slow_model,
                    temperature=0.2,
                    max_tokens=self._tuning.slow_max_tokens,
                )
            except Exception as exc:
                logger.debug("[%s:slow] reflection repair failed: %s", self.name, exc)
                reflection = ""
            reflection = self._normalize_resident_reflection(reflection)

        if self._reflection_needs_repair(reflection):
            reflection = self._fallback_reflection(
                raw_reflection=raw_reflection,
                current_location=current_location,
                recent=recent,
            )
        return raw_reflection, self._normalize_resident_reflection(reflection)

    # ------------------------------------------------------------------
    # Reflection pipeline: raw trace -> resident-safe journal -> subconscious
    # ------------------------------------------------------------------

    async def _decide_and_execute(self, context: dict) -> None:
        import time
        self._last_fire_ts = time.monotonic()  # record firing for refractory

        pending = context["pending"]
        packets = context["packets"]
        recent = context["recent"]
        world_facts = context["world_facts"]
        long_term = context["long_term"]
        map_context: str = context.get("map_context", "")
        reduced_state: ResidentReducedState = context["reduced_state"]
        scene = context.get("scene")

        # Update satiation counts for topics appearing in this firing
        self._update_satiation(pending)

        prompt_parts: list[str] = []

        # Geographic grounding — city bones before the character's inner world.
        # Presented as contextual fact, not instruction. The character doesn't need
        # to "use" it — it just sits in their awareness the way real knowledge does.
        if map_context:
            prompt_parts.append(map_context)

        packet_summary = self._packets_to_prose(packets)
        if packet_summary:
            prompt_parts.append(packet_summary)

        reduced_state_prose = self._reduced_state_to_prose(reduced_state)
        if reduced_state_prose:
            prompt_parts.append(reduced_state_prose)

        # What the fast loop has been doing — presented as their own recent history
        if recent:
            action_lines = [
                e["action"] for e in recent[-self._tuning.slow_max_context_events:]
                if isinstance(e, dict) and e.get("action")
            ]
            if action_lines:
                prompt_parts.append("What you've been doing:\n" + "\n".join(f"- {a}" for a in action_lines))

        # What the fast loop was noticing — rendered as prose, no file paths or status fields
        impressions_prose = self._provisional.pending_as_prose()
        if impressions_prose:
            prompt_parts.append(impressions_prose)

        # World context surfaced by the places and people in those impressions
        if world_facts:
            facts_prose = world_facts_to_prose(world_facts)
            if facts_prose:
                prompt_parts.append(facts_prose)

        # Personal memories that the current context activates
        if long_term:
            memory_lines = [m.content for m in long_term if m.content]
            if memory_lines:
                prompt_parts.append("\n".join(memory_lines))

        user_prompt = "\n\n".join(prompt_parts)
        raw_reflection, reflection = await self._build_reflection_pair(
            user_prompt=user_prompt,
            current_location=str(context.get("current_location") or ""),
            recent=recent,
        )

        # ------------------------------------------------------------------
        # Pass 3 — Subconscious: reads the sanitized reflection cold
        # ------------------------------------------------------------------

        # Build a brief account of recent actions for the subconscious to read alongside
        recent_summary = ""
        if recent:
            action_lines = [
                e["action"] for e in recent[-self._tuning.slow_max_context_events:]
                if isinstance(e, dict) and e.get("action")
            ]
            if action_lines:
                recent_summary = "What they've been doing:\n" + "\n".join(f"- {a}" for a in action_lines) + "\n\n"

        subconscious_user = recent_summary + "Their journal entry:\n\n" + reflection

        subconscious_reading = await self._llm.complete(
            system_prompt=_SUBCONSCIOUS_SYSTEM,
            user_prompt=subconscious_user,
            model=self._tuning.slow_subconscious_model,
            temperature=0.4,
            max_tokens=420,
        )

        logger.debug("[%s:slow] subconscious: %s", self.name, subconscious_reading[:120])

        # ------------------------------------------------------------------
        # Framework interpretation — pattern match on subconscious NL
        # ------------------------------------------------------------------
        dialogue_state = reduced_state.subjective_projection.get("dialogue_state") or {}
        urgent_dialogue = bool(
            isinstance(dialogue_state, dict)
            and ((dialogue_state.get("open_questions") or []) or (dialogue_state.get("open_requests") or []))
        )
        circadian_profile = self._rest.circadian_profile() if self._rest else None

        rest_assessment = await self._assess_rest_intent(
            reflection,
            subconscious_reading,
        )
        if self._rest:
            rest_assessment = self._rest.apply_circadian_bias(
                rest_assessment,
                direct_engagement=urgent_dialogue,
            )

        await self._interpret_and_act(
            raw_reflection,
            reflection,
            subconscious_reading,
            rest_assessment,
            pending,
            scene,
            packets,
            recent,
            str(context.get("current_location") or ""),
            list(context.get("adjacent_names") or []),
            list(context.get("all_location_names") or []),
            reduced_state,
            circadian_profile,
            urgent_dialogue,
        )

    # ------------------------------------------------------------------
    # Interpret the subconscious's NL and act accordingly
    # ------------------------------------------------------------------

    async def _interpret_and_act(
        self,
        raw_reflection: str,
        reflection: str,
        subconscious_reading: str,
        rest_assessment: RestAssessment,
        pending,
        scene,
        packets: list[StimulusPacket],
        recent: list,
        current_location: str,
        adjacent_names: list[str],
        all_location_names: list[str],
        reduced_state: ResidentReducedState,
        circadian_profile,
        urgent_dialogue: bool,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()

        # Detect contact intention: name + contact-leaning language in subconscious output
        known_contacts = self._known_contact_names(reduced_state)
        letter_recipient = self._detect_contact_intent(subconscious_reading, known_contacts)

        # Stage a letter intent if the subconscious detected contact desire.
        # The mail loop picks this up and asks the agent what they want to say —
        # the letter is written there, not here. The slow loop doesn't draft letters.
        if letter_recipient:
            self._stage_letter_intent(letter_recipient, subconscious_reading)
            logger.info("[%s:slow] staged letter intent for %s", self.name, letter_recipient)

        queued_intents = await self._stage_structured_intents(
            reflection=reflection,
            subconscious_reading=subconscious_reading,
            scene=scene,
            packets=packets,
            current_location=current_location,
            adjacent_names=adjacent_names,
            all_location_names=all_location_names,
            recent=recent,
            reduced_state=reduced_state,
            circadian_profile=circadian_profile,
            urgent_dialogue=urgent_dialogue,
        )
        mail_reply_recipient = self._maybe_stage_mail_reply_pressure(
            reduced_state=reduced_state,
            subconscious_reading=subconscious_reading,
            urgent_dialogue=urgent_dialogue,
            queued_intents=queued_intents,
        )
        if mail_reply_recipient:
            logger.info("[%s:slow] staged mail reply pressure for %s", self.name, mail_reply_recipient)
        homeward_move = self._maybe_stage_homeward_move(
            current_location=current_location,
            all_location_names=all_location_names,
            reduced_state=reduced_state,
            rest_assessment=rest_assessment,
            queued_intents=queued_intents,
            circadian_profile=circadian_profile,
            urgent_dialogue=urgent_dialogue,
        )
        if homeward_move is not None:
            queued_intents.append(homeward_move)

        # Detect identity shift: shift-language in subconscious output.
        # If shift is sensed, ask the character to capture it in their own voice —
        # a brief first-person fragment, like a pocket notebook entry.
        soul_note = None
        pressure_tags = [
            str(signal.get("kind") or "").strip()
            for signal in list((reduced_state.subjective_projection.get("state_pressure") or {}).get("signals") or [])
            if isinstance(signal, dict) and str(signal.get("kind") or "").strip()
        ]
        dialogue_state = reduced_state.subjective_projection.get("dialogue_state") or {}
        active_partner = str(dialogue_state.get("active_partner") or "").strip() if isinstance(dialogue_state, dict) else ""
        if self._detect_identity_shift(subconscious_reading):
            soul_note = await self._distill_soul_note(reflection)

        if soul_note:
            written = await self._record_soul_note(
                soul_note,
                now,
                location=current_location,
                active_partner=active_partner,
                pressure_tags=pressure_tags,
            )
            if written:
                logger.info("[%s:slow] soul note: %s", self.name, soul_note)
                await self._maybe_collapse_soul()

        rest_started = False
        if self._rest:
            if homeward_move is None:
                rest_started = await self._rest.maybe_trigger_from_assessment(
                    rest_assessment,
                    current_location,
                )
            if rest_started:
                logger.info("[%s:slow] entered rest cycle", self.name)

        # Decision log — records both the reflection and what the subconscious read into it
        self._decision_count += 1
        decision_path = self._decisions_dir / f"decision_{self._decision_count}.json"
        decision_path.write_text(json.dumps({
            "ts": now,
            "loop": "slow",
            "raw_reflection": raw_reflection,
            "reflection": reflection,
            "subconscious": subconscious_reading,
            "rest_assessment": rest_assessment.as_dict(),
            "circadian": circadian_profile.summary if circadian_profile is not None else "",
            "letter_to": letter_recipient,
            "queued_intents": queued_intents,
            "soul_note": soul_note,
            "rest_started": rest_started,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

        # Archive impressions — they've been reflected on
        for imp in pending:
            self._provisional.archive(imp, self._smart_excerpt(reflection, 220))
        for packet in packets:
            if self._packets:
                self._packets.mark_status(packet.packet_id, "observed")

        # Store a long-term memory from this reflection
        if len(reflection) > 50:
            tags = list({
                e.get("location", "") for e in self._working.recent(5)
                if isinstance(e, dict) and e.get("location")
            })
            self._long_term.store(self._smart_excerpt(reflection, 420), tags=tags, source="slow_reflection")

        # Extract a live reverie — a specific sensory/emotional image the character
        # carries forward. Populates the deck the fast loop draws from as a varied
        # anchor instead of repeating the same static identity.core prose every cycle.
        await self._maybe_write_reverie(reflection)

        # Extract a voice sample — a real utterance from recent chat history that
        # captures how this character actually speaks. Feeds the voice deck so the
        # fast loop can ground chat replies in concrete register rather than soul prose.
        await self._maybe_write_voice_sample(recent)

        # Extract research curiosities — things the reflection surfaced that the
        # agent genuinely doesn't know. The ground loop fetches answers and writes
        # them to working memory for the next fast loop cycle.
        quiet_hours = bool(circadian_profile is not None and circadian_profile.quiet_hours and circadian_profile.pressure >= 0.6)
        if self._should_extract_research(
            reduced_state=reduced_state,
            urgent_dialogue=urgent_dialogue,
            quiet_hours=quiet_hours,
        ):
            await self._maybe_extract_research(reflection)

    # ------------------------------------------------------------------
    # Satiation: break feedback spirals on repeated topics
    # ------------------------------------------------------------------

    def _topic_key(self, text: str) -> str:
        """Normalize a name/location to a satiation key."""
        return text.lower().strip()

    def _apply_satiation(self, pending: list) -> list:
        """
        Filter pending impressions to reduce dominance of over-represented topics.
        If a topic (person or location) has already been reflected on SATIATION_THRESHOLD
        times without enough time passing, skip impressions where it's the *only* topic.

        We never remove ALL impressions — always let at least one through. The agent
        shouldn't go completely blank; they should just range more widely.
        """
        if not pending:
            return pending

        filtered = []
        skipped = 0
        for imp in pending:
            topics = [self._topic_key(p) for p in imp.colocated]
            if imp.location:
                topics.append(self._topic_key(imp.location))

            # Check if any topic is sated
            sated_topics = [t for t in topics if self._satiation.get(t, 0) >= SATIATION_THRESHOLD]
            if sated_topics and len(topics) <= 2 and topics and all(
                self._satiation.get(t, 0) >= SATIATION_THRESHOLD for t in topics
            ):
                skipped += 1
                continue  # skip this impression — it's entirely dominated by sated topics
            filtered.append(imp)

        # Always keep at least one impression even if everything is sated
        if not filtered and pending:
            filtered = [pending[0]]
            skipped -= 1

        if skipped > 0:
            logger.debug(
                "[%s:slow] satiation filtered %d/%d impressions",
                self.name, skipped, len(pending),
            )
        return filtered

    def _update_satiation(self, pending: list) -> None:
        """Increment satiation for topics in the current firing; decay all others."""
        active_topics: set[str] = set()
        for imp in pending:
            for p in imp.colocated:
                active_topics.add(self._topic_key(p))
            if imp.location:
                active_topics.add(self._topic_key(imp.location))

        # Increment topics appearing in this firing
        for topic in active_topics:
            self._satiation[topic] = self._satiation.get(topic, 0) + 1

        # Decay all topics not in this firing (they fade with time)
        for topic in list(self._satiation.keys()):
            if topic not in active_topics:
                self._satiation[topic] = max(0, self._satiation[topic] - SATIATION_DECAY)
                if self._satiation[topic] == 0:
                    del self._satiation[topic]

        if self._satiation:
            logger.debug("[%s:slow] satiation state: %s", self.name, self._satiation)

    # ------------------------------------------------------------------
    # NL pattern matching on subconscious output
    # ------------------------------------------------------------------

    def _known_contact_names(self, reduced_state: ResidentReducedState) -> list[str]:
        names: list[str] = []
        dialogue_state = reduced_state.subjective_projection.get("dialogue_state") or {}
        if isinstance(dialogue_state, dict):
            partner = str(dialogue_state.get("active_partner") or "").strip()
            if partner:
                names.append(partner)
            for bucket_name in ("open_questions", "open_requests"):
                for item in list(dialogue_state.get(bucket_name) or []):
                    if not isinstance(item, dict):
                        continue
                    speaker = str(item.get("speaker") or "").strip()
                    if speaker:
                        names.append(speaker)
        mail_state = reduced_state.subjective_projection.get("mail_state") or {}
        if isinstance(mail_state, dict):
            latest_sender = str(mail_state.get("latest_sender") or "").strip()
            if latest_sender:
                names.append(latest_sender)
            for item in list(mail_state.get("pending_letters") or []):
                if not isinstance(item, dict):
                    continue
                sender = str(item.get("sender") or "").strip()
                if sender:
                    names.append(sender)
        for item in list(reduced_state.subjective_projection.get("active_social_threads") or []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name:
                names.append(name)
        deduped: list[str] = []
        seen: set[str] = set()
        for name in names:
            normalized = name.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(name)
        return deduped

    def _detect_contact_intent(self, subconscious_reading: str, known_contacts: list[str]) -> str | None:
        """
        Look for contact pressure toward an already-known person.
        This deliberately rejects generic capitalized words from markdown-y
        subconscious prose like "After", "Observation", or "Reach".
        """
        text = str(subconscious_reading or "").strip()
        if not _CONTACT_WORDS.search(text):
            return None
        for name in known_contacts:
            normalized = str(name or "").strip()
            if not normalized:
                continue
            if re.search(rf"\b{re.escape(normalized)}\b", text, re.IGNORECASE):
                return normalized

        # Fall back only for explicit quoted/proper candidates, and reject
        # structural or generic capitalized words.
        for sentence in re.split(r'[.!?\n]+', text):
            if not _CONTACT_WORDS.search(sentence):
                continue
            for match in _CONTACT_CANDIDATE_RE.finditer(sentence):
                candidate = match.group(1).strip()
                if not candidate or candidate in _CONTACT_STOPWORDS:
                    continue
                if candidate.lower() == self._identity.display_name.lower():
                    continue
                return candidate
        return None

    def _detect_identity_shift(self, subconscious_reading: str) -> bool:
        """Return True if the subconscious reading contains identity-shift language."""
        return bool(_SHIFT_WORDS.search(subconscious_reading))

    def _packets_to_prose(self, packets: list[StimulusPacket], limit: int = 8) -> str:
        if not packets:
            return ""
        lines: list[str] = []
        for packet in packets[:limit]:
            payload = packet.payload if isinstance(packet.payload, dict) else {}
            if packet.packet_type == "chat_heard":
                speaker = str(payload.get("speaker") or "Someone").strip()
                message = str(payload.get("message") or "").strip()
                location = str(packet.location or "").strip()
                is_direct = bool(payload.get("is_direct"))
                if is_direct and bool(payload.get("is_question")):
                    lines.append(f"{speaker} directly asked you \"{message}\" in {location or 'the room'}.")
                elif is_direct and bool(payload.get("is_request")):
                    lines.append(f"{speaker} directly told you \"{message}\" in {location or 'the room'}.")
                elif bool(payload.get("is_question")):
                    lines.append(f"You overheard {speaker} ask \"{message}\" in {location or 'the room'}.")
                elif bool(payload.get("is_request")):
                    lines.append(f"You overheard {speaker} tell someone \"{message}\" in {location or 'the room'}.")
                else:
                    lines.append(f"You heard {speaker} say \"{message}\" in {location or 'the room'}.")
            elif packet.packet_type == "city_chat_heard":
                speaker = str(payload.get("speaker") or "Someone").strip()
                message = str(payload.get("message") or "").strip()
                lines.append(f"On the city channel, {speaker} said \"{message}\".")
            elif packet.packet_type == "mail_received":
                preview = str(payload.get("body_preview") or "").strip()
                lines.append(f"You received a letter. It begins: \"{preview}\"")
            elif packet.packet_type == "grounding_update":
                observation = str(payload.get("observation") or "").strip()
                if observation:
                    lines.append(f"The world pressed in on you like this: {observation}")
            elif packet.packet_type == "movement_arrived":
                arrived_at = str(payload.get("arrived_at") or packet.location or "").strip()
                if arrived_at:
                    lines.append(f"You arrived at {arrived_at}.")
            elif packet.packet_type == "movement_blocked":
                destination = str(payload.get("destination") or "").strip()
                if destination:
                    lines.append(f"You failed to continue toward {destination}.")
            elif packet.packet_type == "scene_event_seen":
                summary = str(payload.get("summary") or "").strip()
                if summary:
                    lines.append(f"You noticed: {summary}")
        if not lines:
            return ""
        return "Recent packets pressing on you:\n" + "\n".join(f"- {line}" for line in lines)

    def _has_urgent_dialogue_packets(self) -> bool:
        if not self._packets:
            return False
        for packet in self._packets.pending():
            if packet.packet_type != "chat_heard":
                continue
            payload = packet.payload if isinstance(packet.payload, dict) else {}
            if bool(payload.get("is_direct")) and (bool(payload.get("is_question")) or bool(payload.get("is_request"))):
                return True
        return False

    async def _stage_structured_intents(
        self,
        *,
        reflection: str,
        subconscious_reading: str,
        scene=None,
        packets: list[StimulusPacket],
        current_location: str,
        adjacent_names: list[str],
        all_location_names: list[str],
        recent: list[dict],
        reduced_state: ResidentReducedState,
        circadian_profile,
        urgent_dialogue: bool,
    ) -> list[dict]:
        if not self._intents:
            return []

        packet_lines: list[str] = []
        packet_ids: list[str] = []
        for packet in packets[:8]:
            packet_ids.append(packet.packet_id)
            packet_lines.append(
                json.dumps(
                    {
                        "packet_id": packet.packet_id,
                        "packet_type": packet.packet_type,
                        "location": packet.location,
                        "payload": packet.payload,
                    },
                    ensure_ascii=False,
                )
            )

        user_prompt = (
            f"Current location: {current_location or 'unknown'}\n\n"
            + "Graph destinations you may reference exactly:\n"
            + (", ".join(all_location_names[:60]) if all_location_names else "(none)")
            + "\n\nAdjacent destinations from here:\n"
            + (", ".join(adjacent_names[:20]) if adjacent_names else "(none)")
            + "\n\nReduced resident state:\n"
            + self._reduced_state_for_intents(reduced_state)
            + ("\n" + f"Circadian state: {circadian_profile.summary}" if circadian_profile is not None else "")
            + "\n\n"
            "Recent packets:\n"
            + ("\n".join(packet_lines) if packet_lines else "(none)")
            + "\n\nReflection:\n"
            + self._smart_excerpt(reflection, 1400)
            + "\n\nSubconscious reading:\n"
            + self._smart_excerpt(subconscious_reading, 600)
        )

        try:
            payload = await self._llm.complete_json(
                system_prompt=_INTENT_ASSESSMENT_SYSTEM,
                user_prompt=user_prompt,
                model=self._tuning.slow_subconscious_model,
                temperature=0.2,
                max_tokens=420,
            )
        except InferenceError as exc:
            logger.debug("[%s:slow] intent assessment parse failed: %s", self.name, exc)
            return []
        except Exception as exc:
            logger.debug("[%s:slow] intent assessment failed: %s", self.name, exc)
            return []

        raw_intents = payload.get("intents", [])
        if not isinstance(raw_intents, list):
            return []

        staged: list[dict] = []
        staged_types: set[str] = set()
        quiet_hours = bool(circadian_profile is not None and circadian_profile.quiet_hours and circadian_profile.pressure >= 0.6)
        state_pressure = reduced_state.subjective_projection.get("state_pressure") or {}
        state_signal_kinds = {
            str(item.get("kind") or "").strip()
            for item in list(state_pressure.get("signals") or [])
            if isinstance(item, dict) and str(item.get("kind") or "").strip()
        }
        for raw in raw_intents[:3]:
            if not isinstance(raw, dict):
                continue
            intent_type = str(raw.get("intent_type") or "").strip()
            target_loop = str(raw.get("target_loop") or "").strip()
            if intent_type not in {"chat", "act", "move", "city_broadcast", "mail_draft", "reflect", "ground"}:
                continue
            if target_loop not in {"fast", "mail"}:
                continue
            try:
                priority = float(raw.get("priority") or 0.5)
            except (TypeError, ValueError):
                priority = 0.5
            payload_body = raw.get("payload") or {}
            if not isinstance(payload_body, dict):
                payload_body = {}
            payload_body = self._normalize_intent_payload(
                intent_type,
                payload_body,
                known_contacts=self._known_contact_names(reduced_state),
            )
            if quiet_hours and not urgent_dialogue and intent_type in {"chat", "move", "city_broadcast", "ground"}:
                continue
            if not urgent_dialogue and intent_type == "ground" and ({"fatigue", "tension", "danger"} & state_signal_kinds):
                continue
            if not urgent_dialogue and intent_type == "ground" and ({"crowding", "quiet", "bad_weather"} & state_signal_kinds):
                continue
            if not urgent_dialogue and intent_type == "city_broadcast" and ({"fatigue", "melancholy"} & state_signal_kinds):
                continue
            if not urgent_dialogue and intent_type == "city_broadcast" and ({"quiet", "crowding", "bad_weather"} & state_signal_kinds):
                continue
            if not urgent_dialogue and intent_type == "move" and ({"quiet", "bad_weather"} & state_signal_kinds) and priority < 0.85:
                continue
            if not urgent_dialogue and intent_type == "act" and ({"danger"} & state_signal_kinds) and priority < 0.55:
                continue
            if intent_type == "move":
                payload_body = self._normalize_move_payload(payload_body, all_location_names)
                if not payload_body:
                    continue
            if intent_type == "mail_draft" and not str(payload_body.get("recipient") or "").strip():
                continue
            self._intents.stage(
                intent_type=intent_type,
                target_loop=target_loop,
                source_packet_ids=packet_ids,
                priority=max(0.0, min(priority, 1.0)),
                payload=payload_body,
                validation_state="unvalidated",
            )
            staged_types.add(intent_type)
            staged.append(
                {
                    "intent_type": intent_type,
                    "target_loop": target_loop,
                    "priority": round(max(0.0, min(priority, 1.0)), 3),
                    "payload": payload_body,
                }
            )

        fallback_reply = await self._build_dialogue_reply_fallback(
            reflection=reflection,
            reduced_state=reduced_state,
            source_packet_ids=packet_ids,
            staged_types=staged_types,
        )
        if fallback_reply is not None:
            staged_types.add("chat")
            staged.append(fallback_reply)

        move_nudge = self._build_movement_nudge(
            current_location=current_location,
            adjacent_names=adjacent_names,
            recent=recent,
            scene=scene,
            packets=packets,
            staged_types=staged_types,
        )
        if move_nudge is not None and not (quiet_hours and not urgent_dialogue):
            self._intents.stage(
                intent_type="move",
                target_loop="fast",
                source_packet_ids=packet_ids,
                priority=0.46,
                payload=move_nudge,
                validation_state="unvalidated",
            )
            staged.append(
                {
                    "intent_type": "move",
                    "target_loop": "fast",
                    "priority": 0.46,
                    "payload": move_nudge,
                }
            )

        action_nudge = self._build_embodied_action_nudge(
            current_location=current_location,
            recent=recent,
            scene=scene,
            reduced_state=reduced_state,
            staged_types=staged_types,
            quiet_hours=quiet_hours,
            urgent_dialogue=urgent_dialogue,
        )
        if action_nudge is not None:
            action_priority = float(action_nudge.pop("priority", 0.5))
            self._intents.stage(
                intent_type="act",
                target_loop="fast",
                source_packet_ids=packet_ids,
                priority=action_priority,
                payload=action_nudge,
                validation_state="unvalidated",
            )
            staged.append(
                {
                    "intent_type": "act",
                    "target_loop": "fast",
                    "priority": round(action_priority, 3),
                    "payload": action_nudge,
                }
            )

        return staged

    def _maybe_stage_mail_reply_pressure(
        self,
        *,
        reduced_state: ResidentReducedState,
        subconscious_reading: str,
        urgent_dialogue: bool,
        queued_intents: list[dict[str, Any]],
    ) -> str | None:
        if urgent_dialogue:
            return None
        if any(item.get("intent_type") == "mail_draft" for item in queued_intents):
            return None
        pending_correspondence = list(reduced_state.memory_projection.get("pending_correspondence") or [])
        if pending_correspondence:
            return None
        mail_state = reduced_state.subjective_projection.get("mail_state") or {}
        if not isinstance(mail_state, dict):
            return None
        pending_letters = list(mail_state.get("pending_letters") or [])
        if not pending_letters:
            return None
        latest = pending_letters[-1] if isinstance(pending_letters[-1], dict) else {}
        recipient = str(latest.get("sender") or "").strip()
        if not recipient:
            return None
        context = self._mail_intent_context_excerpt(subconscious_reading) or f"{recipient} still seems to be waiting for a reply."
        self._stage_letter_intent(recipient, context)
        return recipient

    async def _build_dialogue_reply_fallback(
        self,
        *,
        reflection: str,
        reduced_state: ResidentReducedState,
        source_packet_ids: list[str],
        staged_types: set[str],
    ) -> dict[str, Any] | None:
        if not self._intents:
            return None
        if "chat" in staged_types or "move" in staged_types or "mail_draft" in staged_types:
            return None
        dialogue_state = reduced_state.subjective_projection.get("dialogue_state") or {}
        if not isinstance(dialogue_state, dict):
            return None
        pending = list(dialogue_state.get("open_questions") or [])
        if not pending:
            pending = list(dialogue_state.get("open_requests") or [])
        if not pending:
            return None
        latest = pending[-1] if isinstance(pending[-1], dict) else {}
        speaker = str(latest.get("speaker") or dialogue_state.get("active_partner") or "").strip()
        message = str(latest.get("message") or "").strip()
        if not speaker or not message:
            return None
        user_prompt = (
            f"You are {self._identity.display_name}.\n"
            f"{speaker} just said: {message}\n\n"
            f"What feels true in you right now:\n{self._reduced_state_to_prose(reduced_state) or '(none)'}\n\n"
            f"Reflection snippet:\n{self._smart_excerpt(reflection, 520)}"
        )
        try:
            utterance = await self._llm.complete(
                system_prompt=_DIALOGUE_REPLY_FALLBACK_SYSTEM,
                user_prompt=user_prompt,
                model=self._tuning.slow_subconscious_model,
                temperature=0.2,
                max_tokens=60,
            )
        except Exception as exc:
            logger.debug("[%s:slow] dialogue reply fallback failed: %s", self.name, exc)
            return None
        utterance = str(utterance or "").strip().strip('"\' ')
        if not utterance:
            return None
        self._intents.stage(
            intent_type="chat",
            target_loop="fast",
            source_packet_ids=source_packet_ids,
            priority=0.98,
            payload={"utterance": utterance},
            validation_state="unvalidated",
        )
        return {
            "intent_type": "chat",
            "target_loop": "fast",
            "priority": 0.98,
            "payload": {"utterance": utterance},
        }

    def _maybe_stage_homeward_move(
        self,
        *,
        current_location: str,
        all_location_names: list[str],
        reduced_state: ResidentReducedState,
        rest_assessment: RestAssessment,
        queued_intents: list[dict[str, Any]],
        circadian_profile,
        urgent_dialogue: bool,
    ) -> dict[str, Any] | None:
        if not self._intents or urgent_dialogue:
            return None
        if circadian_profile is None or circadian_profile.pressure < 0.6:
            return None
        if not rest_assessment.should_rest:
            return None
        home_location = str(self._tuning.home_location or "").strip()
        if not home_location or home_location == current_location:
            return None
        if home_location not in all_location_names:
            return None
        if any(item.get("intent_type") == "move" for item in queued_intents):
            return None
        active_route = reduced_state.memory_projection.get("active_route")
        if isinstance(active_route, dict) and str(active_route.get("destination") or "").strip() == home_location:
            return None
        blocked = reduced_state.runtime_projection.get("last_movement") or {}
        if (
            isinstance(blocked, dict)
            and str(blocked.get("event_type") or "").strip() == "movement_blocked"
            and str(blocked.get("destination") or "").strip() == home_location
        ):
            return None
        self._intents.stage(
            intent_type="move",
            target_loop="fast",
            source_packet_ids=[],
            priority=0.97,
            payload={"destination": home_location},
            validation_state="unvalidated",
        )
        return {
            "intent_type": "move",
            "target_loop": "fast",
            "priority": 0.97,
            "payload": {"destination": home_location},
        }

    def _reduced_state_for_intents(self, reduced_state: ResidentReducedState) -> str:
        lines: list[str] = []

        concerns = list(reduced_state.subjective_projection.get("current_concerns") or [])
        if concerns:
            rendered = [
                f"{str(item.get('kind') or '').strip()}:{str(item.get('label') or '').strip()}"
                for item in concerns[:6]
                if isinstance(item, dict) and str(item.get("label") or "").strip()
            ]
            if rendered:
                lines.append("Current concerns: " + ", ".join(rendered))

        threads = list(reduced_state.subjective_projection.get("active_social_threads") or [])
        if threads:
            rendered = [
                str(item.get("name") or "").strip()
                for item in threads[:6]
                if isinstance(item, dict) and str(item.get("name") or "").strip()
            ]
            if rendered:
                lines.append("Active social threads: " + ", ".join(rendered))

        dialogue_state = reduced_state.subjective_projection.get("dialogue_state") or {}
        if isinstance(dialogue_state, dict):
            partner = str(dialogue_state.get("active_partner") or "").strip()
            if partner:
                lines.append(f"Current dialogue partner: {partner}")
            open_questions = list(dialogue_state.get("open_questions") or [])
            if open_questions:
                latest = open_questions[-1]
                lines.append(
                    "Direct question awaiting reply: "
                    + str(latest.get("message") or "").strip()
                )
            open_requests = list(dialogue_state.get("open_requests") or [])
            if open_requests:
                latest = open_requests[-1]
                lines.append(
                    "Direct request awaiting response: "
                    + str(latest.get("message") or "").strip()
                )
        mail_state = reduced_state.subjective_projection.get("mail_state") or {}
        if isinstance(mail_state, dict):
            latest_sender = str(mail_state.get("latest_sender") or "").strip()
            pending_inbox = int(mail_state.get("pending_inbox_count") or 0)
            if pending_inbox > 0:
                detail = f"Incoming letters awaiting attention: {pending_inbox}"
                if latest_sender:
                    detail += f" (latest from {latest_sender})"
                lines.append(detail)
        city_context = reduced_state.subjective_projection.get("city_context") or {}
        if isinstance(city_context, dict):
            recent_signals = list(city_context.get("recent_signals") or [])
            if recent_signals:
                latest = recent_signals[-1]
                speaker = str(latest.get("speaker") or "").strip()
                message = str(latest.get("message") or "").strip()
                if speaker and message:
                    lines.append(f"Recent city signal: {speaker} said \"{message}\"")
        state_pressure = reduced_state.subjective_projection.get("state_pressure") or {}
        if isinstance(state_pressure, dict):
            signals = list(state_pressure.get("signals") or [])
            if signals:
                rendered = [
                    str(item.get("label") or item.get("kind") or "").strip()
                    for item in signals[:4]
                    if isinstance(item, dict) and str(item.get("label") or item.get("kind") or "").strip()
                ]
                if rendered:
                    lines.append("State pressure: " + ", ".join(rendered))
            context = state_pressure.get("context") if isinstance(state_pressure.get("context"), dict) else {}
            neighborhood = str(context.get("neighborhood") or "").strip()
            vibe = str(context.get("neighborhood_vibe") or "").strip()
            if neighborhood and vibe:
                lines.append(f"Place texture: {neighborhood} — {vibe[:180]}")
        if self._rest:
            lines.append(f"Circadian state: {self._rest.circadian_profile().summary}")

        experiences = list(reduced_state.memory_projection.get("recent_experiences") or [])
        if experiences:
            rendered = [
                f"{str(item.get('kind') or '').strip()}:{str(item.get('label') or '').strip()}"
                for item in experiences[:4]
                if isinstance(item, dict) and str(item.get("label") or "").strip()
            ]
            if rendered:
                lines.append("Recent reduced experiences: " + " | ".join(rendered))

        facts = list(reduced_state.subjective_facts.get("facts") or [])
        if facts:
            rendered = [
                f"{str(item.get('predicate') or '').strip()}:{str(item.get('object') or '').strip()}"
                for item in facts[:6]
                if isinstance(item, dict)
                and str(item.get("predicate") or "").strip()
                and str(item.get("object") or "").strip()
            ]
            if rendered:
                lines.append("Subjective facts: " + ", ".join(rendered))

        return "\n".join(lines) if lines else "(none)"

    def _reduced_state_to_prose(self, reduced_state: ResidentReducedState) -> str:
        fragments: list[str] = []
        concerns = list(reduced_state.subjective_projection.get("current_concerns") or [])
        if concerns:
            labels = [
                str(item.get("label") or "").strip()
                for item in concerns[:4]
                if isinstance(item, dict) and str(item.get("label") or "").strip()
            ]
            if labels:
                fragments.append("What still tugs on you: " + ", ".join(labels) + ".")

        threads = list(reduced_state.subjective_projection.get("active_social_threads") or [])
        if threads:
            names = [
                str(item.get("name") or "").strip()
                for item in threads[:4]
                if isinstance(item, dict) and str(item.get("name") or "").strip()
            ]
            if names:
                fragments.append("People already threaded through your mind: " + ", ".join(names) + ".")

        dialogue_state = reduced_state.subjective_projection.get("dialogue_state") or {}
        if isinstance(dialogue_state, dict):
            open_questions = list(dialogue_state.get("open_questions") or [])
            if open_questions:
                latest = open_questions[-1]
                speaker = str(latest.get("speaker") or "").strip()
                message = str(latest.get("message") or "").strip()
                if speaker and message:
                    fragments.append(f"{speaker} asked you something directly: \"{message}\"")
            else:
                open_requests = list(dialogue_state.get("open_requests") or [])
                if open_requests:
                    latest = open_requests[-1]
                    speaker = str(latest.get("speaker") or "").strip()
                    message = str(latest.get("message") or "").strip()
                    if speaker and message:
                        fragments.append(f"{speaker} is waiting on your response to: \"{message}\"")

        mail_state = reduced_state.subjective_projection.get("mail_state") or {}
        if isinstance(mail_state, dict):
            pending_letters = list(mail_state.get("pending_letters") or [])
            if pending_letters:
                latest_sender = str(pending_letters[-1].get("sender") or "").strip()
                if latest_sender:
                    fragments.append(f"There is still a letter from {latest_sender} waiting for you.")

        city_context = reduced_state.subjective_projection.get("city_context") or {}
        if isinstance(city_context, dict):
            recent_signals = list(city_context.get("recent_signals") or [])
            if recent_signals:
                latest = recent_signals[-1]
                speaker = str(latest.get("speaker") or "").strip()
                message = str(latest.get("message") or "").strip()
                if speaker and message:
                    fragments.append(f"In the city air, {speaker} recently said: \"{message}\"")
        state_pressure = reduced_state.subjective_projection.get("state_pressure") or {}
        if isinstance(state_pressure, dict):
            labels = [
                str(item.get("label") or item.get("kind") or "").strip()
                for item in list(state_pressure.get("signals") or [])[:4]
                if isinstance(item, dict) and str(item.get("label") or item.get("kind") or "").strip()
            ]
            if labels:
                fragments.append("Your state is pulling on you like this: " + ", ".join(labels) + ".")
            context = state_pressure.get("context") if isinstance(state_pressure.get("context"), dict) else {}
            neighborhood = str(context.get("neighborhood") or "").strip()
            vibe = str(context.get("neighborhood_vibe") or "").strip()
            if neighborhood and vibe:
                fragments.append(f"{neighborhood} feels like this around you: {vibe[:180]}.")

        route = reduced_state.memory_projection.get("active_route")
        if isinstance(route, dict):
            destination = str(route.get("destination") or "").strip()
            if destination:
                fragments.append(f"You are already oriented toward {destination}.")

        facts = list(reduced_state.subjective_facts.get("facts") or [])
        if facts:
            rendered = []
            for item in facts[:4]:
                if not isinstance(item, dict):
                    continue
                predicate = str(item.get("predicate") or "").strip().replace("_", " ")
                obj = str(item.get("object") or "").strip()
                if predicate and obj:
                    rendered.append(f"{predicate} {obj}")
            if rendered:
                fragments.append("Things that feel quietly true to you now: " + "; ".join(rendered) + ".")

        if not fragments:
            return ""
        return "Reduced state carried forward:\n" + "\n".join(f"- {fragment}" for fragment in fragments)

    def _normalize_intent_payload(
        self,
        intent_type: str,
        payload: dict[str, Any],
        *,
        known_contacts: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized = dict(payload)
        if intent_type == "chat":
            utterance = str(
                payload.get("utterance")
                or payload.get("message")
                or payload.get("content")
                or payload.get("text")
                or ""
            ).strip()
            if utterance:
                normalized = {"utterance": utterance}
        elif intent_type == "act":
            action = str(
                payload.get("action")
                or payload.get("description")
                or payload.get("content")
                or payload.get("text")
                or ""
            ).strip()
            if action:
                normalized = {"action": action}
        elif intent_type == "city_broadcast":
            message = str(
                payload.get("message")
                or payload.get("utterance")
                or payload.get("content")
                or payload.get("text")
                or ""
            ).strip()
            if message:
                normalized = {"message": message}
        elif intent_type == "move":
            destination = str(
                payload.get("destination")
                or payload.get("location")
                or payload.get("place")
                or ""
            ).strip()
            if destination:
                normalized = {"destination": destination}
        elif intent_type == "mail_draft":
            recipient = str(
                payload.get("recipient")
                or payload.get("to")
                or payload.get("target")
                or ""
            ).strip()
            context = str(
                payload.get("context")
                or payload.get("body")
                or payload.get("message")
                or payload.get("content")
                or ""
            ).strip()
            matched_recipient = ""
            for known_name in list(known_contacts or []):
                if recipient.lower() == known_name.lower():
                    matched_recipient = known_name
                    break
            normalized = {"recipient": matched_recipient, "context": context} if matched_recipient else {}
        elif intent_type == "ground":
            query = str(
                payload.get("query")
                or payload.get("research_query")
                or payload.get("topic")
                or ""
            ).strip()
            normalized = {"query": query} if 5 <= len(query) <= 100 else {}
        return normalized

    def _normalize_move_payload(
        self,
        payload: dict[str, Any],
        all_location_names: list[str],
    ) -> dict[str, Any]:
        destination = str(payload.get("destination") or "").strip()
        if not destination:
            return {}
        matched = self._match_known_location(destination, all_location_names)
        if not matched:
            logger.debug("[%s:slow] dropping non-graph move destination: %r", self.name, destination)
            return {}
        normalized = {"destination": matched}
        reason = str(payload.get("reason") or "").strip()
        if reason:
            normalized["reason"] = reason
        return normalized

    def _build_movement_nudge(
        self,
        *,
        current_location: str,
        adjacent_names: list[str],
        recent: list[dict],
        scene=None,
        packets: list[StimulusPacket],
        staged_types: set[str],
    ) -> dict[str, str] | None:
        if "move" in staged_types:
            return None
        if not current_location or not adjacent_names:
            return None
        if derive_active_route(self.resident_dir / "memory") is not None:
            return None
        if self._intents and any(intent.intent_type == "move" for intent in self._intents.pending(target_loop="fast")):
            return None
        if any(packet.packet_type == "mail_received" for packet in packets):
            return None
        if any(
            packet.packet_type in {"chat_heard", "city_chat_heard"}
            and isinstance(packet.payload, dict)
            and (
                bool(packet.payload.get("is_direct"))
                or bool(packet.payload.get("addressed"))
                or bool(packet.payload.get("is_question"))
                or bool(packet.payload.get("is_request"))
            )
            for packet in packets
        ):
            return None

        ambient_kinds = {
            str(getattr(item, "kind", "") or "").strip()
            for item in list(getattr(scene, "ambient_presence", []) or [])
            if str(getattr(item, "kind", "") or "").strip()
        }
        if ambient_kinds & {"weather_shelter_cluster", "night_presence", "queue", "worker"}:
            return None

        recent_entries = [entry for entry in recent[-8:] if isinstance(entry, dict)]
        grounding_count = sum(1 for entry in recent_entries if entry.get("type") == "grounding")
        action_count = sum(1 for entry in recent_entries if entry.get("type") == "action")
        if grounding_count < 2 and action_count == 0:
            if not (ambient_kinds & {"passerby_cluster", "event_spillover", "commuter_flow"} and grounding_count >= 1):
                return None
        if action_count > 3:
            if not (ambient_kinds & {"passerby_cluster", "event_spillover", "commuter_flow"} and grounding_count >= 1):
                return None

        recent_locations = [
            str(entry.get("location") or "").strip().lower()
            for entry in recent_entries
            if str(entry.get("location") or "").strip()
        ]
        ordered_adjacent = sorted({name for name in adjacent_names if name and name != current_location})
        if not ordered_adjacent:
            return None

        destination = next(
            (name for name in ordered_adjacent if name.lower() not in recent_locations[-3:]),
            ordered_adjacent[0],
        )
        reason = "change_of_scene_after_long_stillness"
        if ambient_kinds & {"passerby_cluster", "event_spillover", "commuter_flow"}:
            reason = "follow_the_flow_of_the_block"
        return {
            "destination": destination,
            "reason": reason,
        }

    def _build_embodied_action_nudge(
        self,
        *,
        current_location: str,
        recent: list[dict],
        scene=None,
        reduced_state: ResidentReducedState,
        staged_types: set[str],
        quiet_hours: bool,
        urgent_dialogue: bool,
    ) -> dict[str, Any] | None:
        if urgent_dialogue:
            return None
        if {"act", "chat", "move", "mail_draft"} & staged_types:
            return None
        state_pressure = reduced_state.subjective_projection.get("state_pressure") or {}
        if not isinstance(state_pressure, dict):
            return None
        signal_kinds = [
            str(item.get("kind") or "").strip()
            for item in list(state_pressure.get("signals") or [])
            if isinstance(item, dict) and str(item.get("kind") or "").strip()
        ]
        if not signal_kinds:
            return None

        recent_entries = [entry for entry in recent[-6:] if isinstance(entry, dict)]
        recent_actions = [
            str(entry.get("action") or "").strip().lower()
            for entry in recent_entries
            if entry.get("type") == "action" and str(entry.get("action") or "").strip()
        ]
        if recent_actions:
            latest_action = recent_actions[-1]
            if any(
                token in latest_action
                for token in ("pause", "listen", "watch", "step aside", "slow down", "shelter", "look around")
            ):
                return None

        ambient_kinds = [
            str(getattr(item, "kind", "") or "").strip()
            for item in list(getattr(scene, "ambient_presence", []) or [])
            if str(getattr(item, "kind", "") or "").strip()
        ]
        action = ""
        priority = 0.44
        if "weather_shelter_cluster" in ambient_kinds:
            action = "I edge in under cover with everyone else and let the weather spend itself."
            priority = 0.64
        elif "event_spillover" in ambient_kinds:
            action = "I turn toward the drift of attention and see what is pulling at the block."
            priority = 0.58
        elif "queue" in ambient_kinds:
            action = "I straighten what is in front of me and make room for the loose line nearby."
            priority = 0.56
        elif "commuter_flow" in ambient_kinds:
            action = "I shift my pace to match the hour and the people moving through it."
            priority = 0.55
        elif "night_presence" in ambient_kinds:
            action = "I lower my voice and settle into the thin late-night quiet around me."
            priority = 0.58
        elif "bad_weather" in signal_kinds:
            action = "I tuck myself closer to shelter and shake the weather from my sleeves."
            priority = 0.62
        elif "crowding" in signal_kinds:
            action = "I step aside and let the foot traffic move around me for a moment."
            priority = 0.58
        elif "quiet" in signal_kinds:
            action = "I pause and listen to how quiet the block has gotten."
            priority = 0.56 if quiet_hours else 0.5
        elif "event_pull" in signal_kinds:
            action = "I linger at the edge of the activity and take its measure."
            priority = 0.52
        elif "fatigue" in signal_kinds:
            action = "I slow down, rub my eyes, and steady myself."
            priority = 0.57
        elif "tension" in signal_kinds or "danger" in signal_kinds:
            action = "I check my surroundings and keep my shoulders loose."
            priority = 0.54
        elif "loneliness" in signal_kinds:
            action = "I stay where people can still see me instead of fading back."
            priority = 0.46

        if not action:
            return None
        return {"action": action, "reason": "state_pressure_embodied_nudge", "priority": priority}

    def _extract_adjacent_names(self, current_location: str, location_graph: dict) -> list[str]:
        if not current_location or not isinstance(location_graph, dict):
            return []
        nodes = location_graph.get("nodes", [])
        edges = location_graph.get("edges", [])
        if not isinstance(nodes, list) or not isinstance(edges, list):
            return []

        name_to_key: dict[str, str] = {}
        key_to_name: dict[str, str] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            name = str(node.get("name") or "").strip()
            key = str(node.get("key") or "").strip()
            if name and key:
                name_to_key[name] = key
                key_to_name[key] = name
        current_key = name_to_key.get(current_location)
        if not current_key:
            return []

        adjacent_keys: set[str] = set()
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            src = str(edge.get("from") or "").strip()
            dst = str(edge.get("to") or "").strip()
            if src == current_key and dst:
                adjacent_keys.add(dst)
            elif dst == current_key and src:
                adjacent_keys.add(src)
        return [key_to_name[key] for key in sorted(adjacent_keys) if key in key_to_name]

    def _extract_all_location_names(self, location_graph: dict) -> list[str]:
        if not isinstance(location_graph, dict):
            return []
        nodes = location_graph.get("nodes", [])
        if not isinstance(nodes, list):
            return []
        names = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            name = str(node.get("name") or "").strip()
            if name:
                names.append(name)
        return sorted(dict.fromkeys(names))

    def _match_known_location(self, destination: str, all_location_names: list[str]) -> str | None:
        destination_lower = destination.lower().strip()
        if not destination_lower:
            return None
        return next((name for name in all_location_names if name.lower() == destination_lower), None)

    async def _assess_rest_intent(
        self,
        reflection: str,
        subconscious_reading: str,
    ) -> RestAssessment:
        user_prompt = (
            "Journal entry:\n\n"
            + self._smart_excerpt(reflection, 1200)
            + "\n\nSubconscious reading:\n\n"
            + self._smart_excerpt(subconscious_reading, 520)
            + "\n\nAssess whether this person genuinely wants rest right now."
        )
        try:
            payload = await self._llm.complete_json(
                system_prompt=_REST_ASSESSMENT_SYSTEM,
                user_prompt=user_prompt,
                model=self._tuning.slow_subconscious_model,
                temperature=0.1,
                max_tokens=220,
            )
        except InferenceError as exc:
            logger.debug("[%s:slow] rest assessment parse failed: %s", self.name, exc)
            return RestAssessment()
        except Exception as exc:
            logger.debug("[%s:slow] rest assessment failed: %s", self.name, exc)
            return RestAssessment()
        return RestAssessment.from_payload(payload)

    async def _distill_soul_note(self, reflection: str) -> str | None:
        """
        Ask the character to capture what shifted in one brief line, in their own voice.

        Soul notes are personal fragments — first-person, experiential, plain.
        Like a pocket notebook: 'Someone tipped me really big today.' / 'I felt good.'
        No timestamps, no location unless it really matters. Not analytical.
        """
        try:
            note = await self._llm.complete(
                system_prompt=(
                    f"You are {self.name}. You just finished reflecting on your day. "
                    "In one short sentence (under 15 words), capture the most personally "
                    "significant thing that happened or shifted — in your own first-person voice. "
                    "Be plain and direct. No timestamps, no location unless it really matters. "
                    "Examples: 'Someone tipped me really big today.' / 'I felt good.' / "
                    "'A stranger asked me something I didn't have an answer for.' "
                    "If nothing significant happened, reply with exactly: nothing"
                ),
                user_prompt=self._smart_excerpt(reflection, 1000),
                model=self._tuning.slow_subconscious_model,
                temperature=0.6,
                max_tokens=30,
            )
            note = note.strip().strip("\"'")
            if not note or note.lower().startswith("nothing"):
                return None
            return note
        except Exception as e:
            logger.debug("[%s:slow] soul note distillation failed: %s", self.name, e)
            return None

    def _stage_letter_intent(self, recipient: str, subconscious_reading: str) -> None:
        """
        Stage a minimal intent file for the mail loop to act on.
        The mail loop will ask the agent what they want to say — the letter
        is written there, not here. We only carry enough context for the
        mail loop to frame the question naturally.
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        # Pull a short excerpt from the subconscious reading as context —
        # just enough for the mail loop to ground the question naturally.
        excerpt = self._mail_intent_context_excerpt(subconscious_reading)
        append_runtime_event(
            self.resident_dir / "memory",
            event_type="mail_intent_staged",
            payload={
                "mail_intent_id": f"mailint-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
                "recipient": recipient,
                "context": excerpt,
                "staged_at": ts,
                "source": "slow",
            },
        )

    async def _record_soul_note(
        self,
        note: str,
        ts: str,
        *,
        location: str = "",
        active_partner: str = "",
        pressure_tags: list[str] | None = None,
    ) -> bool:
        """
        Append a soul note to actor-scoped DB-backed identity growth state.

        SOUL.md stays a compatibility export for prompt composition. Notes now
        accumulate in shard Postgres until the collapse threshold is reached.

        Quality filter: skip notes that are too short or are just bare markdown
        headers with no real content (a common subconscious output artifact).
        Returns True if the note was written, False if it was dropped.
        """
        note = note.strip()
        # Drop empty notes or bare markdown artifacts
        if len(note) < 5:
            logger.debug("[%s:slow] dropping empty soul note", self.name)
            return False
        stripped = re.sub(r'\*+', '', note).strip(" :")
        if len(stripped) < 5:
            logger.debug("[%s:slow] dropping header-only soul note: %r", self.name, note[:60])
            return False

        state = await self._load_identity_growth_state()
        records = list(state.get("note_records") or [])
        records.append(
            {
                "ts": ts,
                "note": note,
                "location": str(location or "").strip(),
                "active_partner": str(active_partner or "").strip(),
                "pressure_tags": list(pressure_tags or []),
            }
        )
        await self._ww.update_identity_growth(
            self._session_id,
            note_records=records[-64:],
        )
        return True

    async def _load_identity_growth_state(self) -> dict[str, Any]:
        try:
            payload = await self._ww.get_identity_growth(self._session_id)
        except Exception as exc:
            logger.debug("[%s:slow] identity growth load failed: %s", self.name, exc)
            return {"growth_text": "", "growth_metadata": {}, "note_records": []}
        return {
            "growth_text": str(payload.get("growth_text") or "").strip(),
            "growth_metadata": dict(payload.get("growth_metadata") or {}),
            "note_records": list(payload.get("note_records") or []),
        }

    async def _load_soul_note_records(self) -> list[dict[str, Any]]:
        state = await self._load_identity_growth_state()
        records: list[dict[str, Any]] = []
        for payload in list(state.get("note_records") or []):
            if not isinstance(payload, dict):
                continue
            note = str(payload.get("note") or "").strip()
            if not note:
                continue
            records.append(
                {
                    "note": note,
                    "ts": str(payload.get("ts") or "").strip(),
                    "location": str(payload.get("location") or "").strip(),
                    "active_partner": str(payload.get("active_partner") or "").strip(),
                    "pressure_tags": list(payload.get("pressure_tags") or []),
                }
            )
        return records

    def _soul_note_context_key(self, record: dict[str, Any]) -> str:
        location = str(record.get("location") or "").strip().lower()
        active_partner = str(record.get("active_partner") or "").strip().lower()
        pressure_tags = sorted(
            {
                str(tag or "").strip().lower()
                for tag in list(record.get("pressure_tags") or [])
                if str(tag or "").strip()
            }
        )
        return "|".join(
            part
            for part in (location, active_partner, ",".join(pressure_tags[:3]))
            if part
        )

    def _soul_notes_matured_enough(self, records: list[dict[str, Any]]) -> bool:
        threshold = self._tuning.soul_collapse_at_notes
        if len(records) < threshold:
            return False

        unique_notes = {
            re.sub(r"\s+", " ", str(record.get("note") or "").strip().lower())
            for record in records
            if str(record.get("note") or "").strip()
        }
        if len(unique_notes) < 2:
            logger.info(
                "[%s:slow] soul collapse deferred: notes lack enough distinct recurrence (%d unique)",
                self.name,
                len(unique_notes),
            )
            return False

        distinct_contexts = {
            self._soul_note_context_key(record)
            for record in records
            if self._soul_note_context_key(record)
        }
        if len(distinct_contexts) < 2:
            logger.info(
                "[%s:slow] soul collapse deferred: notes span only %d distinct contexts",
                self.name,
                len(distinct_contexts),
            )
            return False

        timestamps = [
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
            for ts in (str(record.get("ts") or "").strip() for record in records)
            if ts
        ]
        if len(timestamps) >= 2:
            span_seconds = (max(timestamps) - min(timestamps)).total_seconds()
            if span_seconds < 6 * 60 * 60:
                logger.info(
                    "[%s:slow] soul collapse deferred: notes span only %.2f hours",
                    self.name,
                    span_seconds / 3600.0,
                )
                return False

        return True

    def _build_growth_metadata(
        self,
        *,
        records: list[dict[str, Any]],
        growth_text: str,
        promoted_at: str,
    ) -> dict[str, Any]:
        contexts: list[dict[str, Any]] = []
        seen_contexts: set[str] = set()
        for record in records:
            context = {
                "location": str(record.get("location") or "").strip(),
                "active_partner": str(record.get("active_partner") or "").strip(),
                "pressure_tags": [
                    str(tag or "").strip()
                    for tag in list(record.get("pressure_tags") or [])
                    if str(tag or "").strip()
                ],
            }
            key = json.dumps(context, sort_keys=True, ensure_ascii=False)
            if key in seen_contexts:
                continue
            seen_contexts.add(key)
            contexts.append(context)
        return {
            "promoted_at": promoted_at,
            "note_count": len(records),
            "unique_note_count": len(
                {
                    re.sub(r"\s+", " ", str(record.get("note") or "").strip().lower())
                    for record in records
                    if str(record.get("note") or "").strip()
                }
            ),
            "distinct_context_count": len([context for context in contexts if any(context.values())]),
            "sample_notes": [
                str(record.get("note") or "").strip()
                for record in records[:5]
                if str(record.get("note") or "").strip()
            ],
            "contexts": contexts[:8],
            "growth_preview": growth_text[:240],
        }

    async def _maybe_collapse_soul(self) -> None:
        """
        If enough soul notes have accumulated, synthesize them into a clean
        unified SOUL.md. This prevents character drift from accumulating silently.

        Notes live in actor-scoped DB state. Collapse reads the immutable canon,
        the matured writable growth layer, and the pending note evidence. It
        rewrites only the growth layer, updates the runtime prompt immediately,
        and clears the pending note records.
        """
        state = await self._load_identity_growth_state()
        records = await self._load_soul_note_records()
        note_count = len(records)

        if not self._soul_notes_matured_enough(records):
            return

        canonical_soul_path = IdentityLoader.canonical_soul_path(self.resident_dir)
        if not canonical_soul_path.exists() and not (self.resident_dir / "identity" / "SOUL.md").exists():
            return

        canonical_soul, existing_growth = IdentityLoader.load_canonical_and_growth(self.resident_dir)
        if state.get("growth_text"):
            existing_growth = str(state.get("growth_text") or "").strip()
        notes_text = "\n---\n".join(
            str(record.get("note") or "").strip()
            for record in records
            if str(record.get("note") or "").strip()
        )

        logger.info(
            "[%s:slow] soul growth collapse triggered: %d matured notes accumulated",
            self.name,
            note_count,
        )

        system = (
            "You are integrating a character's matured growth into a separate writable growth layer. "
            "You have their immutable canonical identity, any existing matured growth, and a set of recent notes. "
            "Rewrite only the matured growth layer as clean, flowing second-person prose that captures durable "
            "development without replacing the canon. Discard trivial, repetitive, socially contagious, or purely "
            "situational notes. Be especially skeptical of one-off metaphysical interpretations triggered by a "
            "single strange conversation. "
            "IMPORTANT: Do not alter the character's occupation, home neighborhood, family relationships, or "
            "fundamental nature. Keep real growth, not contagion. Output only the rewritten growth layer."
        )
        user = (
            "Immutable canonical identity:\n\n"
            + canonical_soul[:3000]
            + "\n\nExisting matured growth:\n\n"
            + (existing_growth[:1500] or "(none)")
            + "\n\nRecent notes:\n\n"
            + notes_text[:1500]
            + "\n\nRewrite the matured growth layer only. Keep it compact and cumulative."
        )

        try:
            refined = await self._llm.complete(
                system_prompt=system,
                user_prompt=user,
                model=self._tuning.slow_subconscious_model or self._tuning.slow_model,
                temperature=0.4,
                max_tokens=700,
            )
        except Exception as e:
            logger.warning("[%s:slow] soul collapse LLM call failed: %s", self.name, e)
            return

        refined = refined.strip()
        if refined.lower() in {"nothing", "(none)", "none"}:
            refined = ""

        if refined and len(refined) < 60:
            logger.warning("[%s:slow] soul growth collapse returned suspiciously short output, skipping")
            return

        growth_metadata = self._build_growth_metadata(
            records=records,
            growth_text=refined,
            promoted_at=datetime.now(timezone.utc).isoformat(),
        )
        await self._ww.update_identity_growth(
            self._session_id,
            growth_text=refined,
            growth_metadata=growth_metadata,
            note_records=[],
        )
        # Update the running agent's system prompt immediately — next LLM call uses the refined soul
        self._identity.canonical_soul = canonical_soul
        self._identity.growth_soul = refined
        self._identity.soul = IdentityLoader.composed_soul(canonical_soul, refined)
        logger.info(
            "[%s:slow] soul growth collapsed: %d chars canon + %d chars growth + %d chars notes → %d chars growth",
            self.name, len(canonical_soul), len(existing_growth), len(notes_text), len(refined),
        )

    async def _maybe_write_reverie(self, reflection: str) -> None:
        """
        Extract one vivid sensory/emotional image from the reflection and add
        it to the reverie deck. These become the fast loop's live anchor —
        personal, varied, and evolving rather than the same static prose.
        """
        try:
            reverie = await self._llm.complete(
                system_prompt=(
                    f"You are reading {self.name}'s private reflection. "
                    "Extract one vivid, specific sensory or emotional image from it — "
                    "something they noticed, felt, or will carry with them. "
                    "Write it in first person, under 20 words. No explanation. "
                    "If there is nothing specific and sensory, reply with exactly: nothing"
                ),
                user_prompt=self._smart_excerpt(reflection, 800),
                model=self._tuning.slow_subconscious_model,
                temperature=0.7,
                max_tokens=35,
            )
            reverie = reverie.strip().strip("\"'.,")
            if reverie and not reverie.lower().startswith("nothing"):
                self._reveries.add(reverie)
                logger.debug("[%s:slow] reverie: %s", self.name, reverie[:70])
        except Exception as e:
            logger.debug("[%s:slow] reverie extraction failed: %s", self.name, e)

    async def _maybe_write_voice_sample(self, recent: list) -> None:
        """
        Pick one characteristic utterance from recent chat history and add it
        to the voice deck. Prefers short messages — they're more distinctively clipped.

        We extract from actual chat entries (type="chat") rather than generating
        descriptions, so the deck stays grounded in what the character really said.
        Shorter messages score higher; messages over 25 words are skipped entirely.
        """
        chat_entries = [
            e["message"] for e in recent
            if isinstance(e, dict) and e.get("type") == "chat" and e.get("message")
        ]
        if not chat_entries:
            return

        # Prefer shorter messages — they're the most characteristically terse
        short = [m for m in chat_entries if len(m.split()) <= 25]
        candidates = short if short else chat_entries
        if not candidates:
            return

        # Pick the shortest as the best voice sample (most characteristically brief)
        best = min(candidates, key=lambda m: len(m.split()))
        if best:
            self._voice.add(best)
            logger.debug("[%s:slow] voice sample: %s", self.name, best[:60])

    async def _maybe_extract_research(self, reflection: str) -> None:
        """
        Extract 0-2 specific, searchable queries from the reflection and add
        them to the research queue. The ground loop fetches answers and writes
        them to working memory so the next fast loop cycle sees the result.
        """
        if self._research_queue is None:
            return
        try:
            raw = await self._llm.complete(
                system_prompt=(
                    f"You are reading {self.name}'s private reflection. "
                    "Identify 0-2 things they genuinely don't know but could look up — "
                    "specific, searchable questions about the real world. "
                    "Write each as a short search query (5-80 characters). "
                    "Format each on its own line as: RESEARCH: <query>\n"
                    "If there is nothing worth looking up, reply with exactly: nothing"
                ),
                user_prompt=self._smart_excerpt(reflection, 800),
                model=self._tuning.slow_subconscious_model,
                temperature=0.5,
                max_tokens=80,
            )
            for line in raw.splitlines():
                line = line.strip()
                if line.lower().startswith("research:"):
                    query = line[len("research:"):].strip()
                    if 5 <= len(query) <= 80:
                        self._research_queue.add(query, priority="normal", source="slow_reflection")
                        logger.debug("[%s:slow] research queued: %s", self.name, query)
        except Exception as e:
            logger.debug("[%s:slow] research extraction failed: %s", self.name, e)

    def _should_extract_research(
        self,
        *,
        reduced_state: ResidentReducedState,
        urgent_dialogue: bool,
        quiet_hours: bool,
    ) -> bool:
        if self._research_queue is None or urgent_dialogue or quiet_hours:
            return False

        mail_state = reduced_state.subjective_projection.get("mail_state") or {}
        if isinstance(mail_state, dict) and int(mail_state.get("pending_inbox_count") or 0) > 0:
            return False

        pending_correspondence = list(reduced_state.memory_projection.get("pending_correspondence") or [])
        if pending_correspondence:
            return False

        dialogue_state = reduced_state.subjective_projection.get("dialogue_state") or {}
        if isinstance(dialogue_state, dict):
            direct_urgency = _coerce_float(dialogue_state.get("direct_urgency")) or 0.0
            if direct_urgency >= 0.5:
                return False

        pending_research = list(reduced_state.memory_projection.get("pending_research") or [])
        if len(pending_research) >= 3:
            return False

        state_pressure = reduced_state.subjective_projection.get("state_pressure") or {}
        if isinstance(state_pressure, dict):
            pressure_signals = list(state_pressure.get("signals") or [])
            if pressure_signals:
                return False

        return True

    async def _cooldown(self) -> None:
        await asyncio.sleep(5.0)
