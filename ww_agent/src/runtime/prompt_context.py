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
    include_physical_traces: bool
    include_navigation: bool = True

    @classmethod
    def for_mode(cls, mode: str) -> "PromptContextPolicy":
        # React is the only pulse caused by the current world encounter. Settling,
        # fervor, and venture are self-directed discharges; replaying whatever the
        # last poll happened to contain makes their "nothing is asking" premise false.
        if str(mode or "react") == "react":
            return cls(True, True, True, True)
        return cls(False, False, False, False)


@dataclass(frozen=True)
class HeardContext:
    packet_id: str
    source_id: str
    message_id: str
    speaker: str
    speaker_actor_id: str
    speaker_session_id: str
    location: str
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
            speaker_actor_id=str(raw.get("speaker_actor_id") or "").strip(),
            speaker_session_id=str(raw.get("speaker_session_id") or "").strip(),
            location=str(raw.get("location") or "").strip(),
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
class PhysicalTraceContext:
    packet_id: str
    trace_id: str
    source_id: str
    author_name: str
    location: str
    target: str
    body: str
    created_at: str
    expires_at: str
    provenance: str
    freshness: str
    locality: str
    visibility: str
    selection_mode: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PhysicalTraceContext":
        return cls(
            packet_id=str(raw.get("packet_id") or ""),
            trace_id=str(raw.get("trace_id") or ""),
            source_id=str(raw.get("source_id") or raw.get("trace_id") or ""),
            author_name=str(raw.get("author_name") or "").strip(),
            location=str(raw.get("location") or "").strip(),
            target=str(raw.get("target") or "").strip(),
            body=str(raw.get("body") or "").strip(),
            created_at=str(raw.get("created_at") or ""),
            expires_at=str(raw.get("expires_at") or ""),
            provenance=str(raw.get("provenance") or "physical_trace"),
            freshness=str(raw.get("freshness") or "active"),
            locality=str(raw.get("locality") or raw.get("location") or ""),
            visibility=str(raw.get("visibility") or "local"),
            selection_mode=str(raw.get("selection_mode") or "embodied_local"),
        )


@dataclass(frozen=True)
class AffordanceContext:
    source_id: str
    name: str
    description: str
    provenance: str
    freshness: str
    locality: str
    visibility: str
    selection_mode: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AffordanceContext":
        return cls(
            source_id=str(raw.get("source_id") or ""),
            name=str(raw.get("name") or "").strip(),
            description=str(raw.get("description") or "").strip(),
            provenance=str(raw.get("provenance") or "local-knowledge").strip()
            or "local-knowledge",
            freshness=str(raw.get("freshness") or "unknown").strip() or "unknown",
            locality=str(raw.get("locality") or "unknown").strip() or "unknown",
            visibility=str(raw.get("visibility") or "private").strip() or "private",
            selection_mode=str(raw.get("selection_mode") or "query").strip() or "query",
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
    physical_traces: tuple[PhysicalTraceContext, ...]
    heard: tuple[HeardContext, ...]
    inbox_count: int
    affordances: tuple[AffordanceContext, ...]

    @classmethod
    def from_perception(
        cls, perception: dict[str, Any], *, mode: str
    ) -> "PulseContext":
        return cls(
            mode=str(mode or "react"),
            policy=PromptContextPolicy.for_mode(mode),
            location=str(perception.get("location") or "").strip() or "somewhere",
            present=tuple(
                str(name).strip()
                for name in perception.get("present") or []
                if str(name).strip()
            ),
            grounding=dict(perception.get("grounding") or {}),
            reachable=tuple(
                str(place).strip()
                for place in perception.get("reachable") or []
                if str(place).strip()
            ),
            recent_events=tuple(
                WorldEventContext.from_dict(item)
                for item in perception.get("recent_events") or []
                if isinstance(item, dict)
            ),
            physical_traces=tuple(
                PhysicalTraceContext.from_dict(item)
                for item in perception.get("traces") or []
                if isinstance(item, dict)
            ),
            heard=tuple(
                HeardContext.from_dict(item)
                for item in perception.get("heard") or []
                if isinstance(item, dict)
            ),
            inbox_count=int(perception.get("inbox_count") or 0),
            affordances=tuple(
                AffordanceContext.from_dict(item)
                for item in perception.get("affordances") or []
                if isinstance(item, dict)
            ),
        )

    @property
    def selected_recent_events(self) -> tuple[WorldEventContext, ...]:
        return self.recent_events if self.policy.include_recent_events else ()

    @property
    def selected_heard(self) -> tuple[HeardContext, ...]:
        return self.heard[-4:] if self.policy.include_heard else ()

    @property
    def selected_physical_traces(self) -> tuple[PhysicalTraceContext, ...]:
        return self.physical_traces[:1] if self.policy.include_physical_traces else ()

    @property
    def prompted_packet_ids(self) -> list[str]:
        heard = [
            item.packet_id
            for item in self.selected_heard
            if item.message and item.packet_id
        ]
        traces = [
            item.packet_id
            for item in self.selected_physical_traces
            if item.body and item.packet_id
        ]
        return [*heard, *traces]

    def moment_text(self) -> str:
        """Selected external moment, used by affect and relevance recall too."""
        parts = [item.message for item in self.selected_heard if item.message]
        parts += [item.summary for item in self.selected_recent_events if item.summary]
        parts += [item.body for item in self.selected_physical_traces if item.body]
        if self.location:
            parts.append(self.location)
        return " ".join(parts).strip()

    def to_trace_dict(self) -> dict[str, Any]:
        withheld_heard = self.heard[:-4] if self.policy.include_heard else self.heard
        withheld_events = (
            () if self.policy.include_recent_events else self.recent_events
        )
        return {
            "mode": self.mode,
            "policy": asdict(self.policy),
            "available": {
                "heard": [asdict(item) for item in self.heard],
                "recent_events": [asdict(item) for item in self.recent_events],
                "physical_traces": [asdict(item) for item in self.physical_traces],
                "affordances": [asdict(item) for item in self.affordances],
                "inbox_count": self.inbox_count,
            },
            "selected": {
                "heard": [asdict(item) for item in self.selected_heard],
                "recent_events": [asdict(item) for item in self.selected_recent_events],
                "physical_traces": [
                    asdict(item) for item in self.selected_physical_traces
                ],
                "affordances": [asdict(item) for item in self.affordances],
            },
            "withheld": {
                "heard": [asdict(item) for item in withheld_heard],
                "recent_events": [asdict(item) for item in withheld_events],
                "physical_traces": (
                    []
                    if self.policy.include_physical_traces
                    else [asdict(item) for item in self.physical_traces]
                ),
                "inbox_count": (
                    self.inbox_count if not self.policy.include_inbox_count else 0
                ),
            },
        }


def render_affordance_catalog(context: PulseContext) -> str:
    """Render the named source registry without any ambient perception."""
    blocks: list[str] = []
    known = [
        item for item in context.affordances if item.provenance == "local-knowledge"
    ]
    remembered = [
        item for item in context.affordances if item.provenance == "self-memory"
    ]
    perceived = [
        item for item in context.affordances if item.provenance == "local-perception"
    ]
    computed = [
        item for item in context.affordances if item.provenance == "local-computation"
    ]
    reading = [
        item for item in context.affordances if item.provenance == "scoped-reading"
    ]
    egress = [item for item in context.affordances if item.provenance == "world-egress"]
    classified = {
        "local-knowledge",
        "self-memory",
        "local-perception",
        "local-computation",
        "scoped-reading",
        "world-egress",
    }
    other = [item for item in context.affordances if item.provenance not in classified]
    if known:
        listing = "\n".join(
            f'  source "{item.name}": {item.description}'
            for item in known
            if item.name and item.description
        )
        blocks.append(
            "Things you can USE by reaching privately with the exact source name — these are knowledge you already carry, so speak their results as your own knowing, not as a lookup:\n"
            f"{listing}\n\n"
        )
    if remembered:
        listing = "\n".join(
            f'  source "{item.name}": {item.description}'
            for item in remembered
            if item.name and item.description
        )
        blocks.append(
            "Things you can RECALL privately from your own life with the exact source name — treat the result as remembered experience:\n"
            f"{listing}\n\n"
        )
    if perceived:
        listing = "\n".join(
            f'  source "{item.name}": {item.description}'
            for item in perceived
            if item.name and item.description
        )
        blocks.append(
            "Things you can NOTICE privately in your present surroundings with the exact source name — treat the result as first-hand perception:\n"
            f"{listing}\n\n"
        )
    if computed:
        listing = "\n".join(
            f'  source "{item.name}": {item.description}'
            for item in computed
            if item.name and item.description
        )
        blocks.append(
            "Things you can CALCULATE privately with the exact source name — these are local computed results, so treat them as measured rather than remembered or looked up:\n"
            f"{listing}\n\n"
        )
    if reading:
        listing = "\n".join(
            f'  source "{item.name}": {item.description}'
            for item in reading
            if item.name and item.description
        )
        blocks.append(
            "Things you can READ privately with the exact source name — these are authorized artifacts, so if you use a result keep clear that you read or consulted it rather than already knowing it:\n"
            f"{listing}\n\n"
        )
    if egress:
        listing = "\n".join(
            f'  source "{item.name}": {item.description}'
            for item in egress
            if item.name and item.description
        )
        blocks.append(
            "Things you can USE by reaching outside the world with the exact source name — name that reach plainly as looking something up:\n"
            f"{listing}\n\n"
        )
    if other:
        listing = "\n".join(
            f'  source "{item.name}": {item.description}'
            for item in other
            if item.name and item.description
        )
        blocks.append(
            "Other things you can reach privately with the exact source name — keep the stated source of anything you learn explicit:\n"
            f"{listing}\n\n"
        )
    return "".join(blocks)


def render_pulse_context(context: PulseContext) -> str:
    """Render only policy-selected world sources into final prompt prose."""
    blocks: list[str] = []
    time_of_day = str(context.grounding.get("time_of_day") or "").strip()
    if time_of_day:
        blocks.append(f"It is {time_of_day}.\n")

    present = ", ".join(context.present) or "no one in particular"
    blocks.append(f"Where you are: {context.location}. Present: {present}.\n")

    if context.policy.include_recent_events:
        recent = (
            "; ".join(
                item.summary for item in context.selected_recent_events if item.summary
            )
            or "nothing notable lately"
        )
        blocks.append(f"Recently here: {recent}.\n\n")
    else:
        blocks.append("\n")

    trace_lines: list[str] = []
    for item in context.selected_physical_traces:
        where = f" on {item.target}" if item.target else ""
        by = f" by {item.author_name}" if item.author_name else ""
        trace_lines.append(
            f"  [{item.trace_id}] A physical trace{where}{by}: {item.body}"
        )
    if trace_lines:
        blocks.append(
            f"Marks you physically encounter here:\n{chr(10).join(trace_lines)}\n\n"
        )

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
        blocks.append(
            f"If you move, you can only go to one of these adjacent places: {', '.join(context.reachable)}.\n\n"
        )
    blocks.append(render_affordance_catalog(context))
    return "".join(blocks)
