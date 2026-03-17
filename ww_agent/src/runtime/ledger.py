from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LEDGER_FILENAME = "runtime_ledger.jsonl"
_PROJECTION_FILENAME = "runtime_projection.json"
_SUBJECTIVE_PROJECTION_FILENAME = "subjective_projection.json"
_MEMORY_PROJECTION_FILENAME = "memory_projection.json"
_SUBJECTIVE_FACTS_FILENAME = "subjective_facts.json"
_PACKET_PROJECTION_FILENAME = "stimulus_packets.json"
_INTENT_PROJECTION_FILENAME = "intent_queue.json"
_ROUTE_PROJECTION_FILENAME = "active_route.json"
_MAX_EVENTS = 1000


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _packet_projection_path(memory_dir: Path) -> Path:
    return memory_dir / _PACKET_PROJECTION_FILENAME


def _intent_projection_path(memory_dir: Path) -> Path:
    return memory_dir / _INTENT_PROJECTION_FILENAME


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


def _save_events(memory_dir: Path, events: list[dict[str, Any]]) -> None:
    path = _ledger_path(memory_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    trimmed = events[-_MAX_EVENTS:]
    lines = [json.dumps(event, ensure_ascii=True) for event in trimmed]
    text = ("\n".join(lines) + "\n") if lines else ""
    path.write_text(text, encoding="utf-8")


def derive_packets(memory_dir: Path) -> list[dict[str, Any]]:
    packets: dict[str, dict[str, Any]] = {}
    for event in _load_events(memory_dir):
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


def derive_intents(memory_dir: Path) -> list[dict[str, Any]]:
    intents: dict[str, dict[str, Any]] = {}
    for event in _load_events(memory_dir):
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


def derive_active_route(memory_dir: Path) -> dict[str, Any] | None:
    route: dict[str, Any] | None = None
    for event in _load_events(memory_dir):
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


def derive_active_mail_intents(memory_dir: Path) -> list[dict[str, Any]]:
    staged: dict[str, dict[str, Any]] = {}
    terminal_types = {"mail_intent_sent", "mail_intent_declined", "mail_intent_suppressed"}
    for event in _load_events(memory_dir):
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


def derive_research_queue(memory_dir: Path) -> list[dict[str, Any]]:
    queued: dict[str, dict[str, Any]] = {}
    for event in _load_events(memory_dir):
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


def sync_runtime_queue_projections(memory_dir: Path) -> None:
    memory_dir.mkdir(parents=True, exist_ok=True)
    _packet_projection_path(memory_dir).write_text(
        json.dumps(derive_packets(memory_dir), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    _intent_projection_path(memory_dir).write_text(
        json.dumps(derive_intents(memory_dir), indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def sync_runtime_compatibility_projections(memory_dir: Path) -> None:
    sync_runtime_queue_projections(memory_dir)

    route = derive_active_route(memory_dir)
    route_path = _route_projection_path(memory_dir)
    if route is None:
        route_path.unlink(missing_ok=True)
    else:
        route_path.write_text(
            json.dumps(route, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    intents_dir = _intents_dir(memory_dir)
    intents_dir.mkdir(parents=True, exist_ok=True)
    active_intents = derive_active_mail_intents(memory_dir)
    wanted: set[str] = set()
    for item in active_intents:
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


def write_runtime_projection(memory_dir: Path) -> None:
    events = _load_events(memory_dir)
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

    projection = {
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
    _projection_path(memory_dir).write_text(
        json.dumps(projection, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def write_subjective_projection(memory_dir: Path) -> None:
    packets = derive_packets(memory_dir)
    route = derive_active_route(memory_dir)
    mail_intents = derive_active_mail_intents(memory_dir)
    research_queue = derive_research_queue(memory_dir)
    events = _load_events(memory_dir)

    thread_state: dict[str, dict[str, Any]] = {}

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
            touch_thread(str(payload.get("speaker") or ""), kind=packet_type, ts=ts)
        elif packet_type == "mail_received":
            sender = _sender_from_filename(str(payload.get("filename") or ""))
            touch_thread(sender, kind="mail_received", ts=ts)

    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ts = str(event.get("ts") or "").strip()
        if event_type in {"mail_intent_staged", "mail_intent_sent", "mail_reply_sent", "mail_draft_sent"}:
            touch_thread(
                str(payload.get("recipient") or payload.get("sender_name") or ""),
                kind=event_type,
                ts=ts,
            )

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
    for item in research_queue[:4]:
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

    subjective = {
        "updated_at": _utc_now_iso(),
        "active_social_threads": active_social_threads,
        "current_concerns": concerns[:10],
    }
    _subjective_projection_path(memory_dir).write_text(
        json.dumps(subjective, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def write_memory_projection(memory_dir: Path) -> None:
    events = _load_events(memory_dir)
    route = derive_active_route(memory_dir)
    research_queue = derive_research_queue(memory_dir)
    mail_intents = derive_active_mail_intents(memory_dir)

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

    memory_projection = {
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
    _memory_projection_path(memory_dir).write_text(
        json.dumps(memory_projection, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def write_subjective_facts(memory_dir: Path) -> None:
    route = derive_active_route(memory_dir)
    research_queue = derive_research_queue(memory_dir)
    mail_intents = derive_active_mail_intents(memory_dir)
    packets = derive_packets(memory_dir)
    events = _load_events(memory_dir)

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

    for item in sorted(thread_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:8]:
        name_key, count = item
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

    _subjective_facts_path(memory_dir).write_text(
        json.dumps(
            {
                "updated_at": _utc_now_iso(),
                "facts": facts,
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )


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
    sync_runtime_compatibility_projections(memory_dir)
    write_runtime_projection(memory_dir)
    write_memory_projection(memory_dir)
    write_subjective_projection(memory_dir)
    write_subjective_facts(memory_dir)
    return event
