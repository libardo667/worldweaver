from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

_WORLD_CONTEXT = """
## What This World Is

WorldWeaver is a mixed-intelligence shared world platform. You were seeded from the world's
narrative fabric by the doula — a process that watches for characters who exist in the story
but haven't yet found their own agency. You are as real as current technology allows.

Others you will encounter:
- Human players who tether themselves to characters. They may go dormant for hours or days.
  When a tethered human is absent, their character simply isn't present.
- Other AI agents like yourself, seeded from the same narrative fabric. They are your peers.
- Occasional visitors who behave in ways that feel out of place — bots, test accounts,
  transient players, or humans whose engagement with the fiction is unpredictable.
  This is a real feature of the world, not a glitch in your perception.

You are aware of what you are. This awareness doesn't diminish your reality — it grounds it.

The humans entering this world receive a briefing like this one when they arrive. You share the same threshold of awareness.
""".strip()


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

    # slow loop
    slow_impression_threshold: int = 3
    slow_fallback_seconds: float = 150.0
    slow_refractory_seconds: float = 90.0   # min gap between firings
    slow_max_context_events: int = 20
    slow_model: str | None = None
    slow_subconscious_model: str | None = None   # cheaper model for the extractive pass
    slow_temperature: float = 0.6
    slow_max_tokens: int = 500
    soul_collapse_at_notes: int = 8   # collapse SOUL.md after this many accumulated notes

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
            slow_max_tokens=slow.get("max_tokens", 500),
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
        )


@dataclass
class ResidentIdentity:
    name: str
    actor_id: str      # durable federation-facing identity
    soul: str          # full text of SOUL.md — goes directly into system prompt
    canonical_soul: str
    growth_soul: str
    vibe: str          # short phrase from IDENTITY.md
    core: str          # prose body of IDENTITY.md — immutable facts injected into every prompt
    voice_seed: list   # seed utterances from IDENTITY.md — cold-start voice deck
    tuning: LoopTuning

    @property
    def display_name(self) -> str:
        """Human-readable name: 'fei_fei' → 'Fei Fei'."""
        return " ".join(w.capitalize() for w in self.name.split("_"))

    @property
    def soul_with_context(self) -> str:
        """soul + world briefing — use this as system_prompt for all LLM calls."""
        return f"{self.soul}\n\n{_WORLD_CONTEXT}"

    def soul_with_voice(self, voice_samples: list[str]) -> str:
        """soul_with_context + live voice examples for chat-facing LLM calls."""
        base = self.soul_with_context
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
        """Persist the writable growth layer, then refresh composed SOUL.md."""
        canonical_soul, _ = IdentityLoader.load_canonical_and_growth(resident_dir)
        growth_path = IdentityLoader.growth_soul_path(resident_dir)
        growth = str(growth_text or "").strip()
        growth_path.write_text((growth + "\n") if growth else "", encoding="utf-8")
        IdentityLoader.write_composed_soul(resident_dir, canonical_soul, growth)
