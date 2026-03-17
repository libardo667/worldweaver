from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LEDGER_FILENAME = "runtime_ledger.jsonl"
_PROJECTION_FILENAME = "runtime_projection.json"
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
        elif event_type in {"mail_reply_sent", "mail_draft_sent", "mail_intent_sent", "mail_doula_vote_cast", "mail_intent_declined"}:
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
    return event
