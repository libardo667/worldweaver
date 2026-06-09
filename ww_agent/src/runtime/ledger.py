from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_LEDGER_FILENAME = "runtime_ledger.jsonl"
_PROJECTION_FILENAME = "runtime_projection.json"
_SUBJECTIVE_PROJECTION_FILENAME = "subjective_projection.json"
_MEMORY_PROJECTION_FILENAME = "memory_projection.json"
_SUBJECTIVE_FACTS_FILENAME = "subjective_facts.json"
_COGNITIVE_PROJECTION_FILENAME = "cognitive_projection.json"
_ROUTE_PROJECTION_FILENAME = "active_route.json"
# Rolling cap on the in-file event log. At ~several events/tick this fills in ~2h on an active
# cohort; the durable surfaces (kept_memory.jsonl, the projections) are lossless regardless, but a
# too-small window trims away recent address-edges / short-horizon signal that read-time reducers
# and tooling rely on. Per-resident cost is ~12 KB/1000 events, so a 10x window is still only
# megabytes cohort-wide — cheap insurance for long maturation/observation runs.
_MAX_EVENTS = 10000


@dataclass(frozen=True)
class ResidentReducedState:
    events: list[dict[str, Any]]
    packets: list[dict[str, Any]]
    intents: list[dict[str, Any]]
    active_route: dict[str, Any] | None
    active_mail_intents: list[dict[str, Any]]
    research_queue: list[dict[str, Any]]
    runtime_projection: dict[str, Any]
    subjective_projection: dict[str, Any]
    memory_projection: dict[str, Any]
    subjective_facts: dict[str, Any]
    cognitive_projection: dict[str, Any]


def build_runtime_mirror_payload(reduced: ResidentReducedState) -> dict[str, Any]:
    return {
        "_resident_runtime_projection": reduced.runtime_projection,
        "_resident_subjective_projection": reduced.subjective_projection,
        "_resident_memory_projection": reduced.memory_projection,
        "_resident_subjective_facts": reduced.subjective_facts,
        "_resident_cognitive_projection": reduced.cognitive_projection,
        "_resident_ledger_event_count": int(reduced.runtime_projection.get("ledger_event_count") or 0),
        "_resident_runtime_synced_at": _utc_now_iso(),
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_ts(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _ledger_path(memory_dir: Path) -> Path:
    return memory_dir / _LEDGER_FILENAME


def _projection_path(memory_dir: Path) -> Path:
    return memory_dir / _PROJECTION_FILENAME


def _subjective_projection_path(memory_dir: Path) -> Path:
    return memory_dir / _SUBJECTIVE_PROJECTION_FILENAME


def _memory_projection_path(memory_dir: Path) -> Path:
    return memory_dir / _MEMORY_PROJECTION_FILENAME


def _subjective_facts_path(memory_dir: Path) -> Path:
    return memory_dir / _SUBJECTIVE_FACTS_FILENAME


def _cognitive_projection_path(memory_dir: Path) -> Path:
    return memory_dir / _COGNITIVE_PROJECTION_FILENAME


def _route_projection_path(memory_dir: Path) -> Path:
    return memory_dir / _ROUTE_PROJECTION_FILENAME


def _intents_dir(memory_dir: Path) -> Path:
    return memory_dir.parent / "letters" / "intents"


def _mail_intent_filename(mail_intent_id: str, recipient: str) -> str:
    safe_recipient = re.sub(r"[^a-z0-9]+", "_", recipient.lower()).strip("_") or "unknown"
    return f"intent_{mail_intent_id}_{safe_recipient}.md"


def _sender_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    if stem.startswith("from_"):
        body = stem[5:]
        parts = body.split("_")
        if parts:
            return parts[0].strip().capitalize()
    return ""


def _dialogue_message_kind(message: str) -> str:
    stripped = str(message or "").strip()
    if not stripped:
        return ""
    if "?" in stripped:
        return "question"
    return "request_or_statement"


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _plus_minutes_iso(value: str, minutes: float) -> str | None:
    parsed = _parse_iso_ts(value)
    if parsed is None:
        return None
    return (parsed + timedelta(minutes=minutes)).isoformat()


def _merge_pressure_payload(
    current: dict[str, Any] | None,
    incoming: dict[str, Any] | None,
    *,
    ts: str = "",
) -> dict[str, Any]:
    ambient_signal_kinds = {"crowding", "quiet", "event_pull", "bad_weather"}
    session_signal_kinds = {"danger", "tension", "fatigue", "melancholy", "loneliness"}
    ambient_raw_keys = {"scene_present_count", "scene_event_count", "current_present", "recent_event_count", "vitality_score"}
    session_raw_keys = {"danger_level", "danger", "tension", "_mood_tension", "fatigue", "energy", "_mood_melancholy", "loneliness"}
    ambient_context_keys = {"headline", "location", "neighborhood", "neighborhood_vibe", "region"}
    session_context_keys = {"time_of_day", "weather", "goal_primary"}
    merged: dict[str, Any] = {
        "signals": list((current or {}).get("signals") or []),
        "raw": dict((current or {}).get("raw") or {}),
        "context": dict((current or {}).get("context") or {}),
    }
    if ts:
        merged["ts"] = ts
    payload = incoming if isinstance(incoming, dict) else {}
    source = str(payload.get("source") or "").strip()
    if source == "ambient":
        merged["signals"] = [
            item
            for item in list(merged.get("signals") or [])
            if not (isinstance(item, dict) and str(item.get("kind") or "").strip() in ambient_signal_kinds)
        ]
        for key in ambient_raw_keys:
            merged["raw"].pop(key, None)
        for key in ambient_context_keys:
            merged["context"].pop(key, None)
    elif source == "session_state":
        merged["signals"] = [
            item
            for item in list(merged.get("signals") or [])
            if not (isinstance(item, dict) and str(item.get("kind") or "").strip() in session_signal_kinds)
        ]
        for key in session_raw_keys:
            merged["raw"].pop(key, None)
        for key in session_context_keys:
            merged["context"].pop(key, None)
    signal_index: dict[tuple[str, str], int] = {}
    for idx, item in enumerate(list(merged.get("signals") or [])):
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("kind") or "").strip(),
            str(item.get("label") or item.get("kind") or "").strip(),
        )
        signal_index[key] = idx
    for item in list(payload.get("signals") or []):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        label = str(item.get("label") or kind).strip()
        if not kind or not label:
            continue
        level = _coerce_float(item.get("level"))
        normalized = {
            "kind": kind,
            "label": label,
            "level": round(max(0.0, min(level if level is not None else 0.5, 1.0)), 3),
        }
        key = (kind, label)
        existing_idx = signal_index.get(key)
        if existing_idx is None:
            signal_index[key] = len(merged["signals"])
            merged["signals"].append(normalized)
            continue
        existing = merged["signals"][existing_idx]
        existing_level = _coerce_float(existing.get("level")) if isinstance(existing, dict) else None
        if existing_level is None or normalized["level"] >= existing_level:
            merged["signals"][existing_idx] = normalized
    merged["raw"].update(dict(payload.get("raw") or {}))
    merged["context"].update(dict(payload.get("context") or {}))
    return merged


def _load_events(memory_dir: Path) -> list[dict[str, Any]]:
    path = _ledger_path(memory_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except Exception:
                    continue
                if isinstance(raw, dict):
                    events.append(raw)
    except Exception:
        return []
    return events


def load_runtime_events(memory_dir: Path) -> list[dict[str, Any]]:
    return _load_events(memory_dir)


def _save_events(memory_dir: Path, events: list[dict[str, Any]]) -> None:
    path = _ledger_path(memory_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    trimmed = events[-_MAX_EVENTS:]
    lines = [json.dumps(event, ensure_ascii=True) for event in trimmed]
    text = ("\n".join(lines) + "\n") if lines else ""
    path.write_text(text, encoding="utf-8")


def _derive_packets_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    packets: dict[str, dict[str, Any]] = {}
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event_type == "packet_emitted":
            packet_id = str(payload.get("packet_id") or "").strip()
            if packet_id:
                packets[packet_id] = dict(payload)
        elif event_type == "packet_status_changed":
            packet_id = str(payload.get("packet_id") or "").strip()
            if packet_id and packet_id in packets:
                packets[packet_id]["status"] = str(payload.get("status") or packets[packet_id].get("status") or "pending").strip()
    return sorted(
        packets.values(),
        key=lambda item: str(item.get("created_at") or ""),
    )


def derive_packets(memory_dir: Path) -> list[dict[str, Any]]:
    return _derive_packets_from_events(_load_events(memory_dir))


def _derive_intents_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    intents: dict[str, dict[str, Any]] = {}
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event_type == "intent_staged":
            intent_id = str(payload.get("intent_id") or "").strip()
            if intent_id:
                intents[intent_id] = dict(payload)
        elif event_type == "intent_status_changed":
            intent_id = str(payload.get("intent_id") or "").strip()
            if intent_id and intent_id in intents:
                intents[intent_id]["status"] = str(payload.get("status") or intents[intent_id].get("status") or "pending").strip()
                validation_state = str(payload.get("validation_state") or "").strip()
                if validation_state:
                    intents[intent_id]["validation_state"] = validation_state
    return sorted(
        intents.values(),
        key=lambda item: (-float(item.get("priority") or 0.5), str(item.get("created_at") or "")),
    )


def derive_intents(memory_dir: Path) -> list[dict[str, Any]]:
    return _derive_intents_from_events(_load_events(memory_dir))


def _derive_active_route_from_events(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    route: dict[str, Any] | None = None
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        if event_type != "route_state_changed":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        status = str(payload.get("status") or "").strip()
        if status == "active":
            route = {
                "destination": str(payload.get("destination") or "").strip(),
                "remaining": list(payload.get("remaining") or []),
            }
        elif status == "cleared":
            route = None
    if route and route.get("destination"):
        return route
    return None


def derive_active_route(memory_dir: Path) -> dict[str, Any] | None:
    return _derive_active_route_from_events(_load_events(memory_dir))


def _derive_active_mail_intents_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    staged: dict[str, dict[str, Any]] = {}
    terminal_types = {"mail_intent_sent", "mail_intent_declined", "mail_intent_suppressed"}
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        mail_intent_id = str(payload.get("mail_intent_id") or "").strip()
        if event_type == "mail_intent_staged" and mail_intent_id:
            staged[mail_intent_id] = dict(payload)
        elif event_type in terminal_types and mail_intent_id:
            staged.pop(mail_intent_id, None)
    return sorted(
        staged.values(),
        key=lambda item: str(item.get("staged_at") or item.get("ts") or ""),
    )


def derive_active_mail_intents(memory_dir: Path) -> list[dict[str, Any]]:
    return _derive_active_mail_intents_from_events(_load_events(memory_dir))


def _derive_research_queue_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queued: dict[str, dict[str, Any]] = {}
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        query = str(payload.get("query") or "").strip()
        if not query:
            continue
        key = query.lower()
        if event_type == "research_queued":
            queued[key] = {
                "query": query,
                "priority": str(payload.get("priority") or "normal").strip() or "normal",
                "source": str(payload.get("source") or "").strip(),
                "added_ts": str(payload.get("added_ts") or event.get("ts") or "").strip(),
            }
        elif event_type == "research_popped":
            queued.pop(key, None)
    priority_rank = {"high": 0, "normal": 1, "low": 2}
    return sorted(
        queued.values(),
        key=lambda item: (
            priority_rank.get(str(item.get("priority") or "normal"), 1),
            str(item.get("added_ts") or ""),
        ),
    )


def derive_research_queue(memory_dir: Path) -> list[dict[str, Any]]:
    return _derive_research_queue_from_events(_load_events(memory_dir))


def _build_runtime_projection(
    events: list[dict[str, Any]],
    *,
    research_queue: list[dict[str, Any]],
) -> dict[str, Any]:
    event_counts: dict[str, int] = {}
    last_grounding: dict[str, Any] | None = None
    last_movement: dict[str, Any] | None = None
    last_mail: dict[str, Any] | None = None
    last_research: dict[str, Any] | None = None

    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event_type in {"grounding_observed", "ground_intent_executed"}:
            last_grounding = {
                "ts": str(event.get("ts") or "").strip(),
                "observation": str(payload.get("observation") or "").strip(),
                "query": str(payload.get("query") or "").strip(),
            }
        elif event_type in {"move_executed", "movement_arrived", "movement_blocked"}:
            last_movement = {
                "ts": str(event.get("ts") or "").strip(),
                "event_type": event_type,
                "destination": str(payload.get("destination") or "").strip(),
                "arrived_at": str(payload.get("arrived_at") or "").strip(),
                "status": str(payload.get("status") or "").strip(),
            }
        elif event_type in {"mail_reply_sent", "mail_draft_sent", "mail_intent_sent", "mail_doula_vote_cast", "mail_intent_declined", "mail_intent_suppressed"}:
            last_mail = {
                "ts": str(event.get("ts") or "").strip(),
                "event_type": event_type,
                "recipient": str(payload.get("recipient") or payload.get("sender_name") or "").strip(),
                "vote": str(payload.get("vote") or "").strip(),
            }
        elif event_type in {"research_queued", "research_popped", "research_result_observed"}:
            last_research = {
                "ts": str(event.get("ts") or "").strip(),
                "event_type": event_type,
                "query": str(payload.get("query") or "").strip(),
                "priority": str(payload.get("priority") or "").strip(),
            }

    return {
        "updated_at": _utc_now_iso(),
        "ledger_event_count": len(events),
        "event_counts": event_counts,
        "recent_events": [
            {
                "event_id": str(event.get("event_id") or "").strip(),
                "event_type": str(event.get("event_type") or "").strip(),
                "ts": str(event.get("ts") or "").strip(),
            }
            for event in events[-20:]
        ],
        "last_grounding": last_grounding,
        "last_movement": last_movement,
        "last_mail": last_mail,
        "last_research": last_research,
    }


def _build_subjective_projection(
    events: list[dict[str, Any]],
    *,
    packets: list[dict[str, Any]],
    route: dict[str, Any] | None,
    mail_intents: list[dict[str, Any]],
    research_queue: list[dict[str, Any]],
) -> dict[str, Any]:
    thread_state: dict[str, dict[str, Any]] = {}
    latest_direct: dict[str, Any] | None = None
    open_questions: list[dict[str, Any]] = []
    open_requests: list[dict[str, Any]] = []
    pending_mail: list[dict[str, Any]] = []
    city_signals: list[dict[str, Any]] = []
    state_pressure: dict[str, Any] = {"signals": [], "raw": {}, "context": {}}
    direct_partner: str = ""
    direct_partner_ts: datetime | None = None
    followup_window = timedelta(seconds=90)
    dialogue_expiry_window = timedelta(minutes=5)

    def touch_thread(name: str, *, kind: str, ts: str) -> None:
        normalized = str(name).strip()
        if not normalized:
            return
        key = normalized.lower()
        entry = thread_state.setdefault(
            key,
            {
                "name": normalized,
                "interaction_count": 0,
                "last_kind": "",
                "last_ts": "",
            },
        )
        entry["interaction_count"] += 1
        entry["last_kind"] = kind
        entry["last_ts"] = ts

    for packet in packets:
        packet_type = str(packet.get("packet_type") or "").strip()
        payload = packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
        ts = str(packet.get("created_at") or "").strip()
        if packet_type in {"chat_heard", "city_chat_heard"}:
            speaker = str(payload.get("speaker") or "").strip()
            message = str(payload.get("message") or "").strip()
            is_direct = bool(payload.get("is_direct"))
            is_question = bool(payload.get("is_question"))
            is_request = bool(payload.get("is_request"))
            channel = str(payload.get("channel") or ("local" if packet_type == "chat_heard" else "city")).strip()
            packet_ts = _parse_iso_ts(ts)
            is_followup_direct = (
                packet_type == "chat_heard"
                and not is_direct
                and speaker
                and speaker == direct_partner
                and packet_ts is not None
                and direct_partner_ts is not None
                and packet_ts - direct_partner_ts <= followup_window
                and (is_question or is_request)
            )
            touch_thread(speaker, kind=packet_type, ts=ts)
            if packet_type == "city_chat_heard" and speaker and message:
                city_signals.append(
                    {
                        "speaker": speaker,
                        "message": message,
                        "ts": ts,
                        "channel": channel or "city",
                        "is_direct": bool(is_direct),
                        "is_question": bool(is_question),
                        "is_request": bool(is_request),
                        "tagged": bool(payload.get("tagged")),
                    }
                )
            if (is_direct or is_followup_direct) and speaker:
                latest_direct = {
                    "speaker": speaker,
                    "message": message,
                    "ts": ts,
                    "is_question": is_question,
                    "is_request": is_request,
                }
                direct_partner = speaker
                direct_partner_ts = packet_ts
            if (is_direct or is_followup_direct) and is_question and speaker and message:
                open_questions.append(
                    {
                        "speaker": speaker,
                        "message": message,
                        "ts": ts,
                    }
                )
            elif (is_direct or is_followup_direct) and is_request and speaker and message:
                open_requests.append(
                    {
                        "speaker": speaker,
                        "message": message,
                        "ts": ts,
                    }
                )
        elif packet_type == "mail_received":
            sender = _sender_from_filename(str(payload.get("filename") or ""))
            touch_thread(sender, kind="mail_received", ts=ts)
            if sender:
                pending_mail.append(
                    {
                        "sender": sender,
                        "ts": ts,
                        "filename": str(payload.get("filename") or "").strip(),
                    }
                )

    freshest_direct_questions: list[dict[str, Any]] = []
    latest_direct_ts = _parse_iso_ts(str((latest_direct or {}).get("ts") or ""))
    for item in open_questions[-4:]:
        item_ts = _parse_iso_ts(str(item.get("ts") or ""))
        if latest_direct_ts is None or item_ts is None or latest_direct_ts - item_ts <= dialogue_expiry_window:
            freshest_direct_questions.append(item)

    freshest_direct_requests: list[dict[str, Any]] = []
    for item in open_requests[-4:]:
        item_ts = _parse_iso_ts(str(item.get("ts") or ""))
        if latest_direct_ts is None or item_ts is None or latest_direct_ts - item_ts <= dialogue_expiry_window:
            freshest_direct_requests.append(item)

    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ts = str(event.get("ts") or "").strip()
        if event_type in {"session_state_observed", "ambient_pressure_observed"}:
            state_pressure = _merge_pressure_payload(state_pressure, payload, ts=ts)
        if event_type in {"mail_intent_staged", "mail_intent_sent", "mail_reply_sent", "mail_draft_sent"}:
            touch_thread(
                str(payload.get("recipient") or payload.get("sender_name") or ""),
                kind=event_type,
                ts=ts,
            )

    salient_city_signals = [
        item
        for item in city_signals
        if bool(item.get("tagged"))
        or bool(item.get("is_direct"))
        or bool(item.get("is_question"))
        or bool(item.get("is_request"))
    ]

    active_social_threads = sorted(
        thread_state.values(),
        key=lambda item: (-int(item.get("interaction_count") or 0), str(item.get("last_ts") or "")),
    )[:8]

    concerns: list[dict[str, Any]] = []
    if route is not None:
        concerns.append(
            {
                "kind": "travel",
                "label": str(route.get("destination") or "").strip(),
                "detail": "active route",
            }
        )
    if freshest_direct_questions:
        latest = freshest_direct_questions[-1]
        concerns.append(
            {
                "kind": "reply",
                "label": str(latest.get("speaker") or "").strip(),
                "detail": "direct question awaiting reply",
            }
        )
    elif freshest_direct_requests:
        latest = freshest_direct_requests[-1]
        concerns.append(
            {
                "kind": "reply",
                "label": str(latest.get("speaker") or "").strip(),
                "detail": "direct request awaiting response",
            }
        )
    if pending_mail:
        latest_mail = pending_mail[-1]
        concerns.append(
            {
                "kind": "correspondence_reply",
                "label": str(latest_mail.get("sender") or "").strip(),
                "detail": "incoming letter awaiting triage",
            }
        )
    if salient_city_signals:
        latest_city = salient_city_signals[-1]
        concerns.append(
            {
                "kind": "city_signal",
                "label": str(latest_city.get("speaker") or "").strip(),
                "detail": "recent city-channel signal",
            }
        )
    social_pressure = bool(
        freshest_direct_questions
        or freshest_direct_requests
        or pending_mail
        or mail_intents
    )
    for signal in list(state_pressure.get("signals") or [])[:3]:
        if not isinstance(signal, dict):
            continue
        label = str(signal.get("label") or signal.get("kind") or "").strip()
        if not label:
            continue
        concerns.append(
            {
                "kind": "state_pressure",
                "label": label,
                "detail": str(signal.get("kind") or "state").strip(),
            }
        )
    research_limit = 2 if social_pressure else 4
    for item in research_queue[:research_limit]:
        concerns.append(
            {
                "kind": "research",
                "label": str(item.get("query") or "").strip(),
                "detail": str(item.get("priority") or "").strip(),
            }
        )
    for item in mail_intents[:4]:
        concerns.append(
            {
                "kind": "correspondence",
                "label": str(item.get("recipient") or "").strip(),
                "detail": "unsent letter impulse",
            }
        )
    for event in reversed(events):
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event_type == "movement_blocked":
            destination = str(payload.get("destination") or "").strip()
            if destination:
                concerns.append(
                    {
                        "kind": "blocked_travel",
                        "label": destination,
                        "detail": "recent movement failed",
                    }
                )
            break

    return {
        "updated_at": _utc_now_iso(),
        "active_social_threads": active_social_threads,
        "dialogue_state": {
            "active_partner": str(
                (latest_direct or {}).get("speaker")
                or ((pending_mail[-1] if pending_mail else {}).get("sender") or "")
            ).strip(),
            "last_direct_message": latest_direct,
            "open_questions": freshest_direct_questions,
            "open_requests": freshest_direct_requests,
            "direct_urgency": 1.0 if freshest_direct_questions else 0.8 if freshest_direct_requests else 0.0,
        },
        "mail_state": {
            "pending_inbox_count": len(pending_mail),
            "latest_sender": str((pending_mail[-1] if pending_mail else {}).get("sender") or "").strip(),
            "pending_letters": pending_mail[-4:],
        },
        "city_context": {
            "signal_count": len(city_signals),
            "recent_signals": city_signals[-4:],
        },
        "state_pressure": state_pressure,
        "current_concerns": concerns[:10],
    }


def _build_memory_projection(
    events: list[dict[str, Any]],
    *,
    route: dict[str, Any] | None,
    research_queue: list[dict[str, Any]],
    mail_intents: list[dict[str, Any]],
) -> dict[str, Any]:
    recent_experiences: list[dict[str, Any]] = []
    for event in reversed(events):
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ts = str(event.get("ts") or "").strip()

        experience: dict[str, Any] | None = None
        if event_type == "grounding_observed":
            experience = {
                "kind": "grounding",
                "label": str(payload.get("observation") or "").strip()[:160],
                "ts": ts,
            }
        elif event_type == "research_result_observed":
            experience = {
                "kind": "research_result",
                "label": str(payload.get("query") or "").strip(),
                "detail": str(payload.get("result") or "").strip()[:160],
                "ts": ts,
            }
        elif event_type in {"chat_sent", "city_broadcast_sent"}:
            experience = {
                "kind": "utterance",
                "label": str(payload.get("message") or "").strip()[:120],
                "detail": event_type,
                "ts": ts,
            }
        elif event_type == "action_executed":
            experience = {
                "kind": "action",
                "label": str(payload.get("action") or "").strip()[:120],
                "detail": str(payload.get("location") or "").strip(),
                "ts": ts,
            }
        elif event_type in {"move_executed", "movement_arrived", "movement_blocked"}:
            experience = {
                "kind": "movement",
                "label": str(payload.get("destination") or payload.get("arrived_at") or "").strip(),
                "detail": event_type,
                "ts": ts,
            }
        elif event_type in {"mail_reply_sent", "mail_draft_sent", "mail_intent_sent", "mail_intent_staged"}:
            experience = {
                "kind": "mail",
                "label": str(payload.get("recipient") or payload.get("sender_name") or "").strip(),
                "detail": event_type,
                "ts": ts,
            }
        if experience is not None:
            recent_experiences.append(experience)
        if len(recent_experiences) >= 12:
            break

    return {
        "updated_at": _utc_now_iso(),
        "recent_experiences": recent_experiences,
        "active_route": route,
        "pending_research": [
            {
                "query": str(item.get("query") or "").strip(),
                "priority": str(item.get("priority") or "").strip(),
            }
            for item in research_queue[:6]
        ],
        "pending_correspondence": [
            {
                "recipient": str(item.get("recipient") or "").strip(),
                "staged_at": str(item.get("staged_at") or "").strip(),
            }
            for item in mail_intents[:6]
        ],
    }


def _build_subjective_facts(
    events: list[dict[str, Any]],
    *,
    packets: list[dict[str, Any]],
    route: dict[str, Any] | None,
    mail_intents: list[dict[str, Any]],
    research_queue: list[dict[str, Any]],
) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    thread_counts: dict[str, int] = {}
    for packet in packets:
        packet_type = str(packet.get("packet_type") or "").strip()
        payload = packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
        if packet_type in {"chat_heard", "city_chat_heard"}:
            speaker = str(payload.get("speaker") or "").strip()
            if speaker:
                key = speaker.lower()
                thread_counts[key] = thread_counts.get(key, 0) + 1

    for name_key, count in sorted(thread_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:8]:
        display_name = next(
            (
                str((packet.get("payload") or {}).get("speaker") or "").strip()
                for packet in packets
                if str((packet.get("payload") or {}).get("speaker") or "").strip().lower() == name_key
            ),
            name_key.title(),
        )
        facts.append(
            {
                "subject": "self",
                "predicate": "engaged_with",
                "object": display_name,
                "confidence": min(1.0, 0.35 + (0.15 * count)),
                "evidence": {"chat_packets": count},
                "source": "derived_from_runtime_ledger",
            }
        )

    latest_direct_question = next(
        (
            packet
            for packet in reversed(packets)
            if str(packet.get("packet_type") or "").strip() == "chat_heard"
            and bool((packet.get("payload") or {}).get("is_direct"))
            and bool((packet.get("payload") or {}).get("is_question"))
            and str((packet.get("payload") or {}).get("speaker") or "").strip()
        ),
        None,
    )
    if latest_direct_question is not None:
        payload = latest_direct_question.get("payload") if isinstance(latest_direct_question.get("payload"), dict) else {}
        speaker = str(payload.get("speaker") or "").strip()
        message = str(payload.get("message") or "").strip()
        if speaker and message:
            facts.append(
                {
                    "subject": "self",
                    "predicate": "owes_reply_to",
                    "object": speaker,
                    "confidence": 0.9,
                    "evidence": {"message_kind": _dialogue_message_kind(message), "message": message[:160]},
                    "source": "derived_from_runtime_ledger",
                }
            )

    latest_state_pressure: dict[str, Any] = {"signals": [], "raw": {}, "context": {}}
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        if event_type not in {"session_state_observed", "ambient_pressure_observed"}:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        latest_state_pressure = _merge_pressure_payload(
            latest_state_pressure,
            payload,
            ts=str(event.get("ts") or "").strip(),
        )
    if isinstance(latest_state_pressure, dict):
        for signal in list(latest_state_pressure.get("signals") or [])[:4]:
            if not isinstance(signal, dict):
                continue
            kind = str(signal.get("kind") or "").strip()
            label = str(signal.get("label") or kind).strip()
            level = _coerce_float(signal.get("level"))
            if not kind or not label:
                continue
            facts.append(
                {
                    "subject": "self",
                    "predicate": "pressed_by",
                    "object": label,
                    "confidence": min(0.95, max(0.4, level if level is not None else 0.6)),
                    "evidence": {"kind": kind, "level": level},
                    "source": "derived_from_runtime_ledger",
                }
            )

    if route is not None:
        facts.append(
            {
                "subject": "self",
                "predicate": "headed_toward",
                "object": str(route.get("destination") or "").strip(),
                "confidence": 0.9,
                "evidence": {"remaining": list(route.get("remaining") or [])},
                "source": "derived_from_runtime_ledger",
            }
        )

    for item in research_queue[:6]:
        facts.append(
            {
                "subject": "self",
                "predicate": "curious_about",
                "object": str(item.get("query") or "").strip(),
                "confidence": 0.85 if str(item.get("priority") or "") == "high" else 0.65,
                "evidence": {"priority": str(item.get("priority") or "").strip()},
                "source": "derived_from_runtime_ledger",
            }
        )

    for item in mail_intents[:6]:
        facts.append(
            {
                "subject": "self",
                "predicate": "wants_to_write",
                "object": str(item.get("recipient") or "").strip(),
                "confidence": 0.8,
                "evidence": {"mail_intent_id": str(item.get("mail_intent_id") or "").strip()},
                "source": "derived_from_runtime_ledger",
            }
        )

    if any(str(event.get("event_type") or "").strip() == "movement_blocked" for event in events[-10:]):
        blocked = next(
            (
                str((event.get("payload") or {}).get("destination") or "").strip()
                for event in reversed(events)
                if str(event.get("event_type") or "").strip() == "movement_blocked"
            ),
            "",
        )
        if blocked:
            facts.append(
                {
                    "subject": "self",
                    "predicate": "blocked_from",
                    "object": blocked,
                    "confidence": 0.7,
                    "evidence": {"recent_event": "movement_blocked"},
                    "source": "derived_from_runtime_ledger",
                }
            )

    return {
        "updated_at": _utc_now_iso(),
        "facts": facts,
    }


def _build_cognitive_projection(
    events: list[dict[str, Any]],
    *,
    runtime_projection: dict[str, Any],
    subjective_projection: dict[str, Any],
    subjective_facts: dict[str, Any],
    route: dict[str, Any] | None,
    mail_intents: list[dict[str, Any]],
) -> dict[str, Any]:
    state_pressure = subjective_projection.get("state_pressure") or {}
    pressure_signals = list(state_pressure.get("signals") or [])
    pressure_by_kind: dict[str, dict[str, Any]] = {}
    for item in pressure_signals:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        if kind:
            pressure_by_kind[kind] = item

    concerns = list(subjective_projection.get("current_concerns") or [])
    dialogue_state = subjective_projection.get("dialogue_state") or {}
    mail_state = subjective_projection.get("mail_state") or {}
    social_threads = list(subjective_projection.get("active_social_threads") or [])
    runtime_events = list(runtime_projection.get("recent_events") or [])
    last_event_ts = str((runtime_events[-1] if runtime_events else {}).get("ts") or "").strip() or None

    def signal_ref(kind: str) -> dict[str, Any] | None:
        signal = pressure_by_kind.get(kind)
        if not signal:
            return None
        return {
            "kind": "pressure_signal",
            "signal_kind": kind,
            "label": str(signal.get("label") or kind).strip(),
            "level": _clamp01(_coerce_float(signal.get("level")) or 0.0),
        }

    def concern_ref(kind: str) -> dict[str, Any] | None:
        item = next((entry for entry in concerns if str(entry.get("kind") or "").strip() == kind), None)
        if item is None:
            return None
        return {
            "kind": "concern",
            "concern_kind": kind,
            "label": str(item.get("label") or "").strip(),
            "detail": str(item.get("detail") or "").strip(),
        }

    def node(
        node_id: str,
        *,
        mode: str,
        activation: float,
        evidence_refs: list[dict[str, Any]],
        persistence_class: str,
        last_transition_at: str | None,
        sticky_minutes: float | None = None,
        neighbor_bias: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        normalized_activation = round(_clamp01(activation), 3)
        evidence_count = len(evidence_refs)
        stability = round(_clamp01(0.2 + (0.22 * evidence_count) + (0.45 * normalized_activation)), 3)
        sticky_until = (
            _plus_minutes_iso(last_transition_at or "", sticky_minutes)
            if sticky_minutes is not None and persistence_class == "sticky"
            else None
        )
        return {
            "node_id": node_id,
            "mode": mode,
            "activation": normalized_activation,
            "stability": stability,
            "persistence_class": persistence_class,
            "last_transition_at": last_transition_at,
            "refractory_until": None,
            "sticky_until": sticky_until,
            "evidence_refs": evidence_refs,
            "neighbor_bias": list(neighbor_bias or []),
        }

    vigilance_refs: list[dict[str, Any]] = []
    for signal_kind in ("danger", "tension", "bad_weather", "crowding"):
        ref = signal_ref(signal_kind)
        if ref is not None:
            vigilance_refs.append(ref)
    blocked_movement = runtime_projection.get("last_movement") or {}
    if str(blocked_movement.get("event_type") or "").strip() == "movement_blocked":
        vigilance_refs.append(
            {
                "kind": "runtime_event",
                "event_type": "movement_blocked",
                "destination": str(blocked_movement.get("destination") or "").strip(),
            }
        )
    vigilance_activation = max(
        [
            _coerce_float((pressure_by_kind.get(kind) or {}).get("level")) or 0.0
            for kind in ("danger", "tension", "bad_weather", "crowding")
        ]
        + ([0.72] if str(blocked_movement.get("event_type") or "").strip() == "movement_blocked" else [0.0])
    )
    vigilance_mode = "alarmed" if vigilance_activation >= 0.75 else "wary" if vigilance_activation >= 0.35 else "calm"
    vigilance = node(
        "vigilance",
        mode=vigilance_mode,
        activation=vigilance_activation,
        evidence_refs=vigilance_refs,
        persistence_class="sticky" if vigilance_activation >= 0.6 else "ephemeral",
        last_transition_at=str(blocked_movement.get("ts") or last_event_ts or "") or None,
        sticky_minutes=20.0,
        neighbor_bias=[
            {
                "node_id": "rest_drive",
                "weight": 0.18,
                "reason": "fatigue and vigilance often co-amplify caution",
            }
        ] if vigilance_activation >= 0.35 else [],
    )

    direct_urgency = _coerce_float(dialogue_state.get("direct_urgency")) or 0.0
    inbox_count = int(mail_state.get("pending_inbox_count") or 0)
    thread_strength = min(1.0, len(social_threads) / 4.0) if social_threads else 0.0
    social_refs: list[dict[str, Any]] = []
    for key in ("reply", "correspondence_reply", "city_signal"):
        ref = concern_ref(key)
        if ref is not None:
            social_refs.append(ref)
    if social_threads:
        social_refs.append(
            {
                "kind": "social_threads",
                "count": len(social_threads),
                "top_partner": str((social_threads[0] if social_threads else {}).get("name") or "").strip(),
            }
        )
    social_activation = max(direct_urgency, min(1.0, inbox_count * 0.3), thread_strength * 0.55)
    social_mode = "engaged" if social_activation >= 0.72 else "receptive" if social_activation >= 0.28 else "withdrawn"
    social_pull = node(
        "social_pull",
        mode=social_mode,
        activation=social_activation,
        evidence_refs=social_refs,
        persistence_class="sticky" if (direct_urgency >= 0.8 or inbox_count > 0) else "ephemeral",
        last_transition_at=last_event_ts,
        sticky_minutes=25.0,
        neighbor_bias=[
            {
                "node_id": "correspondence_pull",
                "weight": 0.24,
                "reason": "active dialogue and unanswered mail reinforce each other",
            }
        ] if social_activation >= 0.28 else [],
    )

    mobility_refs: list[dict[str, Any]] = []
    if route is not None:
        mobility_refs.append(
            {
                "kind": "active_route",
                "destination": str(route.get("destination") or "").strip(),
                "remaining_count": len(list(route.get("remaining") or [])),
            }
        )
    for key in ("travel", "blocked_travel", "city_signal", "research"):
        ref = concern_ref(key)
        if ref is not None:
            mobility_refs.append(ref)
    event_pull_level = _coerce_float((pressure_by_kind.get("event_pull") or {}).get("level")) or 0.0
    mobility_activation = 0.92 if route is not None else max(event_pull_level, 0.52 if concern_ref("research") else 0.08)
    mobility_mode = "goal_directed" if mobility_activation >= 0.8 else "wandering" if mobility_activation >= 0.32 else "rooted"
    mobility_drive = node(
        "mobility_drive",
        mode=mobility_mode,
        activation=mobility_activation,
        evidence_refs=mobility_refs,
        persistence_class="sticky" if route is not None or event_pull_level >= 0.6 else "ephemeral",
        last_transition_at=str((runtime_projection.get("last_movement") or {}).get("ts") or last_event_ts or "") or None,
        sticky_minutes=30.0,
        neighbor_bias=[
            {
                "node_id": "vigilance",
                "weight": -0.16,
                "reason": "high vigilance tends to damp open-ended movement",
            }
        ] if mobility_activation >= 0.32 else [],
    )

    correspondence_refs: list[dict[str, Any]] = []
    if inbox_count:
        correspondence_refs.append(
            {
                "kind": "pending_inbox",
                "count": inbox_count,
                "latest_sender": str(mail_state.get("latest_sender") or "").strip(),
            }
        )
    if mail_intents:
        correspondence_refs.append(
            {
                "kind": "mail_intents",
                "count": len(mail_intents),
                "latest_recipient": str((mail_intents[0] if mail_intents else {}).get("recipient") or "").strip(),
            }
        )
    correspondence_activation = max(min(1.0, inbox_count * 0.4), min(1.0, len(mail_intents) * 0.28))
    correspondence_mode = (
        "urgent" if correspondence_activation >= 0.75
        else "pulling" if correspondence_activation >= 0.25
        else "dormant"
    )
    correspondence_pull = node(
        "correspondence_pull",
        mode=correspondence_mode,
        activation=correspondence_activation,
        evidence_refs=correspondence_refs,
        persistence_class="sticky" if (inbox_count > 0 or bool(mail_intents)) else "ephemeral",
        last_transition_at=str((runtime_projection.get("last_mail") or {}).get("ts") or last_event_ts or "") or None,
        sticky_minutes=45.0,
        neighbor_bias=[
            {
                "node_id": "social_pull",
                "weight": 0.24,
                "reason": "lingering social contact often manifests as correspondence pressure",
            }
        ] if correspondence_activation >= 0.25 else [],
    )

    fatigue_level = _coerce_float((pressure_by_kind.get("fatigue") or {}).get("level")) or 0.0
    time_of_day = str((state_pressure.get("context") or {}).get("time_of_day") or "").strip().lower()
    rest_refs: list[dict[str, Any]] = []
    fatigue_ref = signal_ref("fatigue")
    if fatigue_ref is not None:
        rest_refs.append(fatigue_ref)
    if time_of_day:
        rest_refs.append({"kind": "context", "time_of_day": time_of_day})
    rest_activation = max(fatigue_level, 0.62 if time_of_day in {"night", "late_evening", "sleep_window"} else 0.0)
    rest_mode = "shutting_down" if rest_activation >= 0.82 else "tired" if rest_activation >= 0.38 else "active"
    rest_drive = node(
        "rest_drive",
        mode=rest_mode,
        activation=rest_activation,
        evidence_refs=rest_refs,
        persistence_class="sticky" if rest_activation >= 0.55 else "ephemeral",
        last_transition_at=last_event_ts,
        sticky_minutes=40.0,
        neighbor_bias=[
            {
                "node_id": "mobility_drive",
                "weight": -0.22,
                "reason": "high rest drive reduces open-ended exploration",
            }
        ] if rest_activation >= 0.38 else [],
    )

    nodes = {
        "vigilance": vigilance,
        "social_pull": social_pull,
        "mobility_drive": mobility_drive,
        "correspondence_pull": correspondence_pull,
        "rest_drive": rest_drive,
    }
    active_nodes = [
        node_id
        for node_id, node_payload in sorted(
            nodes.items(),
            key=lambda item: (-float(item[1].get("activation") or 0.0), item[0]),
        )
        if float(node_payload.get("activation") or 0.0) >= 0.35
    ]
    facts = list(subjective_facts.get("facts") or [])
    return {
        "updated_at": _utc_now_iso(),
        "node_contract": {
            "version": "v1",
            "fields": [
                "node_id",
                "mode",
                "activation",
                "stability",
                "persistence_class",
                "last_transition_at",
                "refractory_until",
                "sticky_until",
                "evidence_refs",
                "neighbor_bias",
            ],
            "persistence_classes": {
                "ephemeral": "Short-lived activation that should decay automatically if not reinforced.",
                "sticky": "Activation that should persist across several loop cycles and bias later interpretation.",
                "matured": "Repeated, durable structure that may later feed subjective facts or governed identity growth.",
            },
        },
        "active_nodes": active_nodes,
        "nodes": nodes,
        "evidence_summary": {
            "state_pressure_signal_count": len(pressure_signals),
            "subjective_fact_count": len(facts),
            "social_thread_count": len(social_threads),
            "pending_mail_intent_count": len(mail_intents),
        },
    }


def reduce_runtime_events(events: list[dict[str, Any]]) -> ResidentReducedState:
    packets = _derive_packets_from_events(events)
    intents = _derive_intents_from_events(events)
    active_route = _derive_active_route_from_events(events)
    active_mail_intents = _derive_active_mail_intents_from_events(events)
    research_queue = _derive_research_queue_from_events(events)
    runtime_projection = _build_runtime_projection(events, research_queue=research_queue)
    subjective_projection = _build_subjective_projection(
        events,
        packets=packets,
        route=active_route,
        mail_intents=active_mail_intents,
        research_queue=research_queue,
    )
    memory_projection = _build_memory_projection(
        events,
        route=active_route,
        research_queue=research_queue,
        mail_intents=active_mail_intents,
    )
    subjective_facts = _build_subjective_facts(
        events,
        packets=packets,
        route=active_route,
        mail_intents=active_mail_intents,
        research_queue=research_queue,
    )
    return ResidentReducedState(
        events=list(events),
        packets=packets,
        intents=intents,
        active_route=active_route,
        active_mail_intents=active_mail_intents,
        research_queue=research_queue,
        runtime_projection=runtime_projection,
        subjective_projection=subjective_projection,
        memory_projection=memory_projection,
        subjective_facts=subjective_facts,
        cognitive_projection=_build_cognitive_projection(
            events,
            runtime_projection=runtime_projection,
            subjective_projection=subjective_projection,
            subjective_facts=subjective_facts,
            route=active_route,
            mail_intents=active_mail_intents,
        ),
    )


def _write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def _write_runtime_compatibility_projections(memory_dir: Path, state: ResidentReducedState) -> None:
    # Packets and intents are pure event-log views (see signals.py); they are
    # never written as json shadows. Only the sidecars still read directly by
    # loops — the active route and staged mail intents — are materialized here.
    memory_dir.mkdir(parents=True, exist_ok=True)
    route_path = _route_projection_path(memory_dir)
    if state.active_route is None:
        route_path.unlink(missing_ok=True)
    else:
        _write_json(route_path, state.active_route)

    intents_dir = _intents_dir(memory_dir)
    intents_dir.mkdir(parents=True, exist_ok=True)
    wanted: set[str] = set()
    for item in state.active_mail_intents:
        mail_intent_id = str(item.get("mail_intent_id") or "").strip()
        recipient = str(item.get("recipient") or "").strip()
        context = str(item.get("context") or "").strip()
        staged_at = str(item.get("staged_at") or "").strip()
        if not mail_intent_id or not recipient:
            continue
        filename = _mail_intent_filename(mail_intent_id, recipient)
        wanted.add(filename)
        (intents_dir / filename).write_text(
            (
                f"Mail-Intent-ID: {mail_intent_id}\n"
                f"To: {recipient}\n"
                f"Staged-At: {staged_at}\n\n"
                "Context:\n"
                f"{context}"
            ),
            encoding="utf-8",
        )
    for path in intents_dir.glob("intent_*.md"):
        if path.name not in wanted:
            path.unlink(missing_ok=True)


def sync_runtime_compatibility_projections(memory_dir: Path) -> None:
    _write_runtime_compatibility_projections(memory_dir, reduce_runtime_events(_load_events(memory_dir)))


def write_runtime_projection(memory_dir: Path) -> None:
    _write_json(
        _projection_path(memory_dir),
        reduce_runtime_events(_load_events(memory_dir)).runtime_projection,
    )


def write_subjective_projection(memory_dir: Path) -> None:
    _write_json(
        _subjective_projection_path(memory_dir),
        reduce_runtime_events(_load_events(memory_dir)).subjective_projection,
    )


def write_memory_projection(memory_dir: Path) -> None:
    _write_json(
        _memory_projection_path(memory_dir),
        reduce_runtime_events(_load_events(memory_dir)).memory_projection,
    )


def write_subjective_facts(memory_dir: Path) -> None:
    _write_json(
        _subjective_facts_path(memory_dir),
        reduce_runtime_events(_load_events(memory_dir)).subjective_facts,
    )


def write_cognitive_projection(memory_dir: Path) -> None:
    _write_json(
        _cognitive_projection_path(memory_dir),
        reduce_runtime_events(_load_events(memory_dir)).cognitive_projection,
    )


def rebuild_runtime_artifacts(
    memory_dir: Path,
    *,
    events: list[dict[str, Any]] | None = None,
) -> ResidentReducedState:
    reduced = reduce_runtime_events(list(events) if events is not None else _load_events(memory_dir))
    _write_runtime_compatibility_projections(memory_dir, reduced)
    _write_json(_projection_path(memory_dir), reduced.runtime_projection)
    _write_json(_subjective_projection_path(memory_dir), reduced.subjective_projection)
    _write_json(_memory_projection_path(memory_dir), reduced.memory_projection)
    _write_json(_subjective_facts_path(memory_dir), reduced.subjective_facts)
    _write_json(_cognitive_projection_path(memory_dir), reduced.cognitive_projection)
    return reduced


def append_runtime_event(
    memory_dir: Path,
    *,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    events = _load_events(memory_dir)
    event = {
        "event_id": f"evt-{uuid.uuid4().hex[:12]}",
        "ts": _utc_now_iso(),
        "event_type": str(event_type).strip(),
        "payload": dict(payload or {}),
    }
    events.append(event)
    _save_events(memory_dir, events)
    rebuild_runtime_artifacts(memory_dir)
    return event
