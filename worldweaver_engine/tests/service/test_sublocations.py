from datetime import datetime, timedelta, timezone

import pytest

from src.services.sublocations import (
    active_sublocations,
    create_or_refresh_ephemeral,
    graph_with_sublocations,
    is_local_sublocation_candidate,
    resolve_active_sublocation,
    resolve_sublocation,
    sublocation_payload,
)

NOW = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)


def test_creation_is_parent_scoped_stable_and_refreshes_expiry(db_session):
    first = create_or_refresh_ephemeral(
        db_session,
        parent_location="Arbor Lodge",
        label="the duplex near Arbor Lodge Park",
        created_by_session="resident-one",
        ttl_seconds=1800,
        now=NOW,
    )
    first_id = first.id
    initial = sublocation_payload(first)

    refreshed = create_or_refresh_ephemeral(
        db_session,
        parent_location="Arbor Lodge",
        label="the duplex near Arbor Lodge Park",
        created_by_session="resident-two",
        ttl_seconds=1800,
        now=NOW + timedelta(minutes=10),
    )
    payload = sublocation_payload(refreshed)

    assert refreshed.id == first_id
    assert payload["sublocation_id"] == f"sublocation:{first_id}"
    assert payload["parent_location"] == "Arbor Lodge"
    assert payload["created_by_session"] == "resident-one"
    assert payload["expires_at"] > initial["expires_at"]


def test_expired_sublocation_stops_resolving_without_deleting_history(db_session):
    row = create_or_refresh_ephemeral(
        db_session,
        parent_location="Arbor Lodge",
        label="back booth",
        created_by_session="resident-one",
        ttl_seconds=900,
        now=NOW,
    )

    assert active_sublocations(
        db_session,
        parent_location="Arbor Lodge",
        now=NOW + timedelta(minutes=14),
    ) == [row]
    assert (
        active_sublocations(
            db_session,
            parent_location="Arbor Lodge",
            now=NOW + timedelta(minutes=16),
        )
        == []
    )
    assert (
        resolve_active_sublocation(
            db_session,
            label="back booth",
            parent_location="Arbor Lodge",
            now=NOW + timedelta(minutes=16),
        )
        is None
    )
    assert (
        resolve_sublocation(
            db_session,
            label="back booth",
            parent_location="Arbor Lodge",
        )
        is row
    )


def test_creation_rule_rejects_unknown_distant_places(db_session):
    assert is_local_sublocation_candidate(
        "the duplex near Arbor Lodge Park",
        "Arbor Lodge",
    )
    assert is_local_sublocation_candidate("back booth", "Arbor Lodge")
    assert not is_local_sublocation_candidate("Seattle", "Arbor Lodge")

    with pytest.raises(ValueError):
        create_or_refresh_ephemeral(
            db_session,
            parent_location="Arbor Lodge",
            label="Seattle",
            created_by_session="resident-one",
            now=NOW,
        )


def test_scene_graph_adds_children_without_mutating_canonical_graph(db_session):
    row = create_or_refresh_ephemeral(
        db_session,
        parent_location="Arbor Lodge",
        label="back booth",
        created_by_session="resident-one",
        now=NOW,
    )
    canonical = {
        "nodes": [{"key": "location:arbor_lodge", "name": "Arbor Lodge"}],
        "edges": [],
    }

    augmented = graph_with_sublocations(
        canonical,
        parent_location="Arbor Lodge",
        rows=[row],
    )

    assert canonical == {
        "nodes": [{"key": "location:arbor_lodge", "name": "Arbor Lodge"}],
        "edges": [],
    }
    assert {node["name"] for node in augmented["nodes"]} == {
        "Arbor Lodge",
        "back booth",
    }
    assert {(edge["from"], edge["to"]) for edge in augmented["edges"]} == {
        ("location:arbor_lodge", f"sublocation:{row.id}"),
        (f"sublocation:{row.id}", "location:arbor_lodge"),
    }
