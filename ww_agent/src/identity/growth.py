# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Resident-controlled adoption of private identity-growth proposals.

Pulse routing may stage a resident's own words as a proposal, but staging does
not change identity.  This module supplies the separate hearth-only path:
inspect one proposal through a private information source, then explicitly
adopt that exact wording through a typed action.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.identity.loader import IdentityLoader, ResidentIdentity
from src.runtime.ledger import append_runtime_event, load_runtime_projection_events

GROWTH_SOURCE = "growth"
GROWTH_RECORD_PREFIX = "growth-candidate:"
GROWTH_ACTION_PREFIX = "growth-adopt:"
GROWTH_REPLAY_LIMIT = 10_000
GROWTH_METADATA_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GrowthCandidate:
    candidate_id: str
    body: str
    staged_event_id: str
    pulse_event_id: str
    staged_at: str
    related_event_ids: tuple[str, ...] = ()

    @property
    def source_event_ids(self) -> list[str]:
        return [self.pulse_event_id, self.staged_event_id]

    @property
    def record_id(self) -> str:
        return f"{GROWTH_RECORD_PREFIX}{self.candidate_id}"


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("payload")
    return raw if isinstance(raw, dict) else {}


def _candidate_id(value: str) -> str:
    candidate_id = str(value or "").strip()
    for prefix in (GROWTH_RECORD_PREFIX, GROWTH_ACTION_PREFIX):
        if candidate_id.lower().startswith(prefix):
            candidate_id = candidate_id[len(prefix) :].strip()
    return candidate_id


def _adopted_candidate_ids(events: list[dict[str, Any]]) -> set[str]:
    adopted: set[str] = set()
    for event in events:
        candidate_id = str(_payload(event).get("candidate_id") or "").strip()
        if str(event.get("event_type") or "") == "growth_adopted" and candidate_id:
            adopted.add(candidate_id)
    return adopted


def _growth_candidates(
    events: list[dict[str, Any]],
    *,
    include_adopted: bool = False,
) -> list[GrowthCandidate]:
    pulse_events: dict[str, dict[str, Any]] = {}
    for event in events:
        pulse_id = str(_payload(event).get("pulse_id") or "").strip()
        if str(event.get("event_type") or "") == "pulse_emitted" and pulse_id:
            pulse_events[pulse_id] = event
    adopted = set() if include_adopted else _adopted_candidate_ids(events)
    staged: list[dict[str, Any]] = []
    for event in events:
        payload = _payload(event)
        event_id = str(event.get("event_id") or "").strip()
        pulse_id = str(payload.get("pulse_id") or "").strip()
        is_candidate = (
            str(event.get("event_type") or "") == "self_delta_staged"
            and event_id
            and event_id not in adopted
            and str(payload.get("kind") or "") == "soul_edit"
            and str(payload.get("verdict") or "") == "accepted"
            and str(payload.get("body") or "").strip()
            and pulse_id in pulse_events
        )
        if is_candidate:
            staged.append(event)

    candidates: list[GrowthCandidate] = []
    for index, event in enumerate(staged):
        payload = _payload(event)
        body = str(payload.get("body") or "").strip()
        pulse_id = str(payload.get("pulse_id") or "").strip()
        pulse_event = pulse_events[pulse_id]
        related = tuple(
            str(earlier.get("event_id") or "").strip()
            for earlier in staged[:index]
            if str(_payload(earlier).get("body") or "").strip() == body
        )[-3:]
        candidates.append(
            GrowthCandidate(
                candidate_id=str(event.get("event_id") or "").strip(),
                body=body,
                staged_event_id=str(event.get("event_id") or "").strip(),
                pulse_event_id=str(pulse_event.get("event_id") or "").strip(),
                staged_at=str(event.get("ts") or payload.get("cast_ts") or "").strip(),
                related_event_ids=related,
            )
        )
    return candidates


def read_growth_candidate(memory_dir: Path, query: str = "") -> dict[str, Any]:
    """Return one pending proposal and exact ledger provenance, never a rewrite."""
    events = load_runtime_projection_events(memory_dir, max_events=GROWTH_REPLAY_LIMIT)
    candidates = _growth_candidates(events)
    requested = _candidate_id(query)
    if requested and requested.lower() not in {"latest", "newest", "recent"}:
        candidate = next(
            (item for item in candidates if item.candidate_id == requested), None
        )
        selection_mode = "exact_id"
    else:
        candidate = candidates[-1] if candidates else None
        selection_mode = "latest"
    if candidate is None:
        return {
            "ok": False,
            "reason": "growth_candidate_not_found",
            "selection_mode": selection_mode,
            "records": [],
        }

    related = (
        "\nEarlier matching proposal event IDs (context only, not evidence): "
        + ", ".join(candidate.related_event_ids)
        if candidate.related_event_ids
        else ""
    )
    content = (
        "You previously proposed this exact change to your own identity:\n\n"
        f"{candidate.body}\n\n"
        f"Source events: pulse {candidate.pulse_event_id}; proposal {candidate.staged_event_id}."
        f"{related}\n\n"
        "This is still only a proposal. Repetition does not prove that it belongs in your identity. "
        "If you choose to adopt these exact words, make a do action with target "
        f"'{GROWTH_ACTION_PREFIX}{candidate.candidate_id}'."
    )
    return {
        "ok": True,
        "selection_mode": selection_mode,
        "records": [
            {
                "record_id": candidate.record_id,
                "title": f"identity proposal from {candidate.staged_at or 'your ledger'}",
                "content": content,
                "observed_at": candidate.staged_at,
                "freshness": "remembered",
                "locality": "self",
                "visibility": "private",
                "selection_mode": selection_mode,
                "metadata": {
                    "candidate_id": candidate.candidate_id,
                    "source_event_ids": candidate.source_event_ids,
                    "related_event_ids": list(candidate.related_event_ids),
                },
            }
        ],
    }


def _inspection_event(
    events: list[dict[str, Any]],
    candidate: GrowthCandidate,
) -> dict[str, Any] | None:
    for event in reversed(events):
        if str(event.get("event_type") or "") != "information_accessed":
            continue
        payload = _payload(event)
        if str(payload.get("source") or "").strip().lower() != GROWTH_SOURCE:
            continue
        if not bool(payload.get("accessed")):
            continue
        refs = (
            payload.get("record_refs")
            if isinstance(payload.get("record_refs"), list)
            else []
        )
        if any(
            isinstance(ref, dict)
            and str(ref.get("record_id") or "").strip() == candidate.record_id
            for ref in refs
        ):
            return event
    return None


def _growth_metadata(resident_dir: Path) -> dict[str, Any]:
    path = IdentityLoader.growth_metadata_path(resident_dir)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("growth_metadata_invalid") from exc
    if not isinstance(raw, dict):
        raise ValueError("growth_metadata_invalid")
    return dict(raw)


def _persist_adoption(
    resident_dir: Path,
    identity: ResidentIdentity,
    candidate: GrowthCandidate,
    adoption_event: dict[str, Any],
) -> None:
    metadata = _growth_metadata(resident_dir)
    adoptions = [
        dict(item)
        for item in list(metadata.get("adoptions") or [])
        if isinstance(item, dict)
    ]
    candidate_ids = {str(item.get("candidate_id") or "").strip() for item in adoptions}
    if candidate.candidate_id not in candidate_ids:
        adoptions.append(
            {
                "candidate_id": candidate.candidate_id,
                "adoption_event_id": str(adoption_event.get("event_id") or ""),
                "source_event_ids": candidate.source_event_ids,
                "inspection_event_id": str(
                    _payload(adoption_event).get("inspection_event_id") or ""
                ),
                "adopted_at": str(adoption_event.get("ts") or ""),
            }
        )

    _canonical, existing_growth = IdentityLoader.load_canonical_and_growth(resident_dir)
    paragraphs = [
        part.strip() for part in existing_growth.split("\n\n") if part.strip()
    ]
    growth = existing_growth.strip()
    if candidate.body not in paragraphs:
        growth = f"{growth}\n\n{candidate.body}".strip()
    metadata.update(
        {
            "schema_version": GROWTH_METADATA_SCHEMA_VERSION,
            "adoptions": adoptions,
        }
    )
    IdentityLoader.save_growth_soul(resident_dir, growth, metadata=metadata)
    identity.growth_soul = growth
    identity.soul = IdentityLoader.composed_soul(identity.canonical_soul, growth)


def adopt_growth_candidate(
    resident_dir: Path,
    identity: ResidentIdentity,
    candidate_id: str,
) -> dict[str, Any]:
    """Adopt one inspected proposal exactly once and refresh live identity."""
    memory_dir = resident_dir / "memory"
    events = load_runtime_projection_events(memory_dir, max_events=GROWTH_REPLAY_LIMIT)
    requested = _candidate_id(candidate_id)
    candidate = next(
        (
            item
            for item in _growth_candidates(events, include_adopted=True)
            if item.candidate_id == requested
        ),
        None,
    )
    if candidate is None:
        return {"ok": False, "reason": "growth_candidate_not_found"}

    prior_adoption = next(
        (
            event
            for event in events
            if str(event.get("event_type") or "") == "growth_adopted"
            and str(_payload(event).get("candidate_id") or "").strip()
            == candidate.candidate_id
        ),
        None,
    )
    if prior_adoption is not None:
        _persist_adoption(resident_dir, identity, candidate, prior_adoption)
        return {
            "ok": True,
            "adopted": True,
            "replayed": True,
            "candidate_id": candidate.candidate_id,
            "adoption_event_id": str(prior_adoption.get("event_id") or ""),
        }

    inspection = _inspection_event(events, candidate)
    if inspection is None:
        return {"ok": False, "reason": "growth_candidate_not_inspected"}

    adoption_event = append_runtime_event(
        memory_dir,
        event_type="growth_adopted",
        payload={
            "schema_version": GROWTH_METADATA_SCHEMA_VERSION,
            "candidate_id": candidate.candidate_id,
            "body": candidate.body,
            "source_event_ids": candidate.source_event_ids,
            "inspection_event_id": str(inspection.get("event_id") or ""),
            "actor_id": str(identity.actor_id or ""),
        },
    )
    _persist_adoption(resident_dir, identity, candidate, adoption_event)
    return {
        "ok": True,
        "adopted": True,
        "replayed": False,
        "candidate_id": candidate.candidate_id,
        "adoption_event_id": str(adoption_event.get("event_id") or ""),
    }


def repair_growth_adoptions(
    resident_dir: Path,
    identity: ResidentIdentity,
) -> bool:
    """Finish any ledger-recorded adoption whose identity-file write was interrupted."""
    events = load_runtime_projection_events(
        resident_dir / "memory", max_events=GROWTH_REPLAY_LIMIT
    )
    adoption_events = [
        event
        for event in events
        if str(event.get("event_type") or "") == "growth_adopted"
    ]
    if not adoption_events:
        return False
    metadata = _growth_metadata(resident_dir)
    recorded_ids = {
        str(item.get("candidate_id") or "").strip()
        for item in list(metadata.get("adoptions") or [])
        if isinstance(item, dict)
    }
    _canonical, growth = IdentityLoader.load_canonical_and_growth(resident_dir)
    paragraphs = {part.strip() for part in growth.split("\n\n") if part.strip()}
    repaired = False
    for event in adoption_events:
        payload = _payload(event)
        candidate_id = str(payload.get("candidate_id") or "").strip()
        body = str(payload.get("body") or "").strip()
        source_ids = [
            str(value or "").strip()
            for value in list(payload.get("source_event_ids") or [])
            if str(value or "").strip()
        ]
        if not candidate_id or not body or len(source_ids) < 2:
            continue
        if candidate_id in recorded_ids and body in paragraphs:
            continue
        candidate = GrowthCandidate(
            candidate_id=candidate_id,
            body=body,
            staged_event_id=source_ids[-1],
            pulse_event_id=source_ids[0],
            staged_at="",
        )
        _persist_adoption(resident_dir, identity, candidate, event)
        recorded_ids.add(candidate_id)
        paragraphs.add(body)
        repaired = True
    return repaired
