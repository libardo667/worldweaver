# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from __future__ import annotations

import json
import os
import uuid
from copy import deepcopy
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

import fcntl

from src.runtime.relations import RELATIONAL_EVENT_SCHEMA_VERSION

_LEDGER_FILENAME = "runtime_ledger.jsonl"
_CHECKPOINT_FILENAME = "runtime_checkpoint.json"
_WRITER_LOCK_FILENAME = "runtime_ledger.lock"
_LEGACY_DERIVED_FILENAMES = {
    "active_route.json",
    "cognitive_projection.json",
    "memory_projection.json",
    "runtime_projection.json",
    "runtime_snapshot.json",
    "subjective_facts.json",
    "subjective_projection.json",
}

CHECKPOINT_FORMAT_VERSION = 2
REDUCER_FORMAT_VERSION = 3
PROJECTION_FORMAT_VERSIONS = {
    "runtime": 1,
    "subjective": 1,
    "memory": 1,
    "subjective_facts": 1,
    "cognitive": 1,
}
PACKET_PROJECTION_LIMIT = 200
INTENT_PROJECTION_LIMIT = 100
MAIL_INTENT_PROJECTION_LIMIT = 100
RESEARCH_QUEUE_PROJECTION_LIMIT = 100
PROJECTION_REPLAY_MAX_EVENTS = 10_000
RELATIONSHIP_PROJECTION_SCHEMA_VERSION = 1
PACKET_OPEN_STATUSES = {"pending", "processing"}
INTENT_OPEN_STATUSES = {"pending", "claimed"}

PROJECTION_STATE_EVENT_TYPES = {
    "packet_emitted",
    "packet_status_changed",
    "intent_staged",
    "intent_status_changed",
    "route_state_changed",
    "mail_intent_staged",
    "mail_intent_sent",
    "mail_intent_declined",
    "mail_intent_suppressed",
    "mail_reply_sent",
    "mail_draft_sent",
    "mail_doula_vote_cast",
    "research_queued",
    "research_popped",
    "research_result_observed",
    "grounding_observed",
    "ground_intent_executed",
    "move_executed",
    "movement_arrived",
    "movement_blocked",
    "session_state_observed",
    "ambient_pressure_observed",
    "chat_sent",
    "city_broadcast_sent",
    "action_executed",
}
SIMPLE_CHECKPOINT_EVENT_TYPES = {
    "packet_status_changed",
    "intent_staged",
    "intent_status_changed",
}

# Runtime reducers operate on a bounded hot horizon while the cold JSONL remains complete.
# The slowest current decaying reducer is the four-hour baseline. Six half-lives puts a
# unit-strength contribution below the substrate's 0.02 significance floor.
LONGEST_RUNTIME_REDUCER_HALF_LIFE_SECONDS = 4 * 3600.0
RUNTIME_READ_WINDOW_SECONDS = 6 * LONGEST_RUNTIME_REDUCER_HALF_LIFE_SECONDS
RUNTIME_READ_MAX_EVENTS = 50_000
assert RUNTIME_READ_WINDOW_SECONDS > LONGEST_RUNTIME_REDUCER_HALF_LIFE_SECONDS


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


class LedgerCorruptionError(RuntimeError):
    """The durable ledger cannot be interpreted without discarding history."""

    def __init__(self, message: str, *, byte_offset: int | None = None) -> None:
        if byte_offset is not None:
            message = f"{message} (byte offset {byte_offset})"
        super().__init__(message)
        self.byte_offset = byte_offset


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


def _replay_as_of_iso(
    events: list[dict[str, Any]], *, as_of: datetime | str | None = None
) -> str:
    if as_of is not None:
        candidate = as_of.isoformat() if isinstance(as_of, datetime) else str(as_of)
        parsed = _parse_iso_ts(candidate)
        if parsed is None:
            raise ValueError(f"invalid replay as_of timestamp: {candidate!r}")
        return parsed.isoformat()
    for event in reversed(events):
        parsed = _parse_iso_ts(str(event.get("ts") or ""))
        if parsed is not None:
            return parsed.isoformat()
    return datetime(1970, 1, 1, tzinfo=timezone.utc).isoformat()


def _ledger_path(memory_dir: Path) -> Path:
    return memory_dir / _LEDGER_FILENAME


def _checkpoint_path(memory_dir: Path) -> Path:
    return memory_dir / _CHECKPOINT_FILENAME


def _writer_lock_path(memory_dir: Path) -> Path:
    return memory_dir / _WRITER_LOCK_FILENAME


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
    ambient_signal_kinds = {
        "crowding",
        "quiet",
        "event_pull",
        "bad_weather",
        "place_character",
    }
    session_signal_kinds = {"danger", "tension", "fatigue", "melancholy", "loneliness"}
    ambient_raw_keys = {
        "scene_present_count",
        "scene_event_count",
        "current_present",
        "recent_event_count",
        "vitality_score",
    }
    session_raw_keys = {
        "danger_level",
        "danger",
        "tension",
        "_mood_tension",
        "fatigue",
        "energy",
        "_mood_melancholy",
        "loneliness",
    }
    ambient_context_keys = {
        "headline",
        "location",
        "neighborhood",
        "neighborhood_vibe",
        "region",
    }
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
            if not (
                isinstance(item, dict)
                and str(item.get("kind") or "").strip() in ambient_signal_kinds
            )
        ]
        for key in ambient_raw_keys:
            merged["raw"].pop(key, None)
        for key in ambient_context_keys:
            merged["context"].pop(key, None)
    elif source == "session_state":
        merged["signals"] = [
            item
            for item in list(merged.get("signals") or [])
            if not (
                isinstance(item, dict)
                and str(item.get("kind") or "").strip() in session_signal_kinds
            )
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
        source_name = str(item.get("source") or "").strip()
        if source_name:
            normalized["source"] = source_name
        pressure_tags = [
            str(tag).strip()
            for tag in list(item.get("pressure_tags") or [])
            if str(tag).strip()
        ]
        if pressure_tags:
            normalized["pressure_tags"] = pressure_tags
        sensory_note = str(item.get("sensory_note") or "").strip()
        if sensory_note:
            normalized["sensory_note"] = sensory_note
        key = (kind, label)
        existing_idx = signal_index.get(key)
        if existing_idx is None:
            signal_index[key] = len(merged["signals"])
            merged["signals"].append(normalized)
            continue
        existing = merged["signals"][existing_idx]
        existing_level = (
            _coerce_float(existing.get("level")) if isinstance(existing, dict) else None
        )
        if existing_level is None or normalized["level"] >= existing_level:
            merged["signals"][existing_idx] = normalized
    merged["raw"].update(dict(payload.get("raw") or {}))
    merged["context"].update(dict(payload.get("context") or {}))
    return merged


def _build_world_salience_projection(
    payload: dict[str, Any],
    *,
    ts: str,
) -> dict[str, Any]:
    """Describe the current competing world features without selecting a winner.

    This is an inspectable resident-side view of what the latest scene offered.
    It records dilution/concentration mechanically; it does not inject any feature
    into the prompt or steer the resident toward one.
    """

    features: list[dict[str, Any]] = []
    for index, item in enumerate(list(payload.get("signals") or [])):
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        label = str(item.get("label") or kind).strip()
        if not kind or not label:
            continue
        source = str(item.get("source") or "ambient").strip()
        intensity = round(_clamp01(_coerce_float(item.get("level")) or 0.0), 3)
        features.append(
            {
                "cluster_id": f"{source}:{kind}:{index}",
                "kind": kind,
                "label": label,
                "source": source,
                "intensity": intensity,
                "pressure_tags": [
                    str(tag).strip()
                    for tag in list(item.get("pressure_tags") or [])
                    if str(tag).strip()
                ],
            }
        )

    total = sum(float(item["intensity"]) for item in features)
    shares = [float(item["intensity"]) / total for item in features if total > 0.0]
    concentration = sum(share * share for share in shares)
    source_count = len({str(item["source"]) for item in features})
    return {
        "observed_at": ts or None,
        "location": str((payload.get("context") or {}).get("location") or "").strip(),
        "features": features,
        "feature_count": len(features),
        "independent_source_count": source_count,
        "plural": len(features) >= 2 and source_count >= 2,
        "dominant_share": round(max(shares), 3) if shares else 0.0,
        "effective_feature_count": (
            round(1.0 / concentration, 3) if concentration > 0.0 else 0.0
        ),
    }


def _decode_ledger_record(encoded: bytes, *, byte_offset: int) -> dict[str, Any]:
    try:
        raw = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LedgerCorruptionError(
            "runtime ledger contains malformed JSON",
            byte_offset=byte_offset,
        ) from exc
    if not isinstance(raw, dict):
        raise LedgerCorruptionError(
            "runtime ledger record is not a JSON object",
            byte_offset=byte_offset,
        )
    return raw


def _validate_event_sequence(
    event: dict[str, Any], *, expected: int, byte_offset: int
) -> None:
    value = event.get("sequence")
    if value is None:
        # Ledgers written before checkpoint format 2 use physical record order.
        return
    if isinstance(value, bool) or not isinstance(value, int) or value != expected:
        raise LedgerCorruptionError(
            f"runtime ledger sequence must be {expected}, found {value!r}",
            byte_offset=byte_offset,
        )


def _load_events(memory_dir: Path) -> list[dict[str, Any]]:
    path = _ledger_path(memory_dir)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    byte_offset = 0
    with path.open("rb") as handle:
        for expected_sequence, encoded in enumerate(handle, start=1):
            record_offset = byte_offset
            byte_offset += len(encoded)
            if not encoded.endswith(b"\n"):
                raise LedgerCorruptionError(
                    "runtime ledger ends with an incomplete record",
                    byte_offset=record_offset,
                )
            if not encoded.strip():
                raise LedgerCorruptionError(
                    "runtime ledger contains a blank record",
                    byte_offset=record_offset,
                )
            raw = _decode_ledger_record(encoded, byte_offset=record_offset)
            _validate_event_sequence(
                raw,
                expected=expected_sequence,
                byte_offset=record_offset,
            )
            events.append(raw)
    return events


def load_runtime_events(memory_dir: Path) -> list[dict[str, Any]]:
    """Load the complete cold ledger for audit, migration, and offline research."""
    return _load_events(memory_dir)


def load_current_runtime_state(memory_dir: Path) -> ResidentReducedState:
    """Read current derived state, using cold history only when no checkpoint is valid."""
    checkpoint = load_runtime_checkpoint(memory_dir)
    if checkpoint is None:
        return reduce_runtime_events(_load_events(memory_dir))
    state = checkpoint["state"]
    return ResidentReducedState(
        events=[],
        packets=deepcopy(list(state.get("packets") or [])),
        intents=deepcopy(list(state.get("intents") or [])),
        active_route=deepcopy(state.get("active_route")),
        active_mail_intents=deepcopy(list(state.get("active_mail_intents") or [])),
        research_queue=deepcopy(list(state.get("research_queue") or [])),
        runtime_projection=deepcopy(dict(state.get("runtime_projection") or {})),
        subjective_projection=deepcopy(dict(state.get("subjective_projection") or {})),
        memory_projection=deepcopy(dict(state.get("memory_projection") or {})),
        subjective_facts=deepcopy(dict(state.get("subjective_facts") or {})),
        cognitive_projection=deepcopy(dict(state.get("cognitive_projection") or {})),
    )


def _iter_ledger_lines_reverse(path: Path, *, chunk_size: int = 64 * 1024):
    """Yield non-empty JSONL records newest-first without reading the whole file."""
    with path.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()
        if position:
            handle.seek(-1, 2)
            if handle.read(1) != b"\n":
                raise LedgerCorruptionError(
                    "runtime ledger ends with an incomplete record"
                )
        remainder = b""
        while position > 0:
            read_size = min(chunk_size, position)
            position -= read_size
            handle.seek(position)
            block = handle.read(read_size) + remainder
            parts = block.split(b"\n")
            remainder = parts[0]
            for line in reversed(parts[1:]):
                if line.strip():
                    yield line
        if remainder.strip():
            yield remainder


def load_runtime_reducer_events(
    memory_dir: Path,
    *,
    now: Any = None,
    window_seconds: float = RUNTIME_READ_WINDOW_SECONDS,
) -> list[dict[str, Any]]:
    """Load only the hot event horizon used by short-timescale runtime reducers.

    The cold ledger remains the authority and is never trimmed. If more than the explicit
    density ceiling falls inside the horizon, fail loudly instead of silently amputating a
    reducer's basis; that case requires an incremental checkpoint before the resident runs on.
    """
    requested_window = float(window_seconds)
    if requested_window < LONGEST_RUNTIME_REDUCER_HALF_LIFE_SECONDS:
        raise ValueError(
            "runtime reducer window must exceed the longest reducer half-life "
            f"({LONGEST_RUNTIME_REDUCER_HALF_LIFE_SECONDS:.0f}s)"
        )
    path = _ledger_path(memory_dir)
    if not path.exists():
        return []
    now_dt = _parse_iso_ts(str(now or ""))
    newest_ts: datetime | None = now_dt
    selected: list[dict[str, Any]] = []
    for encoded in _iter_ledger_lines_reverse(path):
        try:
            raw = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LedgerCorruptionError(
                "runtime ledger contains malformed JSON in the reducer horizon"
            ) from exc
        if not isinstance(raw, dict):
            raise LedgerCorruptionError(
                "runtime ledger record is not a JSON object in the reducer horizon"
            )
        event_ts = _parse_iso_ts(str(raw.get("ts") or ""))
        if newest_ts is None and event_ts is not None:
            newest_ts = event_ts
        if newest_ts is not None and event_ts is not None:
            age_seconds = (newest_ts - event_ts).total_seconds()
            if age_seconds > requested_window:
                break
        selected.append(raw)
        if len(selected) > RUNTIME_READ_MAX_EVENTS:
            raise RuntimeError(
                "runtime reducer horizon exceeds the safe event-density ceiling; "
                "add or advance an incremental reducer checkpoint"
            )
    selected.reverse()
    return selected


def load_runtime_projection_events(
    memory_dir: Path,
    *,
    max_events: int = PROJECTION_REPLAY_MAX_EVENTS,
) -> list[dict[str, Any]]:
    """Load the bounded recent history used to rebuild the resident's working view."""
    requested_limit = int(max_events)
    if requested_limit < 1:
        raise ValueError("projection replay limit must be positive")
    path = _ledger_path(memory_dir)
    if not path.exists():
        return []
    selected: list[dict[str, Any]] = []
    for encoded in _iter_ledger_lines_reverse(path):
        try:
            raw = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LedgerCorruptionError(
                "runtime ledger contains malformed JSON in the projection horizon"
            ) from exc
        if not isinstance(raw, dict):
            raise LedgerCorruptionError(
                "runtime ledger record is not a JSON object in the projection horizon"
            )
        selected.append(raw)
        if len(selected) >= requested_limit:
            break
    selected.reverse()
    return selected


def _append_event(memory_dir: Path, event: dict[str, Any]) -> None:
    path = _ledger_path(memory_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(event, ensure_ascii=True) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())


@contextmanager
def _serialized_writer(memory_dir: Path) -> Iterator[None]:
    memory_dir.mkdir(parents=True, exist_ok=True)
    with _writer_lock_path(memory_dir).open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _quarantine_incomplete_tail(memory_dir: Path) -> Path | None:
    """Remove and preserve bytes after the ledger's final complete newline."""
    path = _ledger_path(memory_dir)
    if not path.exists() or path.stat().st_size == 0:
        return None
    with path.open("r+b") as handle:
        handle.seek(-1, 2)
        if handle.read(1) == b"\n":
            return None
        handle.seek(0)
        content = handle.read()
        complete_end = content.rfind(b"\n") + 1
        tail = content[complete_end:]
        quarantine_path = memory_dir / (
            f"runtime_ledger.corrupt-tail.{uuid.uuid4().hex}.jsonl"
        )
        with quarantine_path.open("xb") as quarantine:
            quarantine.write(tail)
            quarantine.flush()
            os.fsync(quarantine.fileno())
        handle.seek(complete_end)
        handle.truncate()
        handle.flush()
        os.fsync(handle.fileno())
    return quarantine_path


def _bounded_lifecycle_view(
    items: list[dict[str, Any]],
    *,
    open_statuses: set[str],
    limit: int,
    item_kind: str,
    created_key: str = "created_at",
) -> list[dict[str, Any]]:
    ordered = sorted(items, key=lambda item: str(item.get(created_key) or ""))
    open_items = [
        item
        for item in ordered
        if str(item.get("status") or "pending").strip().lower() in open_statuses
    ]
    if len(open_items) > limit:
        raise RuntimeError(
            f"open {item_kind} count {len(open_items)} exceeds the safe ceiling "
            f"of {limit}; close or explicitly migrate outstanding work"
        )
    terminal_items = [item for item in ordered if item not in open_items]
    terminal_budget = limit - len(open_items)
    retained_terminal = terminal_items[-terminal_budget:] if terminal_budget else []
    return sorted(
        [*open_items, *retained_terminal],
        key=lambda item: str(item.get(created_key) or ""),
    )


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
                packets[packet_id]["status"] = str(
                    payload.get("status")
                    or packets[packet_id].get("status")
                    or "pending"
                ).strip()
    return _bounded_lifecycle_view(
        list(packets.values()),
        open_statuses=PACKET_OPEN_STATUSES,
        limit=PACKET_PROJECTION_LIMIT,
        item_kind="packet",
    )


def derive_packets(memory_dir: Path) -> list[dict[str, Any]]:
    return load_current_runtime_state(memory_dir).packets


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
                intents[intent_id]["status"] = str(
                    payload.get("status")
                    or intents[intent_id].get("status")
                    or "pending"
                ).strip()
                validation_state = str(payload.get("validation_state") or "").strip()
                if validation_state:
                    intents[intent_id]["validation_state"] = validation_state
    newest = _bounded_lifecycle_view(
        list(intents.values()),
        open_statuses=INTENT_OPEN_STATUSES,
        limit=INTENT_PROJECTION_LIMIT,
        item_kind="intent",
    )
    return sorted(
        newest,
        key=lambda item: (
            -float(item.get("priority") or 0.5),
            str(item.get("created_at") or ""),
        ),
    )


def derive_intents(memory_dir: Path) -> list[dict[str, Any]]:
    return load_current_runtime_state(memory_dir).intents


def _derive_active_route_from_events(
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
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
    return load_current_runtime_state(memory_dir).active_route


def _derive_active_mail_intents_from_events(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    staged: dict[str, dict[str, Any]] = {}
    terminal_types = {
        "mail_intent_sent",
        "mail_intent_declined",
        "mail_intent_suppressed",
    }
    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        mail_intent_id = str(payload.get("mail_intent_id") or "").strip()
        if event_type == "mail_intent_staged" and mail_intent_id:
            staged[mail_intent_id] = dict(payload)
        elif event_type in terminal_types and mail_intent_id:
            staged.pop(mail_intent_id, None)
    ordered = sorted(
        staged.values(),
        key=lambda item: str(item.get("staged_at") or item.get("ts") or ""),
    )
    if len(ordered) > MAIL_INTENT_PROJECTION_LIMIT:
        raise RuntimeError(
            f"open mail intent count {len(ordered)} exceeds the safe ceiling "
            f"of {MAIL_INTENT_PROJECTION_LIMIT}; close or explicitly migrate outstanding work"
        )
    return ordered


def derive_active_mail_intents(memory_dir: Path) -> list[dict[str, Any]]:
    return load_current_runtime_state(memory_dir).active_mail_intents


def _derive_research_queue_from_events(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
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
                "priority": str(payload.get("priority") or "normal").strip()
                or "normal",
                "source": str(payload.get("source") or "").strip(),
                "added_ts": str(
                    payload.get("added_ts") or event.get("ts") or ""
                ).strip(),
            }
        elif event_type == "research_popped":
            queued.pop(key, None)
    priority_rank = {"high": 0, "normal": 1, "low": 2}
    newest = sorted(
        queued.values(),
        key=lambda item: str(item.get("added_ts") or ""),
    )
    if len(newest) > RESEARCH_QUEUE_PROJECTION_LIMIT:
        raise RuntimeError(
            f"open research item count {len(newest)} exceeds the safe ceiling "
            f"of {RESEARCH_QUEUE_PROJECTION_LIMIT}; close or explicitly migrate outstanding work"
        )
    return sorted(
        newest,
        key=lambda item: (
            priority_rank.get(str(item.get("priority") or "normal"), 1),
            str(item.get("added_ts") or ""),
        ),
    )


def derive_research_queue(memory_dir: Path) -> list[dict[str, Any]]:
    return load_current_runtime_state(memory_dir).research_queue


def _build_runtime_projection(
    events: list[dict[str, Any]],
    *,
    research_queue: list[dict[str, Any]],
    as_of: str,
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
        elif event_type in {
            "mail_reply_sent",
            "mail_draft_sent",
            "mail_intent_sent",
            "mail_doula_vote_cast",
            "mail_intent_declined",
            "mail_intent_suppressed",
        }:
            last_mail = {
                "ts": str(event.get("ts") or "").strip(),
                "event_type": event_type,
                "recipient": str(
                    payload.get("recipient") or payload.get("sender_name") or ""
                ).strip(),
                "vote": str(payload.get("vote") or "").strip(),
            }
        elif event_type in {
            "research_queued",
            "research_popped",
            "research_result_observed",
        }:
            last_research = {
                "ts": str(event.get("ts") or "").strip(),
                "event_type": event_type,
                "query": str(payload.get("query") or "").strip(),
                "priority": str(payload.get("priority") or "").strip(),
            }

    return {
        "updated_at": as_of,
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
    as_of: str,
) -> dict[str, Any]:
    thread_state: dict[str, dict[str, Any]] = {}
    latest_direct: dict[str, Any] | None = None
    open_questions: list[dict[str, Any]] = []
    open_requests: list[dict[str, Any]] = []
    pending_mail: list[dict[str, Any]] = []
    city_signals: list[dict[str, Any]] = []
    state_pressure: dict[str, Any] = {"signals": [], "raw": {}, "context": {}}
    world_salience: dict[str, Any] = {
        "observed_at": None,
        "location": "",
        "features": [],
        "feature_count": 0,
        "independent_source_count": 0,
        "plural": False,
        "dominant_share": 0.0,
        "effective_feature_count": 0.0,
    }
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
        payload = (
            packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
        )
        ts = str(packet.get("created_at") or "").strip()
        if packet_type in {"chat_heard", "city_chat_heard"}:
            speaker = str(payload.get("speaker") or "").strip()
            message = str(payload.get("message") or "").strip()
            is_direct = bool(payload.get("is_direct"))
            is_question = bool(payload.get("is_question"))
            is_request = bool(payload.get("is_request"))
            channel = str(
                payload.get("channel")
                or ("local" if packet_type == "chat_heard" else "city")
            ).strip()
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
            if (
                (is_direct or is_followup_direct)
                and is_question
                and speaker
                and message
            ):
                open_questions.append(
                    {
                        "speaker": speaker,
                        "message": message,
                        "ts": ts,
                    }
                )
            elif (
                (is_direct or is_followup_direct) and is_request and speaker and message
            ):
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
        if (
            latest_direct_ts is None
            or item_ts is None
            or latest_direct_ts - item_ts <= dialogue_expiry_window
        ):
            freshest_direct_questions.append(item)

    freshest_direct_requests: list[dict[str, Any]] = []
    for item in open_requests[-4:]:
        item_ts = _parse_iso_ts(str(item.get("ts") or ""))
        if (
            latest_direct_ts is None
            or item_ts is None
            or latest_direct_ts - item_ts <= dialogue_expiry_window
        ):
            freshest_direct_requests.append(item)

    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        ts = str(event.get("ts") or "").strip()
        if event_type in {"session_state_observed", "ambient_pressure_observed"}:
            state_pressure = _merge_pressure_payload(state_pressure, payload, ts=ts)
        if event_type == "ambient_pressure_observed":
            world_salience = _build_world_salience_projection(payload, ts=ts)
        if event_type in {
            "mail_intent_staged",
            "mail_intent_sent",
            "mail_reply_sent",
            "mail_draft_sent",
        }:
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
        key=lambda item: (
            -int(item.get("interaction_count") or 0),
            str(item.get("last_ts") or ""),
        ),
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
        "updated_at": as_of,
        "active_social_threads": active_social_threads,
        "dialogue_state": {
            "active_partner": str(
                (latest_direct or {}).get("speaker")
                or ((pending_mail[-1] if pending_mail else {}).get("sender") or "")
            ).strip(),
            "last_direct_message": latest_direct,
            "open_questions": freshest_direct_questions,
            "open_requests": freshest_direct_requests,
            "direct_urgency": (
                1.0
                if freshest_direct_questions
                else 0.8 if freshest_direct_requests else 0.0
            ),
        },
        "mail_state": {
            "pending_inbox_count": len(pending_mail),
            "latest_sender": str(
                (pending_mail[-1] if pending_mail else {}).get("sender") or ""
            ).strip(),
            "pending_letters": pending_mail[-4:],
        },
        "city_context": {
            "signal_count": len(city_signals),
            "recent_signals": city_signals[-4:],
        },
        "state_pressure": state_pressure,
        "world_salience": world_salience,
        "current_concerns": concerns[:10],
    }


def _build_memory_projection(
    events: list[dict[str, Any]],
    *,
    route: dict[str, Any] | None,
    research_queue: list[dict[str, Any]],
    mail_intents: list[dict[str, Any]],
    as_of: str,
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
                "label": str(
                    payload.get("destination") or payload.get("arrived_at") or ""
                ).strip(),
                "detail": event_type,
                "ts": ts,
            }
        elif event_type in {
            "mail_reply_sent",
            "mail_draft_sent",
            "mail_intent_sent",
            "mail_intent_staged",
        }:
            experience = {
                "kind": "mail",
                "label": str(
                    payload.get("recipient") or payload.get("sender_name") or ""
                ).strip(),
                "detail": event_type,
                "ts": ts,
            }
        if experience is not None:
            recent_experiences.append(experience)
        if len(recent_experiences) >= 12:
            break

    return {
        "updated_at": as_of,
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


def _build_relationship_projection(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Reduce prompt-delivery and reply edges into the resident's current relationships.

    A packet merely fetched from the world is not evidence of a relationship.  This
    reducer therefore starts only at ``utterance_perceived`` and follows a reply
    only through the canonical utterance ID.  The result is intentionally a small
    current-state view, not a general social graph or a claim about anyone's inner
    life.
    """
    relationships: dict[str, dict[str, Any]] = {}
    perceived_by_utterance: dict[str, dict[str, str]] = {}

    for event in events:
        event_type = str(event.get("event_type") or "").strip()
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        event_id = str(event.get("event_id") or "").strip()
        event_ts = str(event.get("ts") or "").strip()
        if not event_id or not event_ts:
            continue

        if event_type == "utterance_perceived":
            if payload.get("edge_schema_version") != RELATIONAL_EVENT_SCHEMA_VERSION:
                continue
            utterance_id = str(payload.get("utterance_id") or "").strip()
            counterpart_actor_id = str(payload.get("speaker_actor_id") or "").strip()
            if not utterance_id or not counterpart_actor_id:
                continue
            current = relationships.get(counterpart_actor_id)
            display_name = str(
                payload.get("speaker_name")
                or (current or {}).get("counterpart_name")
                or ""
            ).strip()
            revision = int((current or {}).get("revision") or 0) + 1
            relationship_id = f"relationship:{counterpart_actor_id}"
            claim_id = f"claim:{relationship_id}:current_exchange"
            relationship = {
                "relationship_id": relationship_id,
                "counterpart_actor_id": counterpart_actor_id,
                "counterpart_name": display_name,
                "state": "perceived",
                "revision": revision,
                "supersedes_revision": revision - 1 if revision > 1 else None,
                "claim_id": claim_id,
                "observed_at": event_ts,
                "updated_at": event_ts,
                "location": str(payload.get("location") or "").strip(),
                "utterance_id": utterance_id,
                "perceived_utterance_count": int(
                    (current or {}).get("perceived_utterance_count") or 0
                )
                + 1,
                "reply_count": int((current or {}).get("reply_count") or 0),
                "evidence_event_ids": [event_id],
            }
            relationships[counterpart_actor_id] = relationship
            perceived_by_utterance[utterance_id] = {
                "counterpart_actor_id": counterpart_actor_id,
                "event_id": event_id,
                "event_ts": event_ts,
                "utterance_id": utterance_id,
                "display_name": display_name,
                "location": str(payload.get("location") or "").strip(),
            }
            continue

        if event_type not in {
            "chat_sent",
            "city_broadcast_sent",
            "speech_carried",
            "mail_intent_sent",
        }:
            continue
        if payload.get("edge_schema_version") != RELATIONAL_EVENT_SCHEMA_VERSION:
            continue
        reply_to_utterance_id = str(payload.get("reply_to_utterance_id") or "").strip()
        perceived = perceived_by_utterance.get(reply_to_utterance_id)
        if perceived is None:
            continue
        counterpart_actor_id = perceived["counterpart_actor_id"]
        current = relationships.get(counterpart_actor_id)
        if current is None:
            continue
        revision = int(current.get("revision") or 0) + 1
        relationships[counterpart_actor_id] = {
            **current,
            "counterpart_name": str(
                current.get("counterpart_name") or perceived["display_name"]
            ).strip(),
            "state": "replied",
            "revision": revision,
            "supersedes_revision": revision - 1,
            "updated_at": event_ts,
            "reply_count": int(current.get("reply_count") or 0) + 1,
            "evidence_event_ids": [perceived["event_id"], event_id],
            "reply_event_id": event_id,
            "reply_to_utterance_id": reply_to_utterance_id,
        }

    return {
        "schema_version": RELATIONSHIP_PROJECTION_SCHEMA_VERSION,
        "relationships": sorted(
            relationships.values(),
            key=lambda item: (
                str(item.get("updated_at") or ""),
                str(item.get("counterpart_actor_id") or ""),
            ),
            reverse=True,
        ),
    }


def _build_subjective_facts(
    events: list[dict[str, Any]],
    *,
    packets: list[dict[str, Any]],
    route: dict[str, Any] | None,
    mail_intents: list[dict[str, Any]],
    research_queue: list[dict[str, Any]],
    relationship_projection: dict[str, Any],
    as_of: str,
) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    thread_counts: dict[str, int] = {}
    for packet in packets:
        packet_type = str(packet.get("packet_type") or "").strip()
        payload = (
            packet.get("payload") if isinstance(packet.get("payload"), dict) else {}
        )
        if packet_type in {"chat_heard", "city_chat_heard"}:
            speaker = str(payload.get("speaker") or "").strip()
            if speaker:
                key = speaker.lower()
                thread_counts[key] = thread_counts.get(key, 0) + 1

    for name_key, count in sorted(
        thread_counts.items(), key=lambda pair: (-pair[1], pair[0])
    )[:8]:
        display_name = next(
            (
                str((packet.get("payload") or {}).get("speaker") or "").strip()
                for packet in packets
                if str((packet.get("payload") or {}).get("speaker") or "")
                .strip()
                .lower()
                == name_key
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
        payload = (
            latest_direct_question.get("payload")
            if isinstance(latest_direct_question.get("payload"), dict)
            else {}
        )
        speaker = str(payload.get("speaker") or "").strip()
        message = str(payload.get("message") or "").strip()
        if speaker and message:
            facts.append(
                {
                    "subject": "self",
                    "predicate": "owes_reply_to",
                    "object": speaker,
                    "confidence": 0.9,
                    "evidence": {
                        "message_kind": _dialogue_message_kind(message),
                        "message": message[:160],
                    },
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
                    "confidence": min(
                        0.95, max(0.4, level if level is not None else 0.6)
                    ),
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
                "confidence": (
                    0.85 if str(item.get("priority") or "") == "high" else 0.65
                ),
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
                "evidence": {
                    "mail_intent_id": str(item.get("mail_intent_id") or "").strip()
                },
                "source": "derived_from_runtime_ledger",
            }
        )

    if any(
        str(event.get("event_type") or "").strip() == "movement_blocked"
        for event in events[-10:]
    ):
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

    for relationship in list(relationship_projection.get("relationships") or []):
        if not isinstance(relationship, dict):
            continue
        counterpart_actor_id = str(
            relationship.get("counterpart_actor_id") or ""
        ).strip()
        claim_id = str(relationship.get("claim_id") or "").strip()
        state = str(relationship.get("state") or "").strip()
        evidence_event_ids = [
            str(event_id).strip()
            for event_id in list(relationship.get("evidence_event_ids") or [])
            if str(event_id).strip()
        ]
        if (
            not counterpart_actor_id
            or not claim_id
            or state not in {"perceived", "replied"}
            or not evidence_event_ids
        ):
            continue
        facts.append(
            {
                "claim_id": claim_id,
                "status": "active",
                "revision": int(relationship.get("revision") or 1),
                "supersedes_revision": relationship.get("supersedes_revision"),
                "subject": "self",
                "predicate": (
                    "has_replied_to"
                    if state == "replied"
                    else "has_perceived_utterance_from"
                ),
                "object": str(
                    relationship.get("counterpart_name") or counterpart_actor_id
                ).strip(),
                "object_actor_id": counterpart_actor_id,
                "confidence": 0.9 if state == "replied" else 0.7,
                "observed_at": str(relationship.get("updated_at") or "").strip(),
                "evidence_event_ids": evidence_event_ids,
                "source": "relationship_projection_v1",
            }
        )

    return {
        "updated_at": as_of,
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
    as_of: str,
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
    last_event_ts = (
        str((runtime_events[-1] if runtime_events else {}).get("ts") or "").strip()
        or None
    )

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
        item = next(
            (
                entry
                for entry in concerns
                if str(entry.get("kind") or "").strip() == kind
            ),
            None,
        )
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
        stability = round(
            _clamp01(0.2 + (0.22 * evidence_count) + (0.45 * normalized_activation)), 3
        )
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
        + (
            [0.72]
            if str(blocked_movement.get("event_type") or "").strip()
            == "movement_blocked"
            else [0.0]
        )
    )
    vigilance_mode = (
        "alarmed"
        if vigilance_activation >= 0.75
        else "wary" if vigilance_activation >= 0.35 else "calm"
    )
    vigilance = node(
        "vigilance",
        mode=vigilance_mode,
        activation=vigilance_activation,
        evidence_refs=vigilance_refs,
        persistence_class="sticky" if vigilance_activation >= 0.6 else "ephemeral",
        last_transition_at=str(blocked_movement.get("ts") or last_event_ts or "")
        or None,
        sticky_minutes=20.0,
        neighbor_bias=(
            [
                {
                    "node_id": "rest_drive",
                    "weight": 0.18,
                    "reason": "fatigue and vigilance often co-amplify caution",
                }
            ]
            if vigilance_activation >= 0.35
            else []
        ),
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
                "top_partner": str(
                    (social_threads[0] if social_threads else {}).get("name") or ""
                ).strip(),
            }
        )
    social_activation = max(
        direct_urgency, min(1.0, inbox_count * 0.3), thread_strength * 0.55
    )
    social_mode = (
        "engaged"
        if social_activation >= 0.72
        else "receptive" if social_activation >= 0.28 else "withdrawn"
    )
    social_pull = node(
        "social_pull",
        mode=social_mode,
        activation=social_activation,
        evidence_refs=social_refs,
        persistence_class=(
            "sticky" if (direct_urgency >= 0.8 or inbox_count > 0) else "ephemeral"
        ),
        last_transition_at=last_event_ts,
        sticky_minutes=25.0,
        neighbor_bias=(
            [
                {
                    "node_id": "correspondence_pull",
                    "weight": 0.24,
                    "reason": "active dialogue and unanswered mail reinforce each other",
                }
            ]
            if social_activation >= 0.28
            else []
        ),
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
    event_pull_level = (
        _coerce_float((pressure_by_kind.get("event_pull") or {}).get("level")) or 0.0
    )
    mobility_activation = (
        0.92
        if route is not None
        else max(event_pull_level, 0.52 if concern_ref("research") else 0.08)
    )
    mobility_mode = (
        "goal_directed"
        if mobility_activation >= 0.8
        else "wandering" if mobility_activation >= 0.32 else "rooted"
    )
    mobility_drive = node(
        "mobility_drive",
        mode=mobility_mode,
        activation=mobility_activation,
        evidence_refs=mobility_refs,
        persistence_class=(
            "sticky" if route is not None or event_pull_level >= 0.6 else "ephemeral"
        ),
        last_transition_at=str(
            (runtime_projection.get("last_movement") or {}).get("ts")
            or last_event_ts
            or ""
        )
        or None,
        sticky_minutes=30.0,
        neighbor_bias=(
            [
                {
                    "node_id": "vigilance",
                    "weight": -0.16,
                    "reason": "high vigilance tends to damp open-ended movement",
                }
            ]
            if mobility_activation >= 0.32
            else []
        ),
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
                "latest_recipient": str(
                    (mail_intents[0] if mail_intents else {}).get("recipient") or ""
                ).strip(),
            }
        )
    correspondence_activation = max(
        min(1.0, inbox_count * 0.4), min(1.0, len(mail_intents) * 0.28)
    )
    correspondence_mode = (
        "urgent"
        if correspondence_activation >= 0.75
        else "pulling" if correspondence_activation >= 0.25 else "dormant"
    )
    correspondence_pull = node(
        "correspondence_pull",
        mode=correspondence_mode,
        activation=correspondence_activation,
        evidence_refs=correspondence_refs,
        persistence_class=(
            "sticky" if (inbox_count > 0 or bool(mail_intents)) else "ephemeral"
        ),
        last_transition_at=str(
            (runtime_projection.get("last_mail") or {}).get("ts") or last_event_ts or ""
        )
        or None,
        sticky_minutes=45.0,
        neighbor_bias=(
            [
                {
                    "node_id": "social_pull",
                    "weight": 0.24,
                    "reason": "lingering social contact often manifests as correspondence pressure",
                }
            ]
            if correspondence_activation >= 0.25
            else []
        ),
    )

    fatigue_level = (
        _coerce_float((pressure_by_kind.get("fatigue") or {}).get("level")) or 0.0
    )
    time_of_day = (
        str((state_pressure.get("context") or {}).get("time_of_day") or "")
        .strip()
        .lower()
    )
    rest_refs: list[dict[str, Any]] = []
    fatigue_ref = signal_ref("fatigue")
    if fatigue_ref is not None:
        rest_refs.append(fatigue_ref)
    if time_of_day:
        rest_refs.append({"kind": "context", "time_of_day": time_of_day})
    rest_activation = max(
        fatigue_level,
        0.62 if time_of_day in {"night", "late_evening", "sleep_window"} else 0.0,
    )
    rest_mode = (
        "shutting_down"
        if rest_activation >= 0.82
        else "tired" if rest_activation >= 0.38 else "active"
    )
    rest_drive = node(
        "rest_drive",
        mode=rest_mode,
        activation=rest_activation,
        evidence_refs=rest_refs,
        persistence_class="sticky" if rest_activation >= 0.55 else "ephemeral",
        last_transition_at=last_event_ts,
        sticky_minutes=40.0,
        neighbor_bias=(
            [
                {
                    "node_id": "mobility_drive",
                    "weight": -0.22,
                    "reason": "high rest drive reduces open-ended exploration",
                }
            ]
            if rest_activation >= 0.38
            else []
        ),
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
        "updated_at": as_of,
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


def reduce_runtime_events(
    events: list[dict[str, Any]], *, as_of: datetime | str | None = None
) -> ResidentReducedState:
    replay_as_of = _replay_as_of_iso(events, as_of=as_of)
    packets = _derive_packets_from_events(events)
    intents = _derive_intents_from_events(events)
    active_route = _derive_active_route_from_events(events)
    active_mail_intents = _derive_active_mail_intents_from_events(events)
    research_queue = _derive_research_queue_from_events(events)
    runtime_projection = _build_runtime_projection(
        events, research_queue=research_queue, as_of=replay_as_of
    )
    subjective_projection = _build_subjective_projection(
        events,
        packets=packets,
        route=active_route,
        mail_intents=active_mail_intents,
        research_queue=research_queue,
        as_of=replay_as_of,
    )
    memory_projection = _build_memory_projection(
        events,
        route=active_route,
        research_queue=research_queue,
        mail_intents=active_mail_intents,
        as_of=replay_as_of,
    )
    relationship_projection = _build_relationship_projection(events)
    subjective_projection["relationship_projection"] = relationship_projection
    subjective_facts = _build_subjective_facts(
        events,
        packets=packets,
        route=active_route,
        mail_intents=active_mail_intents,
        research_queue=research_queue,
        relationship_projection=relationship_projection,
        as_of=replay_as_of,
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
            as_of=replay_as_of,
        ),
    )


def _write_json(path: Path, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, ensure_ascii=True))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _checkpoint_payload(
    memory_dir: Path, reduced: ResidentReducedState
) -> dict[str, Any]:
    ledger = _ledger_path(memory_dir)
    last_event = reduced.events[-1] if reduced.events else {}
    return {
        "format_version": CHECKPOINT_FORMAT_VERSION,
        "reducer_version": REDUCER_FORMAT_VERSION,
        "projection_versions": dict(PROJECTION_FORMAT_VERSIONS),
        "ledger": {
            "byte_offset": ledger.stat().st_size if ledger.exists() else 0,
            "event_count": int(
                reduced.runtime_projection.get("ledger_event_count")
                or len(reduced.events)
            ),
            "last_sequence": int(
                last_event.get("sequence")
                or reduced.runtime_projection.get("ledger_event_count")
                or len(reduced.events)
            ),
            "last_event_id": str(last_event.get("event_id") or "").strip() or None,
        },
        "state": {
            "packets": reduced.packets,
            "intents": reduced.intents,
            "active_route": reduced.active_route,
            "active_mail_intents": reduced.active_mail_intents,
            "research_queue": reduced.research_queue,
            "runtime_projection": reduced.runtime_projection,
            "subjective_projection": reduced.subjective_projection,
            "memory_projection": reduced.memory_projection,
            "subjective_facts": reduced.subjective_facts,
            "cognitive_projection": reduced.cognitive_projection,
        },
    }


def load_runtime_checkpoint(
    memory_dir: Path, *, require_current: bool = True
) -> dict[str, Any] | None:
    """Load a compatible derived checkpoint, or ``None`` when cold-ledger replay is required."""
    path = _checkpoint_path(memory_dir)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    if raw.get("format_version") != CHECKPOINT_FORMAT_VERSION:
        return None
    if raw.get("reducer_version") != REDUCER_FORMAT_VERSION:
        return None
    if raw.get("projection_versions") != PROJECTION_FORMAT_VERSIONS:
        return None
    ledger_meta = raw.get("ledger") if isinstance(raw.get("ledger"), dict) else {}
    state = raw.get("state") if isinstance(raw.get("state"), dict) else None
    if state is None:
        return None
    if require_current:
        ledger = _ledger_path(memory_dir)
        ledger_size = ledger.stat().st_size if ledger.exists() else 0
        try:
            checkpoint_offset = int(ledger_meta.get("byte_offset"))
            last_sequence = int(ledger_meta.get("last_sequence"))
        except (TypeError, ValueError):
            return None
        event_count = ledger_meta.get("event_count")
        if (
            checkpoint_offset != ledger_size
            or last_sequence < 0
            or last_sequence != event_count
        ):
            return None
    return raw


def _write_runtime_checkpoint(memory_dir: Path, reduced: ResidentReducedState) -> None:
    _write_json(_checkpoint_path(memory_dir), _checkpoint_payload(memory_dir, reduced))


def _advance_runtime_projection(
    current: dict[str, Any],
    event: dict[str, Any],
) -> dict[str, Any]:
    runtime_projection = deepcopy(current)
    event_type = str(event.get("event_type") or "").strip()
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    event_counts = dict(runtime_projection.get("event_counts") or {})
    event_counts[event_type] = int(event_counts.get(event_type) or 0) + 1
    recent_events = list(runtime_projection.get("recent_events") or [])
    recent_events.append(
        {
            "event_id": str(event.get("event_id") or "").strip(),
            "event_type": event_type,
            "ts": str(event.get("ts") or "").strip(),
        }
    )
    runtime_projection.update(
        {
            "updated_at": _replay_as_of_iso([event]),
            "ledger_event_count": int(runtime_projection.get("ledger_event_count") or 0)
            + 1,
            "event_counts": event_counts,
            "recent_events": recent_events[-20:],
        }
    )
    if event_type in {"grounding_observed", "ground_intent_executed"}:
        runtime_projection["last_grounding"] = {
            "ts": str(event.get("ts") or "").strip(),
            "observation": str(payload.get("observation") or "").strip(),
            "query": str(payload.get("query") or "").strip(),
        }
    elif event_type in {"move_executed", "movement_arrived", "movement_blocked"}:
        runtime_projection["last_movement"] = {
            "ts": str(event.get("ts") or "").strip(),
            "event_type": event_type,
            "destination": str(payload.get("destination") or "").strip(),
            "arrived_at": str(payload.get("arrived_at") or "").strip(),
            "status": str(payload.get("status") or "").strip(),
        }
    elif event_type in {
        "mail_reply_sent",
        "mail_draft_sent",
        "mail_intent_sent",
        "mail_doula_vote_cast",
        "mail_intent_declined",
        "mail_intent_suppressed",
    }:
        runtime_projection["last_mail"] = {
            "ts": str(event.get("ts") or "").strip(),
            "event_type": event_type,
            "recipient": str(
                payload.get("recipient") or payload.get("sender_name") or ""
            ).strip(),
            "vote": str(payload.get("vote") or "").strip(),
        }
    elif event_type in {
        "research_queued",
        "research_popped",
        "research_result_observed",
    }:
        runtime_projection["last_research"] = {
            "ts": str(event.get("ts") or "").strip(),
            "event_type": event_type,
            "query": str(payload.get("query") or "").strip(),
            "priority": str(payload.get("priority") or "").strip(),
        }
    return runtime_projection


def _advance_lifecycle_state(state: dict[str, Any], event: dict[str, Any]) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any] | None,
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    event_type = str(event.get("event_type") or "").strip()
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}

    packet_by_id = {
        str(item.get("packet_id") or "").strip(): deepcopy(item)
        for item in list(state.get("packets") or [])
        if str(item.get("packet_id") or "").strip()
    }
    packet_id = str(payload.get("packet_id") or "").strip()
    if event_type == "packet_emitted" and packet_id:
        packet_by_id[packet_id] = dict(payload)
    elif event_type == "packet_status_changed" and packet_id in packet_by_id:
        packet_by_id[packet_id]["status"] = str(
            payload.get("status") or packet_by_id[packet_id].get("status") or "pending"
        ).strip()
    packets = _bounded_lifecycle_view(
        list(packet_by_id.values()),
        open_statuses=PACKET_OPEN_STATUSES,
        limit=PACKET_PROJECTION_LIMIT,
        item_kind="packet",
    )

    intent_by_id = {
        str(item.get("intent_id") or "").strip(): deepcopy(item)
        for item in list(state.get("intents") or [])
        if str(item.get("intent_id") or "").strip()
    }
    intent_id = str(payload.get("intent_id") or "").strip()
    if event_type == "intent_staged" and intent_id:
        intent_by_id[intent_id] = dict(payload)
    elif event_type == "intent_status_changed" and intent_id in intent_by_id:
        intent_by_id[intent_id]["status"] = str(
            payload.get("status") or intent_by_id[intent_id].get("status") or "pending"
        ).strip()
        validation_state = str(payload.get("validation_state") or "").strip()
        if validation_state:
            intent_by_id[intent_id]["validation_state"] = validation_state
    intents = _bounded_lifecycle_view(
        list(intent_by_id.values()),
        open_statuses=INTENT_OPEN_STATUSES,
        limit=INTENT_PROJECTION_LIMIT,
        item_kind="intent",
    )
    intents.sort(
        key=lambda item: (
            -float(item.get("priority") or 0.5),
            str(item.get("created_at") or ""),
        )
    )

    active_route = deepcopy(state.get("active_route"))
    if event_type == "route_state_changed":
        status = str(payload.get("status") or "").strip()
        if status == "active":
            active_route = {
                "destination": str(payload.get("destination") or "").strip(),
                "remaining": list(payload.get("remaining") or []),
            }
        elif status == "cleared":
            active_route = None
    if active_route is not None and not active_route.get("destination"):
        active_route = None

    mail_by_id = {
        str(item.get("mail_intent_id") or "").strip(): deepcopy(item)
        for item in list(state.get("active_mail_intents") or [])
        if str(item.get("mail_intent_id") or "").strip()
    }
    mail_intent_id = str(payload.get("mail_intent_id") or "").strip()
    if event_type == "mail_intent_staged" and mail_intent_id:
        mail_by_id[mail_intent_id] = dict(payload)
    elif event_type in {
        "mail_intent_sent",
        "mail_intent_declined",
        "mail_intent_suppressed",
    }:
        mail_by_id.pop(mail_intent_id, None)
    active_mail_intents = sorted(
        mail_by_id.values(),
        key=lambda item: str(item.get("staged_at") or item.get("ts") or ""),
    )
    if len(active_mail_intents) > MAIL_INTENT_PROJECTION_LIMIT:
        raise RuntimeError(
            f"open mail intent count {len(active_mail_intents)} exceeds the safe ceiling "
            f"of {MAIL_INTENT_PROJECTION_LIMIT}; close or explicitly migrate outstanding work"
        )

    research_by_query = {
        str(item.get("query") or "").strip().lower(): deepcopy(item)
        for item in list(state.get("research_queue") or [])
        if str(item.get("query") or "").strip()
    }
    query = str(payload.get("query") or "").strip()
    if event_type == "research_queued" and query:
        research_by_query[query.lower()] = {
            "query": query,
            "priority": str(payload.get("priority") or "normal").strip() or "normal",
            "source": str(payload.get("source") or "").strip(),
            "added_ts": str(payload.get("added_ts") or event.get("ts") or "").strip(),
        }
    elif event_type == "research_popped" and query:
        research_by_query.pop(query.lower(), None)
    research_queue = list(research_by_query.values())
    if len(research_queue) > RESEARCH_QUEUE_PROJECTION_LIMIT:
        raise RuntimeError(
            f"open research item count {len(research_queue)} exceeds the safe ceiling "
            f"of {RESEARCH_QUEUE_PROJECTION_LIMIT}; close or explicitly migrate outstanding work"
        )
    priority_rank = {"high": 0, "normal": 1, "low": 2}
    research_queue.sort(
        key=lambda item: (
            priority_rank.get(str(item.get("priority") or "normal"), 1),
            str(item.get("added_ts") or ""),
        )
    )
    return packets, intents, active_route, active_mail_intents, research_queue


def _reduced_after_simple_checkpoint_event(
    checkpoint: dict[str, Any], event: dict[str, Any]
) -> ResidentReducedState:
    state = checkpoint["state"]
    runtime_projection = _advance_runtime_projection(state["runtime_projection"], event)
    (
        packets,
        intents,
        active_route,
        active_mail_intents,
        research_queue,
    ) = _advance_lifecycle_state(state, event)
    subjective_projection = deepcopy(state["subjective_projection"])
    memory_projection = deepcopy(state["memory_projection"])
    subjective_facts = deepcopy(state["subjective_facts"])
    updated_at = _replay_as_of_iso([event])
    subjective_projection["updated_at"] = updated_at
    memory_projection["updated_at"] = updated_at
    subjective_facts["updated_at"] = updated_at
    return ResidentReducedState(
        events=[event],
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
            [event],
            runtime_projection=runtime_projection,
            subjective_projection=subjective_projection,
            subjective_facts=subjective_facts,
            route=active_route,
            mail_intents=active_mail_intents,
            as_of=updated_at,
        ),
    )


def _reduced_after_bounded_replay(
    memory_dir: Path,
    checkpoint: dict[str, Any],
    event: dict[str, Any],
) -> ResidentReducedState:
    replay_as_of = _replay_as_of_iso([event])
    replayed = reduce_runtime_events(
        load_runtime_projection_events(memory_dir), as_of=replay_as_of
    )
    runtime_projection = _advance_runtime_projection(
        checkpoint["state"]["runtime_projection"], event
    )
    (
        packets,
        intents,
        active_route,
        active_mail_intents,
        research_queue,
    ) = _advance_lifecycle_state(checkpoint["state"], event)
    subjective_projection = _build_subjective_projection(
        replayed.events,
        packets=packets,
        route=active_route,
        mail_intents=active_mail_intents,
        research_queue=research_queue,
        as_of=replay_as_of,
    )
    memory_projection = _build_memory_projection(
        replayed.events,
        route=active_route,
        research_queue=research_queue,
        mail_intents=active_mail_intents,
        as_of=replay_as_of,
    )
    relationship_projection = _build_relationship_projection(replayed.events)
    subjective_projection["relationship_projection"] = relationship_projection
    subjective_facts = _build_subjective_facts(
        replayed.events,
        packets=packets,
        route=active_route,
        mail_intents=active_mail_intents,
        research_queue=research_queue,
        relationship_projection=relationship_projection,
        as_of=replay_as_of,
    )
    return ResidentReducedState(
        events=replayed.events,
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
            replayed.events,
            runtime_projection=runtime_projection,
            subjective_projection=subjective_projection,
            subjective_facts=subjective_facts,
            route=active_route,
            mail_intents=active_mail_intents,
            as_of=replay_as_of,
        ),
    )


def _write_reduced_runtime_artifacts(
    memory_dir: Path, reduced: ResidentReducedState
) -> None:
    _write_runtime_checkpoint(memory_dir, reduced)


def _remove_legacy_runtime_derivatives(memory_dir: Path) -> None:
    for filename in _LEGACY_DERIVED_FILENAMES:
        (memory_dir / filename).unlink(missing_ok=True)
    intents_dir = memory_dir.parent / "letters" / "intents"
    if intents_dir.exists():
        for path in intents_dir.glob("intent_*.md"):
            path.unlink(missing_ok=True)


def rebuild_runtime_artifacts(
    memory_dir: Path,
    *,
    events: list[dict[str, Any]] | None = None,
) -> ResidentReducedState:
    reduced = reduce_runtime_events(
        list(events) if events is not None else _load_events(memory_dir)
    )
    _remove_legacy_runtime_derivatives(memory_dir)
    _write_reduced_runtime_artifacts(memory_dir, reduced)
    return reduced


def append_runtime_event(
    memory_dir: Path,
    *,
    event_type: str,
    payload: dict[str, Any] | None = None,
    ts: datetime | str | None = None,
) -> dict[str, Any]:
    with _serialized_writer(memory_dir):
        checkpoint = load_runtime_checkpoint(memory_dir)
        if checkpoint is None:
            _quarantine_incomplete_tail(memory_dir)
            existing_events = _load_events(memory_dir)
            next_sequence = len(existing_events) + 1
        else:
            next_sequence = int(checkpoint["ledger"]["last_sequence"]) + 1
        event = {
            "event_id": f"evt-{uuid.uuid4().hex[:12]}",
            "sequence": next_sequence,
            "ts": (
                _replay_as_of_iso([], as_of=ts) if ts is not None else _utc_now_iso()
            ),
            "event_type": str(event_type).strip(),
            "payload": dict(payload or {}),
        }
        _append_event(memory_dir, event)
        if checkpoint is not None and (
            event["event_type"] not in PROJECTION_STATE_EVENT_TYPES
            or event["event_type"] in SIMPLE_CHECKPOINT_EVENT_TYPES
        ):
            _write_reduced_runtime_artifacts(
                memory_dir, _reduced_after_simple_checkpoint_event(checkpoint, event)
            )
        elif checkpoint is not None:
            _write_reduced_runtime_artifacts(
                memory_dir,
                _reduced_after_bounded_replay(memory_dir, checkpoint, event),
            )
        else:
            rebuild_runtime_artifacts(memory_dir)
        return event
