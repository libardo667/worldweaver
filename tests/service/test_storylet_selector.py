"""Tests for src/services/storylet_selector.py."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.models import Storylet
from src.services.prefetch_service import (
    clear_prefetch_cache,
    set_prefetched_stubs_for_session,
)
from src.services.storylet_selector import pick_storylet_enhanced


def _make_storylet(
    db,
    title: str,
    *,
    weight: float = 1.0,
    embedding=None,
    requires=None,
):
    storylet = Storylet(
        title=title,
        text_template=f"{title} text.",
        requires=requires if requires is not None else {},
        choices=[{"label": "Continue", "set": {}}],
        weight=weight,
        embedding=embedding,
    )
    db.add(storylet)
    db.commit()
    db.refresh(storylet)
    return storylet


@pytest.fixture(autouse=True)
def _reset_prefetch_cache():
    clear_prefetch_cache()
    yield
    clear_prefetch_cache()


def test_returns_none_when_no_storylets_are_eligible(db_session):
    _make_storylet(db_session, "Ineligible", requires={"needs": "x"})
    state_manager = MagicMock()
    state_manager.evaluate_condition.return_value = False
    state_manager.get_active_narrative_beats.return_value = []

    assert pick_storylet_enhanced(db_session, state_manager) is None


def test_weighted_fallback_used_without_embeddings(db_session):
    first = _make_storylet(db_session, "Weighted A", weight=1.0, embedding=None)
    second = _make_storylet(db_session, "Weighted B", weight=3.0, embedding=None)
    state_manager = MagicMock()
    state_manager.evaluate_condition.return_value = True
    state_manager.get_active_narrative_beats.return_value = []

    with patch("src.services.storylet_selector.random.choices", return_value=[second]) as mock_choices:
        chosen = pick_storylet_enhanced(db_session, state_manager)

    assert chosen is second
    args, kwargs = mock_choices.call_args
    assert args[0] == [first, second]
    assert kwargs["weights"] == [1.0, 3.0]
    assert kwargs["k"] == 1


def test_uses_semantic_selection_when_embeddings_exist(db_session):
    embedded = _make_storylet(db_session, "Embedded", embedding=[0.1, 0.2, 0.3])
    _make_storylet(db_session, "NoEmbedding", embedding=None)

    state_manager = MagicMock()
    state_manager.evaluate_condition.return_value = True
    state_manager.session_id = "semantic-session"
    state_manager.get_active_narrative_beats.return_value = []

    event = MagicMock()
    event.storylet_id = embedded.id

    with patch("src.services.world_memory.get_world_history", return_value=[event]):
        with patch(
            "src.services.semantic_selector.compute_player_context_vector",
            return_value=[0.2, 0.3, 0.4],
        ) as mock_context:
            with patch(
                "src.services.semantic_selector.score_storylets",
                return_value=[(embedded, 0.9)],
            ) as mock_score:
                with patch(
                    "src.services.semantic_selector.select_storylet",
                    return_value=embedded,
                ):
                    chosen = pick_storylet_enhanced(db_session, state_manager)

    assert chosen is embedded
    assert mock_context.call_count == 1
    score_args, _ = mock_score.call_args
    assert score_args[1] == [embedded]
    assert score_args[2] == [embedded.id]
    assert mock_score.call_args.kwargs["active_beats"] == []


def test_semantic_failure_falls_back_to_weighted_choice(db_session):
    embedded = _make_storylet(db_session, "Embedded Fallback", weight=2.0, embedding=[0.1, 0.1, 0.1])
    state_manager = MagicMock()
    state_manager.evaluate_condition.return_value = True
    state_manager.session_id = "semantic-fallback"
    state_manager.get_active_narrative_beats.return_value = []

    with patch(
        "src.services.semantic_selector.compute_player_context_vector",
        side_effect=RuntimeError("semantic broke"),
    ):
        with patch(
            "src.services.storylet_selector.random.choices",
            return_value=[embedded],
        ) as mock_choices:
            chosen = pick_storylet_enhanced(db_session, state_manager)

    assert chosen is embedded
    mock_choices.assert_called_once()


def test_prefetched_storylet_is_preferred_when_eligible(db_session, monkeypatch):
    primary = _make_storylet(db_session, "Prefetch Primary", weight=1.0, embedding=[1.0, 0.0, 0.0])
    preferred = _make_storylet(db_session, "Prefetch Preferred", weight=1.0, embedding=[0.5, 0.5, 0.0])

    state_manager = MagicMock()
    state_manager.evaluate_condition.return_value = True
    state_manager.session_id = "prefetch-priority-session"
    state_manager.get_active_narrative_beats.return_value = []
    state_manager.get_variable.return_value = "start"

    monkeypatch.setattr("src.services.storylet_selector.settings.enable_frontier_prefetch", True)
    monkeypatch.setattr("src.services.storylet_selector.settings.enable_runtime_storylet_synthesis", False)

    set_prefetched_stubs_for_session(
        "prefetch-priority-session",
        [
            {"storylet_id": int(preferred.id), "location": "start", "semantic_score": 0.9},
            {"storylet_id": int(primary.id), "location": "start", "semantic_score": 0.2},
        ],
        context_summary={"trigger": "selector-test"},
    )

    chosen = pick_storylet_enhanced(db_session, state_manager)

    assert chosen is preferred


def test_stale_prefetch_entries_fall_back_to_existing_selection(db_session, monkeypatch):
    candidate = _make_storylet(db_session, "Prefetch Fallback Candidate", weight=1.0, embedding=None)

    state_manager = MagicMock()
    state_manager.evaluate_condition.return_value = True
    state_manager.session_id = "prefetch-fallback-session"
    state_manager.get_active_narrative_beats.return_value = []
    state_manager.get_variable.return_value = "start"

    monkeypatch.setattr("src.services.storylet_selector.settings.enable_frontier_prefetch", True)
    monkeypatch.setattr("src.services.storylet_selector.settings.enable_runtime_storylet_synthesis", False)

    set_prefetched_stubs_for_session(
        "prefetch-fallback-session",
        [
            {"storylet_id": 999999, "location": "start", "semantic_score": 1.0},
        ],
        context_summary={"trigger": "selector-test"},
    )

    with patch("src.services.storylet_selector.random.choices", return_value=[candidate]) as mock_choices:
        chosen = pick_storylet_enhanced(db_session, state_manager)

    assert chosen is candidate
    mock_choices.assert_called_once()


def test_decays_active_beats_after_pick(db_session):
    embedded = _make_storylet(db_session, "Embedded Decay", weight=2.0, embedding=[0.1, 0.1, 0.1])
    state_manager = MagicMock()
    state_manager.evaluate_condition.return_value = True
    state_manager.session_id = "semantic-decay"
    state_manager.get_active_narrative_beats.return_value = [
        SimpleNamespace(name="IncreasingTension", intensity=0.5, turns_remaining=2, decay=0.65)
    ]

    with patch(
        "src.services.semantic_selector.compute_player_context_vector",
        return_value=[0.1, 0.1, 0.1],
    ):
        with patch(
            "src.services.semantic_selector.score_storylets",
            return_value=[(embedded, 0.9)],
        ):
            with patch(
                "src.services.semantic_selector.select_storylet",
                return_value=embedded,
            ):
                chosen = pick_storylet_enhanced(db_session, state_manager)

    assert chosen is embedded
    state_manager.decay_narrative_beats.assert_called_once()


def test_sparse_context_triggers_runtime_synthesis(db_session, monkeypatch):
    _make_storylet(db_session, "Sparse Base", embedding=[0.0, 1.0, 0.0], requires={})
    state_manager = MagicMock()
    state_manager.evaluate_condition.return_value = True
    state_manager.session_id = "runtime-sparse-session"
    state_manager.get_active_narrative_beats.return_value = []
    state_manager.get_variable.return_value = "start"
    state_manager.get_contextual_variables.return_value = {"location": "start"}

    monkeypatch.setattr(
        "src.services.storylet_selector.settings.enable_runtime_storylet_synthesis",
        True,
    )
    monkeypatch.setattr(
        "src.services.storylet_selector.settings.runtime_synthesis_min_eligible_storylets",
        5,
    )
    monkeypatch.setattr(
        "src.services.storylet_selector.settings.runtime_synthesis_max_per_session",
        3,
    )

    with patch("src.services.world_memory.get_world_history", return_value=[]), patch(
        "src.services.world_memory.get_recent_graph_fact_summaries",
        return_value=["The lantern district is unstable."],
    ), patch(
        "src.services.semantic_selector.compute_player_context_vector",
        return_value=[1.0, 0.0, 0.0],
    ), patch(
        "src.services.llm_service.generate_runtime_storylet_candidates",
        return_value=[
            {
                "title": "Runtime rescue",
                "text_template": "A fresh lead appears.",
                "requires": {"location": "start"},
                "choices": [{"label": "Take lead", "set": {}}],
                "weight": 1.0,
            }
        ],
    ), patch(
        "src.services.embedding_service.embed_storylet_payload",
        return_value=[1.0, 0.0, 0.0],
    ):
        chosen = pick_storylet_enhanced(db_session, state_manager)

    assert chosen is not None
    assert chosen.source == "runtime_synthesis"
    runtime_rows = (
        db_session.query(Storylet)
        .filter(Storylet.source == "runtime_synthesis")
        .all()
    )
    assert len(runtime_rows) == 0
    assert chosen.seed_event_ids == []


def test_synthesized_storylets_flow_through_semantic_scoring(db_session, monkeypatch):
    _make_storylet(db_session, "Low Match", embedding=[0.0, 1.0, 0.0], requires={})
    state_manager = MagicMock()
    state_manager.evaluate_condition.return_value = True
    state_manager.session_id = "runtime-semantic-flow"
    state_manager.get_active_narrative_beats.return_value = []
    state_manager.get_variable.return_value = "start"
    state_manager.get_contextual_variables.return_value = {"location": "start"}

    monkeypatch.setattr(
        "src.services.storylet_selector.settings.enable_runtime_storylet_synthesis",
        True,
    )
    monkeypatch.setattr(
        "src.services.storylet_selector.settings.runtime_synthesis_min_eligible_storylets",
        5,
    )

    captured_titles = []

    def _score_side_effect(context, storylets, *_args, **_kwargs):
        captured_titles.append([s.title for s in storylets])
        return [(s, 0.9 if s.source == "runtime_synthesis" else 0.1) for s in storylets]

    with patch("src.services.world_memory.get_world_history", return_value=[]), patch(
        "src.services.world_memory.get_recent_graph_fact_summaries",
        return_value=[],
    ), patch(
        "src.services.semantic_selector.compute_player_context_vector",
        return_value=[1.0, 0.0, 0.0],
    ), patch(
        "src.services.semantic_selector.score_storylets",
        side_effect=_score_side_effect,
    ), patch(
        "src.services.semantic_selector.select_storylet",
        side_effect=lambda scored: max(scored, key=lambda pair: pair[1])[0] if scored else None,
    ), patch(
        "src.services.llm_service.generate_runtime_storylet_candidates",
        return_value=[
            {
                "title": "Runtime scored",
                "text_template": "A synthesized option appears.",
                "requires": {"location": "start"},
                "choices": [{"label": "Continue", "set": {}}],
                "weight": 1.0,
            }
        ],
    ), patch(
        "src.services.embedding_service.embed_storylet_payload",
        return_value=[1.0, 0.0, 0.0],
    ):
        chosen = pick_storylet_enhanced(db_session, state_manager)

    assert chosen is not None
    assert chosen.source == "runtime_synthesis"
    assert any(
        any("runtime-" in title.lower() for title in batch)
        for batch in captured_titles
    )
