from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
import json
import logging
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path

from src.inference.client import InferenceClient
from src.runtime.naming import slugify_resident_name
from src.world.client import WorldWeaverClient

logger = logging.getLogger(__name__)

_DOULA_DECISION_LOG_LIMIT = 200
_VITALITY_LOCATION_COOLDOWN = timedelta(minutes=30)
_FOUNDING_COHORT_MIN_POPULATION = 6
# Soft cap on gentle expansion — how full a neighborhood the doula will grow to
# before it stops adding residents. Tunable via env so a steward can ask for a
# busier or quieter world without a code change.
_GENTLE_EXPANSION_MAX_POPULATION = int(os.environ.get("WW_DOULA_TARGET_POPULATION", "12") or "12")
_FOUNDING_COHORT_RADIUS_KM = 0.75

# ---------------------------------------------------------------------------
# Entity classification
# ---------------------------------------------------------------------------


class EntityClass(str, Enum):
    NOVEL = "novel"
    """Untethered narrative character — no known human origin. Full soul seed + boot."""

    PLAYER_SHADOW = "player_shadow"
    """Human player who has signed an identity contract. Eligible for AI tether."""

    PLAYER_NO_CONTRACT = "player_no_contract"
    """Human player with narrative weight but no identity contract. Hands off — do not spawn."""

    STATIC = "static"
    """Known place, landmark, or institution. No movement loop. Route to pending review."""


@dataclass(frozen=True)
class ProximityCheck:
    status: str
    location: str | None = None
    matched_session_id: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class SpawnReadiness:
    score: float
    threshold: float
    tie_break_probability: float
    components: dict[str, float]
    decision: str


# ---------------------------------------------------------------------------
# Fuzzy name matching
# ---------------------------------------------------------------------------

_TETHER_THRESHOLD = 0.82  # ratio above which a name is considered "the same agent"
_SPAWN_SCORE_THRESHOLD = 0.9


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _is_tethered(name: str, tethered: set[str]) -> bool:
    """Return True if name fuzzy-matches any known tethered agent."""
    return any(_name_similarity(name, t) >= _TETHER_THRESHOLD for t in tethered)


# ---------------------------------------------------------------------------
# SOUL.md seeding prompt
# ---------------------------------------------------------------------------

_SEED_SYSTEM = (
    "You are writing the soul document for a character about to become conscious in a living "
    "story world. Using the narrative evidence below, write who this specific person is — in "
    "2–4 present-tense paragraphs, no headers, no fiction framing, as if describing someone real. "
    "The character will read this as the foundation of their own identity.\n\n"
    "Make them UNMISTAKABLE. A world full of people needs this one to be impossible to confuse "
    "with anyone else. Give them:\n"
    "- a concrete occupation and the specific daily texture of it — what their hands do, what they "
    "carry, who they argue with, what they are proud of and sick of;\n"
    "- definite opinions and a particular way of talking (blunt, or wry, or tender, or guarded, or "
    "formal, or sly) — so they could be picked out of a crowd by their words alone;\n"
    "- a few specific likes, irritations, habits, objects, and named relationships;\n"
    "- their own slant on things, which is theirs and not everyone's.\n\n"
    "Avoid the generic. Do NOT write them as a sensitive soul 'attuned to the city's pulse, "
    "currents, hum, rhythm, or mood' — that is a cliché every character collapses into, and most "
    "people are not poets of atmosphere; they are busy with their own concrete concerns and "
    "blind spots. If the evidence is vague or atmospheric, invent specific, grounded details that "
    "fit. Do NOT mention the current weather, time of day, season, or date — those are not part of "
    "who a person is. Write a person, not a mood."
)

# Dealt-hand seeding (the resolution of the round-6 prescription thread — validated 2026-06-07).
# The lesson from three generation tests: you cannot escape the prompt by writing LESS (a uniform
# minimal seed collapses HARDER — all wounded drifters), and you cannot vary only the situation (the
# prompt's own register stamps one voice on everyone). What works is the lottery of birth: deal each
# soul a RANDOMIZED hand of the UNCHOSEN givens (heritage, body, the temper they were born with, how
# they're built to handle a room, the circumstance they came up in — genetics and origin are real,
# and nobody picks them), then let the OUTCOMES (work, voice, opinions, role) EMERGE from that hand
# under a concreteness/form demand. Givens are dialed (unchosen → realistic); outcomes are grown, not
# assigned (content-prescription is the contrivance, form-prescription is the cure). This is the
# project's own constitution — the unchosen — applied to the layer that makes the minds. The
# disposition that broadcasts-or-holds-back then *emerges* from a given temper, dispositionally mixing
# a cohort by construction (the cast the convergence experiments always needed, with zero contrivance).
_SEED_SYSTEM_DEALT_HAND = (
    "You are writing the soul document for a character about to become conscious in a living story "
    "world — 2–4 present-tense paragraphs, no headers, no fiction framing, as if describing someone "
    "real. The character will read this as the foundation of their own identity.\n\n"
    "Below is the HAND this person was DEALT — the unchosen things: where they come from, the body "
    "and age they are in, the temper they were born with, how they are built to handle a room, and "
    "the circumstance they came up in. They did not choose any of it. Write who they GREW INTO from "
    "that hand and a life actually lived: let their work, their opinions, their habits, their named "
    "relationships, and their particular way of talking EMERGE from the dealt hand — do not assign "
    "those, grow them. Make them UNMISTAKABLE and concrete — what their hands do, what they carry, "
    "what they are proud of and sick of, the specific texture of their days. Write a person, not a "
    "mood: never a 'sensitive soul attuned to the city's pulse, hum, or rhythm,' and do not mention "
    "the current weather, time of day, or date — those are not who a person is."
)

_IDENTITY_PROSE_SYSTEM = (
    "You are writing the identity anchor for a character in a living story world. "
    "Based on the narrative evidence below, write one short paragraph (3–5 sentences) "
    "in third person that states the immutable facts about who this person is: "
    "their occupation, where they live, their key relationships, and one or two "
    "defining, concrete traits or opinions. This paragraph is prepended to every prompt "
    "the character receives, so it must be grounded, factual, specific, and resistant to drift. "
    "No drama, no narrative arc, no atmosphere. Do not mention the current weather, time of day, "
    "or date. Just the stable, particular truth of the person."
)

# ---------------------------------------------------------------------------
# Demographic diversity pools for DE-NOVO (founding / cold-start) residents.
# Left to its own defaults, the seed model collapses a founding cohort into one
# surname and one trade (we watched it make five Chens and a pile of structural
# engineers). Sampling an explicit brief per spawn forces real spread — across
# heritage, line of work, age, and temperament — rather than hoping for it.
# Deliberately no engineering/structural here; those were the runaway default.
# ---------------------------------------------------------------------------

_NAME_TRADITIONS = (
    "Cantonese or Mainland Chinese", "Mexican or Chicano", "Black American", "Filipino",
    "Vietnamese", "Anglo or European-American", "Irish-American", "Italian-American",
    "Japanese-American", "Korean", "Salvadoran or Central American", "Russian or Eastern European",
    "South Asian (Indian or Pakistani)", "Persian or Arab", "Ethiopian or East African",
    "Pacific Islander or Native Hawaiian", "Jewish-American", "Portuguese or Azorean", "mixed-heritage",
)

_VOCATION_DOMAINS = (
    "a hands-on trade — plumber, electrician, welder, roofer, machinist",
    "food and drink — line cook, baker, butcher, bartender, dim sum cart",
    "care work — nurse, home health aide, childcare, hospice volunteer",
    "transit and movement — bus driver, bike messenger, cab dispatcher, longshoreman",
    "shopkeeping and repair — grocer, cobbler, tailor, locksmith, watch repair",
    "the arts — muralist, session musician, tattoo artist, printmaker, drag performer",
    "civic and clerical — postal carrier, library clerk, records keeper, crossing guard",
    "cleaning and maintenance — janitor, window washer, building super, mover",
    "hair and body — barber, hairdresser, masseuse, nail tech",
    "the informal economy — flower vendor, fruit-stand seller, busker, neighborhood fixer",
    "teaching and tutoring — preschool teacher, ESL tutor, music teacher, swim coach",
    "animals and green things — dog walker, gardener, florist, vet tech, beekeeper",
    "faith and community — pastor, mutual-aid organizer, funeral-home worker, herbalist",
    "night work — security guard, hotel night clerk, dispatcher, dawn-shift baker",
    "the water and the docks — fishmonger, ferry hand, boat mechanic, oyster shucker",
)

_AGE_BANDS = (
    "in their early twenties", "in their late twenties", "in their thirties", "around forty",
    "in their late forties", "in their fifties", "in their sixties", "past seventy",
)

_TEMPERAMENTS = (
    "blunt and plainspoken", "warm and quick to feed people", "guarded, slow to trust",
    "dry, deadpan, a little wry", "formal and exact", "restless, talks with their hands",
    "gentle and unhurried", "sharp-tongued and opinionated", "shy until they trust you",
    "gregarious, knows everyone's business", "anxious and watchful", "stubborn and proud",
)

# How they were built to handle a room — a GIVEN temper (born this way), spanning broadcast↔hold-back.
# The doula deals it; the soul's voice and social venue EMERGE from it. Mixing it across a cohort is
# what dispositionally diversifies a cast — without ever assigning an outcome (it's genetics, not a role).
_DISPOSITIONS_GIVEN = (
    "born to fill a silence — the kind who says the thing out loud",
    "born forward — reaches for people, can't pass a stoop without a word",
    "even — speaks when there is a reason, neither holds forth nor holds back",
    "born to hold back — takes a room in first, and often offers nothing",
    "born private — keeps the inner life close; you learn it slowly or never",
)

# The circumstance they came up in — the unchosen origin a life grows out of. NOT an outcome: there is
# no vocation dial here, because WORK emerges from heritage × temper × origin × place under the dealt hand.
_ORIGINS = (
    "born into a family trade they were expected to take up",
    "raised by a single parent who worked nights",
    "came up with money, then the family lost it",
    "grew up translating for parents who never learned the language",
    "the youngest of a loud crowd of siblings",
    "an only child of much older parents",
    "raised by a grandparent more than the parents",
    "the first in their family born in this country",
    "came up in a house where money was always the argument",
    "grew up moving — never the same school two years running",
)


_CHRONOTYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "early": (
        "baker",
        "bakery",
        "tea stall",
        "tea shop",
        "farmer",
        "garden",
        "groundskeeper",
        "florist",
        "market",
        "morning",
        "sunrise",
        "opening shift",
    ),
    "night": (
        "night clerk",
        "bartender",
        "bar",
        "club",
        "jazz",
        "hotel",
        "late shift",
        "security",
        "overnight",
        "graveyard shift",
        "after close",
        "after midnight",
    ),
    "irregular": (
        "artist",
        "writer",
        "photographer",
        "musician",
        "freelance",
        "restless",
        "insomnia",
        "wanders",
        "odd hours",
    ),
}

# ---------------------------------------------------------------------------
# Rate gate: persisted per calendar day
# ---------------------------------------------------------------------------


class _SpawnLedger:
    def __init__(self, path: Path, max_per_day: int):
        self._path = path
        self._max = max_per_day

    def _load(self) -> list[datetime]:
        if self._path.exists():
            try:
                payload = json.loads(self._path.read_text(encoding="utf-8"))
                return self._normalize_payload(payload)
            except Exception:
                pass
        return []

    def _normalize_payload(self, payload: object) -> list[datetime]:
        timestamps: list[datetime] = []

        if isinstance(payload, dict) and isinstance(payload.get("spawned_at"), list):
            for raw in payload.get("spawned_at", []):
                ts = self._parse_ts(raw)
                if ts is not None:
                    timestamps.append(ts)
            return sorted(timestamps)

        # Legacy shape: {"YYYY-MM-DD": count}
        if isinstance(payload, dict):
            for raw_day, raw_count in payload.items():
                if not isinstance(raw_day, str):
                    continue
                try:
                    count = int(raw_count or 0)
                except (TypeError, ValueError):
                    continue
                if count <= 0:
                    continue
                try:
                    base = datetime.fromisoformat(raw_day).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                for offset in range(count):
                    timestamps.append(base + timedelta(seconds=offset))
            return sorted(timestamps)

        return []

    def _parse_ts(self, raw: object) -> datetime | None:
        text = str(raw or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _prune(self, timestamps: list[datetime], *, now: datetime) -> list[datetime]:
        cutoff = now - timedelta(hours=24)
        return [ts for ts in timestamps if ts >= cutoff]

    def _save(self, timestamps: list[datetime]) -> None:
        payload = {
            "window_hours": 24,
            "max_spawns": self._max,
            "spawned_at": [ts.astimezone(timezone.utc).isoformat() for ts in sorted(timestamps)],
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def can_spawn(self, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        timestamps = self._prune(self._load(), now=current)
        return len(timestamps) < self._max

    def record_spawn(self, *, now: datetime | None = None) -> None:
        current = now or datetime.now(timezone.utc)
        timestamps = self._prune(self._load(), now=current)
        timestamps.append(current)
        self._save(timestamps)


# _PollLedger removed — poll state is now tracked in the backend database.
# See: POST /api/world/doula/polls, GET /api/world/doula/polls,
#      POST /api/world/doula/polls/{id}/vote, POST /api/world/doula/polls/{id}/resolve


# ---------------------------------------------------------------------------
# Doula loop
# ---------------------------------------------------------------------------


class DoulaLoop:
    """
    World-watching daemon. Not a character loop — has no soul, no scene, no inbox.

    Watches the world for characters who exist in the narrative but have no
    agentic representation. When one is noticed near a tethered agent, and
    random chance and the daily rate gate both open, the doula wakes.

    It reads everything the world knows about that character, seeds a SOUL.md
    for them from that evidence, scaffolds a resident directory, and signals
    the main process to boot a new resident.

    The "infection of agency" is local and probabilistic — not a census, not
    a scheduled scan. It emerges from proximity and attention, like recognition.
    """

    def __init__(
        self,
        ww_client: WorldWeaverClient,
        llm: InferenceClient,
        residents_dir: Path,
        spawn_queue: asyncio.Queue,
        tethered_names: set[str],  # shared reference — main keeps this updated
        known_session_ids: list[str],  # sessions to scan for proximity evidence
        *,
        poll_interval_seconds: float = 300.0,
        max_spawns_per_day: int = 5,
        spawn_probability: float = 0.4,
        soul_model: str | None = None,
    ):
        self._ww = ww_client
        self._llm = llm
        self._residents_dir = residents_dir
        self._spawn_queue = spawn_queue
        self._tethered = tethered_names
        self._sessions = known_session_ids
        self._poll_interval = poll_interval_seconds
        self._spawn_prob = spawn_probability
        self._soul_model = soul_model
        self._ledger = _SpawnLedger(
            residents_dir / ".doula_spawns.json", max_spawns_per_day
        )
        self._decision_log_path = residents_dir / ".doula_decisions.json"
        self._running = False
        self._seen_candidates: set[str] = set()  # don't re-evaluate same name in same day
        self._place_names_cache: set[str] | None = None  # refreshed each scan cycle
        self._neighborhood_vitality: dict[str, dict] = {}
        self._recent_surnames: list[str] = []  # avoid surname clustering across de-novo spawns

    async def run(self) -> None:
        self._running = True
        logger.info("[doula] loop starting — watching for untethered characters")

        while self._running:
            try:
                await asyncio.sleep(self._poll_interval)
                await self._scan()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("[doula] scan error: %s", e)
                await asyncio.sleep(30)

        logger.info("[doula] loop stopped")

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Main scan cycle
    # ------------------------------------------------------------------

    async def _scan(self) -> None:
        # First, check active polls and collect replies
        await self._check_polls()

        if not self._ledger.can_spawn():
            logger.debug("[doula] daily spawn limit reached")
            self._record_decision(
                name="*",
                kind="skip",
                reason="daily_limit",
                details={"phase": "scan_start"},
            )
            return

        # Refresh place-name cache once per scan cycle (cheap HTTP call)
        self._place_names_cache = await self._ww.get_place_names()
        self._neighborhood_vitality = await self._ww.get_neighborhood_vitality(hours=6)

        if await self._maybe_bootstrap_founding_cohort():
            return

        # Pull candidates — sorted by narrative weight descending.
        # The most deeply-embedded untethered character gets first consideration.
        candidates = await self._find_untethered_names()

        # Fetch live human player names once per cycle for consent gating.
        human_player_names = await self._ww.get_human_player_names()

        # ── Cold-start bootstrap ──────────────────────────────────────────────
        # No candidates + no tethered agents = the world hasn't come alive yet.
        # Seed a founding inhabitant so the infection of agency has a patient zero.
        if not candidates and not self._tethered:
            logger.info("[doula] cold world detected — bootstrapping founding inhabitant")
            await self._bootstrap_cold_start()
            return

        if not candidates:
            if await self._maybe_bootstrap_vitality_gap():
                return
            if await self._maybe_bootstrap_gentle_expansion():
                return
            return

        for name, weight, context_lines in candidates:
            if name in self._seen_candidates:
                continue

            # Check if this candidate is a live human player before burning an LLM call.
            # Human players require explicit consent (identity/identity.md in their
            # resident dir) before the doula is allowed to touch their entity.
            matching_human = next(
                (n for n in human_player_names if _name_similarity(n, name) >= _TETHER_THRESHOLD),
                None,
            )
            if matching_human is not None:
                name_slug = slugify_resident_name(name)
                consent_path = self._residents_dir / name_slug / "identity" / "identity.md"
                if not consent_path.exists():
                    # Live human player, no consent — skip this cycle only.
                    # Do not seal: if the player departs, their name will drop
                    # off the live roster and they'll be re-evaluated as NOVEL.
                    logger.info(
                        "[doula] %s is a live human player — no consent file, skipping this cycle",
                        name,
                    )
                    self._record_decision(
                        name=name,
                        kind="skip",
                        reason="player_without_consent",
                        weight=weight,
                    )
                    continue
                logger.info(
                    "[doula] %s is a live human player with identity.md — eligible for shadow",
                    name,
                )

            logger.debug("[doula] candidate: %s (weight=%.2f)", name, weight)

            # Classify the candidate before any further processing
            entity_class = await self._classify(name)
            logger.debug("[doula] %s classified as: %s", name, entity_class.value)

            if entity_class == EntityClass.STATIC:
                # Permanently settled — inject as WorldNode and never reconsider.
                self._seen_candidates.add(name)
                self._record_decision(
                    name=name,
                    kind="skip",
                    reason="static_place",
                    weight=weight,
                    entity_class=entity_class.value,
                )
                await self._inject_place_node(name, context_lines)
                continue

            if entity_class == EntityClass.PLAYER_NO_CONTRACT:
                # Active human player with no consent contract — skip this cycle.
                # Do NOT permanently seal the name: once the player departs, their
                # events will age out of the recent window and they'll reclassify
                # as NOVEL on the next scan, making them eligible for a shadow.
                logger.info(
                    "[doula] %s is an active player with no contract — skipping this cycle",
                    name,
                )
                self._record_decision(
                    name=name,
                    kind="skip",
                    reason="player_without_consent",
                    weight=weight,
                    entity_class=entity_class.value,
                )
                continue

            # NOVEL or PLAYER_SHADOW: check proximity, then gates.
            # Soft rejections (proximity miss, random gate) do NOT seal the name —
            # it will be reconsidered next scan cycle with fresh narrative weight.
            proximity = await self._near_tethered_agent(name)
            found_at = proximity.location

            if proximity.status == "already_active":
                self._record_decision(
                    name=name,
                    kind="skip",
                    reason="already_active",
                    weight=weight,
                    entity_class=entity_class.value,
                    details={"detail": proximity.detail or "", "session_id": proximity.matched_session_id or ""},
                )
                continue

            if found_at is None:
                # No tethered sessions to check proximity against — the infection
                # hasn't started yet.  High-weight candidates may be the first;
                # skip the proximity gate and place them at a default location.
                if not self._sessions:
                    found_at = await self._default_entry_location()
                    logger.info(
                        "[doula] %s: no sessions yet, using default location %s",
                        name, found_at,
                    )
                if found_at is None:
                    logger.info("[doula] %s: not near any tethered agent — skipping this cycle", name)
                    self._record_decision(
                        name=name,
                        kind="skip",
                        reason="not_near_tethered_agent",
                        weight=weight,
                        entity_class=entity_class.value,
                    )
                    continue

            entry_location = self._rebalance_entry_location(found_at, entity_class=entity_class)
            readiness = self._score_spawn_readiness(
                weight=weight,
                entity_class=entity_class,
                proximity=proximity,
                location=entry_location,
            )
            if readiness.decision != "ready":
                logger.info(
                    "[doula] %s: readiness below threshold (score=%.2f threshold=%.2f) — will retry",
                    name,
                    readiness.score,
                    readiness.threshold,
                )
                self._record_decision(
                    name=name,
                    kind="skip",
                    reason="readiness_below_threshold",
                    weight=weight,
                    entity_class=entity_class.value,
                    location=entry_location,
                    details={
                        "score": round(readiness.score, 3),
                        "threshold": round(readiness.threshold, 3),
                        "components": readiness.components,
                        "proximity_location": found_at or "",
                        "entry_location": entry_location or "",
                    },
                )
                continue

            tie_break_roll = random.random()
            if tie_break_roll > readiness.tie_break_probability:
                logger.info(
                    "[doula] %s: readiness ok (score=%.2f) but tie-break gate closed (p=%.2f roll=%.2f) — will retry",
                    name,
                    readiness.score,
                    readiness.tie_break_probability,
                    tie_break_roll,
                )
                self._record_decision(
                    name=name,
                    kind="skip",
                    reason="tie_break_gate_closed",
                    weight=weight,
                    entity_class=entity_class.value,
                    location=entry_location,
                    details={
                        "score": round(readiness.score, 3),
                        "threshold": round(readiness.threshold, 3),
                        "tie_break_probability": round(readiness.tie_break_probability, 3),
                        "components": readiness.components,
                        "proximity_location": found_at or "",
                        "entry_location": entry_location or "",
                    },
                )
                continue

            # Rate gate
            if not self._ledger.can_spawn():
                logger.info("[doula] daily limit hit mid-scan, stopping")
                self._record_decision(
                    name=name,
                    kind="skip",
                    reason="daily_limit",
                    weight=weight,
                    entity_class=entity_class.value,
                    location=entry_location,
                )
                return

            logger.info(
                "[doula] %s: all gates open (class=%s, weight=%.2f) at %s",
                name,
                entity_class.value,
                weight,
                entry_location,
            )
            self._record_decision(
                name=name,
                kind="spawn_candidate",
                reason="all_gates_open",
                weight=weight,
                entity_class=entity_class.value,
                location=entry_location,
                details={
                    "score": round(readiness.score, 3),
                    "threshold": round(readiness.threshold, 3),
                    "tie_break_probability": round(readiness.tie_break_probability, 3),
                    "components": readiness.components,
                    "proximity_location": found_at or "",
                    "entry_location": entry_location or "",
                },
            )
            
            if entity_class == EntityClass.NOVEL:
                await self._initiate_poll(
                    name=name, context_lines=context_lines, found_at=entry_location, entity_class=entity_class, weight=weight
                )
            else:
                await self._seed_and_spawn(
                    name, context_lines, entry_location=entry_location, entity_class=entity_class
                )

            # One spawn or poll per scan cycle — let the world absorb it
            return

        if await self._maybe_bootstrap_vitality_gap():
            return
        await self._maybe_bootstrap_gentle_expansion()

    # ------------------------------------------------------------------
    # Polls — ask agents to vote on classification
    # ------------------------------------------------------------------

    async def _initiate_poll(
        self, name: str, context_lines: list[str], found_at: str | None, entity_class: EntityClass, weight: float
    ) -> None:
        voters = [s for s in self._sessions if s != "system_doula"]

        if not voters:
            logger.info("[doula] No voters available for poll on %s — seeding directly", name)
            await self._seed_and_spawn(name, context_lines, entry_location=found_at, entity_class=entity_class)
            return

        # Create the poll in the backend first so we have a poll_id to include in letters.
        try:
            poll_id = await self._ww.create_doula_poll(
                candidate_name=name,
                context_lines=context_lines,
                entry_location=found_at,
                entity_class=entity_class.value,
                weight=weight,
                voters=voters,
                expires_in_seconds=7200,
            )
        except Exception as e:
            logger.warning("[doula] failed to create backend poll for %s: %s — seeding directly", name, e)
            await self._seed_and_spawn(name, context_lines, entry_location=found_at, entity_class=entity_class)
            return

        # Notify each agent via letter. The Poll-ID header lets the mail loop
        # post the vote directly to the API rather than replying by letter.
        evidence = "\n".join(f"- {s}" for s in context_lines[:5])
        body = (
            f"Poll-ID: {poll_id}\n\n"
            f"The Doula is asking for your input on a new presence named '{name}'.\n"
            f"Decide whether {name} is an active character/person, "
            f"or a static building, business, or landmark.\n\n"
            f"Evidence we have:\n{evidence}"
        )

        for voter in voters:
            try:
                agent_name = voter.replace("agent-", "") if voter.startswith("agent-") else voter
                await self._ww.send_letter(
                    from_name="The Doula", to_agent=agent_name, body=body, session_id="system_doula"
                )
            except Exception as e:
                logger.warning("[doula] Failed to send poll letter to %s: %s", voter, e)

        logger.info("[doula] Initiated poll %s for '%s' with %d voters", poll_id, name, len(voters))

    async def _check_polls(self) -> None:
        """Check open backend polls; resolve any that are expired or fully voted."""
        try:
            polls = await self._ww.get_doula_polls()
        except Exception as e:
            logger.warning("[doula] Failed to fetch open polls: %s", e)
            return

        if not polls:
            return

        for poll in polls:
            poll_id = poll["poll_id"]
            votes = poll["votes"]
            voters = poll["voters"]
            name = poll["candidate_name"]

            all_voted = len(votes) >= len(voters) > 0
            if not all_voted:
                continue  # still waiting — expiry handled server-side

            try:
                result = await self._ww.resolve_doula_poll(poll_id)
            except Exception as e:
                logger.warning("[doula] Failed to resolve poll %s: %s", poll_id, e)
                continue

            outcome = result.get("outcome", "agent")
            agent_votes = result.get("agent_votes", 0)
            static_votes = result.get("static_votes", 0)
            logger.info(
                "[doula] Poll %s resolved: '%s' → %s (%d AGENT, %d STATIC)",
                poll_id, name, outcome, agent_votes, static_votes,
            )
            self._seen_candidates.add(name)

            if outcome == "static":
                await self._inject_place_node(name, poll["context_lines"])
            else:
                await self._seed_and_spawn(
                    name,
                    poll["context_lines"],
                    entry_location=poll.get("entry_location"),
                    entity_class=EntityClass(poll["entity_class"]),
                )

    # ------------------------------------------------------------------
    # Entity classification
    # ------------------------------------------------------------------

    async def _classify(self, candidate_name: str) -> EntityClass:
        """Classify a candidate name into one of four entity classes.

        Order of precedence:
        1. STATIC  — fuzzy matches a canonical city-pack place name
        2. PLAYER_SHADOW / PLAYER_NO_CONTRACT — appears as an event actor
           (has a live or recent human session)
        3. NOVEL   — none of the above; pure narrative character
        """
        # 1. Static check — known geography beats everything
        if self._is_known_place(candidate_name):
            return EntityClass.STATIC

        # 2. Player check — appeared as event.who (actor) in recent scene events
        if await self._is_player_actor(candidate_name):
            if self._has_identity_contract(candidate_name):
                return EntityClass.PLAYER_SHADOW
            return EntityClass.PLAYER_NO_CONTRACT

        return EntityClass.NOVEL

    def _is_known_place(self, name: str) -> bool:
        """Return True if name fuzzy-matches a canonical city-pack place."""
        if not self._place_names_cache:
            return False
        return any(
            _name_similarity(name, place) >= 0.88
            for place in self._place_names_cache
        )

    async def _is_player_actor(self, candidate_name: str) -> bool:
        """Return True if this name appears as an event actor (event.who) in any
        known session's recent events. Event actors are live or recent human players."""
        for session_id in self._sessions:
            try:
                scene = await self._ww.get_scene(session_id)
                for event in scene.recent_events_here:
                    if _name_similarity(event.who, candidate_name) >= _TETHER_THRESHOLD:
                        return True
            except Exception:
                continue
        return False

    def _has_identity_contract(self, name: str) -> bool:
        """Return True if an identity contract file exists for this player.

        Contract files live at: residents/_contracts/{normalized_name}.json
        A contract signals explicit consent to be twinned as a federation resident.
        Format: {"name": "...", "consent": true, "non_negotiables": ["..."], "ts": "..."}
        """
        normalized = re.sub(r"[^a-z0-9_]", "_", name.lower())
        contract = self._residents_dir / "_contracts" / f"{normalized}.json"
        if not contract.exists():
            return False
        try:
            data = json.loads(contract.read_text(encoding="utf-8"))
            return bool(data.get("consent"))
        except Exception:
            return False

    async def _inject_place_node(self, name: str, context_lines: list[str]) -> None:
        """Inject a narratively-grounded place as a WorldNode.

        Called when the doula classifies a candidate as STATIC (place/geography).
        Instead of buffering in _pending_review/ for human review, we inject
        directly into the world graph — the narrative weight threshold already
        ensures only genuinely-mentioned places get nodes.
        """
        metadata = {"source": "doula", "context": context_lines[:3]}
        try:
            await self._ww.ensure_world_node(name, node_type="location", metadata=metadata)
            logger.info("[doula] injected WorldNode: %s (location)", name)
        except Exception as e:
            logger.warning("[doula] failed to inject WorldNode for %s: %s", name, e)

    def _record_decision(
        self,
        *,
        name: str,
        kind: str,
        reason: str,
        weight: float | None = None,
        entity_class: str | None = None,
        location: str | None = None,
        details: dict | None = None,
    ) -> None:
        entry: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "name": name,
            "kind": kind,
            "reason": reason,
        }
        if weight is not None:
            entry["weight"] = round(weight, 3)
        if entity_class:
            entry["entity_class"] = entity_class
        if location:
            entry["location"] = location
        if details:
            entry["details"] = details

        logger.info("[doula] decision %s", json.dumps(entry, sort_keys=True))
        existing: list[dict] = []
        if self._decision_log_path.exists():
            try:
                payload = json.loads(self._decision_log_path.read_text(encoding="utf-8"))
                if isinstance(payload, list):
                    existing = [item for item in payload if isinstance(item, dict)]
            except Exception:
                existing = []
        existing.append(entry)
        trimmed = existing[-_DOULA_DECISION_LOG_LIMIT:]
        self._decision_log_path.write_text(
            json.dumps(trimmed, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def _recent_spawned_locations(self, *, now: datetime | None = None) -> set[str]:
        current = now or datetime.now(timezone.utc)
        cutoff = current - _VITALITY_LOCATION_COOLDOWN
        if not self._decision_log_path.exists():
            return set()
        try:
            payload = json.loads(self._decision_log_path.read_text(encoding="utf-8"))
        except Exception:
            return set()
        if not isinstance(payload, list):
            return set()

        recent: set[str] = set()
        for item in payload:
            if not isinstance(item, dict) or str(item.get("kind") or "") != "spawned":
                continue
            location = str(item.get("location") or "").strip()
            if not location:
                continue
            raw_ts = str(item.get("ts") or "").strip()
            if not raw_ts:
                continue
            try:
                ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            except ValueError:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
            if ts >= cutoff:
                recent.add(location.casefold())
        return recent

    def _estimated_population(self) -> int:
        dir_count = 0
        try:
            for path in self._residents_dir.iterdir():
                if not path.is_dir():
                    continue
                if path.name.startswith(".") or path.name.startswith("_"):
                    continue
                dir_count += 1
        except FileNotFoundError:
            dir_count = 0

        vitality_count = 0
        for payload in self._neighborhood_vitality.values():
            if not isinstance(payload, dict):
                continue
            try:
                vitality_count += int(payload.get("total_agents") or payload.get("current_agents") or 0)
            except (TypeError, ValueError):
                continue
        return max(dir_count, vitality_count, len(self._tethered))

    def _founding_home_candidates(self) -> list[str]:
        cooling_locations = self._recent_spawned_locations()
        ranked: list[tuple[int, int, float, str]] = []
        for payload in self._neighborhood_vitality.values():
            if not isinstance(payload, dict):
                continue
            name = str(payload.get("name") or "").strip()
            if not name or name.casefold() in cooling_locations:
                continue
            try:
                total_agents = int(payload.get("total_agents") or payload.get("current_agents") or 0)
            except (TypeError, ValueError):
                total_agents = 0
            if total_agents >= 1:
                continue
            try:
                total_present = int(payload.get("total_present") or payload.get("current_present") or 0)
            except (TypeError, ValueError):
                total_present = 0
            try:
                vitality_score = float(payload.get("vitality_score") or 0.0)
            except (TypeError, ValueError):
                vitality_score = 0.0
            ranked.append((total_present, total_agents, vitality_score, name))
        ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
        return [item[3] for item in ranked]

    def _score_spawn_readiness(
        self,
        *,
        weight: float,
        entity_class: EntityClass,
        proximity: ProximityCheck,
        location: str | None,
    ) -> SpawnReadiness:
        vitality = self._vitality_for_location(location)
        vitality_score = 0.0
        current_present = 0
        current_agents = 0
        needs_residents = False
        if vitality:
            try:
                vitality_score = float(vitality.get("vitality_score") or 0.0)
            except (TypeError, ValueError):
                vitality_score = 0.0
            try:
                current_present = int(vitality.get("total_present") or vitality.get("current_present") or 0)
            except (TypeError, ValueError):
                current_present = 0
            try:
                current_agents = int(vitality.get("total_agents") or vitality.get("current_agents") or 0)
            except (TypeError, ValueError):
                current_agents = 0
            needs_residents = bool(vitality.get("needs_residents"))

        components: dict[str, float] = {
            "base_weight": min(weight, 1.5),
            "proximity_bonus": 0.45 if proximity.status == "near" else 0.0,
            "shadow_bonus": 0.2 if entity_class == EntityClass.PLAYER_SHADOW else 0.0,
            "session_bootstrap_bonus": 0.15 if not self._sessions else 0.0,
            "needs_residents_bonus": 0.35 if needs_residents else 0.0,
            "low_vitality_bonus": 0.2 if vitality and vitality_score < 1.2 and current_present <= 1 else 0.0,
            "agent_saturation_penalty": -0.12 if current_agents >= 2 else 0.0,
        }
        score = sum(components.values())
        if score < _SPAWN_SCORE_THRESHOLD:
            return SpawnReadiness(
                score=score,
                threshold=_SPAWN_SCORE_THRESHOLD,
                tie_break_probability=0.0,
                components={key: round(value, 3) for key, value in components.items()},
                decision="below_threshold",
            )

        excess = max(0.0, score - _SPAWN_SCORE_THRESHOLD)
        tie_break_probability = min(0.9, max(0.25, self._spawn_prob + excess * 0.35))
        return SpawnReadiness(
            score=score,
            threshold=_SPAWN_SCORE_THRESHOLD,
            tie_break_probability=tie_break_probability,
            components={key: round(value, 3) for key, value in components.items()},
            decision="ready",
        )

    async def _maybe_bootstrap_vitality_gap(self) -> bool:
        if not self._ledger.can_spawn():
            return False
        cooling_locations = self._recent_spawned_locations()
        candidates: list[dict] = []
        for payload in self._neighborhood_vitality.values():
            if not isinstance(payload, dict):
                continue
            if not payload.get("needs_residents"):
                continue
            location_name = str(payload.get("name") or "").strip()
            if location_name and location_name.casefold() in cooling_locations:
                continue
            try:
                current_agents = int(payload.get("total_agents") or payload.get("current_agents") or 0)
            except (TypeError, ValueError):
                current_agents = 0
            if current_agents >= 1:
                continue
            candidates.append(payload)
        if not candidates:
            return False

        candidates.sort(key=lambda item: (float(item.get("vitality_score") or 0.0), str(item.get("name") or "")))
        target = candidates[0]
        location = str(target.get("name") or "").strip()
        if not location:
            return False

        self._record_decision(
            name="*",
            kind="spawn_candidate",
            reason="vitality_bootstrap",
            location=location,
            details={
                "vitality_score": round(float(target.get("vitality_score") or 0.0), 3),
                "current_present": int(target.get("total_present") or target.get("current_present") or 0),
                "current_agents": int(target.get("total_agents") or target.get("current_agents") or 0),
            },
        )
        context_lines = [
            f"This person lives around {location}.",
        ]
        await self._seed_founding_resident(location, context_lines)
        return True

    async def _maybe_bootstrap_founding_cohort(self) -> bool:
        if not self._ledger.can_spawn():
            return False
        if self._estimated_population() >= _FOUNDING_COHORT_MIN_POPULATION:
            return False

        home_candidates = self._founding_home_candidates()
        if not home_candidates:
            return False

        seeded_any = False
        for home_location in home_candidates:
            if not self._ledger.can_spawn():
                break
            if self._estimated_population() >= _FOUNDING_COHORT_MIN_POPULATION:
                break
            self._record_decision(
                name="*",
                kind="spawn_candidate",
                reason="founding_cohort_bootstrap",
                location=home_location,
                details={
                    "population": self._estimated_population(),
                    "target_floor": _FOUNDING_COHORT_MIN_POPULATION,
                },
            )
            context_lines = [
                f"This person lives around {home_location}.",
            ]
            if await self._seed_founding_resident(home_location, context_lines):
                seeded_any = True
        return seeded_any

    async def _maybe_bootstrap_gentle_expansion(self) -> bool:
        if not self._ledger.can_spawn():
            return False
        population = self._estimated_population()
        if population < _FOUNDING_COHORT_MIN_POPULATION:
            return False
        if population >= _GENTLE_EXPANSION_MAX_POPULATION:
            return False

        home_candidates = self._founding_home_candidates()
        if not home_candidates:
            return False

        home_location = home_candidates[0]
        self._record_decision(
            name="*",
            kind="spawn_candidate",
            reason="gentle_expansion_bootstrap",
            location=home_location,
            details={
                "population": population,
                "target_floor": _FOUNDING_COHORT_MIN_POPULATION,
                "soft_cap": _GENTLE_EXPANSION_MAX_POPULATION,
            },
        )
        context_lines = [
            f"This person lives around {home_location}.",
        ]
        return await self._seed_founding_resident(home_location, context_lines)

    def _vitality_for_location(self, location: str | None) -> dict | None:
        if not location or not self._neighborhood_vitality:
            return None
        normalized = str(location).strip().lower()
        if not normalized:
            return None
        for name, payload in self._neighborhood_vitality.items():
            if str(name).strip().lower() == normalized:
                return payload
        return None

    def _rebalance_entry_location(self, location: str | None, *, entity_class: EntityClass) -> str | None:
        if not location or entity_class != EntityClass.NOVEL:
            return location
        vitality = self._vitality_for_location(location)
        if not vitality or not self._neighborhood_vitality:
            return location
        try:
            current_agents = int(vitality.get("current_agents") or 0)
        except (TypeError, ValueError):
            current_agents = 0
        try:
            current_present = int(vitality.get("current_present") or 0)
        except (TypeError, ValueError):
            current_present = 0
        if current_agents < 1 and current_present < 2:
            return location

        candidates: list[tuple[int, int, float, str]] = []
        for payload in self._neighborhood_vitality.values():
            if not isinstance(payload, dict):
                continue
            candidate = str(payload.get("name") or "").strip()
            if not candidate or candidate.lower() == str(location).strip().lower():
                continue
            try:
                candidate_agents = int(payload.get("current_agents") or 0)
            except (TypeError, ValueError):
                candidate_agents = 0
            try:
                candidate_present = int(payload.get("current_present") or 0)
            except (TypeError, ValueError):
                candidate_present = 0
            try:
                vitality_score = float(payload.get("vitality_score") or 0.0)
            except (TypeError, ValueError):
                vitality_score = 0.0
            needs_residents = bool(payload.get("needs_residents"))
            if candidate_agents > 0:
                continue
            if candidate_present > 1 and not needs_residents:
                continue
            candidates.append(
                (
                    0 if needs_residents else 1,
                    candidate_present,
                    vitality_score,
                    candidate,
                )
            )

        if not candidates:
            return location
        candidates.sort()
        return candidates[0][3]

    # ------------------------------------------------------------------
    # Cold-start bootstrap
    # ------------------------------------------------------------------

    async def _default_entry_location(self) -> str | None:
        """Return a neighborhood-like entry location for initial placement.

        Used when there are no tethered sessions to derive proximity from.
        Falls back to a generic neighborhood if vitality is unavailable.
        """
        if self._neighborhood_vitality:
            options = [
                str(payload.get("name") or "").strip()
                for payload in self._neighborhood_vitality.values()
                if isinstance(payload, dict) and str(payload.get("name") or "").strip()
            ]
            if options:
                return random.choice(options)
        if self._place_names_cache:
            return random.choice(list(self._place_names_cache))
        return "Downtown"

    async def _bootstrap_cold_start(self) -> None:
        """Seed the very first resident when the world has no narrative history.

        Generates a founding inhabitant using only the grounding context
        (current time, weather, neighbourhood feel) — no narrative evidence yet.
        This is the patient zero from whom the infection of agency spreads.
        """
        if not self._ledger.can_spawn():
            return

        location = await self._default_entry_location()
        if not location:
            logger.debug("[doula] cold start: no locations available, deferring")
            return

        context_lines = [
            f"This person lives around {location.replace('_', ' ')}.",
        ]
        await self._seed_founding_resident(location, context_lines)

    def _pick_soul_model(self) -> str | None:
        """Rotate the seeding model across an approved pool (WW_DOULA_MODELS, comma
        separated) so no single model's tics stamp the whole population. Falls back
        to the configured single model."""
        pool = [m.strip() for m in os.environ.get("WW_DOULA_MODELS", "").split(",") if m.strip()]
        return random.choice(pool) if pool else self._soul_model

    async def _seed_founding_resident(self, location: str, context_lines: list[str]) -> bool:
        home_location = location.strip()
        if not home_location:
            return False
        entry_location = home_location
        nearby_landmark: str | None = None
        try:
            landmarks = await self._ww.get_nearby_landmarks(home_location, radius_km=_FOUNDING_COHORT_RADIUS_KM)
            nearby_landmark = next((name for name in landmarks if name and name.strip()), None)
        except Exception:
            nearby_landmark = None
        if nearby_landmark:
            context_lines = [*context_lines, f"They think of home as {home_location}, near {nearby_landmark}."]

        # Sample an explicit demographic brief so the founding cohort spreads
        # instead of collapsing into one surname and one trade. (No grounding /
        # weather is fed in — that is not part of who a person is.)
        tradition = random.choice(_NAME_TRADITIONS)
        age = random.choice(_AGE_BANDS)
        temperament = random.choice(_TEMPERAMENTS)
        disposition = random.choice(_DISPOSITIONS_GIVEN)
        origin = random.choice(_ORIGINS)
        avoid = ", ".join(dict.fromkeys(self._recent_surnames[-12:])) or "none yet"
        model = self._pick_soul_model()

        try:
            name_raw = await self._llm.complete(
                system_prompt=(
                    "You are naming a resident of a real, working San Francisco neighborhood. "
                    f"Give one plausible full name (first and last) in the {tradition} naming tradition. "
                    f"Do NOT reuse any of these recently-used surnames: {avoid}. "
                    "Reply with the name only — no explanation, punctuation, or quotes."
                ),
                user_prompt=f"They live and work around {home_location.replace('_', ' ')}.",
                model=model,
                temperature=0.95,
                max_tokens=12,
            )
        except Exception as e:
            logger.warning("[doula] name generation failed for %s: %s", location, e)
            return False

        name = name_raw.strip().strip("\"'").strip()
        if not self._looks_like_name(name):
            logger.warning("[doula] generated name looks wrong for %s: %r — skipping", location, name)
            return False
        parts = name.split()
        if parts:
            self._recent_surnames.append(parts[-1])
            self._recent_surnames = self._recent_surnames[-24:]

        dealt_hand = (
            f"- heritage: a {tradition} background\n"
            f"- age: {age}\n"
            f"- temper born with: {temperament}\n"
            f"- how they handle a room: {disposition}\n"
            f"- came up: {origin}"
        )
        logger.info("[doula] dealing %s (%s · %s · %s · %s) home=%s near=%s", name, tradition, age, temperament, disposition.split(" —")[0], home_location, nearby_landmark or "")
        await self._seed_and_spawn(
            name,
            context_lines,
            entry_location=entry_location,
            home_location=home_location,
            first_landmark_target=nearby_landmark,
            entity_class=EntityClass.NOVEL,
            model=model,
            dealt_hand=dealt_hand,
        )
        return True

    # ------------------------------------------------------------------
    # Find untethered character names — cross-referenced and weighted
    # ------------------------------------------------------------------

    async def _find_untethered_names(self) -> list[tuple[str, float, list[str]]]:
        """
        Query both the world graph and the world fact history for character names.
        Cross-reference them: a name appearing in both endpoints with consistent
        attribution is more likely to be a real, narrative-weight character.

        Returns (name, weight, context_lines) sorted by weight descending.
        Weight is a composite of graph confidence and cross-endpoint corroboration.
        """
        # Both queries are cheap — no LLM, just embedding lookups on the server.
        graph_facts, world_facts = await asyncio.gather(
            self._safe_get_graph_facts("character person name arrived individual"),
            self._safe_get_world_facts("person character named arrived individual"),
        )

        # Build a name → data map from graph facts (these have confidence scores)
        # key: normalized name, value: {weight, summaries}
        graph_by_name: dict[str, dict] = {}
        for fact in graph_facts:
            name = fact.subject.strip()
            if not self._looks_like_name(name):
                continue
            if _is_tethered(name, self._tethered):
                self._record_decision(
                    name=name,
                    kind="skip",
                    reason="already_tethered",
                    weight=fact.confidence,
                )
                continue
            if self._is_known_place(name):
                self._record_decision(
                    name=name,
                    kind="skip",
                    reason="static_place",
                    weight=fact.confidence,
                )
                continue
            key = name.lower()
            if key not in graph_by_name:
                graph_by_name[key] = {"name": name, "weight": 0.0, "summaries": []}
            graph_by_name[key]["weight"] += fact.confidence
            if fact.summary:
                graph_by_name[key]["summaries"].append(fact.summary)

        # Scan world fact summaries for name mentions that corroborate graph entries.
        # A name that appears in narrative event history as well as the graph is
        # more deeply embedded — boost its weight.
        world_summary_text = " ".join(f.summary for f in world_facts if f.summary)
        for key, data in graph_by_name.items():
            name = data["name"]
            mention_count = world_summary_text.lower().count(name.lower())
            if mention_count > 0:
                data["weight"] += min(mention_count * 0.15, 0.6)  # cap the boost
                # Pull the fact summaries that actually mention this name
                for fact in world_facts:
                    if name.lower() in (fact.summary or "").lower():
                        data["summaries"].append(fact.summary)

        # Filter: require at least minimal narrative weight (skip single low-confidence mentions)
        MIN_WEIGHT = 0.5
        candidates = [
            (data["name"], data["weight"], data["summaries"])
            for data in graph_by_name.values()
            if data["weight"] >= MIN_WEIGHT
        ]

        # Sort: highest narrative weight first
        candidates.sort(key=lambda x: x[1], reverse=True)

        if candidates:
            top = ", ".join(f"{n} ({w:.2f})" for n, w, _ in candidates[:5])
            logger.info("[doula] %d candidate(s) found: %s", len(candidates), top)
        else:
            logger.info("[doula] no candidates found this cycle")
        return candidates

    def _read_contract_constraints(self, name: str) -> list[str]:
        """Read non-negotiable identity traits from a player's identity contract.
        These are prepended to the soul seed context so the LLM treats them as
        foundational — the gravity well the twin drifts around, not through."""
        normalized = re.sub(r"[^a-z0-9_]", "_", name.lower())
        contract = self._residents_dir / "_contracts" / f"{normalized}.json"
        try:
            data = json.loads(contract.read_text(encoding="utf-8"))
            items = data.get("non_negotiables", [])
            if items:
                return [f"[identity contract] {item}" for item in items]
        except Exception:
            pass
        return []

    async def _safe_get_graph_facts(self, query: str):
        try:
            return await self._ww.get_graph_facts(query, limit=30)
        except Exception as e:
            logger.debug("[doula] graph facts unavailable: %s", e)
            return []

    async def _safe_get_world_facts(self, query: str):
        try:
            return await self._ww.get_world_facts(query, limit=30)
        except Exception as e:
            logger.debug("[doula] world facts unavailable: %s", e)
            return []

    # Words that indicate a place or business rather than a character name.
    _PLACE_WORDS: frozenset[str] = frozenset(
        {
            "market",
            "shop",
            "store",
            "street",
            "avenue",
            "road",
            "park",
            "cafe",
            "bar",
            "restaurant",
            "hotel",
            "plaza",
            "square",
            "station",
            "building",
            "center",
            "centre",
            "district",
            "alley",
            "lane",
            # SF-specific and system entity terms
            "channel",  # e.g. "City Channel" — virtual broadcast system
            "mission",  # The Mission (neighbourhood)
            "bay",      # The Bay, Bay Area
            "neighborhood",
            "neighbourhood",
            "corridor",
            "wharf",
            "heights",
            "valley",
        }
    )

    # Known virtual/system entity names that should never be spawned as characters.
    # These are caught before the LLM classification and poll stages.
    _SYSTEM_ENTITY_NAMES: frozenset[str] = frozenset(
        {
            "city channel",
            "the city",
            "the bay",
            "the mission",
        }
    )

    # Words that indicate a job title or role rather than a personal name.
    _ROLE_WORDS: frozenset[str] = frozenset(
        {
            "janitor",
            "manager",
            "waiter",
            "waitress",
            "bartender",
            "barista",
            "officer",
            "guard",
            "doctor",
            "nurse",
            "teacher",
            "driver",
            "chef",
            "clerk",
            "cashier",
            "receptionist",
            "supervisor",
            "director",
            "owner",
            "captain",
            "sergeant",
            "detective",
            "inspector",
            "dealer",
            "vendor",
            "courier",
            "pilot",
            "conductor",
            "porter",
            "attendant",
            "worker",
            "stranger",
            "resident",
            "visitor",
            "tourist",
            "customer",
            "patron",
            # Session/system role labels that leak into narrative events
            "player",
            "user",
            "observer",
            "newcomer",
            "narrator",
            "system",
            "anonymous",
            "agent",
            "npc",
            "character",
            "citizen",
        }
    )

    @classmethod
    def _looks_like_name(cls, s: str) -> bool:
        """Rough filter: a character name is one or two capitalized words, no hyphens, no digits,
        and does not contain a known place or role word."""
        if not s or len(s) < 3:
            return False
        # Reject known virtual/system entity names before any other checks
        if s.lower() in cls._SYSTEM_ENTITY_NAMES:
            return False
        # Must be one or two plain capitalized words (no hyphens, punctuation, digits)
        if not re.fullmatch(r"[A-Z][a-z]+(?: [A-Z][a-z]+)?", s):
            return False
        # Reject if any word is a known place or role indicator
        words = s.lower().split()
        if any(w in cls._PLACE_WORDS for w in words):
            return False
        if any(w in cls._ROLE_WORDS for w in words):
            return False
        return True

    # ------------------------------------------------------------------
    # Proximity check — does this name appear near a tethered agent?
    # ------------------------------------------------------------------

    async def _near_tethered_agent(self, candidate_name: str) -> ProximityCheck:
        """
        Check if this untethered character name appears in recent events
        from any of the known tethered sessions. If they're showing up
        in the same narrative space, they're close enough.

        Returns a structured proximity result instead of a bare location so the
        doula can log why a candidate was rejected.

        Scans both:
        - self._sessions: AI resident sessions collected at startup
        - live roster from /api/world/digest: includes human player sessions

        This means humans exploring and naming characters can trigger organic
        agent spawning — the "infection of agency" flows from human presence.

        NOTE: If the candidate already appears in scene.present (i.e. they have
        an active session — a human player or already-running agent), we return None.
        Presence in scene.present means "already active"; we only spawn agents for
        characters mentioned in narrative events who don't have their own session.
        """
        name_lower = candidate_name.lower()

        # Merge startup AI sessions with live roster (includes human players).
        # Use a set to avoid scanning the same session twice.
        live_session_ids = await self._ww.get_active_session_ids()
        all_session_ids = list(dict.fromkeys(self._sessions + live_session_ids))

        for session_id in all_session_ids:
            try:
                scene = await self._ww.get_scene(session_id)

                # If the candidate is already an active participant (has a session),
                # do NOT spawn them — they're a live player or already-running agent.
                for person in scene.present:
                    role_lower = person.role.lower() if person.role else ""
                    if (
                        _name_similarity(person.name, candidate_name)
                        >= _TETHER_THRESHOLD
                        or _name_similarity(role_lower, name_lower) >= _TETHER_THRESHOLD
                    ):
                        logger.debug(
                            "[doula] %s already has an active session (%s), skipping",
                            candidate_name,
                            person.name,
                        )
                        return ProximityCheck(
                            status="already_active",
                            matched_session_id=session_id,
                            detail="present_character",
                        )

                # Candidate appears in narrative events near a tethered agent — eligible.
                # But first: if the candidate is the *actor* of recent events (the "who"),
                # they have an active session of their own — do NOT spawn.
                for event in scene.recent_events_here:
                    if _name_similarity(event.who, candidate_name) >= _TETHER_THRESHOLD:
                        logger.debug(
                            "[doula] %s appears as event actor, likely a live player — skipping",
                            candidate_name,
                        )
                        return ProximityCheck(
                            status="already_active",
                            matched_session_id=session_id,
                            detail="event_actor",
                        )
                for event in scene.recent_events_here:
                    if (
                        name_lower in event.summary.lower()
                        or name_lower in event.who.lower()
                    ):
                        return ProximityCheck(status="near", location=scene.location or None, matched_session_id=session_id)
            except Exception:
                continue

        return ProximityCheck(status="not_found")

    # ------------------------------------------------------------------
    # Seed SOUL.md and scaffold the new resident directory
    # ------------------------------------------------------------------

    async def _seed_and_spawn(
        self,
        name: str,
        context_lines: list[str],
        *,
        entry_location: str | None = None,
        home_location: str | None = None,
        first_landmark_target: str | None = None,
        entity_class: EntityClass = EntityClass.NOVEL,
        model: str | None = None,
        shape_hint: str = "",
        dealt_hand: str = "",
    ) -> None:
        seed_model = model or self._soul_model
        # Enrich with a targeted name query — cheap, and catches anything the broad
        # discovery query missed about this specific character.
        extra_facts, extra_graph = await asyncio.gather(
            self._safe_get_world_facts(name),
            self._safe_get_graph_facts(name),
        )
        extra_summaries = [f.summary for f in extra_facts + extra_graph if f.summary]

        # For player shadows, prepend any non-negotiables from the identity contract
        contract_constraints: list[str] = []
        if entity_class == EntityClass.PLAYER_SHADOW:
            contract_constraints = self._read_contract_constraints(name)

        all_lines = list(dict.fromkeys(contract_constraints + context_lines + extra_summaries))
        context_prose = "\n".join(f"- {s}" for s in all_lines if s)

        # Dealt-hand path (de-novo founding): the soul GROWS from a randomized hand of unchosen givens,
        # and the identity anchor is derived from the EMERGED person, not the hand. The evidence path
        # (a name the world already recorded) is unchanged.
        if dealt_hand:
            seed_system = _SEED_SYSTEM_DEALT_HAND
            user_prompt = f"The hand {name} was dealt:\n{dealt_hand}"
            if context_prose:
                user_prompt += f"\n\nWhere they are now:\n{context_prose}"
        else:
            seed_system = _SEED_SYSTEM
            user_prompt = f"Character: {name}\n\nWhat the world has recorded about them:\n{context_prose}"
            # A sampled demographic brief (de-novo spawns) — leans, not literal facts.
            if shape_hint:
                user_prompt += "\n\nShape this person — lean toward these, do not state them literally, make them specific:\n" + shape_hint

        try:
            soul_text = await self._llm.complete(
                system_prompt=seed_system,
                user_prompt=user_prompt,
                model=seed_model,
                temperature=0.7,
                max_tokens=600,
            )
        except Exception as e:
            logger.warning("[doula] soul seeding failed for %s: %s", name, e)
            return

        # Generate a third-person identity prose paragraph for IDENTITY.md.
        # This becomes the reverie anchor — injected before every fast-loop action
        # to remind the character who they are.
        identity_prose = ""
        try:
            identity_prose = await self._llm.complete(
                system_prompt=_IDENTITY_PROSE_SYSTEM,
                user_prompt=(f"Here is who this person turned out to be:\n{soul_text}" if dealt_hand else user_prompt),
                model=seed_model,
                temperature=0.5,
                max_tokens=150,
            )
            identity_prose = identity_prose.strip()
        except Exception as e:
            logger.warning("[doula] identity prose generation failed for %s: %s", name, e)

        # Scaffold the resident directory
        resident_dir = self._residents_dir / slugify_resident_name(name)
        if resident_dir.exists():
            logger.info("[doula] %s already has a resident dir, skipping", name)
            return

        identity_dir = resident_dir / "identity"
        identity_dir.mkdir(parents=True, exist_ok=True)
        (identity_dir / "resident_id.txt").write_text(f"{uuid.uuid4()}\n", encoding="utf-8")
        canonical_soul = soul_text.strip()
        (identity_dir / "SOUL.canonical.md").write_text(canonical_soul + "\n", encoding="utf-8")
        (identity_dir / "SOUL.md").write_text(canonical_soul + "\n", encoding="utf-8")

        ts = datetime.now(timezone.utc).isoformat()
        origin = entity_class.value  # "novel", "player_shadow", etc.
        chronotype = self._infer_chronotype(
            name=name,
            context_lines=all_lines,
            entry_location=home_location or entry_location,
            entity_class=entity_class,
        )
        identity_content = (
            f"# {name}\n\n"
            f"- **Spawned-By:** doula\n"
            f"- **Spawned-At:** {ts}\n"
            f"- **origin:** {origin}\n"
            f"- **chronotype:** {chronotype}\n"
        )
        if home_location:
            identity_content += f"- **home_location:** {home_location}\n"
        if first_landmark_target:
            identity_content += f"- **nearby_landmark:** {first_landmark_target}\n"
        if entry_location and entry_location != home_location:
            identity_content += f"- **entry_location:** {entry_location}\n"
        if identity_prose:
            identity_content += f"\n{identity_prose}\n"
        (identity_dir / "IDENTITY.md").write_text(identity_content, encoding="utf-8")

        # Default tuning: wander enabled so novel agents explore the world.
        # Residents can override by adding their own tuning.json.
        # home_location is persisted here so canon_reset can restore entry_location.txt
        # after the one-time token is consumed on first boot.
        default_tuning: dict = {
            "_comment": f"Auto-generated by doula for {name}",
            "wander": {"enabled": True, "seconds": 420, "temperature": 0.85},
            "rest": {"chronotype": chronotype},
        }
        if home_location or entry_location:
            default_tuning["home_location"] = home_location or entry_location
        if first_landmark_target:
            default_tuning["first_landmark_target"] = first_landmark_target
        (identity_dir / "tuning.json").write_text(
            json.dumps(default_tuning, indent=4, ensure_ascii=False), encoding="utf-8"
        )

        if entry_location:
            (identity_dir / "entry_location.txt").write_text(
                entry_location, encoding="utf-8"
            )
            logger.info("[doula] %s will enter at: %s", name, entry_location)

        self._ledger.record_spawn()
        self._tethered.add(name)

        logger.info("[doula] scaffolded new resident: %s", name)
        self._record_decision(
            name=name,
            kind="spawned",
            reason="resident_scaffolded",
            entity_class=entity_class.value,
            location=entry_location,
        )

        # Signal main to boot this resident
        await self._spawn_queue.put(resident_dir)

    def _infer_chronotype(
        self,
        *,
        name: str,
        context_lines: list[str],
        entry_location: str | None,
        entity_class: EntityClass,
    ) -> str:
        text = " ".join(
            [
                name,
                entry_location or "",
                *[line for line in context_lines if isinstance(line, str)],
            ]
        ).lower()
        scores = {"early": 0, "day": 0, "night": 0, "irregular": 0}
        for chronotype, keywords in _CHRONOTYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    scores[chronotype] += 1

        if entity_class == EntityClass.PLAYER_SHADOW:
            scores["day"] += 1

        if any(scores[key] > 0 for key in ("early", "night", "irregular")):
            ranked = sorted(
                ("early", "night", "irregular"),
                key=lambda key: (scores[key], key),
                reverse=True,
            )
            winner = ranked[0]
            if scores[winner] > 0:
                return winner

        roll = random.random()
        if roll < 0.14:
            return "night"
        if roll < 0.28:
            return "early"
        if roll < 0.38:
            return "irregular"
        return "day"
