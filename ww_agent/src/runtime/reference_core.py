# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Small reference loop for one WorldWeaver resident activation.

This module deliberately does not model arousal, prediction, drives, salience, or
personality health. It gives a resident current local facts, permits one elective
read, and accepts one final choice. Shared consequences still pass through the
existing typed world effector.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from src.identity.loader import ResidentIdentity
from src.inference.client import InferenceClient
from src.runtime.ledger import append_runtime_event
from src.runtime.pulse import Act, PulseValidationError, Reach

logger = logging.getLogger(__name__)

_FINAL_CHOICES = {"act", "continue", "wait"}
_UNKNOWN_OUTCOME_REASONS = {
    "connection_lost",
    "exception",
    "response_lost",
    "timeout",
    "unknown",
}

Effector = Callable[..., Awaitable[Any]]
InformationAccess = Callable[..., Awaitable[Any]]


class ReferenceDecisionError(ValueError):
    """A model response did not match the small activation contract."""


@dataclass(frozen=True, slots=True)
class ReferenceDecision:
    choice: str
    read: Reach | None = None
    act: Act | None = None
    activity: str = ""

    @classmethod
    def from_dict(
        cls,
        raw: dict[str, Any],
        *,
        allow_read: bool,
        source_names: set[str],
    ) -> "ReferenceDecision":
        if not isinstance(raw, dict):
            raise ReferenceDecisionError("decision must be an object")
        choice = str(raw.get("choice") or "").strip().lower()
        allowed = {*_FINAL_CHOICES, *({"read"} if allow_read else set())}
        if choice not in allowed:
            raise ReferenceDecisionError(
                f"choice must be one of {sorted(allowed)}, got {choice!r}"
            )

        expected_keys = {
            "read": {"choice", "source", "query"},
            "act": {"choice", "action"},
            "continue": {"choice", "activity"},
            "wait": {"choice"},
        }[choice]
        unexpected = set(raw) - expected_keys
        if unexpected:
            raise ReferenceDecisionError(
                f"unexpected fields for {choice}: {sorted(unexpected)}"
            )

        if choice == "read":
            source = str(raw.get("source") or "").strip().lower()
            if source not in source_names:
                raise ReferenceDecisionError(
                    "read source must be one of the currently advertised sources"
                )
            try:
                reach = Reach.from_dict(
                    {
                        "kind": "read",
                        "source": source,
                        "query": str(raw.get("query") or "").strip(),
                    }
                )
            except PulseValidationError as exc:
                raise ReferenceDecisionError(str(exc)) from exc
            return cls(choice=choice, read=reach)

        if choice == "act":
            action = raw.get("action")
            if not isinstance(action, dict):
                raise ReferenceDecisionError("act.action must be an object")
            if set(action) - {"kind", "body", "target"}:
                raise ReferenceDecisionError("act.action contains unexpected fields")
            try:
                act = Act.from_dict(action)
            except PulseValidationError as exc:
                raise ReferenceDecisionError(str(exc)) from exc
            return cls(choice=choice, act=act)

        if choice == "continue":
            activity = str(raw.get("activity") or "").strip()
            if not activity:
                raise ReferenceDecisionError("continue.activity must be non-empty")
            if len(activity) > 500:
                raise ReferenceDecisionError("continue.activity is too long")
            return cls(choice=choice, activity=activity)

        return cls(choice="wait")


@dataclass(frozen=True, slots=True)
class ReferenceObservation:
    availability: dict[str, str]
    location: str = ""
    present: tuple[str, ...] = ()
    ambient: tuple[str, ...] = ()
    recent_events: tuple[str, ...] = ()
    local_speech: tuple[str, ...] = ()
    traces: tuple[str, ...] = ()
    reachable: tuple[str, ...] = ()
    sources: tuple[tuple[str, str], ...] = ()

    @property
    def source_names(self) -> set[str]:
        return {name for name, _description in self.sources}


def _reachable_destinations(location: str, graph: Any) -> tuple[str, ...]:
    if not location or not isinstance(graph, dict):
        return ()
    names_by_key = {
        str(node.get("key") or "").strip(): str(node.get("name") or "").strip()
        for node in list(graph.get("nodes") or [])
        if isinstance(node, dict)
    }
    current_key = next(
        (
            key
            for key, name in names_by_key.items()
            if name.casefold() == location.casefold()
        ),
        "",
    )
    if not current_key:
        return ()
    destination_keys: set[str] = set()
    for edge in list(graph.get("edges") or []):
        if not isinstance(edge, dict):
            continue
        start = str(edge.get("from") or "").strip()
        end = str(edge.get("to") or "").strip()
        if start == current_key and end:
            destination_keys.add(end)
        elif end == current_key and start:
            destination_keys.add(start)
    return tuple(
        sorted({names_by_key[key] for key in destination_keys if names_by_key.get(key)})
    )


async def observe_reference_world(
    world: Any,
    *,
    session_id: str,
    identity: ResidentIdentity,
) -> ReferenceObservation:
    """Read current-place facts while preserving unavailable as a real state."""

    availability = {"scene": "unavailable", "local_speech": "not_requested"}
    try:
        scene = await world.get_scene(session_id)
    except Exception as exc:
        logger.info("[%s] current scene unavailable: %s", identity.name, exc)
        return ReferenceObservation(availability=availability)

    availability["scene"] = "available"
    location = str(getattr(scene, "location", "") or "").strip()
    own_names = {
        str(identity.name or "").strip().casefold(),
        str(identity.name or "").replace("_", " ").strip().casefold(),
        str(identity.display_name or "").strip().casefold(),
    }
    present = tuple(
        str(getattr(person, "role", "") or getattr(person, "name", "") or "").strip()
        for person in list(getattr(scene, "present", []) or [])
        if str(getattr(person, "name", "") or "").strip().casefold() not in own_names
    )
    ambient = tuple(
        str(getattr(item, "label", "") or "").strip()
        for item in list(getattr(scene, "ambient_presence", []) or [])[:5]
        if str(getattr(item, "label", "") or "").strip()
    )
    recent_events = tuple(
        str(getattr(item, "summary", "") or "").strip()
        for item in list(getattr(scene, "recent_events_here", []) or [])[:8]
        if str(getattr(item, "summary", "") or "").strip()
    )
    traces = tuple(
        " ".join(
            part
            for part in (
                str(getattr(item, "author_name", "") or "").strip(),
                str(getattr(item, "body", "") or "").strip(),
            )
            if part
        )
        for item in list(getattr(scene, "traces_here", []) or [])[:8]
        if str(getattr(item, "body", "") or "").strip()
    )
    sources = tuple(
        (
            str(getattr(item, "name", "") or "").strip().lower(),
            str(getattr(item, "description", "") or "").strip(),
        )
        for item in list(getattr(scene, "affordances", []) or [])
        if str(getattr(item, "name", "") or "").strip()
    )

    local_speech: tuple[str, ...] = ()
    if not location:
        availability["local_speech"] = "not_applicable"
    else:
        try:
            messages = await world.get_location_chat(location, session_id=session_id)
            local_speech = tuple(
                f"{str(getattr(item, 'display_name', '') or '').strip()}: "
                f"{str(getattr(item, 'message', '') or '').strip()}".strip()
                for item in list(messages or [])[-10:]
                if str(getattr(item, "message", "") or "").strip()
                and str(getattr(item, "session_id", "") or "").strip() != session_id
            )
            availability["local_speech"] = "available"
        except Exception as exc:
            logger.info("[%s] local speech unavailable: %s", identity.name, exc)
            availability["local_speech"] = "unavailable"

    return ReferenceObservation(
        availability=availability,
        location=location,
        present=tuple(item for item in present if item),
        ambient=ambient,
        recent_events=recent_events,
        local_speech=local_speech,
        traces=traces,
        reachable=_reachable_destinations(
            location, getattr(scene, "location_graph", {})
        ),
        sources=sources,
    )


def render_reference_observation(observation: ReferenceObservation) -> str:
    """Render facts as short prose rather than an undifferentiated JSON payload."""

    if observation.availability.get("scene") != "available":
        return "The current scene is unavailable. Do not guess what is present."
    lines = [f"You are at {observation.location or 'an unnamed place'}. "]
    lines.append(
        "People here: " + ", ".join(observation.present)
        if observation.present
        else "No one else is reported here."
    )
    if observation.ambient:
        lines.append("Around you: " + "; ".join(observation.ambient) + ".")
    if observation.local_speech:
        lines.append("Recently said here:\n" + "\n".join(observation.local_speech))
    elif observation.availability.get("local_speech") == "unavailable":
        lines.append("Local speech is unavailable; do not treat it as silence.")
    if observation.recent_events:
        lines.append("Recent public events: " + "; ".join(observation.recent_events))
    if observation.traces:
        lines.append("Visible marks: " + "; ".join(observation.traces))
    if observation.reachable:
        lines.append("You can move toward: " + ", ".join(observation.reachable) + ".")
    if observation.sources:
        lines.append(
            "Information you may choose to read:\n"
            + "\n".join(
                f"- {name}: {description}" for name, description in observation.sources
            )
        )
    else:
        lines.append("No elective information source is currently advertised.")
    return "\n".join(lines)


def _render_information_result(result: Any) -> str:
    payload = dict(result or {}) if isinstance(result, dict) else {}
    if not bool(payload.get("accessed")):
        reason = str(payload.get("reason") or "unavailable").strip()
        return f"The chosen source was unavailable ({reason})."
    detail = str(payload.get("detail") or "").strip()
    if not detail:
        detail = "The source returned no readable detail."
    return detail[:12_000]


def classify_action_outcome(result: Any) -> str:
    if not isinstance(result, dict):
        return "unknown"
    if bool(result.get("executed")):
        return "confirmed"
    reason = str(result.get("reason") or "").strip().lower()
    if reason in _UNKNOWN_OUTCOME_REASONS:
        return "unknown"
    return "declined"


class ReferenceResidentCore:
    """One small activation at a fixed cadence, without CognitiveCore policy."""

    def __init__(
        self,
        *,
        identity: ResidentIdentity,
        memory_dir: Path,
        world: Any,
        llm: InferenceClient,
        session_id: str,
        effector: Effector,
        information_access: InformationAccess,
        tick_seconds: float = 20.0,
        model: str | None = None,
        temperature: float | None = 0.7,
    ) -> None:
        self._identity = identity
        self._memory_dir = memory_dir
        self._world = world
        self._llm = llm
        self._session_id = session_id
        self._effector = effector
        self._information_access = information_access
        self._tick_seconds = max(2.0, float(tick_seconds))
        self._model = str(model or "").strip() or None
        self._temperature = temperature

    @property
    def name(self) -> str:
        return self._identity.name

    @property
    def tick_seconds(self) -> float:
        return self._tick_seconds

    def _system_prompt(self, *, allow_read: bool) -> str:
        identity_text = str(
            self._identity.soul
            or self._identity.canonical_soul
            or self._identity.display_name
        ).strip()
        choices = (
            "read, act, continue, or wait" if allow_read else "act, continue, or wait"
        )
        return (
            f"{identity_text}\n\n"
            "This is one brief chance to notice the place and choose what, if anything, to do. "
            "Speaking, moving, reading, continuing privately, and doing nothing are all valid. "
            "A direct remark is available to your attention but does not require a reply. "
            "Do not claim that an action succeeded; the world decides that afterward.\n\n"
            f"Return exactly one JSON object choosing {choices}. "
            'Read: {"choice":"read","source":"advertised-name","query":"..."}. '
            'Act: {"choice":"act","action":{"kind":"speak|move|do|write|mark","body":"...","target":null}}. '
            'Continue privately: {"choice":"continue","activity":"..."}. '
            'Do nothing: {"choice":"wait"}.'
        )

    async def _infer(
        self,
        *,
        phase: str,
        prompt: str,
        allow_read: bool,
        source_names: set[str],
    ) -> ReferenceDecision:
        try:
            raw = await self._llm.complete_json(
                self._system_prompt(allow_read=allow_read),
                prompt,
                model=self._model,
                temperature=self._temperature,
                max_tokens=450,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            append_runtime_event(
                self._memory_dir,
                event_type="reference_inference_failed",
                payload={"phase": phase, "reason": type(exc).__name__},
            )
            raise
        try:
            decision = ReferenceDecision.from_dict(
                raw,
                allow_read=allow_read,
                source_names=source_names,
            )
        except ReferenceDecisionError:
            append_runtime_event(
                self._memory_dir,
                event_type="reference_inference_invalid",
                payload={"phase": phase},
            )
            raise
        append_runtime_event(
            self._memory_dir,
            event_type="reference_inference_completed",
            payload={"phase": phase, "choice": decision.choice},
        )
        return decision

    async def tick_once(
        self,
        *,
        now: Any = None,
        force_ignite: bool = False,
    ) -> dict[str, Any]:
        """Run one activation. ``force_ignite`` is accepted only for host compatibility."""

        _ = force_ignite
        effective_now = now or datetime.now(timezone.utc)
        observation = await observe_reference_world(
            self._world,
            session_id=self._session_id,
            identity=self._identity,
        )
        append_runtime_event(
            self._memory_dir,
            event_type="reference_activation_started",
            payload={
                "as_of": (
                    effective_now.isoformat()
                    if isinstance(effective_now, datetime)
                    else str(effective_now)
                ),
                "availability": dict(observation.availability),
                "present_count": len(observation.present),
                "local_speech_count": len(observation.local_speech),
                "source_count": len(observation.sources),
            },
            ts=effective_now,
        )
        prompt = render_reference_observation(observation)
        try:
            decision = await self._infer(
                phase="initial",
                prompt=prompt,
                allow_read=True,
                source_names=observation.source_names,
            )
        except Exception as exc:
            return {
                "status": "inference_failed",
                "choice": "none",
                "error": type(exc).__name__,
            }

        reads = 0
        if decision.choice == "read" and decision.read is not None:
            reads = 1
            append_runtime_event(
                self._memory_dir,
                event_type="reference_information_requested",
                payload={
                    "source": decision.read.source,
                    "query_present": bool(decision.read.query),
                },
            )
            try:
                read_result = await self._information_access(
                    decision.read, now=effective_now
                )
            except Exception as exc:
                read_result = {
                    "accessed": False,
                    "reason": type(exc).__name__,
                }
            append_runtime_event(
                self._memory_dir,
                event_type="reference_information_returned",
                payload={
                    "source": decision.read.source,
                    "accessed": bool(
                        isinstance(read_result, dict) and read_result.get("accessed")
                    ),
                    "reason": (
                        str(read_result.get("reason") or "")
                        if isinstance(read_result, dict)
                        else "invalid_result"
                    ),
                },
            )
            continuation_prompt = (
                f"{prompt}\n\nYou chose to read {decision.read.source}.\n"
                f"Result:\n{_render_information_result(read_result)}\n\n"
                "Now make the final choice. You cannot request another source in this activation."
            )
            try:
                decision = await self._infer(
                    phase="after_read",
                    prompt=continuation_prompt,
                    allow_read=False,
                    source_names=observation.source_names,
                )
            except Exception as exc:
                return {
                    "status": "inference_failed",
                    "choice": "none",
                    "reads": reads,
                    "error": type(exc).__name__,
                }

        if decision.choice == "act" and decision.act is not None:
            try:
                result = await self._effector(decision.act, now=effective_now)
            except Exception as exc:
                logger.warning("[%s] action outcome unknown: %s", self.name, exc)
                result = {"executed": False, "reason": "exception"}
            outcome = classify_action_outcome(result)
            append_runtime_event(
                self._memory_dir,
                event_type="reference_action_outcome",
                payload={
                    "kind": decision.act.kind,
                    "outcome": outcome,
                    "reason": (
                        str(result.get("reason") or "")
                        if isinstance(result, dict)
                        else "invalid_result"
                    ),
                },
            )
            return {
                "status": "completed",
                "choice": "act",
                "reads": reads,
                "action_outcome": outcome,
                "act_executed": result,
            }

        if decision.choice == "continue":
            append_runtime_event(
                self._memory_dir,
                event_type="reference_activity_continued",
                payload={"activity": decision.activity},
            )
            return {
                "status": "completed",
                "choice": "continue",
                "reads": reads,
            }

        append_runtime_event(
            self._memory_dir,
            event_type="reference_activation_outcome",
            payload={"outcome": "no_action"},
        )
        return {
            "status": "completed",
            "choice": "wait",
            "reads": reads,
        }
