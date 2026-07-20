# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Directory-local admission, revocation, and key recovery for federation nodes."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import FederationNodeTrustEvent, FederationShard


class FederationNodeTrustError(ValueError):
    pass


def _required(value: str, label: str, *, maximum: int) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > maximum:
        raise FederationNodeTrustError(
            f"{label} must be between 1 and {maximum} characters."
        )
    return normalized


def admit_node(
    db: Session,
    *,
    node_id: str,
    public_key: str,
    shard_type: str,
    city_id: str | None,
    reason: str,
) -> FederationShard:
    node_id = _required(node_id, "node_id", maximum=80)
    public_key = _required(public_key, "public_key", maximum=80)
    reason = _required(reason, "reason", maximum=255)
    existing = db.get(FederationShard, node_id)
    if existing is not None:
        if existing.public_key != public_key:
            raise FederationNodeTrustError(
                "This node ID is already bound to another key. Revoke it before key recovery."
            )
        if existing.admission_state == "revoked":
            raise FederationNodeTrustError(
                "This node is revoked. Use explicit key recovery rather than admitting it again."
            )
        return existing

    now = datetime.now(timezone.utc)
    shard = FederationShard(
        shard_id=node_id,
        shard_url="",
        shard_type=_required(shard_type, "shard_type", maximum=20),
        city_id=str(city_id or "").strip() or None,
        public_key=public_key,
        identity_bound_at=now,
        admission_state="approved",
        admitted_at=now,
    )
    db.add(shard)
    db.add(
        FederationNodeTrustEvent(
            node_id=node_id,
            event_type="admitted",
            public_key=public_key,
            reason=reason,
        )
    )
    db.commit()
    db.refresh(shard)
    return shard


def revoke_node(db: Session, *, node_id: str, reason: str) -> FederationShard:
    node_id = _required(node_id, "node_id", maximum=80)
    reason = _required(reason, "reason", maximum=255)
    shard = db.get(FederationShard, node_id)
    if shard is None:
        raise FederationNodeTrustError("Node is not known to this directory.")
    if shard.admission_state == "revoked":
        return shard
    shard.admission_state = "revoked"
    shard.revoked_at = datetime.now(timezone.utc)
    shard.revocation_reason = reason
    shard.last_pulse_ts = None
    db.add(
        FederationNodeTrustEvent(
            node_id=node_id,
            event_type="revoked",
            previous_public_key=shard.public_key,
            public_key=shard.public_key,
            reason=reason,
        )
    )
    db.commit()
    db.refresh(shard)
    return shard


def recover_node_key(
    db: Session,
    *,
    node_id: str,
    public_key: str,
    shard_type: str,
    city_id: str | None,
    reason: str,
) -> FederationShard:
    node_id = _required(node_id, "node_id", maximum=80)
    public_key = _required(public_key, "public_key", maximum=80)
    reason = _required(reason, "reason", maximum=255)
    shard = db.get(FederationShard, node_id)
    if shard is None:
        raise FederationNodeTrustError("Unknown nodes must be admitted, not recovered.")
    if shard.admission_state != "revoked":
        raise FederationNodeTrustError(
            "Revoke the old node identity before recovering its key."
        )
    if shard.public_key == public_key:
        raise FederationNodeTrustError(
            "Recovery requires a newly generated public key."
        )

    previous_key = shard.public_key
    now = datetime.now(timezone.utc)
    shard.public_key = public_key
    shard.shard_type = _required(shard_type, "shard_type", maximum=20)
    shard.city_id = str(city_id or "").strip() or None
    shard.identity_bound_at = now
    shard.key_recovered_at = now
    shard.admission_state = "approved"
    shard.admitted_at = now
    shard.revoked_at = None
    shard.revocation_reason = None
    db.add(
        FederationNodeTrustEvent(
            node_id=node_id,
            event_type="key_recovered",
            previous_public_key=previous_key,
            public_key=public_key,
            reason=reason,
        )
    )
    db.commit()
    db.refresh(shard)
    return shard
