# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Versioned relational fields for resident-ledger events.

The ledger already records what a resident did. These helpers add the stable
actor, place, co-presence, and utterance identifiers needed to answer who was
actually involved without guessing from names or timestamps.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

RELATIONAL_EVENT_SCHEMA_VERSION = 1


def _text(value: Any) -> str:
    return str(value or "").strip()


def chat_utterance_id(location: str, transport_id: Any) -> str:
    """Canonical ID shared by the chat sender and every recipient ledger."""
    channel = _text(location)
    message_id = _text(transport_id)
    return f"chat:{channel}:{message_id}" if channel and message_id else ""


def normalize_actor_refs(
    items: Iterable[Mapping[str, Any]] | None,
) -> list[dict[str, str]]:
    """Return one deterministic reference per actor/session without inventing IDs."""
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items or ():
        actor_id = _text(item.get("actor_id"))
        session_id = _text(item.get("session_id"))
        name = _text(item.get("name"))
        key = (actor_id, session_id)
        if not any(key) or key in seen:
            continue
        seen.add(key)
        refs.append({"actor_id": actor_id, "session_id": session_id, "name": name})
    return refs


def relational_event_fields(
    *,
    actor_id: str,
    actor_session_id: str,
    location: str,
    co_present: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the common, versioned envelope used by relational ledger events."""
    own_actor_id = _text(actor_id)
    refs = normalize_actor_refs(co_present)
    co_present_ids = sorted(
        {
            _text(ref.get("actor_id"))
            for ref in refs
            if _text(ref.get("actor_id")) and _text(ref.get("actor_id")) != own_actor_id
        }
    )
    return {
        "edge_schema_version": RELATIONAL_EVENT_SCHEMA_VERSION,
        "actor_id": own_actor_id,
        "actor_session_id": _text(actor_session_id),
        "location": _text(location),
        "co_present": co_present_ids,
    }


def utterance_perceived_fields(
    *,
    packet: Any,
    recipient_actor_id: str,
    recipient_session_id: str,
    co_present: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Describe a chat packet that crossed the prompt boundary.

    Polling alone leaves a packet pending. This event is built only after that
    packet was selected into a resident-model prompt, which is the first point at
    which the runtime can honestly say the resident attended to the utterance.
    """
    packet_type = _text(getattr(packet, "packet_type", ""))
    if packet_type not in {"chat_heard", "city_chat_heard"}:
        return None
    payload = dict(getattr(packet, "payload", {}) or {})
    utterance_id = _text(payload.get("source_id"))
    if not utterance_id:
        return None
    location = _text(getattr(packet, "location", "") or payload.get("location"))
    return {
        **relational_event_fields(
            actor_id=recipient_actor_id,
            actor_session_id=recipient_session_id,
            location=location,
            co_present=co_present,
        ),
        "packet_id": _text(getattr(packet, "packet_id", "")),
        "utterance_id": utterance_id,
        "transport_id": _text(payload.get("id")),
        "speaker_actor_id": _text(payload.get("actor_id")),
        "speaker_session_id": _text(payload.get("session_id")),
        "speaker_name": _text(payload.get("speaker")),
        "channel": _text(payload.get("channel"))
        or ("city" if packet_type == "city_chat_heard" else "local"),
        "is_direct": bool(payload.get("is_direct")),
    }
