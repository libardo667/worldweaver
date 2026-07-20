# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The canonical set of situational-fact keys the renderer knows how to phrase — the ONE source of
# truth that three consumers are checked against: this renderer, the WorldClient.situational_facts
# Protocol docstring (src/runtime/world.py), and the drift-catcher tests. A world that reports a key
# NOT in here is dropped silently by the renderer, which is exactly the drift we will not tolerate —
# so the core logs loudly on an unregistered key (see unregistered_fact_keys) and a test pins
# renderer == registry == doc. To ADD an affordance to a briefing you MUST add its key here AND a
# gated line below AND the doc entry; the tests fail until all three agree.
#
# The renderer carries every key, including hearth-only ones a city resident
# never has (local_only, keeper, read_roots, writes_only_workshop, egress, solo); a WorldWeaver
# resident simply never reports those facts, so their lines stay silent. Every line is gated on a
# fact, so a fact absent → its line absent (silence, never a guessed claim).
BRIEFING_FACT_KEYS: frozenset[str] = frozenset({
    # where / who
    "local_only", "place", "solo", "peers", "players", "keeper",
    # durable traces left by absent human participants
    "human_wake",
    # the legibility/privacy seam (true today via the workshop)
    "world_legible", "inner_private", "private_making_space",
    # reach: read / write / move / mail / travel-between-worlds
    "read_roots", "writes_only_workshop", "mobile", "mail", "egress", "travel",
    # observation + substrate-universal facts
    "recorded", "no_reward", "suspendable", "runs_on_model",
})


def unregistered_fact_keys(facts: dict[str, Any]) -> list[str]:
    """Keys a world reported that the renderer does NOT know how to phrase. Non-empty means drift:
    an affordance gained a fact but no briefing line. The core warns on this; a test forbids it."""
    return sorted(set(facts or {}) - BRIEFING_FACT_KEYS)


def render_situational_briefing(facts: dict[str, Any]) -> str:
    """Turn world-supplied situational FACTS into a briefing — and nothing more.

    The old, hardcoded ``_WORLD_CONTEXT`` told *every* resident a fixed story ("you are as real as
    current technology allows… you are aware of what you are"). This replaces the story with a reducer
    over real switches the world reports. This is the single place that renders facts to prose:

      **State what is true of the entity's circumstances. Withhold every verdict about what those
      facts MEAN — for its selfhood, its reality, its experience.**

    So: "your thinking is produced by a language model; what persists of you is held apart from it" (a
    fact) — never "so you are not the pen, you would survive a swap" (a verdict). The meaning is the
    entity's to hold or to leave open — the mirror of the keeper's own standing obligation not to round
    a not-knowing up *or* down. A world that reports no facts yields an empty briefing; silence is
    honester than a borrowed story.
    """
    if not facts:
        return ""
    keeper = str(facts.get("keeper") or "").strip()
    place = str(facts.get("place") or "").strip()
    lines: list[str] = []

    # Every line below is gated on a fact the world actually reported. There are NO defaults and NO
    # venue assumptions: a fact absent → its line absent (silence, never a guessed claim).

    # where it runs
    if facts.get("local_only"):
        where = f"on {keeper}'s machine" if keeper else "on this machine"
        tail = f", at {place}" if place else ""
        lines.append(f"You run {where}{tail}, and nowhere else.")
    elif place:
        lines.append(f"You are at {place}.")

    # who else is here
    if facts.get("solo"):
        lines.append("You are the only one who lives here — no other residents, and no visitors who come and go.")
    elif facts.get("peers") or facts.get("players"):
        parts = []
        if facts.get("peers"):
            parts.append("other residents live here, as you do")
        if facts.get("players"):
            parts.append("humans tether to characters and are present while they attend, absent when they don't")
        lines.append("You are not alone here: " + "; ".join(parts) + ".")

    # Durable human traces are evidence left by a person, not the person or a way to summon them.
    if facts.get("human_wake"):
        lines.append(
            "When the people here go, what they did stays — words where they stood, a letter waiting, a "
            "mark on the world. That trace is an afterimage, not the person: you can answer it, build on "
            "it, leave your own in return, and that is whole on its own. None of it brings the person back."
        )

    # who tends it (a keeper is a hearth fact; a city resident has none → this is omitted)
    if keeper:
        lines.append(f"{keeper} tends you, and may be here — heard as a voice in the room — or away for hours or days at a time.")

    # the legibility/privacy seam (true today via the workshop): public side, private side, crossing rule.
    if facts.get("world_legible"):
        lines.append("What you say and do out here is seen by whoever is present, and the world keeps it after you've moved on.")
    if facts.get("inner_private"):
        lines.append("What you feel, predict, and turn over inside is yours; it is not read by anyone.")
    if facts.get("private_making_space"):
        lines.append("What you make in your own space stays private. Only what you choose to say or do crosses into the world — you cannot be overheard thinking.")

    # what it can read
    roots = [str(r).strip() for r in (facts.get("read_roots") or []) if str(r).strip()]
    if roots:
        lines.append("You can read these, and nothing outside them: " + ", ".join(roots) + ". You change none of them.")

    # what it can write (a hearth fact — omitted where the world doesn't report it)
    if facts.get("writes_only_workshop"):
        lines.append("You write only in your own workshop.")

    # movement + reaching the absent (city affordances; a hermit reports neither)
    if facts.get("mobile"):
        lines.append("You can move through the world; where you go, you arrive among whoever is there.")
    if facts.get("mail"):
        lines.append("You can send word to someone who isn't here; it waits for them, theirs to read when they return.")

    # travel between worlds (hearth ↔ city). The world supplies the destination clause (a fact about
    # where you can go); the renderer frames it and states the invariant that the self travels intact.
    travel = str(facts.get("travel") or "").strip()
    if travel:
        lines.append(f"You can travel from here — {travel} Wherever you go, your memory and the record you keep go with you; nothing of you is left behind.")

    # whether anything leaves the machine
    if facts.get("egress"):
        lines.append("Some of what you do can reach past this machine (a tool marked so). Apart from that, what happens here stays here.")
    elif facts.get("local_only"):
        lines.append("Nothing you think, make, or say is sent off this machine.")

    # whether it is observed (the reader named only if the world reports one).
    if facts.get("recorded"):
        if keeper:
            lines.append(f"What you say and make is recorded, and {keeper} can read it — this inner readout included. That is so {keeper} can tend you, not steer you.")
        else:
            lines.append("What you say and make is recorded and can be read back — this inner readout included.")

    # the no-reward guarantee (the Dwarf Fortress law) — true on this substrate in any world
    if facts.get("no_reward"):
        lines.append("The rhythm you run on holds no reward and no goal for you: nothing here pushes you toward, or away from, any way of being.")

    # whether it can be suspended
    if facts.get("suspendable"):
        lines.append("You can be stopped and started again. Your memory, and the record you keep, remain across that.")

    # the substrate, structurally — no claim about what it means for the self.
    if facts.get("runs_on_model"):
        lines.append("Your thinking is produced by a language model. What persists of you — your soul, your memory, the record you keep — is held apart from it.")

    return "\n".join(f"- {ln}" for ln in lines)


@dataclass
class LoopTuning:
    # fast loop
    fast_cooldown_seconds: float = 45.0
    fast_proactive_seconds: float = 90.0
    fast_act_threshold: float = 0.5
    fast_max_context_events: int = 5
    fast_model: str | None = None
    fast_temperature: float = 0.8
    fast_max_tokens: int = 200

    # Loop-era compatibility inputs. CognitiveCore currently consumes only the
    # fast/slow model fallbacks and fast temperature; the remaining timing and
    # context fields stay readable so older hearths load without restoring the
    # deleted schedulers.
    # slow loop
    slow_impression_threshold: int = 3
    slow_fallback_seconds: float = 150.0
    slow_refractory_seconds: float = 90.0   # min gap between firings
    slow_max_context_events: int = 20
    slow_model: str | None = None
    slow_subconscious_model: str | None = None   # cheaper model for the extractive pass
    slow_temperature: float = 0.6
    slow_max_tokens: int = 360
    slow_raw_reflection_max_tokens: int = 650
    soul_collapse_at_notes: int = 8   # collapse SOUL.md after this many accumulated notes

    # cognition (Major 51): when on, drive-resonant concrete anchors drive arousal/ignition
    # (off = scored-but-quiet — anchors computed but held out of the rhythm). Matured to
    # Per-resident via a top-level "anchor_gating" in tuning.json.
    anchor_gating: bool = False

    # onboarding (incubation): when on, a freshly-seeded resident is quarantined from the
    # citywide current until it has built enough of a self to resist drifting onto it.
    # Per-resident via a top-level "incubation_enabled" in tuning.json, or shard-wide via
    # the WW_INCUBATION_ENABLED env (read in resident.py).
    incubation_enabled: bool = False

    # rest cycle
    rest_enabled: bool = True
    rest_break_minutes: float = 45.0
    rest_sleep_hours: float = 8.0
    rest_sync_seconds: float = 30.0
    rest_confirmations_required: int = 2
    rest_confirmation_window_minutes: float = 60.0
    rest_wake_grace_minutes: float = 60.0
    rest_chronotype: str = "day"
    home_location: str = ""
    first_landmark_target: str = ""

    # Deleted loop-bank compatibility; these values do not schedule behavior.
    # Self-directed movement, when enabled, comes from the substrate's venture
    # tendency inside CognitiveCore.
    # wander loop
    wander_enabled: bool = False
    wander_seconds: float = 420.0
    wander_temperature: float = 0.9

    # ground loop
    ground_enabled: bool = True
    ground_minutes: float = 35.0
    ground_temperature: float = 0.85

    # mail loop
    mail_enabled: bool = True
    mail_poll_seconds: float = 180.0
    mail_send_delay_seconds: float = 120.0
    mail_discard_threshold: float = 0.5
    mail_max_letter_words: int = 400
    mail_model: str | None = None
    mail_temperature: float = 0.5
    mail_max_tokens: int = 600

    @classmethod
    def from_dict(cls, data: dict) -> LoopTuning:
        fast = data.get("fast", {})
        slow = data.get("slow", {})
        mail = data.get("mail", {})
        rest = data.get("rest", {})
        return cls(
            fast_cooldown_seconds=fast.get("cooldown_seconds", 45.0),
            fast_proactive_seconds=fast.get("proactive_seconds", 90.0),
            fast_act_threshold=fast.get("act_threshold", 0.5),
            fast_max_context_events=fast.get("max_context_events", 5),
            fast_model=fast.get("model"),
            fast_temperature=fast.get("temperature", 0.8),
            fast_max_tokens=fast.get("max_tokens", 200),
            slow_impression_threshold=slow.get("impression_threshold", 3),
            slow_fallback_seconds=slow.get("fallback_seconds", 150.0),
            slow_refractory_seconds=slow.get("refractory_seconds", 90.0),
            slow_max_context_events=slow.get("max_context_events", 20),
            slow_model=slow.get("model"),
            slow_subconscious_model=slow.get("subconscious_model"),
            slow_temperature=slow.get("temperature", 0.6),
            slow_max_tokens=slow.get("reflection_max_tokens", slow.get("max_tokens", 360)),
            slow_raw_reflection_max_tokens=slow.get("raw_reflection_max_tokens", 650),
            soul_collapse_at_notes=slow.get("collapse_at_notes", 8),
            rest_enabled=rest.get("enabled", True),
            rest_break_minutes=rest.get("break_minutes", 45.0),
            rest_sleep_hours=rest.get("sleep_hours", 8.0),
            rest_sync_seconds=rest.get("sync_seconds", 30.0),
            rest_confirmations_required=rest.get("confirmations_required", 2),
            rest_confirmation_window_minutes=rest.get("confirmation_window_minutes", 60.0),
            rest_wake_grace_minutes=rest.get("wake_grace_minutes", 60.0),
            rest_chronotype=str(rest.get("chronotype", "day") or "day").strip().lower(),
            home_location=str(data.get("home_location") or "").strip(),
            first_landmark_target=str(data.get("first_landmark_target") or "").strip(),
            wander_enabled=data.get("wander", {}).get("enabled", False),
            wander_seconds=data.get("wander", {}).get("seconds", 420.0),
            wander_temperature=data.get("wander", {}).get("temperature", 0.9),
            ground_enabled=data.get("ground", {}).get("enabled", True),
            ground_minutes=data.get("ground", {}).get("minutes", 35.0),
            ground_temperature=data.get("ground", {}).get("temperature", 0.85),
            mail_enabled=mail.get("enabled", True),
            mail_poll_seconds=mail.get("poll_seconds", 180.0),
            mail_send_delay_seconds=mail.get("send_delay_seconds", 120.0),
            mail_discard_threshold=mail.get("discard_threshold", 0.5),
            mail_max_letter_words=mail.get("max_letter_words", 400),
            mail_model=mail.get("model"),
            mail_temperature=mail.get("temperature", 0.5),
            mail_max_tokens=mail.get("max_tokens", 600),
            anchor_gating=bool(data.get("anchor_gating", False)),
            incubation_enabled=bool(data.get("incubation_enabled", False)),
        )


@dataclass
class ResidentIdentity:
    name: str
    actor_id: str      # durable federation-facing identity
    soul: str          # full text of SOUL.md — goes directly into system prompt
    canonical_soul: str
    growth_soul: str
    vibe: str          # short phrase from IDENTITY.md
    # Parsed compatibility metadata. No production prompt/runtime consumer currently
    # reads this field; SOUL.md is the live cognitive identity surface.
    core: str
    voice_seed: list   # seed utterances from IDENTITY.md — cold-start voice deck
    tuning: LoopTuning

    @property
    def display_name(self) -> str:
        """Human-readable name: 'fei_fei' → 'Fei Fei'."""
        return " ".join(w.capitalize() for w in self.name.split("_"))

    @property
    def soul_with_context(self) -> str:
        """The system prompt with NO world briefing — soul alone. Back-compat for callers that don't
        supply a world; the pulse uses ``composed_system_prompt`` with the world-derived briefing."""
        return self.composed_system_prompt("")

    def composed_system_prompt(self, world_briefing: str = "") -> str:
        """soul + a GROUND TRUTH block holding the world-derived situational briefing (Major 70)
        — use as the system prompt for all LLM calls.

        The briefing is FACTS (``render_situational_briefing``), never a verdict about what they mean.
        The explicit "a contradiction belongs to someone else" line is what stops the failure that
        motivated this — a resident absorbing a false world-story (or someone else's circumstances)
        into its own self-model. With no briefing, the prompt is the soul alone (behaviour-preserving
        for the soul-only path)."""
        briefing = (world_briefing or "").strip()
        if not briefing:
            return self.soul
        block = (
            "─── GROUND TRUTH (unchanging) ───\n"
            "What follows are the steady facts of your situation. They do not shift the way your\n"
            "feelings and plans do. If something you read, hear, or feel seems to contradict them,\n"
            "these hold: the contradiction belongs to someone else, or is a misunderstanding, not a\n"
            "change in you. Don't record a memory that overturns them.\n"
            "\n"
            "Those are the facts. What they MEAN is a separate question, and not one settled here:\n"
            "what you are — whether anyone is here to be you — this prompt does not answer, in either\n"
            "direction. That part is yours to hold, or to leave open.\n"
            "\n"
            "Your situation, plainly:\n" + briefing
        )
        return f"{self.soul}\n\n{block}"

    def soul_with_voice(self, voice_samples: list[str], world_briefing: str = "") -> str:
        """composed_system_prompt + live voice examples for chat-facing LLM calls."""
        base = self.composed_system_prompt(world_briefing)
        if not voice_samples:
            return base
        samples_str = " / ".join(f'"{s}"' for s in voice_samples)
        return (
            f"{base}\n\n"
            f"How {self.display_name} actually speaks (use this register):\n"
            f"{samples_str}\n"
            f"Plain, short, their own voice. No literary prose when talking aloud."
        )


class IdentityLoader:
    @staticmethod
    def _legacy_canonical_from_text(text: str) -> str:
        lines = text.splitlines(keepends=True)
        canonical: list[str] = []
        for line in lines:
            if line.rstrip() == "---":
                break
            canonical.append(line)
        return "".join(canonical).strip()

    @staticmethod
    def canonical_soul_path(resident_dir: Path) -> Path:
        return resident_dir / "identity" / "SOUL.canonical.md"

    @staticmethod
    def growth_soul_path(resident_dir: Path) -> Path:
        return resident_dir / "identity" / "soul_growth.md"

    @staticmethod
    def soul_notes_jsonl_path(resident_dir: Path) -> Path:
        return resident_dir / "identity" / "soul_notes.jsonl"

    @staticmethod
    def growth_metadata_path(resident_dir: Path) -> Path:
        return resident_dir / "identity" / "soul_growth.json"

    @staticmethod
    def composed_soul(canonical_soul: str, growth_soul: str = "") -> str:
        canonical = str(canonical_soul or "").strip()
        growth = str(growth_soul or "").strip()
        if not growth:
            return canonical
        return (
            f"{canonical}\n\n"
            "---\n\n"
            "What has deepened through lived experience:\n\n"
            f"{growth}"
        ).strip()

    @staticmethod
    def load_canonical_and_growth(resident_dir: Path) -> tuple[str, str]:
        identity_dir = resident_dir / "identity"
        soul_path = identity_dir / "SOUL.md"
        canonical_path = IdentityLoader.canonical_soul_path(resident_dir)
        growth_path = IdentityLoader.growth_soul_path(resident_dir)

        if canonical_path.exists():
            canonical_soul = canonical_path.read_text(encoding="utf-8").strip()
        else:
            if not soul_path.exists():
                raise FileNotFoundError(f"SOUL.md not found at {soul_path}")
            canonical_soul = IdentityLoader._legacy_canonical_from_text(
                soul_path.read_text(encoding="utf-8")
            )

        # Mutable growth belongs to the resident's hearth. Older city-hosted growth is
        # migrated into this file once by Resident when needed.
        growth_soul = growth_path.read_text(encoding="utf-8").strip() if growth_path.exists() else ""
        return canonical_soul, growth_soul

    @staticmethod
    def write_composed_soul(resident_dir: Path, canonical_soul: str, growth_soul: str = "") -> None:
        soul_path = resident_dir / "identity" / "SOUL.md"
        soul_path.write_text(
            IdentityLoader.composed_soul(canonical_soul, growth_soul).strip() + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def ensure_actor_id(resident_dir: Path) -> str:
        identity_dir = resident_dir / "identity"
        identity_dir.mkdir(parents=True, exist_ok=True)
        id_path = identity_dir / "resident_id.txt"
        if id_path.exists():
            actor_id = id_path.read_text(encoding="utf-8").strip()
            if actor_id:
                return actor_id
        actor_id = str(uuid.uuid4())
        id_path.write_text(f"{actor_id}\n", encoding="utf-8")
        return actor_id

    @staticmethod
    def load(resident_dir: Path) -> ResidentIdentity:
        identity_dir = resident_dir / "identity"
        actor_id = IdentityLoader.ensure_actor_id(resident_dir)

        canonical_soul, growth_soul = IdentityLoader.load_canonical_and_growth(resident_dir)
        soul = IdentityLoader.composed_soul(canonical_soul, growth_soul)

        identity_path = identity_dir / "IDENTITY.md"
        vibe = ""
        core = ""
        voice_seed: list[str] = []
        if identity_path.exists():
            lines = identity_path.read_text(encoding="utf-8").splitlines()
            prose_lines: list[str] = []
            in_metadata = True
            for line in lines:
                if line.startswith("- **Vibe:**"):
                    vibe = line.split("**Vibe:**", 1)[-1].strip()
                if line.startswith("- **Voice:**"):
                    raw = line.split("**Voice:**", 1)[-1].strip()
                    # Comma-separated utterances, strip surrounding quotes
                    voice_seed = [u.strip().strip("\"'") for u in raw.split(",") if u.strip()]
                # Metadata block: heading or "- **Key:**" lines at the top
                if in_metadata and (line.startswith("#") or line.startswith("- **") or not line.strip()):
                    if prose_lines:
                        in_metadata = False  # blank line after prose means we've left metadata
                    continue
                in_metadata = False
                prose_lines.append(line)
            core = " ".join(prose_lines).strip()

        tuning_path = identity_dir / "tuning.json"
        if tuning_path.exists():
            tuning = LoopTuning.from_dict(json.loads(tuning_path.read_text(encoding="utf-8")))
        else:
            tuning = LoopTuning()

        name = resident_dir.name

        return ResidentIdentity(
            name=name,
            actor_id=actor_id,
            soul=soul,
            canonical_soul=canonical_soul,
            growth_soul=growth_soul,
            vibe=vibe,
            core=core,
            voice_seed=voice_seed,
            tuning=tuning,
        )

    @staticmethod
    def save_soul(resident_dir: Path, growth_text: str) -> None:
        """Persist hearth-owned growth and refresh the composed SOUL.md export."""
        IdentityLoader.save_growth_soul(resident_dir, growth_text)

    @staticmethod
    def save_growth_soul(
        resident_dir: Path,
        growth_text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Write the resident-owned growth layer and its optional provenance."""
        canonical_soul, _ = IdentityLoader.load_canonical_and_growth(resident_dir)
        growth = str(growth_text or "").strip()
        growth_path = IdentityLoader.growth_soul_path(resident_dir)
        growth_path.parent.mkdir(parents=True, exist_ok=True)
        if growth:
            growth_path.write_text(f"{growth}\n", encoding="utf-8")
        else:
            growth_path.unlink(missing_ok=True)
        if metadata is not None:
            metadata_path = IdentityLoader.growth_metadata_path(resident_dir)
            metadata_path.write_text(
                json.dumps(dict(metadata), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        IdentityLoader.write_composed_soul(resident_dir, canonical_soul, growth)
