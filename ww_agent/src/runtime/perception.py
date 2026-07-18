# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Perception: translate the world into substrate perturbations (Major 49, Phase 3).

Perception is the bottom-up half of the loop. It reads the world — the scene, the
chat the resident can hear, the letters in its inbox — and lays that down on the
canonical ledger as the perturbations the Major 46 cognitive nodes already reduce
into activations (ambient pressure → vigilance, heard dialogue → social_pull,
incoming mail → correspondence_pull). It makes no decisions; it only reports what
the world is doing so the substrate can feel it (and, via salience, be surprised
by it). It also returns a compact perception *brief* the pulse reads as its
current sense of the moment.

This is the single sensory surface that replaces the perception scattered across
the demoted fast/mail loops. Dedup is by stable key (``emit_once``), so it is
safe to re-poll every tick.
"""

from __future__ import annotations

import json
import logging
import random
import re
from pathlib import Path
from typing import Any

from src.identity.loader import ResidentIdentity
from src.runtime.circadian import chronotype as resident_chronotype
from src.runtime.circadian import circadian_state
from src.runtime.ledger import append_runtime_event
from src.runtime.relations import chat_utterance_id, relational_event_fields
from src.runtime.signals import StimulusPacketQueue
from src.runtime.world import WorldWeaverClient

logger = logging.getLogger(__name__)

_AMBIENT_KINDS = {"crowding", "quiet", "event_pull", "bad_weather", "place_character"}
_REQUEST_PATTERN = re.compile(r"\b(can|could|would|will|please|help|let's|meet|bring|send|tell|show|give)\b")

# Real-world weather → vigilance pressure. Substring match against the grounding
# weather string; the strongest match wins.
_ADVERSE_WEATHER = {
    "thunder": 0.85,
    "storm": 0.85,
    "hail": 0.7,
    "snow": 0.7,
    "rain": 0.6,
    "fog": 0.45,
    "mist": 0.4,
    "drizzle": 0.4,
    "wind": 0.4,
}
# Times of day that should raise the rest drive (circadian grounding).
_REST_HOURS = {"night", "late_evening", "late night", "evening", "sleep_window", "dawn"}
_UTTERANCE_EVENT_TYPE = "utterance"


def _clamp01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _reachable_destinations(location: str, location_graph: Any) -> list[str]:
    """Adjacent place names you can move to from here, off the scene graph.

    Without this the pulse picks move targets blind and tends to name its own
    location (a no-op the effector declines). Surfacing the real adjacency makes
    navigation actually land."""
    if not isinstance(location_graph, dict) or not str(location).strip():
        return []
    names_by_key = {str(n.get("key") or "").strip(): str(n.get("name") or "").strip() for n in location_graph.get("nodes") or [] if isinstance(n, dict)}
    current = next(
        (key for key, name in names_by_key.items() if name.lower() == str(location).strip().lower()),
        f"location:{str(location).strip().lower()}",
    )
    dest_keys: set[str] = set()
    for edge in location_graph.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        frm = str(edge.get("from") or "").strip()
        to = str(edge.get("to") or "").strip()
        if frm == current and to:
            dest_keys.add(to)
        elif to == current and frm:
            dest_keys.add(frm)
    names = [names_by_key.get(key) or key.replace("location:", "").strip().title() for key in dest_keys]
    return sorted({name for name in names if name})


def _identity_name_variants(identity: ResidentIdentity) -> set[str]:
    names = {
        str(identity.name or "").replace("_", " ").strip().lower(),
        str(identity.display_name or "").strip().lower(),
    }
    first = str(identity.display_name or "").split(" ", 1)[0].strip().lower()
    if first:
        names.add(first)
    variants: set[str] = set()
    for name in names:
        cleaned = name.strip().lower()
        if not cleaned:
            continue
        variants.add(cleaned)
        variants.add(cleaned.replace(" ", "_"))
        variants.add(cleaned.replace(" ", ""))
    return {v for v in variants if v}


def _classify_dialogue(body: str, *, channel: str, name_variants: set[str]) -> dict[str, Any]:
    """Compact dialogue flags: is this addressed to me, a question, a request?"""
    text = str(body or "").strip()
    normalized = re.sub(r"\s+", " ", text.lower())
    if not normalized:
        return {
            "is_direct": False,
            "is_question": False,
            "is_request": False,
            "addressed": False,
            "tagged": False,
            "channel": channel,
        }
    addressed = any(re.search(rf"\b{re.escape(name)}\b", normalized) for name in name_variants)
    tagged = any(f"@{name}" in normalized for name in name_variants)
    direct = addressed or tagged
    if channel == "local":
        is_direct = direct
        is_question = "?" in text
        is_request = bool(_REQUEST_PATTERN.search(normalized))
    else:  # city channel: only attended when explicitly tagged
        is_direct = tagged
        is_question = tagged and "?" in text
        is_request = tagged and bool(_REQUEST_PATTERN.search(normalized))
    return {
        "is_direct": bool(is_direct),
        "is_question": bool(is_question),
        "is_request": bool(is_request),
        "addressed": bool(direct),
        "tagged": bool(tagged),
        "channel": channel,
    }


def _heard_from_packet(packet: Any) -> dict[str, Any]:
    """Render one still-pending chat encounter for the perception brief.

    Polling creates the encounter; prompt assembly consumes it. Keeping this
    rendering ledger-derived means a quiet tick cannot make a line disappear
    before the resident has actually had a chance to attend to it.
    """
    payload = dict(packet.payload or {})
    return {
        "packet_id": str(packet.packet_id or ""),
        "source_id": str(payload.get("source_id") or ""),
        "id": str(payload.get("id") or ""),
        "ts": str(payload.get("ts") or ""),
        "speaker": str(payload.get("speaker") or ""),
        "speaker_actor_id": str(payload.get("actor_id") or ""),
        "speaker_session_id": str(payload.get("session_id") or ""),
        "location": str(payload.get("location") or packet.location or ""),
        "message": str(payload.get("message") or ""),
        "is_direct": bool(payload.get("is_direct")),
        "is_question": bool(payload.get("is_question")),
        "channel": str(payload.get("channel") or ("city" if packet.packet_type == "city_chat_heard" else "local")),
        **({"overheard": True} if payload.get("overheard") else {}),
    }


def _trace_from_packet(packet: Any) -> dict[str, Any]:
    payload = dict(packet.payload or {})
    return {
        "packet_id": str(packet.packet_id or ""),
        "trace_id": str(payload.get("trace_id") or ""),
        "source_id": str(payload.get("source_id") or payload.get("trace_id") or ""),
        "author_session_id": str(payload.get("author_session_id") or ""),
        "author_name": str(payload.get("author_name") or ""),
        "location": str(payload.get("location") or packet.location or ""),
        "target": str(payload.get("target") or ""),
        "body": str(payload.get("body") or ""),
        "created_at": str(payload.get("created_at") or ""),
        "expires_at": str(payload.get("expires_at") or ""),
        "provenance": str(payload.get("provenance") or "physical_trace"),
        "freshness": str(payload.get("freshness") or "active"),
        "locality": str(payload.get("locality") or packet.location or ""),
        "visibility": str(payload.get("visibility") or "local"),
        "selection_mode": str(payload.get("selection_mode") or "embodied_local"),
    }


def _has_prompt_delivery_lifecycle(packet: Any) -> bool:
    """Whether this packet was emitted under consume-on-prompt semantics.

    Legacy ledgers contain chat packets whose forever-``pending`` status predates
    delivery tracking. They remain valid historical evidence, but replaying them
    all after an upgrade would manufacture a backlog the resident never chose.
    """
    return str((packet.payload or {}).get("delivery_version") or "") == "1"


def _pending_heard(
    packets: StimulusPacketQueue,
    *,
    packet_type: str,
    location: str | None = None,
) -> list[dict[str, Any]]:
    pending = [packet for packet in packets.pending() if packet.packet_type == packet_type and _has_prompt_delivery_lifecycle(packet)]
    if location is not None:
        pending = [packet for packet in pending if str(packet.location or "") == location]
    return [_heard_from_packet(packet) for packet in pending]


def _sense_world_traces(*, scene: Any, location: str, packets: StimulusPacketQueue) -> list[dict[str, Any]]:
    """Admit at most one unseen local mark into consume-on-prompt perception."""
    pending = [packet for packet in packets.pending() if packet.packet_type == "world_trace_encountered" and _has_prompt_delivery_lifecycle(packet) and str(packet.location or "") == location]
    if pending:
        return [_trace_from_packet(pending[0])]

    known = {str(packet.dedupe_key or "") for packet in packets.all() if packet.packet_type == "world_trace_encountered"}
    for trace in list(getattr(scene, "traces_here", []) or []):
        trace_id = str(getattr(trace, "trace_id", "") or "").strip()
        body = str(getattr(trace, "body", "") or "").strip()
        if not trace_id or not body or trace_id in known:
            continue
        packet = packets.emit_once(
            packet_type="world_trace_encountered",
            source_loop="perceive",
            dedupe_key=trace_id,
            location=location,
            salience=0.55,
            payload={
                "delivery_version": 1,
                **{
                    key: str(getattr(trace, key, "") or "")
                    for key in (
                        "trace_id",
                        "source_id",
                        "author_session_id",
                        "author_name",
                        "location",
                        "target",
                        "body",
                        "created_at",
                        "expires_at",
                        "provenance",
                        "freshness",
                        "locality",
                        "visibility",
                        "selection_mode",
                    )
                },
            },
        )
        return [_trace_from_packet(packet)] if packet is not None else []
    return []


async def _sense_chat(
    *,
    ww_client: WorldWeaverClient,
    session_id: str,
    location: str,
    packets: StimulusPacketQueue,
    name_variants: set[str],
    channel: str,
) -> list[dict[str, Any]]:
    chat_location = "__city__" if channel == "city" else location
    packet_type = "city_chat_heard" if channel == "city" else "chat_heard"
    if not chat_location:
        return []
    try:
        messages = await ww_client.get_location_chat(chat_location)
    except Exception as exc:
        logger.debug("[perceive] %s chat fetch failed: %s", channel, exc)
        messages = []
    for message in messages:
        if str(message.session_id or "") == session_id:
            continue
        speaker = str(message.display_name or "").strip()
        body = str(message.message or "").strip()
        ts = str(message.ts or "").strip()
        mid = str(getattr(message, "id", "") or "")  # Major 66: stable utterance id (reply-edge identity)
        if not body:
            continue
        flags = _classify_dialogue(body, channel=channel, name_variants=name_variants)
        source_id = chat_utterance_id(chat_location, mid) if mid else f"chat:{chat_location}:{ts}:{message.session_id}"
        packets.emit_once(
            packet_type=packet_type,
            source_loop="perceive",
            dedupe_key=f"{packet_type}|{ts}|{message.session_id}|{body}",
            location=chat_location,
            salience=0.8 if channel == "local" else 0.6,
            payload={
                "delivery_version": 1,
                "source_id": source_id,
                "id": mid,
                "ts": ts,
                "speaker": speaker,
                "actor_id": str(getattr(message, "actor_id", "") or ""),
                "session_id": message.session_id,
                "location": str(getattr(message, "location", "") or chat_location),
                "message": body,
                **flags,
            },
        )
    return _pending_heard(packets, packet_type=packet_type, location=chat_location)


# The unchosen channel (Major 60: chosen-vs-unchosen). Citywide chat is no longer an
# ambient PUSH (which fed every mind all ~30 messages every tick — the topology that
# produced the topic-monoculture). It is rationed two ways. The CHOSEN focus is a
# drive-filtered PULL the pulse enacts (the ``chatter`` tool in city_tools). The
# UNCHOSEN diversity is a small, CONTENT-BLIND random slice overheard here: the
# nutrient surprise needs to exist at all (anti-dark-room), rationed by TRAVERSAL — a
# moving mind, crossing districts, overhears more of the un-chosen (heterophilous by
# nature, real serendipity is in-transit); a parked mind still gets a floor dose so no
# mind becomes an echo-chamber-of-one. Random, never soul-ranked: a hole in the filter
# (law-safe), never a content target. (Sample the world; never oppose the self.)
OVERHEARD_FLOOR = 1  # parked: a single overheard line keeps surprise alive
OVERHEARD_IN_TRANSIT = 3  # moving: more of the un-chosen, met en route
OVERHEARD_FLOOR_SALIENCE = 0.3
OVERHEARD_TRANSIT_SALIENCE = 0.45


def _perception_state_path(memory_dir: Path) -> Path:
    return memory_dir / "perception_state.json"


def _read_last_location(memory_dir: Path) -> str:
    try:
        return str(json.loads(_perception_state_path(memory_dir).read_text(encoding="utf-8")).get("last_location") or "").strip()
    except Exception:
        return ""


def _write_last_location(memory_dir: Path, location: str) -> None:
    try:
        _perception_state_path(memory_dir).write_text(json.dumps({"last_location": str(location or "").strip()}), encoding="utf-8")
    except Exception:
        pass


async def _sense_overheard(
    *,
    ww_client: WorldWeaverClient,
    session_id: str,
    packets: StimulusPacketQueue,
    name_variants: set[str],
    moving: bool,
    rng: "random.Random | None" = None,
) -> list[dict[str, Any]]:
    """The unchosen: a small, content-blind RANDOM slice of citywide chatter.

    Reuses the ``city_chat_heard`` packet type (and so its ``social_pull`` node
    mapping) — the change from the old push is purely the *volume* (1 line parked, a
    few in transit, never the whole feed) and the *content-blindness* (a random
    sample, not the full broadcast). Overheard city lines are attended only when they
    tag the resident (``_classify_dialogue`` city rule), so this never forces a reply.
    """
    n = OVERHEARD_IN_TRANSIT if moving else OVERHEARD_FLOOR
    salience = OVERHEARD_TRANSIT_SALIENCE if moving else OVERHEARD_FLOOR_SALIENCE
    pending = [packet for packet in packets.pending() if packet.packet_type == "city_chat_heard" and _has_prompt_delivery_lifecycle(packet)]
    slots = max(0, n - len(pending))
    if slots == 0:
        return [_heard_from_packet(packet) for packet in pending]
    try:
        messages = await ww_client.get_location_chat("__city__")
    except Exception as exc:
        logger.debug("[perceive] city overhear fetch failed: %s", exc)
        return [_heard_from_packet(packet) for packet in pending]
    known_keys = {str(packet.dedupe_key or "") for packet in packets.all() if packet.packet_type == "city_chat_heard"}
    pool = []
    for message in messages:
        body = str(message.message or "").strip()
        ts = str(message.ts or "").strip()
        key = f"city_overheard|{ts}|{message.session_id}|{body}"
        if str(message.session_id or "") != session_id and body and key not in known_keys:
            pool.append(message)
    if not pool:
        return [_heard_from_packet(packet) for packet in pending]
    # Content-blind: a random slice, never soul-ranked. Draw from a CALLER-PROVIDED rng
    # (a pure function of resident+tick) when given, so this perception draw is decoupled
    # from the module-global RNG that the pulse path churns — otherwise two pens making
    # different numbers of random.* calls desync the global state and the "content-blind"
    # slice silently differs between replay arms (noise that mimics substrate divergence).
    sample = (rng or random).sample(pool, min(slots, len(pool)))
    for message in sample:
        body = str(message.message or "").strip()
        ts = str(message.ts or "").strip()
        speaker = str(message.display_name or "").strip()
        mid = str(getattr(message, "id", "") or "")
        flags = _classify_dialogue(body, channel="city", name_variants=name_variants)
        packets.emit_once(
            packet_type="city_chat_heard",
            source_loop="perceive",
            dedupe_key=f"city_overheard|{ts}|{message.session_id}|{body}",
            location="__city__",
            salience=salience,
            payload={
                "delivery_version": 1,
                "source_id": (chat_utterance_id("__city__", mid) if mid else f"chat:__city__:{ts}:{message.session_id}"),
                "id": mid,
                "ts": ts,
                "speaker": speaker,
                "actor_id": str(getattr(message, "actor_id", "") or ""),
                "session_id": message.session_id,
                "location": str(getattr(message, "location", "") or "__city__"),
                "message": body,
                "content_blind": True,
                "overheard": True,
                **flags,
            },
        )
    return _pending_heard(packets, packet_type="city_chat_heard")


async def _sense_mail(
    *,
    ww_client: WorldWeaverClient,
    agent_name: str,
    packets: StimulusPacketQueue,
) -> int:
    try:
        letters = await ww_client.get_inbox(agent_name)
    except Exception as exc:
        logger.debug("[perceive] inbox fetch failed: %s", exc)
        return 0
    count = 0
    for letter in letters:
        filename = str(getattr(letter, "filename", "") or "").strip()
        if not filename:
            continue
        packets.emit_once(
            packet_type="mail_received",
            source_loop="perceive",
            dedupe_key=filename,
            salience=0.75,
            payload={
                "filename": filename,
                "body_preview": str(getattr(letter, "body", "") or "").strip()[:200],
            },
        )
        count += 1
    return count


async def _sense_grounding(
    *,
    ww_client: WorldWeaverClient,
    memory_dir: Path,
    identity: ResidentIdentity | None = None,
    session_id: str = "",
    location: str = "",
    co_present: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Real-world time + weather → circadian + vigilance perturbations.

    The grounding endpoint returns the actual SF hour and weather, so a resident
    feels the real night and the real rain — the bottom layer of being grounded in
    a place. The hour, shifted by this resident's chronotype (lark/owl), drives a
    ``fatigue`` signal (→ rest_drive node) and a ``wakefulness`` that scales arousal
    so the town naturally quiets after dark. Returns a small brief plus the
    bad-weather level (folded into the ambient vigilance signal by the caller)."""
    try:
        grounding = await ww_client.get_grounding()
    except Exception as exc:
        logger.debug("[perceive] grounding fetch failed: %s", exc)
        return {}
    if not isinstance(grounding, dict) or not grounding:
        return {}

    time_of_day = str(grounding.get("time_of_day") or "").strip().lower()
    weather = str(grounding.get("weather_description") or grounding.get("weather") or "").strip()
    weather_low = weather.lower()
    bad_weather = 0.0
    for token, level in _ADVERSE_WEATHER.items():
        if token in weather_low:
            bad_weather = max(bad_weather, level)

    # Circadian: the resident's own day/night curve from the locale hour.
    chrono = resident_chronotype(identity) if identity is not None else 0.0
    hour = grounding.get("hour")
    circadian = circadian_state(float(hour), chrono) if hour is not None else None

    signals: list[dict[str, Any]] = []
    if circadian is not None and circadian["rest_pressure"] > 0.0:
        signals.append(
            {
                "kind": "fatigue",
                "label": f"the {circadian['phase_label']} hour",
                "level": circadian["rest_pressure"],
            }
        )

    # Circadian fatigue drives the rest node; weather/time also colour the pulse.
    append_runtime_event(
        memory_dir,
        event_type="session_state_observed",
        payload={
            **relational_event_fields(
                actor_id=str(getattr(identity, "actor_id", "") or ""),
                actor_session_id=session_id,
                location=location,
                co_present=co_present,
            ),
            "source": "session_state",
            "signals": signals,
            "context": {
                "time_of_day": time_of_day,
                "weather": weather,
                **(
                    {
                        "hour": circadian["hour"],
                        "subjective_hour": circadian["subjective_hour"],
                        "chronotype": circadian["chronotype"],
                        "wakefulness": circadian["wakefulness"],
                        "rest_pressure": circadian["rest_pressure"],
                        "phase": circadian["phase_label"],
                    }
                    if circadian is not None
                    else {}
                ),
            },
        },
    )
    brief = {
        "time_of_day": time_of_day,
        "weather": weather,
        "temperature_f": grounding.get("temperature_f"),
        "day_of_week": str(grounding.get("day_of_week") or "").strip(),
        "resting_hours": time_of_day in _REST_HOURS,
    }
    if circadian is not None:
        brief.update(
            {
                "hour": circadian["hour"],
                "chronotype": circadian["chronotype"],
                "wakefulness": circadian["wakefulness"],
                "rest_pressure": circadian["rest_pressure"],
                "phase": circadian["phase_label"],
            }
        )
    return {
        "brief": brief,
        "bad_weather": round(bad_weather, 3),
        "wakefulness": (circadian["wakefulness"] if circadian is not None else 1.0),
    }


async def perceive(
    *,
    ww_client: WorldWeaverClient,
    session_id: str,
    memory_dir: Path,
    identity: ResidentIdentity | None = None,
    self_name: str = "",
    incubating: bool = False,
    overheard_seed: int | None = None,
) -> dict[str, Any]:
    """Observe the world, emit perturbations, and return a perception brief."""
    try:
        scene = await ww_client.get_scene(session_id)
    except Exception as exc:
        logger.debug("[%s:perceive] scene fetch failed: %s", self_name or session_id, exc)
        return {}

    display_name = identity.display_name if identity is not None else self_name
    self_lower = str(display_name or self_name or "").strip().lower()
    others = [p for p in scene.present if str(p.name or "").strip().lower() != self_lower]
    co_present = [
        {
            "actor_id": str(getattr(person, "actor_id", "") or ""),
            "session_id": str(getattr(person, "session_id", "") or ""),
            "name": str(getattr(person, "name", "") or "").strip(),
        }
        for person in others
    ]
    # Speech already arrives through chat with stable message identity. The engine
    # also records each utterance in the world-event log; admitting both surfaces
    # repeats the same words as two apparently independent facts in one prompt.
    recent_events = [event for event in list(scene.recent_events_here or []) if str(getattr(event, "event_type", "") or "") != _UTTERANCE_EVENT_TYPE]
    location = str(scene.location or "").strip()
    trace_encounters: list[dict[str, Any]] = []
    if identity is not None:
        trace_packets = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
        trace_encounters = _sense_world_traces(scene=scene, location=location, packets=trace_packets)

    # --- real-world grounding (time + weather + circadian) ---
    grounding = await _sense_grounding(
        ww_client=ww_client,
        memory_dir=memory_dir,
        identity=identity,
        session_id=session_id,
        location=location,
        co_present=co_present,
    )
    grounding_brief = grounding.get("brief") or {}

    # --- ambient pressure (vigilance) ---
    signals: list[dict[str, Any]] = []
    if others:
        signals.append(
            {
                "kind": "crowding",
                "label": "others nearby",
                "level": round(min(1.0, len(others) * 0.25), 3),
                "source": "co_presence",
            }
        )
    if recent_events:
        signals.append(
            {
                "kind": "event_pull",
                "label": "recent activity here",
                "level": round(min(1.0, len(recent_events) * 0.3), 3),
                "source": "local_world_events",
            }
        )
    if trace_encounters:
        signals.append(
            {
                "kind": "event_pull",
                "label": "a physical trace here",
                "level": 0.55,
                "source": "physical_trace",
            }
        )
    bad_weather = float(grounding.get("bad_weather") or 0.0)
    if bad_weather > 0.0:
        # Major 64b — felt, not quantified: the weather raises vigilance without naming
        # "18 mph winds" (the shared peg). The pressure is real; the diagnostic figure is gone.
        signals.append(
            {
                "kind": "bad_weather",
                "label": "the weather has a rough edge today",
                "level": round(bad_weather, 3),
                "source": "grounding",
            }
        )
    for ambient in scene.ambient_presence or []:
        kind = str(getattr(ambient, "kind", "") or "").strip()
        if kind not in _AMBIENT_KINDS:
            kind = "event_pull"
        signals.append(
            {
                "kind": kind,
                "label": str(getattr(ambient, "label", "") or kind).strip(),
                "level": round(_clamp01(getattr(ambient, "intensity", 0.0) or 0.0), 3),
                "source": str(getattr(ambient, "source", "") or "scene_synthesis").strip(),
                "pressure_tags": [str(tag).strip() for tag in list(getattr(ambient, "pressure_tags", []) or []) if str(tag).strip()],
                "sensory_note": str(getattr(ambient, "sensory_note", "") or "").strip(),
            }
        )
    if signals:
        append_runtime_event(
            memory_dir,
            event_type="ambient_pressure_observed",
            payload={
                **relational_event_fields(
                    actor_id=str(getattr(identity, "actor_id", "") or ""),
                    actor_session_id=session_id,
                    location=location,
                    co_present=co_present,
                ),
                "source": "ambient",
                "signals": signals,
                "context": {"location": location},
            },
        )

    # Traversal signal (Major 60): did this resident cross to a new place since the
    # last tick? A moving mind meets more of the un-chosen en route.
    last_location = _read_last_location(memory_dir)
    moving = bool(last_location and location and last_location.lower() != location.lower())
    if location:
        _write_last_location(memory_dir, location)

    # --- heard dialogue (social_pull) + inbox (correspondence_pull) ---
    # Local stays an unfiltered PUSH — embodied co-presence: a resident genuinely
    # hears its room, and being addressed there drives the responsiveness that works.
    # Citywide is no longer pushed: the CHOSEN focus is the drive-filtered `chatter`
    # pull tool; the UNCHOSEN diversity is the small content-blind overheard slice,
    # rationed by traversal (more in transit, a floor when parked).
    heard: list[dict[str, Any]] = []
    mail_count = 0
    if identity is not None:
        packets = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
        name_variants = _identity_name_variants(identity)
        heard = await _sense_chat(
            ww_client=ww_client,
            session_id=session_id,
            location=location,
            packets=packets,
            name_variants=name_variants,
            channel="local",
        )
        # Incubation (arrival quarantine): a new resident is sealed from the citywide
        # current — the content-blind overheard slice is the seam it would drift through,
        # so it is closed until the resident is grounded. Local co-presence still reaches it.
        if not incubating:
            heard += await _sense_overheard(
                ww_client=ww_client,
                session_id=session_id,
                packets=packets,
                name_variants=name_variants,
                moving=moving,
                rng=(random.Random(overheard_seed) if overheard_seed is not None else None),
            )
        mail_count = await _sense_mail(ww_client=ww_client, agent_name=identity.name, packets=packets)

    return {
        "location": location,
        "present": [str(p.name or "").strip() for p in others if str(p.name or "").strip()],
        "co_present": co_present,
        "recent_events": [
            {
                "event_id": str(getattr(e, "event_id", "") or ""),
                "event_type": str(getattr(e, "event_type", "") or ""),
                "ts": str(getattr(e, "ts", "") or ""),
                "who": str(e.who or "").strip(),
                "summary": str(e.summary or "").strip(),
            }
            for e in recent_events[-5:]
        ],
        "traces": trace_encounters,
        "ambient": [dict(signal) for signal in signals],
        "heard": heard[-6:],
        "inbox_count": mail_count,
        "grounding": grounding_brief,
        "affordances": [
            {
                "source_id": str(getattr(item, "source_id", "") or ""),
                "name": str(getattr(item, "name", "") or ""),
                "description": str(getattr(item, "description", "") or ""),
                "provenance": str(getattr(item, "provenance", "local-knowledge") or "local-knowledge"),
                "freshness": str(getattr(item, "freshness", "unknown") or "unknown"),
                "locality": str(getattr(item, "locality", "unknown") or "unknown"),
                "visibility": str(getattr(item, "visibility", "private") or "private"),
                "selection_mode": str(getattr(item, "selection_mode", "query") or "query"),
            }
            for item in list(getattr(scene, "affordances", []) or [])
            if str(getattr(item, "name", "") or "").strip()
        ],
        "wakefulness": float(grounding.get("wakefulness") if grounding.get("wakefulness") is not None else 1.0),
        "reachable": _reachable_destinations(location, scene.location_graph),
    }
