"""Tests for semantic constellation debug endpoint."""

import pytest

from src.models import Storylet, WorldEvent
from src.services.embedding_service import EMBEDDING_DIMENSIONS


def _vec(*values: float) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for idx, value in enumerate(values):
        if idx >= EMBEDDING_DIMENSIONS:
            break
        vector[idx] = float(value)
    return vector


def test_constellation_endpoint_disabled_by_default(client):
    response = client.get("/api/semantic/constellation/constellation-disabled")
    assert response.status_code == 404


def test_constellation_endpoint_returns_scored_storylets_without_embeddings(
    client,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("src.api.semantic.settings.enable_constellation", True)

    db_session.add_all(
        [
            Storylet(
                title="constellation-start",
                text_template="A starting point.",
                requires={"location": "start"},
                choices=[{"label": "Wait", "set": {}}],
                weight=1.0,
                position={"x": 0, "y": 0},
                embedding=_vec(1.0, 0.0, 0.0),
            ),
            Storylet(
                title="constellation-north",
                text_template="A road heads north.",
                requires={},
                choices=[{"label": "Move", "set": {}}],
                weight=1.0,
                position={"x": 0, "y": -1},
                embedding=_vec(0.9, 0.1, 0.0),
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/semantic/constellation/constellation-shape?top_n=2")
    assert response.status_code == 200
    payload = response.json()

    assert payload["session_id"] == "constellation-shape"
    assert payload["top_n"] == 2
    assert payload["count"] == 2
    assert "location" in payload["context"]
    assert "vars" in payload["context"]

    first = payload["storylets"][0]
    for key in ("id", "title", "position", "score", "edges"):
        assert key in first
    assert "embedding" not in first
    assert "spatial_neighbors" in first["edges"]
    assert "semantic_neighbors" in first["edges"]


def test_constellation_endpoint_applies_floor_and_recency_penalty(
    client,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr("src.api.semantic.settings.enable_constellation", True)
    monkeypatch.setattr(
        "src.services.semantic_selector.settings.llm_semantic_floor_probability",
        0.2,
    )
    monkeypatch.setattr(
        "src.services.semantic_selector.settings.llm_recency_penalty",
        0.5,
    )
    monkeypatch.setattr(
        "src.services.constellation_service.compute_player_context_vector",
        lambda *_args, **_kwargs: _vec(1.0, 0.0, 0.0),
    )

    recent_storylet = Storylet(
        title="constellation-recent",
        text_template="Recently seen.",
        requires={},
        choices=[{"label": "Continue", "set": {}}],
        weight=1.0,
        embedding=_vec(-1.0, 0.0, 0.0),
    )
    baseline_storylet = Storylet(
        title="constellation-baseline",
        text_template="Not recently seen.",
        requires={},
        choices=[{"label": "Continue", "set": {}}],
        weight=1.0,
        embedding=_vec(-1.0, 0.0, 0.0),
    )
    db_session.add_all([recent_storylet, baseline_storylet])
    db_session.commit()
    db_session.refresh(recent_storylet)

    db_session.add(
        WorldEvent(
            session_id="constellation-score",
            storylet_id=recent_storylet.id,
            event_type="storylet_fired",
            summary="Recent semantic candidate fired",
            world_state_delta={},
        )
    )
    db_session.commit()

    response = client.get(
        "/api/semantic/constellation/constellation-score?top_n=2&include_edges=false"
    )
    assert response.status_code == 200
    payload = response.json()
    by_title = {item["title"]: item for item in payload["storylets"]}

    assert by_title["constellation-baseline"]["score"] == pytest.approx(0.2, rel=1e-6)
    assert by_title["constellation-recent"]["score"] == pytest.approx(0.1, rel=1e-6)
