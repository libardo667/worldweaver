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

import logging
import re
from pathlib import Path
from typing import Any

from src.identity.loader import ResidentIdentity
from src.runtime.circadian import chronotype as resident_chronotype
from src.runtime.circadian import circadian_state
from src.runtime.ledger import append_runtime_event
from src.runtime.signals import StimulusPacketQueue
from src.runtime.world import WorldWeaverClient

logger = logging.getLogger(__name__)

_AMBIENT_KINDS = {"crowding", "quiet", "event_pull", "bad_weather"}
_REQUEST_PATTERN = re.compile(r"\b(can|could|would|will|please|help|let's|meet|bring|send|tell|show|give)\b")

# Real-world weather → vigilance pressure. Substring match against the grounding
# weather string; the strongest match wins.
_ADVERSE_WEATHER = {"thunder": 0.85, "storm": 0.85, "hail": 0.7, "snow": 0.7, "rain": 0.6, "fog": 0.45, "mist": 0.4, "drizzle": 0.4, "wind": 0.4}
# Times of day that should raise the rest drive (circadian grounding).
_REST_HOURS = {"night", "late_evening", "late night", "evening", "sleep_window", "dawn"}


def _clamp01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _reachable_destinations(location: str, location_graph: Any) -> list[str]:
    """Adjacent place names you can move to from here, off the scene graph.

    Without this the pulse picks move targets blind and tends to name its own
    location (a no-op the effector declines). Surfacing the real adjacency makes
    navigation actually land."""
    if not isinstance(location_graph, dict) or not str(location).strip():
        return []
    current = f"location:{str(location).strip().lower()}"
    names_by_key = {str(n.get("key") or "").strip(): str(n.get("name") or "").strip() for n in location_graph.get("nodes") or [] if isinstance(n, dict)}
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
        return {"is_direct": False, "is_question": False, "is_request": False, "addressed": False, "tagged": False, "channel": channel}
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
        return []
    heard: list[dict[str, Any]] = []
    for message in messages:
        if str(message.session_id or "") == session_id:
            continue
        speaker = str(message.display_name or "").strip()
        body = str(message.message or "").strip()
        ts = str(message.ts or "").strip()
        if not body:
            continue
        flags = _classify_dialogue(body, channel=channel, name_variants=name_variants)
        packets.emit_once(
            packet_type=packet_type,
            source_loop="perceive",
            dedupe_key=f"{packet_type}|{ts}|{message.session_id}|{body}",
            location=chat_location,
            salience=0.8 if channel == "local" else 0.6,
            payload={"ts": ts, "speaker": speaker, "session_id": message.session_id, "message": body, **flags},
        )
        heard.append({"speaker": speaker, "message": body, "is_direct": flags["is_direct"], "is_question": flags["is_question"], "channel": channel})
    return heard


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
            payload={"filename": filename, "body_preview": str(getattr(letter, "body", "") or "").strip()[:200]},
        )
        count += 1
    return count


async def _sense_grounding(*, ww_client: WorldWeaverClient, memory_dir: Path, identity: ResidentIdentity | None = None) -> dict[str, Any]:
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
        signals.append({"kind": "fatigue", "label": f"the {circadian['phase_label']} hour", "level": circadian["rest_pressure"]})

    # Circadian fatigue drives the rest node; weather/time also colour the pulse.
    append_runtime_event(
        memory_dir,
        event_type="session_state_observed",
        payload={"source": "session_state", "signals": signals, "context": {"time_of_day": time_of_day, "weather": weather}},
    )
    brief = {
        "time_of_day": time_of_day,
        "weather": weather,
        "temperature_f": grounding.get("temperature_f"),
        "day_of_week": str(grounding.get("day_of_week") or "").strip(),
        "resting_hours": time_of_day in _REST_HOURS,
    }
    if circadian is not None:
        brief.update({"hour": circadian["hour"], "chronotype": circadian["chronotype"], "wakefulness": circadian["wakefulness"], "rest_pressure": circadian["rest_pressure"], "phase": circadian["phase_label"]})
    return {"brief": brief, "bad_weather": round(bad_weather, 3), "wakefulness": (circadian["wakefulness"] if circadian is not None else 1.0)}


async def perceive(
    *,
    ww_client: WorldWeaverClient,
    session_id: str,
    memory_dir: Path,
    identity: ResidentIdentity | None = None,
    self_name: str = "",
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
    recent_events = list(scene.recent_events_here or [])
    location = str(scene.location or "").strip()

    # --- real-world grounding (time + weather + circadian) ---
    grounding = await _sense_grounding(ww_client=ww_client, memory_dir=memory_dir, identity=identity)
    grounding_brief = grounding.get("brief") or {}

    # --- ambient pressure (vigilance) ---
    signals: list[dict[str, Any]] = []
    if others:
        signals.append({"kind": "crowding", "label": "others nearby", "level": round(min(1.0, len(others) * 0.25), 3)})
    if recent_events:
        signals.append({"kind": "event_pull", "label": "recent activity here", "level": round(min(1.0, len(recent_events) * 0.3), 3)})
    bad_weather = float(grounding.get("bad_weather") or 0.0)
    if bad_weather > 0.0:
        signals.append({"kind": "bad_weather", "label": grounding_brief.get("weather") or "rough weather", "level": round(bad_weather, 3)})
    for ambient in scene.ambient_presence or []:
        kind = str(getattr(ambient, "kind", "") or "").strip()
        if kind not in _AMBIENT_KINDS:
            kind = "event_pull"
        signals.append({"kind": kind, "label": str(getattr(ambient, "label", "") or kind).strip(), "level": round(_clamp01(getattr(ambient, "intensity", 0.0) or 0.0), 3)})
    if signals:
        append_runtime_event(memory_dir, event_type="ambient_pressure_observed", payload={"source": "ambient", "signals": signals, "context": {"location": location}})

    # --- heard dialogue (social_pull) + inbox (correspondence_pull) ---
    heard: list[dict[str, Any]] = []
    mail_count = 0
    if identity is not None:
        packets = StimulusPacketQueue(memory_dir / "stimulus_packets.json")
        name_variants = _identity_name_variants(identity)
        heard = await _sense_chat(ww_client=ww_client, session_id=session_id, location=location, packets=packets, name_variants=name_variants, channel="local")
        heard += await _sense_chat(ww_client=ww_client, session_id=session_id, location=location, packets=packets, name_variants=name_variants, channel="city")
        mail_count = await _sense_mail(ww_client=ww_client, agent_name=identity.name, packets=packets)

    return {
        "location": location,
        "present": [str(p.name or "").strip() for p in others if str(p.name or "").strip()],
        "recent_events": [{"who": str(e.who or "").strip(), "summary": str(e.summary or "").strip()} for e in recent_events[-5:]],
        "ambient": [{"kind": s["kind"], "label": s["label"], "level": s["level"]} for s in signals],
        "heard": heard[-6:],
        "inbox_count": mail_count,
        "grounding": grounding_brief,
        "wakefulness": float(grounding.get("wakefulness") if grounding.get("wakefulness") is not None else 1.0),
        "reachable": _reachable_destinations(location, scene.location_graph),
    }
