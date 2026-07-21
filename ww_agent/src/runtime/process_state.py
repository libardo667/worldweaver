# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Small, versioned resident-process fields shared across model adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

CONFIRMED_ACTION_RECEIPT_VERSION = 1
CONFIRMED_ACTION_KINDS = {"speak", "move", "do", "write", "mark"}


class ActionChoice(Protocol):
    kind: str
    target: str | None


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
