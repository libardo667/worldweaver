from __future__ import annotations

import pytest

from src.models import FederationNodeTrustEvent, FederationShard
from src.services.federation_node_trust import (
    FederationNodeTrustError,
    admit_node,
    recover_node_key,
    revoke_node,
)


def test_node_trust_changes_are_explicit_and_audited(db_session):
    admitted = admit_node(
        db_session,
        node_id="alderbank-node",
        public_key="first-public-key",
        shard_type="city",
        city_id="alderbank",
        reason="Invite the Alderbank steward.",
    )
    revoked = revoke_node(
        db_session,
        node_id="alderbank-node",
        reason="The old private key may have been copied.",
    )
    revoked_at = revoked.revoked_at
    recovered = recover_node_key(
        db_session,
        node_id="alderbank-node",
        public_key="replacement-public-key",
        shard_type="city",
        city_id="alderbank",
        reason="The steward verified a replacement descriptor out of band.",
    )

    events = db_session.query(FederationNodeTrustEvent).filter(FederationNodeTrustEvent.node_id == "alderbank-node").order_by(FederationNodeTrustEvent.id).all()
    assert admitted.shard_id == "alderbank-node"
    assert revoked_at is not None
    assert recovered.admission_state == "approved"
    assert recovered.public_key == "replacement-public-key"
    assert recovered.revoked_at is None
    assert [event.event_type for event in events] == ["admitted", "revoked", "key_recovered"]
    assert events[-1].previous_public_key == "first-public-key"


def test_node_key_cannot_change_without_revocation(db_session):
    admit_node(
        db_session,
        node_id="fixed-node",
        public_key="first-public-key",
        shard_type="city",
        city_id="portland",
        reason="Known local node.",
    )

    with pytest.raises(FederationNodeTrustError, match="Revoke"):
        recover_node_key(
            db_session,
            node_id="fixed-node",
            public_key="replacement-public-key",
            shard_type="city",
            city_id="portland",
            reason="Attempted replacement without revocation.",
        )

    assert db_session.get(FederationShard, "fixed-node").public_key == "first-public-key"
