from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_status(value: str, *, allowed: set[str], default: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in allowed:
        return normalized
    return default


@dataclass(frozen=True)
class StimulusPacket:
    packet_id: str
    packet_type: str
    created_at: str
    source_loop: str
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
        items = self._load()
        items.append(packet)
        if len(items) > self._max_items:
            items = items[-self._max_items :]
        self._save(items)
        return packet

    def emit(
        self,
        *,
        packet_type: str,
        source_loop: str,
        location: str | None = None,
        salience: float = 0.5,
        payload: dict[str, Any] | None = None,
        expires_at: str | None = None,
    ) -> StimulusPacket:
        packet = StimulusPacket.create(
            packet_type=packet_type,
            source_loop=source_loop,
            location=location,
            salience=salience,
            payload=payload,
            expires_at=expires_at,
        )
        return self.append(packet)

    def all(self) -> list[StimulusPacket]:
        return self._load()

    def pending(self) -> list[StimulusPacket]:
        return [item for item in self._load() if item.status == "pending"]

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
        return updated

    def ensure_file(self) -> None:
        if not self._path.exists():
            self._save([])

    def _load(self) -> list[StimulusPacket]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        items: list[StimulusPacket] = []
        for entry in raw:
            if isinstance(entry, dict):
                items.append(StimulusPacket.from_dict(entry))
        return items

    def _save(self, items: list[StimulusPacket]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([item.to_dict() for item in items], indent=2, ensure_ascii=True),
            encoding="utf-8",
        )


class IntentQueue:
    def __init__(self, path: Path, max_items: int = 100) -> None:
        self._path = path
        self._max_items = max_items

    def append(self, intent: IntentQueueEntry) -> IntentQueueEntry:
        items = self._load()
        items.append(intent)
        items.sort(key=lambda item: (-float(item.priority), item.created_at))
        if len(items) > self._max_items:
            items = items[: self._max_items]
        self._save(items)
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
        return updated

    def ensure_file(self) -> None:
        if not self._path.exists():
            self._save([])

    def _load(self) -> list[IntentQueueEntry]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        items: list[IntentQueueEntry] = []
        for entry in raw:
            if isinstance(entry, dict):
                items.append(IntentQueueEntry.from_dict(entry))
        return items

    def _save(self, items: list[IntentQueueEntry]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([item.to_dict() for item in items], indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
