# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from src.models import WorldNode
from src.services.location_routes import resolve_route_anchor
from src.services.world_memory import seed_location_graph


def test_route_anchor_keeps_a_connected_canonical_location(db_session):
    seed_location_graph(
        db_session,
        [{"name": "Tea House"}, {"name": "Market Street"}],
    )

    assert resolve_route_anchor(db_session, "Tea House") == "Tea House"


def test_route_anchor_uses_an_exact_places_declared_parent(db_session):
    seed_location_graph(
        db_session,
        [{"name": "Tea House"}, {"name": "Market Street"}],
    )
    db_session.add(
        WorldNode(
            name="Back Booth",
            normalized_name="tea_house::back_booth",
            node_type="sublocation",
            metadata_json={"parent_location": "Tea House"},
        )
    )
    db_session.commit()

    assert resolve_route_anchor(db_session, "Back Booth") == "Tea House"


def test_route_anchor_leaves_an_unknown_name_for_normal_route_failure(db_session):
    assert resolve_route_anchor(db_session, "Somewhere Else") == "Somewhere Else"
