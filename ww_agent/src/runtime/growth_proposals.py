# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Collect accepted self-delta proposals from the ledger, to post to the server gate.

This is the agent half of the city growth pipeline. The substrate stages
``self_delta`` (soul-edit) candidates through the constitution gate
(``pulse.route_pulse`` → ``self_delta_staged`` events on the ledger). This reader
lifts the *accepted* ones and hands them to the resident runner, which posts them
to the server's identity-growth endpoint as ``growth_proposals``.

Note what this is NOT: it does not promote, distil, or write any soul file. The
worldweaver growth gate lives **server-side** (``growth_service.promote_growth``,
the concordance gate over the DB) — the agent only posts proposals; the server
decides what becomes soul. (Contrast the-stable's local-file ``growth.py``, the
right design for a DB-less single machine, the wrong one to bolt onto worldweaver.)
"""

from __future__ import annotations

from pathlib import Path

from src.runtime.ledger import load_runtime_events


def collect_new_growth_proposals(memory_dir: Path, posted_ids: set[str]) -> list[dict[str, str]]:
    """Accepted soul-edit self-deltas not yet posted, as ``{body, pulse_id, ts}`` records.

    ``posted_ids`` is the set of pulse_ids already sent this run (to avoid re-posting);
    the server also dedups by pulse_id, so a missed entry here is harmless.
    """
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for event in load_runtime_events(memory_dir):
        if str(event.get("event_type") or "") != "self_delta_staged":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if str(payload.get("verdict") or "") != "accepted" or str(payload.get("kind") or "") != "soul_edit":
            continue
        pulse_id = str(payload.get("pulse_id") or "").strip()
        if not pulse_id or pulse_id in posted_ids or pulse_id in seen:
            continue
        body = str(payload.get("body") or "").strip()
        if not body:
            continue
        seen.add(pulse_id)
        out.append({
            "body": body,
            "pulse_id": pulse_id,
            "ts": str(event.get("ts") or payload.get("cast_ts") or "").strip(),
        })
    return out
