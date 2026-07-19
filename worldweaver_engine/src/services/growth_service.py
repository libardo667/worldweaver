# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Compatibility storage for identity proposals sent by older residents.

Current residents keep self-edit proposals in their private hearth ledgers. A city
does not inspect those proposals or decide which ones become identity. This small
helper remains so an older resident runner can post without corrupting its history
while deployments are upgraded.
"""

from __future__ import annotations

from typing import Any

from ..models import ResidentIdentityGrowth


def append_growth_proposals(
    row: ResidentIdentityGrowth,
    incoming: list[dict[str, Any]],
) -> int:
    """Append compatibility proposals as posted, deduplicated by pulse ID."""
    existing = [proposal for proposal in list(row.growth_proposals or []) if isinstance(proposal, dict)]
    seen = {str(proposal.get("pulse_id") or "") for proposal in existing if str(proposal.get("pulse_id") or "")}
    legacy_metadata = dict(row.growth_metadata or {})
    seen.update(str(pulse_id) for pulse_id in legacy_metadata.get("promoted_pulse_ids") or [] if str(pulse_id))

    added: list[dict[str, Any]] = []
    for proposal in list(incoming or []):
        if not isinstance(proposal, dict):
            continue
        pulse_id = str(proposal.get("pulse_id") or "").strip()
        if pulse_id and pulse_id in seen:
            continue
        if pulse_id:
            seen.add(pulse_id)
        added.append(dict(proposal))

    if added:
        row.growth_proposals = existing + added
    return len(added)
