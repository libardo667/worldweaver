# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Small, versioned resident-process fields shared across model adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

CONFIRMED_ACTION_RECEIPT_VERSION = 1
CONFIRMED_ACTION_KINDS = {"speak", "move", "do", "write", "mark"}
PRIVATE_ACTIVITY_STATE_VERSION = 1
PRIVATE_ACTIVITY_WAKE_EVENT_CLASSES = frozenset({"local_speech"})
REFERENCE_ACTIVATION_STATE_VERSION = 1
RESIDENT_PROCESS_ENVELOPE_VERSION = 1
REFERENCE_ADAPTER_ID = "worldweaver.reference-resident"
REFERENCE_ADAPTER_VERSION = 1
STATELESS_MODEL_STATE_FORMAT = "none"
STATELESS_MODEL_STATE_FORMAT_VERSION = 1


class ActionChoice(Protocol):
    kind: str
    target: str | None


@dataclass(frozen=True, slots=True)
class ResidentProcessBinding:
    """Versioned identity and runtime binding for one private process checkpoint."""

    actor_id: str
    hearth_shard_id: str
    runtime_generation: int
    attachment_kind: str
    world_id: str
    city_id: str
    session_id: str
    model_id: str
    adapter_id: str = REFERENCE_ADAPTER_ID
    adapter_version: int = REFERENCE_ADAPTER_VERSION

    def as_dict(self) -> dict[str, Any]:
        actor_id = str(self.actor_id or "").strip()
        attachment_kind = str(self.attachment_kind or "").strip()
        model_id = str(self.model_id or "").strip()
        if not actor_id:
            raise ValueError("resident process actor_id is required")
        if attachment_kind not in {"city", "hearth"}:
            raise ValueError("resident process attachment must be city or hearth")
        if (
            isinstance(self.runtime_generation, bool)
            or not isinstance(self.runtime_generation, int)
            or self.runtime_generation < 0
        ):
            raise ValueError("resident process generation cannot be negative")
        if not model_id:
            raise ValueError("resident process model_id is required")
        if self.adapter_id != REFERENCE_ADAPTER_ID:
            raise ValueError("unsupported resident process adapter")
        if (
            isinstance(self.adapter_version, bool)
            or not isinstance(self.adapter_version, int)
            or self.adapter_version != REFERENCE_ADAPTER_VERSION
        ):
            raise ValueError("unsupported resident process adapter version")
        return {
            "process_envelope_version": RESIDENT_PROCESS_ENVELOPE_VERSION,
            "actor_id": actor_id,
            "hearth": {
                "shard_id": str(self.hearth_shard_id or "").strip(),
                # Zero is reserved for old, unmanifested test/dev hearths. A
                # packaged resident always has a positive authoritative value.
                "runtime_generation": int(self.runtime_generation),
            },
            "attachment": {
                "kind": attachment_kind,
                "world_id": str(self.world_id or "").strip(),
                "city_id": str(self.city_id or "").strip(),
                "session_id": str(self.session_id or "").strip(),
            },
            "adapter": {
                "id": self.adapter_id,
                "version": self.adapter_version,
            },
            "model": {"id": model_id},
            "model_state": {
                "format": STATELESS_MODEL_STATE_FORMAT,
                "format_version": STATELESS_MODEL_STATE_FORMAT_VERSION,
                "byte_length": 0,
                "max_bytes": 0,
            },
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ResidentProcessBinding":
        if raw.get("process_envelope_version") != RESIDENT_PROCESS_ENVELOPE_VERSION:
            raise ValueError("unsupported resident process envelope version")
        hearth = raw.get("hearth") if isinstance(raw.get("hearth"), dict) else {}
        attachment = (
            raw.get("attachment") if isinstance(raw.get("attachment"), dict) else {}
        )
        adapter = raw.get("adapter") if isinstance(raw.get("adapter"), dict) else {}
        model = raw.get("model") if isinstance(raw.get("model"), dict) else {}
        model_state = (
            raw.get("model_state") if isinstance(raw.get("model_state"), dict) else {}
        )
        generation = hearth.get("runtime_generation")
        adapter_version = adapter.get("version")
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or isinstance(adapter_version, bool)
            or not isinstance(adapter_version, int)
        ):
            raise ValueError("invalid resident process version field")
        if model_state != {
            "format": STATELESS_MODEL_STATE_FORMAT,
            "format_version": STATELESS_MODEL_STATE_FORMAT_VERSION,
            "byte_length": 0,
            "max_bytes": 0,
        }:
            raise ValueError("unsupported resident model-state format")
        binding = cls(
            actor_id=str(raw.get("actor_id") or "").strip(),
            hearth_shard_id=str(hearth.get("shard_id") or "").strip(),
            runtime_generation=generation,
            attachment_kind=str(attachment.get("kind") or "").strip(),
            world_id=str(attachment.get("world_id") or "").strip(),
            city_id=str(attachment.get("city_id") or "").strip(),
            session_id=str(attachment.get("session_id") or "").strip(),
            model_id=str(model.get("id") or "").strip(),
            adapter_id=str(adapter.get("id") or "").strip(),
            adapter_version=adapter_version,
        )
        binding.as_dict()
        return binding


def advance_resident_process_envelope(
    current: dict[str, Any] | None,
    event: dict[str, Any],
) -> dict[str, Any] | None:
    """Project process bindings and acknowledged city cursors without prose."""

    event_type = str(event.get("event_type") or "").strip()
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    if event_type == "reference_process_bound":
        try:
            binding = ResidentProcessBinding.from_dict(payload)
        except ValueError:
            return current
        projected = binding.as_dict()
        projected["bound_at"] = str(event.get("ts") or "").strip()
        old_attachment = (
            current.get("attachment")
            if isinstance(current, dict) and isinstance(current.get("attachment"), dict)
            else {}
        )
        new_attachment = projected["attachment"]
        if (
            isinstance(current, dict)
            and current.get("actor_id") == projected["actor_id"]
            and old_attachment == new_attachment
            and isinstance(current.get("event_cursor"), dict)
        ):
            projected["event_cursor"] = dict(current["event_cursor"])
        else:
            projected["event_cursor"] = None
        return projected

    if event_type != "live_signal_cursor_advanced" or not isinstance(current, dict):
        return current
    attachment = (
        current.get("attachment") if isinstance(current.get("attachment"), dict) else {}
    )
    if (
        attachment.get("kind") != "city"
        or str(payload.get("session_id") or "").strip()
        != str(attachment.get("session_id") or "").strip()
    ):
        return current
    try:
        after_id = int(payload.get("after_id"))
    except (TypeError, ValueError):
        return current
    shard_id = str(payload.get("shard_id") or "").strip()
    location = str(payload.get("location") or "").strip()
    if after_id < 0 or not shard_id or not location:
        return current
    projected = dict(current)
    projected["event_cursor"] = {
        "cursor_version": 1,
        "session_id": str(payload.get("session_id") or "").strip(),
        "shard_id": shard_id,
        "location": location,
        "after_id": after_id,
    }
    return projected


@dataclass(frozen=True, slots=True)
class ConfirmedActionReceipt:
    """One exact confirmed own action restored from private checkpoint state."""

    event_id: str
    ts: str
    kind: str
    location: str = ""
    target: str = ""
    reference_kind: str = ""
    reference_id: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ConfirmedActionReceipt":
        if raw.get("receipt_version") != CONFIRMED_ACTION_RECEIPT_VERSION:
            raise ValueError("unsupported confirmed-action receipt version")
        event_id = str(raw.get("event_id") or "").strip()
        kind = str(raw.get("kind") or "").strip()
        if not event_id or kind not in CONFIRMED_ACTION_KINDS:
            raise ValueError("invalid confirmed-action receipt")
        return cls(
            event_id=event_id,
            ts=str(raw.get("ts") or "").strip(),
            kind=kind,
            location=str(raw.get("location") or "").strip(),
            target=str(raw.get("target") or "").strip(),
            reference_kind=str(raw.get("reference_kind") or "").strip(),
            reference_id=str(raw.get("reference_id") or "").strip(),
        )


@dataclass(frozen=True, slots=True)
class OpenPrivateActivity:
    """One resident-authored activity that remains open across activations."""

    activity_id: str
    activity: str
    opened_at: str
    updated_at: str
    return_at: str = ""
    wake_on: tuple[str, ...] = ("local_speech",)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "OpenPrivateActivity":
        if raw.get("activity_state_version") != PRIVATE_ACTIVITY_STATE_VERSION:
            raise ValueError("unsupported private-activity state version")
        activity_id = str(raw.get("activity_id") or "").strip()
        activity = str(raw.get("activity") or "").strip()
        opened_at = str(raw.get("opened_at") or "").strip()
        updated_at = str(raw.get("updated_at") or "").strip()
        return_at = str(raw.get("return_at") or "").strip()
        if return_at:
            try:
                parsed_return_at = datetime.fromisoformat(
                    return_at.replace("Z", "+00:00")
                )
            except ValueError as exc:
                raise ValueError("invalid private-activity return time") from exc
            if parsed_return_at.tzinfo is None:
                raise ValueError("private-activity return time must include a timezone")
        raw_wake_on = raw.get("wake_on", ["local_speech"])
        if not isinstance(raw_wake_on, (list, tuple)):
            raise ValueError("invalid private-activity wake classes")
        wake_on = tuple(str(value or "").strip() for value in raw_wake_on)
        if len(wake_on) != len(set(wake_on)) or not set(wake_on) <= set(
            PRIVATE_ACTIVITY_WAKE_EVENT_CLASSES
        ):
            raise ValueError("invalid private-activity wake classes")
        if not activity_id or not activity or len(activity) > 500:
            raise ValueError("invalid private-activity state")
        return cls(
            activity_id=activity_id,
            activity=activity,
            opened_at=opened_at,
            updated_at=updated_at,
            return_at=return_at,
            wake_on=wake_on,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "activity_state_version": PRIVATE_ACTIVITY_STATE_VERSION,
            "activity_id": self.activity_id,
            "activity": self.activity,
            "opened_at": self.opened_at,
            "updated_at": self.updated_at,
            "return_at": self.return_at,
            "wake_on": list(self.wake_on),
        }


def advance_open_private_activity(
    current: dict[str, Any] | None,
    event: dict[str, Any],
) -> dict[str, Any] | None:
    """Apply one explicitly versioned activity event without interpreting prose."""

    event_type = str(event.get("event_type") or "").strip()
    if event_type not in {
        "reference_activity_continued",
        "reference_activity_finished",
        "reference_activity_return_consumed",
    }:
        return current
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    if payload.get("activity_state_version") != PRIVATE_ACTIVITY_STATE_VERSION:
        return current
    activity_id = str(payload.get("activity_id") or "").strip()
    if not activity_id:
        return current

    if event_type == "reference_activity_finished":
        if current and str(current.get("activity_id") or "").strip() == activity_id:
            return None
        return current

    if event_type == "reference_activity_return_consumed":
        if not current or str(current.get("activity_id") or "").strip() != activity_id:
            return current
        consumed_return_at = str(payload.get("return_at") or "").strip()
        if str(current.get("return_at") or "").strip() != consumed_return_at:
            return current
        consumed = dict(current)
        consumed["return_at"] = ""
        return OpenPrivateActivity.from_dict(consumed).as_dict()

    activity = str(payload.get("activity") or "").strip()
    opened_at = str(payload.get("opened_at") or "").strip()
    updated_at = str(event.get("ts") or "").strip()
    candidate = {
        "activity_state_version": PRIVATE_ACTIVITY_STATE_VERSION,
        "activity_id": activity_id,
        "activity": activity,
        "opened_at": opened_at,
        "updated_at": updated_at,
        "return_at": str(payload.get("return_at") or "").strip(),
        "wake_on": payload.get("wake_on", ["local_speech"]),
    }
    try:
        return OpenPrivateActivity.from_dict(candidate).as_dict()
    except ValueError:
        return current


def project_reference_activation_at(event: dict[str, Any]) -> str | None:
    """Project a versioned activation time for restart-safe scheduling."""

    if str(event.get("event_type") or "").strip() not in {
        "reference_activation_started",
        "reference_activity_return_consumed",
    }:
        return None
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    if payload.get("process_state_version") != REFERENCE_ACTIVATION_STATE_VERSION:
        return None
    return str(payload.get("as_of") or event.get("ts") or "").strip() or None


def project_confirmed_action_receipt(
    event: dict[str, Any],
) -> dict[str, Any] | None:
    """Project one exact confirmed action without interpreting it."""

    if str(event.get("event_type") or "").strip() != "reference_action_outcome":
        return None
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    if payload.get("receipt_version") != CONFIRMED_ACTION_RECEIPT_VERSION:
        return None
    if str(payload.get("outcome") or "").strip() != "confirmed":
        return None
    kind = str(payload.get("kind") or "").strip()
    if kind not in CONFIRMED_ACTION_KINDS:
        return None
    return {
        "receipt_version": CONFIRMED_ACTION_RECEIPT_VERSION,
        "event_id": str(event.get("event_id") or "").strip(),
        "ts": str(event.get("ts") or "").strip(),
        "kind": kind,
        "location": str(payload.get("location") or "").strip(),
        "target": str(payload.get("target") or "").strip(),
        "reference_kind": str(payload.get("reference_kind") or "").strip(),
        "reference_id": str(payload.get("reference_id") or "").strip(),
    }


def confirmed_action_payload(
    act: ActionChoice,
    result: Any,
    *,
    outcome: str,
    observed_location: str,
) -> dict[str, Any]:
    """Keep bounded engine identifiers and coordinates, never result narration."""

    result_payload = dict(result) if isinstance(result, dict) else {}
    trace = (
        dict(result_payload.get("trace") or {})
        if isinstance(result_payload.get("trace"), dict)
        else {}
    )
    location = str(
        result_payload.get("arrived_at")
        or result_payload.get("location")
        or trace.get("location")
        or observed_location
        or ""
    ).strip()[:200]
    target = str(
        result_payload.get("destination")
        or result_payload.get("addressed")
        or result_payload.get("carried_to")
        or result_payload.get("recipient")
        or result_payload.get("command")
        or trace.get("target")
        or act.target
        or ""
    ).strip()[:200]
    reference_kind = ""
    reference_id = ""
    candidates = (
        ("trace", trace.get("trace_id")),
        ("receipt", result_payload.get("receipt_id")),
        ("exchange", result_payload.get("exchange_id")),
        ("object", result_payload.get("object_id")),
        ("activity", result_payload.get("candidate_id")),
    )
    for candidate_kind, candidate_id in candidates:
        normalized_id = str(candidate_id or "").strip()
        if normalized_id:
            reference_kind = candidate_kind
            reference_id = normalized_id[:200]
            break
    return {
        "receipt_version": CONFIRMED_ACTION_RECEIPT_VERSION,
        "kind": act.kind,
        "outcome": outcome,
        "reason": (
            str(result_payload.get("reason") or "").strip()[:120]
            if isinstance(result, dict)
            else "invalid_result"
        ),
        "location": location,
        "target": target,
        "reference_kind": reference_kind,
        "reference_id": reference_id,
    }


def render_confirmed_action_receipt(receipt: ConfirmedActionReceipt) -> str:
    """Render only stored receipt fields, without inventing a summary."""

    fields = [f"kind={receipt.kind}"]
    if receipt.location:
        fields.append(f"location={receipt.location}")
    if receipt.target:
        fields.append(f"target={receipt.target}")
    if receipt.reference_kind and receipt.reference_id:
        fields.append(f"reference={receipt.reference_kind}:{receipt.reference_id}")
    if receipt.ts:
        fields.append(f"time={receipt.ts}")
    return "- " + "; ".join(fields)
