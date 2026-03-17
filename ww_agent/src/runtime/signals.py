from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.runtime.ledger import (
    append_runtime_event,
    derive_intents,
    derive_packets,
    derive_research_queue,
    sync_runtime_compatibility_projections,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_status(value: str, *, allowed: set[str], default: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in allowed:
        return normalized
    return default


def _load_signal_list(path: Path, item_cls: Any) -> list[Any]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    items: list[Any] = []
    for entry in raw:
        if isinstance(entry, dict):
            items.append(item_cls.from_dict(entry))
    return items


def write_runtime_snapshot(memory_dir: Path) -> None:
    packets = [StimulusPacket.from_dict(item) for item in derive_packets(memory_dir)]
    intents = [IntentQueueEntry.from_dict(item) for item in derive_intents(memory_dir)]
    research_items = derive_research_queue(memory_dir)

    packet_status_counts: dict[str, int] = {}
    packet_type_counts: dict[str, int] = {}
    for packet in packets:
        packet_status_counts[packet.status] = packet_status_counts.get(packet.status, 0) + 1
        packet_type_counts[packet.packet_type] = packet_type_counts.get(packet.packet_type, 0) + 1

    intent_status_counts: dict[str, int] = {}
    intent_type_counts: dict[str, int] = {}
    for intent in intents:
        intent_status_counts[intent.status] = intent_status_counts.get(intent.status, 0) + 1
        intent_type_counts[intent.intent_type] = intent_type_counts.get(intent.intent_type, 0) + 1

    recent_failures = [
        {
            "intent_id": intent.intent_id,
            "intent_type": intent.intent_type,
            "status": intent.status,
            "validation_state": intent.validation_state,
            "source_packet_ids": intent.source_packet_ids,
            "target_loop": intent.target_loop,
            "created_at": intent.created_at,
        }
        for intent in reversed(intents)
        if intent.status == "failed"
    ][:10]

    pending_packets = [
        {
            "packet_id": packet.packet_id,
            "packet_type": packet.packet_type,
            "source_loop": packet.source_loop,
            "location": packet.location,
            "salience": packet.salience,
            "created_at": packet.created_at,
        }
        for packet in packets
        if packet.status == "pending"
    ][:20]

    queued_intents = [
        {
            "intent_id": intent.intent_id,
            "intent_type": intent.intent_type,
            "target_loop": intent.target_loop,
            "status": intent.status,
            "priority": intent.priority,
            "validation_state": intent.validation_state,
            "source_packet_ids": intent.source_packet_ids,
            "created_at": intent.created_at,
        }
        for intent in intents
        if intent.status in {"pending", "claimed"}
    ][:20]

    lineage = [
        {
            "intent_id": intent.intent_id,
            "intent_type": intent.intent_type,
            "status": intent.status,
            "source_packet_ids": intent.source_packet_ids,
            "target_loop": intent.target_loop,
            "validation_state": intent.validation_state,
        }
        for intent in intents[-20:]
    ]

    snapshot = {
        "updated_at": _utc_now_iso(),
        "packet_counts": {
            "total": len(packets),
            "pending": packet_status_counts.get("pending", 0),
            "observed": packet_status_counts.get("observed", 0),
            "ignored": packet_status_counts.get("ignored", 0),
            "processing": packet_status_counts.get("processing", 0),
            "expired": packet_status_counts.get("expired", 0),
            "by_type": packet_type_counts,
        },
        "intent_counts": {
            "total": len(intents),
            "pending": intent_status_counts.get("pending", 0),
            "claimed": intent_status_counts.get("claimed", 0),
            "executed": intent_status_counts.get("executed", 0),
            "failed": intent_status_counts.get("failed", 0),
            "cancelled": intent_status_counts.get("cancelled", 0),
            "expired": intent_status_counts.get("expired", 0),
            "by_type": intent_type_counts,
        },
        "research_queue": {
            "total": len(research_items),
            "high": sum(1 for item in research_items if isinstance(item, dict) and str(item.get("priority") or "") == "high"),
            "normal": sum(1 for item in research_items if isinstance(item, dict) and str(item.get("priority") or "") == "normal"),
            "low": sum(1 for item in research_items if isinstance(item, dict) and str(item.get("priority") or "") == "low"),
            "pending_items": [
                {
                    "query": str(item.get("query") or "").strip(),
                    "priority": str(item.get("priority") or "").strip(),
                    "source": str(item.get("source") or "").strip(),
                    "added_ts": str(item.get("added_ts") or "").strip(),
                }
                for item in research_items[:10]
                if isinstance(item, dict)
            ],
        },
        "pending_packets": pending_packets,
        "queued_intents": queued_intents,
        "lineage": lineage,
        "recent_failures": recent_failures,
    }

    snapshot_path = memory_dir / "runtime_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=True), encoding="utf-8")


def _write_runtime_snapshot(memory_dir: Path) -> None:
    write_runtime_snapshot(memory_dir)


@dataclass(frozen=True)
class StimulusPacket:
    packet_id: str
    packet_type: str
    created_at: str
    source_loop: str
    dedupe_key: str | None = None
    location: str | None = None
    salience: float = 0.5
    payload: dict[str, Any] = field(default_factory=dict)
    expires_at: str | None = None
    status: str = "pending"

    @classmethod
    def create(
        cls,
        *,
        packet_type: str,
        source_loop: str,
        dedupe_key: str | None = None,
        location: str | None = None,
        salience: float = 0.5,
        payload: dict[str, Any] | None = None,
        expires_at: str | None = None,
        status: str = "pending",
    ) -> "StimulusPacket":
        return cls(
            packet_id=f"pkt-{uuid.uuid4().hex[:12]}",
            packet_type=str(packet_type).strip(),
            created_at=_utc_now_iso(),
            source_loop=str(source_loop).strip(),
            dedupe_key=str(dedupe_key).strip() if dedupe_key else None,
            location=str(location).strip() if location else None,
            salience=float(salience),
            payload=dict(payload or {}),
            expires_at=expires_at,
            status=_normalize_status(
                status,
                allowed={"pending", "processing", "observed", "ignored", "expired"},
                default="pending",
            ),
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StimulusPacket":
        return cls(
            packet_id=str(raw.get("packet_id") or f"pkt-{uuid.uuid4().hex[:12]}"),
            packet_type=str(raw.get("packet_type") or "").strip(),
            created_at=str(raw.get("created_at") or _utc_now_iso()),
            source_loop=str(raw.get("source_loop") or "").strip(),
            dedupe_key=str(raw.get("dedupe_key")).strip() if raw.get("dedupe_key") else None,
            location=str(raw.get("location")).strip() if raw.get("location") else None,
            salience=float(raw.get("salience") or 0.5),
            payload=dict(raw.get("payload") or {}),
            expires_at=str(raw.get("expires_at")).strip() if raw.get("expires_at") else None,
            status=_normalize_status(
                str(raw.get("status") or "pending"),
                allowed={"pending", "processing", "observed", "ignored", "expired"},
                default="pending",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IntentQueueEntry:
    intent_id: str
    intent_type: str
    created_at: str
    source_packet_ids: list[str]
    status: str
    priority: float
    target_loop: str
    payload: dict[str, Any] = field(default_factory=dict)
    validation_state: str = "unvalidated"
    expires_at: str | None = None

    @classmethod
    def create(
        cls,
        *,
        intent_type: str,
        target_loop: str,
        source_packet_ids: list[str] | None = None,
        status: str = "pending",
        priority: float = 0.5,
        payload: dict[str, Any] | None = None,
        validation_state: str = "unvalidated",
        expires_at: str | None = None,
    ) -> "IntentQueueEntry":
        return cls(
            intent_id=f"int-{uuid.uuid4().hex[:12]}",
            intent_type=str(intent_type).strip(),
            created_at=_utc_now_iso(),
            source_packet_ids=[str(item).strip() for item in source_packet_ids or [] if str(item).strip()],
            status=_normalize_status(
                status,
                allowed={"pending", "claimed", "cancelled", "expired", "executed", "failed"},
                default="pending",
            ),
            priority=float(priority),
            target_loop=str(target_loop).strip(),
            payload=dict(payload or {}),
            validation_state=str(validation_state or "unvalidated").strip() or "unvalidated",
            expires_at=expires_at,
        )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "IntentQueueEntry":
        return cls(
            intent_id=str(raw.get("intent_id") or f"int-{uuid.uuid4().hex[:12]}"),
            intent_type=str(raw.get("intent_type") or "").strip(),
            created_at=str(raw.get("created_at") or _utc_now_iso()),
            source_packet_ids=[
                str(item).strip()
                for item in list(raw.get("source_packet_ids") or [])
                if str(item).strip()
            ],
            status=_normalize_status(
                str(raw.get("status") or "pending"),
                allowed={"pending", "claimed", "cancelled", "expired", "executed", "failed"},
                default="pending",
            ),
            priority=float(raw.get("priority") or 0.5),
            target_loop=str(raw.get("target_loop") or "").strip(),
            payload=dict(raw.get("payload") or {}),
            validation_state=str(raw.get("validation_state") or "unvalidated").strip() or "unvalidated",
            expires_at=str(raw.get("expires_at")).strip() if raw.get("expires_at") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StimulusPacketQueue:
    def __init__(self, path: Path, max_items: int = 200) -> None:
        self._path = path
        self._max_items = max_items

    def append(self, packet: StimulusPacket) -> StimulusPacket:
        append_runtime_event(
            self._path.parent,
            event_type="packet_emitted",
            payload=packet.to_dict(),
        )
        return packet

    def emit(
        self,
        *,
        packet_type: str,
        source_loop: str,
        dedupe_key: str | None = None,
        location: str | None = None,
        salience: float = 0.5,
        payload: dict[str, Any] | None = None,
        expires_at: str | None = None,
    ) -> StimulusPacket:
        packet = StimulusPacket.create(
            packet_type=packet_type,
            source_loop=source_loop,
            dedupe_key=dedupe_key,
            location=location,
            salience=salience,
            payload=payload,
            expires_at=expires_at,
        )
        return self.append(packet)

    def emit_once(
        self,
        *,
        packet_type: str,
        source_loop: str,
        dedupe_key: str,
        location: str | None = None,
        salience: float = 0.5,
        payload: dict[str, Any] | None = None,
        expires_at: str | None = None,
    ) -> StimulusPacket:
        existing = self.find_by_dedupe_key(
            packet_type=packet_type,
            source_loop=source_loop,
            dedupe_key=dedupe_key,
        )
        if existing is not None:
            return existing
        return self.emit(
            packet_type=packet_type,
            source_loop=source_loop,
            dedupe_key=dedupe_key,
            location=location,
            salience=salience,
            payload=payload,
            expires_at=expires_at,
        )

    def all(self) -> list[StimulusPacket]:
        return self._load()

    def pending(self) -> list[StimulusPacket]:
        return [item for item in self._load() if item.status == "pending"]

    def find_by_dedupe_key(
        self,
        *,
        packet_type: str,
        source_loop: str,
        dedupe_key: str,
    ) -> StimulusPacket | None:
        normalized_packet_type = str(packet_type).strip()
        normalized_source_loop = str(source_loop).strip()
        normalized_dedupe_key = str(dedupe_key).strip()
        for item in self._load():
            if (
                item.packet_type == normalized_packet_type
                and item.source_loop == normalized_source_loop
                and item.dedupe_key == normalized_dedupe_key
            ):
                return item
        return None

    def mark_status(self, packet_id: str, status: str) -> StimulusPacket | None:
        items = self._load()
        updated: StimulusPacket | None = None
        normalized = _normalize_status(
            status,
            allowed={"pending", "processing", "observed", "ignored", "expired"},
            default="pending",
        )
        rewritten: list[StimulusPacket] = []
        for item in items:
            if item.packet_id == packet_id:
                updated = StimulusPacket.from_dict({**item.to_dict(), "status": normalized})
                rewritten.append(updated)
            else:
                rewritten.append(item)
        self._save(rewritten)
        if updated is not None:
            append_runtime_event(
                self._path.parent,
                event_type="packet_status_changed",
                payload={
                    "packet_id": updated.packet_id,
                    "packet_type": updated.packet_type,
                    "status": updated.status,
                    "source_loop": updated.source_loop,
                },
            )
        return updated

    def ensure_file(self) -> None:
        sync_runtime_compatibility_projections(self._path.parent)
        _write_runtime_snapshot(self._path.parent)

    def _load(self) -> list[StimulusPacket]:
        return [StimulusPacket.from_dict(entry) for entry in derive_packets(self._path.parent)]

    def _save(self, items: list[StimulusPacket]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([item.to_dict() for item in items], indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        _write_runtime_snapshot(self._path.parent)


class IntentQueue:
    def __init__(self, path: Path, max_items: int = 100) -> None:
        self._path = path
        self._max_items = max_items

    def append(self, intent: IntentQueueEntry) -> IntentQueueEntry:
        append_runtime_event(
            self._path.parent,
            event_type="intent_staged",
            payload=intent.to_dict(),
        )
        return intent

    def stage(
        self,
        *,
        intent_type: str,
        target_loop: str,
        source_packet_ids: list[str] | None = None,
        priority: float = 0.5,
        payload: dict[str, Any] | None = None,
        validation_state: str = "unvalidated",
        expires_at: str | None = None,
    ) -> IntentQueueEntry:
        intent = IntentQueueEntry.create(
            intent_type=intent_type,
            target_loop=target_loop,
            source_packet_ids=source_packet_ids,
            priority=priority,
            payload=payload,
            validation_state=validation_state,
            expires_at=expires_at,
        )
        return self.append(intent)

    def all(self) -> list[IntentQueueEntry]:
        return self._load()

    def pending(self, *, target_loop: str | None = None) -> list[IntentQueueEntry]:
        items = [item for item in self._load() if item.status == "pending"]
        if target_loop:
            normalized = str(target_loop).strip()
            items = [item for item in items if item.target_loop == normalized]
        items.sort(key=lambda item: (-float(item.priority), item.created_at))
        return items

    def claim_next(self, *, target_loop: str | None = None) -> IntentQueueEntry | None:
        items = self._load()
        chosen: IntentQueueEntry | None = None
        rewritten: list[IntentQueueEntry] = []
        normalized_target = str(target_loop).strip() if target_loop else None
        pending = sorted(
            [
                item
                for item in items
                if item.status == "pending"
                and (normalized_target is None or item.target_loop == normalized_target)
            ],
            key=lambda item: (-float(item.priority), item.created_at),
        )
        chosen_id = pending[0].intent_id if pending else None
        for item in items:
            if chosen_id and item.intent_id == chosen_id:
                chosen = IntentQueueEntry.from_dict({**item.to_dict(), "status": "claimed"})
                rewritten.append(chosen)
            else:
                rewritten.append(item)
        self._save(rewritten)
        if chosen is not None:
            append_runtime_event(
                self._path.parent,
                event_type="intent_status_changed",
                payload={
                    "intent_id": chosen.intent_id,
                    "intent_type": chosen.intent_type,
                    "status": chosen.status,
                    "target_loop": chosen.target_loop,
                    "validation_state": chosen.validation_state,
                },
            )
        return chosen

    def mark_status(
        self,
        intent_id: str,
        *,
        status: str,
        validation_state: str | None = None,
    ) -> IntentQueueEntry | None:
        items = self._load()
        updated: IntentQueueEntry | None = None
        normalized_status = _normalize_status(
            status,
            allowed={"pending", "claimed", "cancelled", "expired", "executed", "failed"},
            default="pending",
        )
        rewritten: list[IntentQueueEntry] = []
        for item in items:
            if item.intent_id == intent_id:
                next_payload = item.to_dict()
                next_payload["status"] = normalized_status
                if validation_state is not None:
                    next_payload["validation_state"] = str(validation_state).strip() or item.validation_state
                updated = IntentQueueEntry.from_dict(next_payload)
                rewritten.append(updated)
            else:
                rewritten.append(item)
        self._save(rewritten)
        if updated is not None:
            append_runtime_event(
                self._path.parent,
                event_type="intent_status_changed",
                payload={
                    "intent_id": updated.intent_id,
                    "intent_type": updated.intent_type,
                    "status": updated.status,
                    "target_loop": updated.target_loop,
                    "validation_state": updated.validation_state,
                },
            )
        return updated

    def ensure_file(self) -> None:
        sync_runtime_compatibility_projections(self._path.parent)
        _write_runtime_snapshot(self._path.parent)

    def _load(self) -> list[IntentQueueEntry]:
        return [IntentQueueEntry.from_dict(entry) for entry in derive_intents(self._path.parent)]

    def _save(self, items: list[IntentQueueEntry]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([item.to_dict() for item in items], indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        _write_runtime_snapshot(self._path.parent)
