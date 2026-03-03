"""Tests for dual-layer navigation behavior in spatial navigator."""

from unittest.mock import patch

from src.models import Storylet
from src.services.spatial_navigator import SpatialNavigator


def _add_storylet(
    db_session,
    *,
    title: str,
    position: dict,
    embedding: list[float] | None = None,
    requires: dict | None = None,
):
    storylet = Storylet(
        title=title,
        text_template=f"{title} text.",
        requires=requires or {},
        choices=[{"label": "Continue", "set": {}}],
        weight=1.0,
        position=position,
        embedding=embedding,
    )
    db_session.add(storylet)
    db_session.commit()
    db_session.refresh(storylet)
    return storylet


def test_ranked_field_biases_toward_requested_direction(db_session):
    current = _add_storylet(
        db_session,
        title="Current",
        position={"x": 0, "y": 0},
        requires={"location": "start"},
        embedding=[1.0, 0.0, 0.0],
    )
    _add_storylet(
        db_session,
        title="North Relevant",
        position={"x": 0, "y": -1},
        embedding=[0.8, 0.0, 0.0],
    )
    _add_storylet(
        db_session,
        title="East Also Relevant",
        position={"x": 1, "y": 0},
        embedding=[0.9, 0.0, 0.0],
    )
    _add_storylet(
        db_session,
        title="Northwest Lead",
        position={"x": -1, "y": -1},
        embedding=[0.75, 0.0, 0.0],
    )

    navigator = SpatialNavigator(db_session)
    nav = navigator.get_navigation_options(
        current_storylet_id=int(current.id),
        player_vars={"location": "start"},
        context_vector=[1.0, 0.0, 0.0],
        preferred_direction="north",
    )

    leads = nav["leads"]
    assert len(leads) >= 3
    assert "score" in leads[0]
    assert leads[0]["score"] == leads[0]["blended_score"]
    assert leads[0]["direction"] in {"north", "northeast", "northwest"}
    assert leads[0]["blended_score"] >= leads[1]["blended_score"]


def test_semantic_goal_hint_points_to_blacksmith_direction(db_session):
    current = _add_storylet(
        db_session,
        title="Town Square",
        position={"x": 0, "y": 0},
        requires={"location": "start"},
        embedding=[0.2, 0.8, 0.0],
    )
    _add_storylet(
        db_session,
        title="Blacksmith Forge",
        position={"x": 1, "y": 0},
        embedding=[1.0, 0.0, 0.0],
    )
    _add_storylet(
        db_session,
        title="Quiet Chapel",
        position={"x": -1, "y": 0},
        embedding=[0.0, 1.0, 0.0],
    )

    navigator = SpatialNavigator(db_session)

    def _fake_embed(text: str) -> list[float]:
        return [1.0, 0.0, 0.0] if "blacksmith" in text.lower() else [0.0, 1.0, 0.0]

    with patch("src.services.spatial_navigator.embed_text", side_effect=_fake_embed):
        hint = navigator.get_semantic_goal_hint(
            current_storylet_id=int(current.id),
            player_vars={"location": "start"},
            semantic_goal="blacksmith",
            context_vector=[0.0, 1.0, 0.0],
        )

    assert hint is not None
    assert hint["direction"] == "east"
    assert "hammers" in hint["hint"].lower()
    assert "east" in hint["hint"].lower()


def test_navigation_directions_only_include_accessible_targets(db_session):
    current = _add_storylet(
        db_session,
        title="Gatehouse",
        position={"x": 0, "y": 0},
        requires={"location": "start"},
    )
    _add_storylet(
        db_session,
        title="Open Courtyard",
        position={"x": 1, "y": 0},
        requires={},
    )
    _add_storylet(
        db_session,
        title="Locked Tower",
        position={"x": 0, "y": -1},
        requires={"tower_key": True},
    )

    navigator = SpatialNavigator(db_session)
    nav = navigator.get_navigation_options(
        current_storylet_id=int(current.id),
        player_vars={"location": "start", "tower_key": False},
        context_vector=[1.0, 0.0, 0.0],
    )

    assert "east" in nav["directions"]
    assert "north" not in nav["directions"]
    assert nav["available_directions"]["east"]["accessible"] is True
    assert nav["available_directions"]["north"]["accessible"] is False
