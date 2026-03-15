"""Tests for src/services/semantic_selector.py."""

import math
import random
from unittest.mock import MagicMock, patch

from src.models import NarrativeBeat, Storylet
from src.services import semantic_selector
from src.services.embedding_service import EMBEDDING_DIMENSIONS
from src.services.state_manager import AdvancedStateManager
from src.services.semantic_selector import (
    apply_narrative_beats,
    compute_player_context_vector,
    get_floor_probability,
    get_recency_penalty,
    score_storylets,
    select_storylet,
)


def _make_storylet(db, title, weight=1.0, embedding=None):
    s = Storylet(
        title=title,
        text_template="Text.",
        requires={},
        choices=[],
        weight=weight,
        embedding=embedding,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _nonzero_vector(seed: float) -> list:
    """Create a distinguishable unit-ish vector."""
    v = [0.0] * EMBEDDING_DIMENSIONS
    v[0] = seed
    v[1] = 1.0 - abs(seed)
    mag = math.sqrt(sum(x * x for x in v))
    return [x / mag for x in v] if mag else v


def _axis_vector(index: int) -> list:
    """Create a deterministic one-hot embedding vector."""
    v = [0.0] * EMBEDDING_DIMENSIONS
    v[index] = 1.0
    return v


class TestComputePlayerContextVector:

    def test_returns_correct_length(self, db_session):
        sm = MagicMock()
        sm.get_contextual_variables.return_value = {"location": "forest"}
        sm.inventory = {}
        sm.relationships = {}
        sm.session_id = "test"

        wm = MagicMock()
        wm.get_world_history.return_value = []

        result = compute_player_context_vector(sm, wm, db_session)
        assert len(result) == EMBEDDING_DIMENSIONS

    def test_includes_inventory_and_relationships(self, db_session):
        sm = MagicMock()
        sm.get_contextual_variables.return_value = {"location": "cave"}
        item = MagicMock()
        item.name = "torch"
        sm.inventory = {"torch": item}
        rel = MagicMock()
        rel.entity_b = "goblin"
        rel.get_overall_disposition.return_value = "hostile"
        sm.relationships = {"goblin": rel}
        sm.session_id = "test"

        wm = MagicMock()
        wm.get_world_history.return_value = []

        result = compute_player_context_vector(sm, wm, db_session)
        assert isinstance(result, list)

    @patch("src.services.semantic_selector.embed_text")
    def test_blends_weighted_world_context_vector(self, mock_embed, db_session):
        sm = MagicMock()
        sm.get_contextual_variables.return_value = {"location": "bridge"}
        sm.inventory = {}
        sm.relationships = {}
        sm.session_id = "test"

        wm = MagicMock()
        wm.get_world_history.return_value = []
        wm.get_world_context_vector.return_value = [1.0] * EMBEDDING_DIMENSIONS

        mock_embed.return_value = [0.0] * EMBEDDING_DIMENSIONS

        result = compute_player_context_vector(sm, wm, db_session)
        assert math.isclose(result[0], 0.3, rel_tol=1e-9)

    @patch("src.services.semantic_selector.embed_text")
    def test_goal_context_changes_scoring_bias(self, mock_embed, db_session):
        goal_a = [0.0] * EMBEDDING_DIMENSIONS
        goal_a[0] = 1.0
        goal_b = [0.0] * EMBEDDING_DIMENSIONS
        goal_b[1] = 1.0

        def _embed_side_effect(text):
            txt = str(text).lower()
            if "deliver medicine" in txt:
                return list(goal_a)
            if "find the relic" in txt:
                return list(goal_b)
            return [0.0] * EMBEDDING_DIMENSIONS

        mock_embed.side_effect = _embed_side_effect

        sm = MagicMock()
        sm.get_contextual_variables.return_value = {"location": "crossroads"}
        sm.inventory = {}
        sm.relationships = {}
        sm.session_id = "goal-bias"

        wm = MagicMock()
        wm.get_world_history.return_value = []
        wm.get_world_context_vector.return_value = None
        wm.get_recent_graph_fact_summaries.return_value = []

        a_storylet = _make_storylet(db_session, "Goal A", embedding=goal_a)
        b_storylet = _make_storylet(db_session, "Goal B", embedding=goal_b)

        sm.get_goal_lens_payload.return_value = {"primary_goal": "deliver medicine"}
        context_a = compute_player_context_vector(sm, wm, db_session)
        scores_a = {s.title: sc for s, sc in score_storylets(context_a, [a_storylet, b_storylet])}

        sm.get_goal_lens_payload.return_value = {"primary_goal": "find the relic"}
        context_b = compute_player_context_vector(sm, wm, db_session)
        scores_b = {s.title: sc for s, sc in score_storylets(context_b, [a_storylet, b_storylet])}

        assert scores_a["Goal A"] > scores_a["Goal B"]
        assert scores_b["Goal B"] > scores_b["Goal A"]

    @patch("src.services.semantic_selector.embed_text")
    def test_goal_context_included_after_primary_goal_backfill(self, mock_embed, db_session):
        seen_prompts = []

        def _capture_embed(text):
            seen_prompts.append(str(text))
            return [0.0] * EMBEDDING_DIMENSIONS

        mock_embed.side_effect = _capture_embed

        sm = AdvancedStateManager("goal-backfill-context")
        sm.set_variable("player_role", "rift courier")
        sm.set_world_bible(
            {
                "central_tension": "A fractured citadel is collapsing under rival claims.",
            }
        )
        sm.advance_story_arc()  # turn_count -> 1
        backfill = sm.backfill_primary_goal_if_empty_after_initial_turn()
        assert backfill["applied"] is True

        wm = MagicMock()
        wm.get_world_history.return_value = []
        wm.get_world_context_vector.return_value = None
        wm.get_recent_graph_fact_summaries.return_value = []

        compute_player_context_vector(sm, wm, db_session)

        joined = " ".join(seen_prompts)
        assert "Goal:" in joined
        assert "rift courier" in joined.lower()


class TestScoreStorylets:

    def test_all_get_floor_minimum(self, db_session):
        """With fallback zero vectors, all scores should be at least FLOOR_PROBABILITY."""
        vec = [0.0] * EMBEDDING_DIMENSIONS
        s1 = _make_storylet(db_session, "A", embedding=vec)
        s2 = _make_storylet(db_session, "B", embedding=vec)

        context = list(vec)
        scored = score_storylets(context, [s1, s2])
        floor_prob = get_floor_probability()
        for _, score in scored:
            assert score >= floor_prob

    def test_recency_penalty(self, db_session):
        vec = _nonzero_vector(0.5)
        s = _make_storylet(db_session, "Recent", embedding=vec)

        context = _nonzero_vector(0.5)
        scored_normal = score_storylets(context, [s], recent_storylet_ids=[])
        scored_recent = score_storylets(context, [s], recent_storylet_ids=[s.id])

        normal_score = scored_normal[0][1]
        recent_score = scored_recent[0][1]
        assert recent_score < normal_score
        assert math.isclose(
            recent_score,
            normal_score * (1.0 - get_recency_penalty()),
            rel_tol=1e-9,
        )

    def test_weight_multiplier(self, db_session):
        vec = _nonzero_vector(0.8)
        s_low = _make_storylet(db_session, "Low", weight=0.5, embedding=vec)
        s_high = _make_storylet(db_session, "High", weight=2.0, embedding=vec)

        context = _nonzero_vector(0.8)
        scored = score_storylets(context, [s_low, s_high])
        scores = {s.title: sc for s, sc in scored}
        assert scores["High"] > scores["Low"]

    def test_skips_storylets_without_embedding(self, db_session):
        s_with = _make_storylet(db_session, "With", embedding=[0.1] * EMBEDDING_DIMENSIONS)
        s_without = _make_storylet(db_session, "Without", embedding=None)

        scored = score_storylets([0.1] * EMBEDDING_DIMENSIONS, [s_with, s_without])
        titles = [s.title for s, _ in scored]
        assert "With" in titles
        assert "Without" not in titles

    @patch("src.services.semantic_selector.cosine_similarity")
    def test_high_similarity_scores_higher(self, mock_sim, db_session):
        vec = [0.1] * EMBEDDING_DIMENSIONS
        s_close = _make_storylet(db_session, "Close", embedding=vec)
        s_far = _make_storylet(db_session, "Far", embedding=vec)

        mock_sim.side_effect = lambda a, b: 0.9 if b is s_close.embedding else 0.1

        # Need to re-read embeddings since mock replaces similarity
        scored = score_storylets(vec, [s_close, s_far])
        scores = {s.title: sc for s, sc in scored}
        assert scores["Close"] > scores["Far"]

    def test_uses_configured_floor_and_penalty(self, db_session, monkeypatch):
        vec = [0.0] * EMBEDDING_DIMENSIONS
        s = _make_storylet(db_session, "Configurable", embedding=vec)

        monkeypatch.setattr(
            semantic_selector.settings,
            "llm_semantic_floor_probability",
            0.25,
        )
        monkeypatch.setattr(
            semantic_selector.settings,
            "llm_recency_penalty",
            0.8,
        )

        normal = score_storylets(vec, [s], recent_storylet_ids=[])[0][1]
        recent = score_storylets(vec, [s], recent_storylet_ids=[s.id])[0][1]

        assert math.isclose(normal, 0.25, rel_tol=1e-6)
        assert math.isclose(recent, 0.05, rel_tol=1e-6)

    def test_dark_action_beat_increases_dark_storylet_score(self, db_session):
        dark_vec = [0.0] * EMBEDDING_DIMENSIONS
        dark_vec[0] = 1.0
        light_vec = [0.0] * EMBEDDING_DIMENSIONS
        light_vec[1] = 1.0
        dark = _make_storylet(db_session, "Dark", embedding=dark_vec)
        light = _make_storylet(db_session, "Light", embedding=light_vec)

        context = [0.0] * EMBEDDING_DIMENSIONS
        beat = NarrativeBeat(
            name="IncreasingTension",
            intensity=1.0,
            turns_remaining=3,
            decay=0.65,
            vector=dark_vec,
        )
        scores = {
            s.title: score
            for s, score in score_storylets(
                context,
                [dark, light],
                active_beats=[beat],
            )
        }
        assert scores["Dark"] > scores["Light"]

    def test_multiple_beats_are_blended_as_weighted_sum(self):
        base = [0.0] * EMBEDDING_DIMENSIONS
        first = [0.0] * EMBEDDING_DIMENSIONS
        first[0] = 1.0
        second = [0.0] * EMBEDDING_DIMENSIONS
        second[1] = 1.0
        beats = [
            NarrativeBeat(name="IncreasingTension", intensity=0.6, turns_remaining=3, vector=first),
            NarrativeBeat(name="Catharsis", intensity=0.25, turns_remaining=2, vector=second),
        ]

        warped = apply_narrative_beats(base, beats)
        assert math.isclose(warped[0], 0.6, rel_tol=1e-9)
        assert math.isclose(warped[1], 0.25, rel_tol=1e-9)

    def test_high_semantic_relevance_can_outweigh_farther_distance(self, db_session):
        close_embedding = [0.0] * EMBEDDING_DIMENSIONS
        close_embedding[1] = 1.0
        pulled_embedding = [0.0] * EMBEDDING_DIMENSIONS
        pulled_embedding[0] = 1.0

        close_storylet = _make_storylet(db_session, "Close But Off Theme", embedding=close_embedding)
        pulled_storylet = _make_storylet(db_session, "Pulled Neighbor", embedding=pulled_embedding)
        context = [0.0] * EMBEDDING_DIMENSIONS
        context[0] = 1.0

        scores = {
            s.title: score
            for s, score in score_storylets(
                context,
                [close_storylet, pulled_storylet],
                player_position={"x": 0, "y": 0},
                storylet_positions={
                    int(close_storylet.id): {"x": 0, "y": -1},
                    int(pulled_storylet.id): {"x": 0, "y": -2},
                },
            )
        }
        assert scores["Pulled Neighbor"] > scores["Close But Off Theme"]

    def test_score_ordering_with_fixed_embeddings_is_deterministic(self, db_session):
        context = _axis_vector(0)
        exact = _make_storylet(db_session, "Exact Match", weight=1.0, embedding=_axis_vector(0))
        orthogonal = _make_storylet(db_session, "Orthogonal", weight=1.0, embedding=_axis_vector(1))
        weighted = _make_storylet(db_session, "Weighted Match", weight=1.5, embedding=_axis_vector(0))

        breakdown = []
        scored = score_storylets(
            context,
            [exact, orthogonal, weighted],
            score_breakdown=breakdown,
        )
        ranked_titles = [s.title for s, _ in sorted(scored, key=lambda item: item[1], reverse=True)]
        assert ranked_titles == ["Weighted Match", "Exact Match", "Orthogonal"], f"Unexpected ranking order: {ranked_titles}"
        assert len(breakdown) == 3

    def test_zero_vectors_respect_floor_with_debug_breakdown(self, db_session):
        zero = [0.0] * EMBEDDING_DIMENSIONS
        storylet = _make_storylet(db_session, "Zero Candidate", weight=1.0, embedding=zero)

        breakdown = []
        scored = score_storylets(
            zero,
            [storylet],
            score_breakdown=breakdown,
        )
        floor_prob = get_floor_probability()
        assert math.isclose(scored[0][1], floor_prob, rel_tol=1e-9)
        assert math.isclose(
            breakdown[0]["floored_similarity"],
            floor_prob,
            rel_tol=1e-9,
        )

    def test_debug_breakdown_does_not_change_scores(self, db_session):
        vec = _axis_vector(0)
        candidate = _make_storylet(db_session, "Debug Candidate", weight=1.25, embedding=vec)

        plain = score_storylets(vec, [candidate])[0][1]
        breakdown = []
        debug_score = score_storylets(vec, [candidate], score_breakdown=breakdown)[0][1]
        assert math.isclose(plain, debug_score, rel_tol=1e-9)
        assert breakdown and breakdown[0]["title"] == "Debug Candidate"


class TestSelectStorylet:

    def test_returns_storylet(self, db_session):
        s = _make_storylet(db_session, "Only", embedding=[0.0] * EMBEDDING_DIMENSIONS)
        result = select_storylet([(s, 1.0)])
        assert result is s

    def test_returns_none_when_empty(self):
        assert select_storylet([]) is None

    def test_returns_from_candidates(self, db_session):
        s1 = _make_storylet(db_session, "A1", embedding=[0.0] * EMBEDDING_DIMENSIONS)
        s2 = _make_storylet(db_session, "B1", embedding=[0.0] * EMBEDDING_DIMENSIONS)
        result = select_storylet([(s1, 0.5), (s2, 0.5)])
        assert result in (s1, s2)

    def test_weighted_selection_is_stable_with_seeded_rng(self, db_session):
        s1 = _make_storylet(db_session, "Heavy", embedding=[0.0] * EMBEDDING_DIMENSIONS)
        s2 = _make_storylet(db_session, "Light", embedding=[0.0] * EMBEDDING_DIMENSIONS)

        rng_a = random.Random(20260302)
        rng_b = random.Random(20260302)
        picks_a = [select_storylet([(s1, 9.0), (s2, 1.0)], rng=rng_a).title for _ in range(12)]
        picks_b = [select_storylet([(s1, 9.0), (s2, 1.0)], rng=rng_b).title for _ in range(12)]
        assert picks_a == picks_b, "Seeded RNG should produce a stable weighted-pick sequence."
        assert picks_a.count("Heavy") > picks_a.count("Light")
