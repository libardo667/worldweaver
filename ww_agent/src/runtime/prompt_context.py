# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Typed source envelope for one resident-model pulse.

Perception reports what is available. A mode policy chooses what this particular
pulse may receive. Only the final renderer turns selected records into prose, so
source identity and withheld-vs-selected evidence survive up to the inference
boundary instead of disappearing inside string concatenation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PromptContextPolicy:
    include_recent_events: bool
    include_heard: bool
    include_inbox_count: bool
    include_navigation: bool = True

    @classmethod
    def for_mode(cls, mode: str) -> "PromptContextPolicy":
        # React is the only pulse caused by the current world encounter. Settling,
        # fervor, and venture are self-directed discharges; replaying whatever the
        # last poll happened to contain makes their "nothing is asking" premise false.
        if str(mode or "react") == "react":
            return cls(True, True, True)
        return cls(False, False, False)


@dataclass(frozen=True)
class HeardContext:
    packet_id: str
    source_id: str
    message_id: str
    speaker: str
    message: str
    channel: str
    timestamp: str
    is_direct: bool
    is_question: bool
    overheard: bool

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "HeardContext":
        return cls(
            packet_id=str(raw.get("packet_id") or ""),
            source_id=str(raw.get("source_id") or ""),
            message_id=str(raw.get("id") or ""),
            speaker=str(raw.get("speaker") or "").strip(),
            message=str(raw.get("message") or "").strip(),
            channel=str(raw.get("channel") or "local").strip() or "local",
            timestamp=str(raw.get("ts") or ""),
            is_direct=bool(raw.get("is_direct")),
            is_question=bool(raw.get("is_question")),
            overheard=bool(raw.get("overheard")),
        )


@dataclass(frozen=True)
class WorldEventContext:
    event_id: str
    event_type: str
    who: str
    summary: str
    timestamp: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorldEventContext":
        return cls(
            event_id=str(raw.get("event_id") or ""),
            event_type=str(raw.get("event_type") or ""),
            who=str(raw.get("who") or "").strip(),
            summary=str(raw.get("summary") or "").strip(),
            timestamp=str(raw.get("ts") or ""),
        )


@dataclass(frozen=True)
class AffordanceContext:
    source_id: str
    name: str
    description: str
    provenance: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AffordanceContext":
        return cls(
            source_id=str(raw.get("source_id") or ""),
            name=str(raw.get("name") or "").strip(),
            description=str(raw.get("description") or "").strip(),
            provenance=str(raw.get("provenance") or "local-knowledge").strip() or "local-knowledge",
        )


@dataclass(frozen=True)
class PulseContext:
    mode: str
    policy: PromptContextPolicy
    location: str
    present: tuple[str, ...]
    grounding: dict[str, Any]
    reachable: tuple[str, ...]
    recent_events: tuple[WorldEventContext, ...]
    heard: tuple[HeardContext, ...]
    inbox_count: int
    affordances: tuple[AffordanceContext, ...]

    @classmethod
    def from_perception(cls, perception: dict[str, Any], *, mode: str) -> "PulseContext":
        return cls(
            mode=str(mode or "react"),
            policy=PromptContextPolicy.for_mode(mode),
            location=str(perception.get("location") or "").strip() or "somewhere",
            present=tuple(str(name).strip() for name in perception.get("present") or [] if str(name).strip()),
            grounding=dict(perception.get("grounding") or {}),
            reachable=tuple(str(place).strip() for place in perception.get("reachable") or [] if str(place).strip()),
            recent_events=tuple(WorldEventContext.from_dict(item) for item in perception.get("recent_events") or [] if isinstance(item, dict)),
            heard=tuple(HeardContext.from_dict(item) for item in perception.get("heard") or [] if isinstance(item, dict)),
            inbox_count=int(perception.get("inbox_count") or 0),
            affordances=tuple(AffordanceContext.from_dict(item) for item in perception.get("affordances") or [] if isinstance(item, dict)),
        )

    @property
    def selected_recent_events(self) -> tuple[WorldEventContext, ...]:
        return self.recent_events if self.policy.include_recent_events else ()

    @property
    def selected_heard(self) -> tuple[HeardContext, ...]:
        return self.heard[-4:] if self.policy.include_heard else ()

    @property
    def prompted_packet_ids(self) -> list[str]:
        return [item.packet_id for item in self.selected_heard if item.message and item.packet_id]

    def moment_text(self) -> str:
        """Selected external moment, used by affect and relevance recall too."""
        parts = [item.message for item in self.selected_heard if item.message]
        parts += [item.summary for item in self.selected_recent_events if item.summary]
        if self.location:
            parts.append(self.location)
        return " ".join(parts).strip()

    def to_trace_dict(self) -> dict[str, Any]:
        withheld_heard = self.heard[:-4] if self.policy.include_heard else self.heard
        withheld_events = () if self.policy.include_recent_events else self.recent_events
        return {
            "mode": self.mode,
            "policy": asdict(self.policy),
            "available": {
                "heard": [asdict(item) for item in self.heard],
                "recent_events": [asdict(item) for item in self.recent_events],
                "affordances": [asdict(item) for item in self.affordances],
                "inbox_count": self.inbox_count,
            },
            "selected": {
                "heard": [asdict(item) for item in self.selected_heard],
                "recent_events": [asdict(item) for item in self.selected_recent_events],
                "affordances": [asdict(item) for item in self.affordances],
            },
            "withheld": {
                "heard": [asdict(item) for item in withheld_heard],
                "recent_events": [asdict(item) for item in withheld_events],
                "inbox_count": self.inbox_count if not self.policy.include_inbox_count else 0,
            },
        }


def render_pulse_context(context: PulseContext) -> str:
    """Render only policy-selected world sources into final prompt prose."""
    blocks: list[str] = []
    time_of_day = str(context.grounding.get("time_of_day") or "").strip()
    if time_of_day:
        blocks.append(f"It is {time_of_day}.\n")

    present = ", ".join(context.present) or "no one in particular"
    blocks.append(f"Where you are: {context.location}. Present: {present}.\n")

    if context.policy.include_recent_events:
        recent = "; ".join(item.summary for item in context.selected_recent_events if item.summary) or "nothing notable lately"
        blocks.append(f"Recently here: {recent}.\n\n")
    else:
        blocks.append("\n")

    heard_lines: list[str] = []
    for item in context.selected_heard:
        if not item.message:
            continue
        if item.is_direct:
            tag = "  (to you)"
        elif item.channel == "city":
            tag = '  (heard citywide — they may not be here; reply with target "city" or to them by name to reach them)'
        else:
            tag = ""
        heard_lines.append(f'  {item.speaker}: "{item.message}"{tag}')
    if heard_lines:
        blocks.append(f"What you can hear nearby:\n{chr(10).join(heard_lines)}\n\n")

    if context.policy.include_inbox_count and context.inbox_count:
        blocks.append(f"Letters waiting in your inbox: {context.inbox_count}.\n\n")
    if context.policy.include_navigation and context.reachable:
        blocks.append(f"If you move, you can only go to one of these adjacent places: {', '.join(context.reachable)}.\n\n")
    known = [item for item in context.affordances if item.provenance != "world-egress"]
    egress = [item for item in context.affordances if item.provenance == "world-egress"]
    if known:
        listing = "; ".join(item.description for item in known if item.description)
        blocks.append(
            "Things you can USE from first-hand knowledge or local sense — speak their results as your own knowing, not as a lookup:\n"
            f"  {listing}.\n\n"
        )
    if egress:
        listing = "; ".join(item.description for item in egress if item.description)
        blocks.append(
            "Tools you can USE that reach outside the world — name that reach plainly as looking something up:\n"
            f"  {listing}.\n\n"
        )
    return "".join(blocks)
