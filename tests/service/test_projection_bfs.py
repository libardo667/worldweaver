"""Tests for the non-canon projection BFS planner (Major 101)."""

import pytest

from src.models import Storylet
from src.models.schemas import ProjectionNode, ProjectionTree
from src.services.prefetch_service import (
    _compute_projection_pressure,
    _expand_projection_bfs,
    _generate_risk_tags,
    _extract_seed_anchors,
    _pressure_tier,
    _should_prune_bfs_node,
    clear_prefetch_cache,
    refresh_frontier_for_session,
)
from src.services.session_service import get_state_manager, save_state
from src.services.state_manager import AdvancedStateManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_storylet(db, title, *, requires=None, choices=None, embedding=None, position=None):
    storylet = Storylet(
        title=title,
        text_template=f"{title} text.",
        requires=requires if requires is not None else {},
        choices=choices if choices is not None else [{"label": "Continue", "set": {}}],
        weight=1.0,
        embedding=embedding,
        position=position,
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


# ---------------------------------------------------------------------------
# Step 1: Schema + State Fork
# ---------------------------------------------------------------------------


class TestProjectionSchemas:
    def test_projection_node_validates(self):
        node = ProjectionNode(
            node_id="d0-s1",
            depth=0,
            storylet_id=1,
            title="Test",
        )
        assert node.non_canon is True
        assert node.confidence == 1.0
        assert node.allowed is True

    def test_projection_tree_validates(self):
        tree = ProjectionTree(
            session_id="test",
            root_location="start",
            nodes=[
                ProjectionNode(node_id="d0-s1", depth=0, storylet_id=1, title="A"),
            ],
            max_depth_reached=0,
            total_nodes=1,
            generated_at="2026-01-01T00:00:00",
        )
        assert tree.total_nodes == 1
        assert tree.referee_scored is False

    def test_projection_tree_round_trip(self):
        tree = ProjectionTree(
            session_id="rt",
            root_location="start",
            nodes=[
                ProjectionNode(node_id="d0-s1", depth=0, title="X"),
                ProjectionNode(
                    node_id="d1-s2-c0",
                    depth=1,
                    title="Y",
                    parent_node_id="d0-s1",
                    parent_choice_index=0,
                    parent_choice_label="Go",
                    stakes_delta={"danger": 3},
                    risk_tags=["danger_increase"],
                ),
            ],
            max_depth_reached=1,
            total_nodes=2,
            generated_at="2026-01-01T00:00:00",
        )
        data = tree.model_dump()
        restored = ProjectionTree.model_validate(data)
        assert len(restored.nodes) == 2
        assert restored.nodes[1].parent_node_id == "d0-s1"


class TestForkForProjection:
    def test_fork_isolates_state(self):
        sm = AdvancedStateManager("test-fork")
        sm.set_variable("location", "start")
        sm.set_variable("danger", 1)

        fork = sm.fork_for_projection()
        fork.set_variable("location", "cave")
        fork.set_variable("danger", 5)

        # Original unchanged
        assert sm.get_variable("location") == "start"
        assert sm.get_variable("danger") == 1
        # Fork has new values
        assert fork.get_variable("location") == "cave"
        assert fork.get_variable("danger") == 5

    def test_fork_guards_flag(self):
        sm = AdvancedStateManager("test-flag")
        fork = sm.fork_for_projection()
        assert getattr(fork, "_is_projection_fork", False) is True
        assert not getattr(sm, "_is_projection_fork", False)

    def test_fork_shares_inventory_reference(self):
        sm = AdvancedStateManager("test-inv")
        fork = sm.fork_for_projection()
        assert fork.inventory is sm.inventory


# ---------------------------------------------------------------------------
# Step 2: BFS Expansion
# ---------------------------------------------------------------------------


class TestBFSExpansion:
    def test_bfs_expands_to_depth_1(self, db_session):
        """Storylet B requires has_key=True; storylet A's choice sets it."""
        a = _make_storylet(
            db_session,
            "Gate",
            requires={},
            choices=[{"label": "Use key", "set": {"has_key": True}}],
        )
        b = _make_storylet(
            db_session,
            "Treasure Room",
            requires={"has_key": True},
            choices=[{"label": "Take gold", "set": {"gold": 1}}],
        )

        sm = AdvancedStateManager("bfs-d1")
        sm.set_variable("location", "start")

        tree = _expand_projection_bfs(
            sm,
            [a],
            [a, b],
            max_depth=2,
            max_nodes=50,
            time_budget_seconds=5.0,
            session_id="bfs-d1",
            root_location="start",
        )

        assert tree["total_nodes"] >= 2
        # Find the depth-1 node that is Treasure Room
        depth_1_nodes = [n for n in tree["nodes"] if n["depth"] == 1]
        titles_at_depth_1 = [n["title"] for n in depth_1_nodes]
        assert "Treasure Room" in titles_at_depth_1

    def test_bfs_respects_max_nodes_budget(self, db_session):
        storylets = []
        for i in range(10):
            storylets.append(
                _make_storylet(
                    db_session,
                    f"Story-{i}",
                    requires={},
                    choices=[{"label": "Go", "set": {"step": i}}],
                )
            )

        sm = AdvancedStateManager("bfs-nodes")
        tree = _expand_projection_bfs(
            sm,
            storylets[:5],
            storylets,
            max_depth=3,
            max_nodes=3,
            time_budget_seconds=5.0,
        )

        assert tree["total_nodes"] <= 3

    def test_bfs_respects_max_depth_budget(self, db_session):
        a = _make_storylet(
            db_session,
            "Start",
            requires={},
            choices=[{"label": "Go", "set": {"step": 1}}],
        )
        b = _make_storylet(
            db_session,
            "Mid",
            requires={"step": 1},
            choices=[{"label": "Go", "set": {"step": 2}}],
        )
        c = _make_storylet(
            db_session,
            "Far",
            requires={"step": 2},
            choices=[{"label": "Done", "set": {}}],
        )

        sm = AdvancedStateManager("bfs-depth")
        tree = _expand_projection_bfs(
            sm,
            [a],
            [a, b, c],
            max_depth=1,
            max_nodes=50,
            time_budget_seconds=5.0,
        )

        depths = [n["depth"] for n in tree["nodes"]]
        assert max(depths) <= 1

    def test_bfs_respects_time_budget(self, db_session):
        storylets = []
        for i in range(5):
            storylets.append(
                _make_storylet(
                    db_session,
                    f"Time-{i}",
                    requires={},
                    choices=[{"label": "Go", "set": {f"k{i}": True}}],
                )
            )

        sm = AdvancedStateManager("bfs-time")

        # Set time budget to essentially 0
        tree = _expand_projection_bfs(
            sm,
            storylets,
            storylets,
            max_depth=3,
            max_nodes=100,
            time_budget_seconds=0.0,
        )

        assert tree["budget_exhausted"] is True

    def test_projection_does_not_mutate_canonical_state(self, db_session):
        a = _make_storylet(
            db_session,
            "Mutate-Test",
            requires={},
            choices=[{"label": "Change", "set": {"changed": True, "location": "elsewhere"}}],
        )

        sm = AdvancedStateManager("bfs-safe")
        sm.set_variable("location", "start")
        sm.set_variable("changed", False)

        _expand_projection_bfs(
            sm,
            [a],
            [a],
            max_depth=2,
            max_nodes=50,
            time_budget_seconds=5.0,
        )

        assert sm.get_variable("location") == "start"
        assert sm.get_variable("changed") is False


# ---------------------------------------------------------------------------
# Step 2b: Risk tags and seed anchors
# ---------------------------------------------------------------------------


class TestRiskTagsAndAnchors:
    def test_risk_tags_from_danger_key(self):
        tags = _generate_risk_tags({"danger_level": 5})
        assert "danger_increase" in tags

    def test_risk_tags_from_location_key(self):
        tags = _generate_risk_tags({"location": "cave"})
        assert "location_change" in tags

    def test_risk_tags_empty_for_unrelated(self):
        tags = _generate_risk_tags({"gold": 10})
        assert tags == []

    def test_seed_anchors_from_title(self):
        anchors = _extract_seed_anchors("The Forgotten Temple of Shadows")
        assert "forgotten" in anchors
        assert "temple" in anchors


# ---------------------------------------------------------------------------
# Step 3: Referee scoring fallback
# ---------------------------------------------------------------------------


class TestRefereeScoring:
    def test_deterministic_fallback_when_ai_disabled(self):
        from src.services.llm_service import score_projection_nodes

        nodes = [
            {"node_id": "d0-s1", "title": "A", "semantic_score": 0.9},
            {"node_id": "d1-s2-c0", "title": "B", "semantic_score": None},
        ]
        scored = score_projection_nodes(nodes, {"location": "start"})
        assert scored[0]["confidence"] == round(0.9 * 0.8 + 0.2, 4)
        assert scored[1]["confidence"] == 0.6
        assert scored[0]["allowed"] is True
        assert scored[1]["allowed"] is True

    def test_score_projection_nodes_return_meta_flag(self):
        from src.services.llm_service import score_projection_nodes

        nodes = [{"node_id": "d0-s1", "title": "A", "semantic_score": 0.5}]
        scored, referee_scored = score_projection_nodes(
            nodes,
            {"location": "start"},
            return_meta=True,
        )
        assert isinstance(scored, list)
        assert referee_scored is False
        assert scored[0]["confidence"] == 0.6

    def test_bfs_marks_referee_scored_when_scores_apply(self, db_session, monkeypatch):
        def _fake_score_projection_nodes(nodes, world_context, **kwargs):
            for node in nodes:
                node["confidence"] = 0.77
                node["allowed"] = True
            if kwargs.get("return_meta"):
                return nodes, True
            return nodes

        monkeypatch.setattr(
            "src.services.llm_service.score_projection_nodes",
            _fake_score_projection_nodes,
        )

        a = _make_storylet(
            db_session,
            "Referee-A",
            requires={},
            choices=[{"label": "Open", "set": {"opened": True}}],
        )
        b = _make_storylet(
            db_session,
            "Referee-B",
            requires={"opened": True},
            choices=[{"label": "Proceed", "set": {}}],
        )

        sm = AdvancedStateManager("referee-scored")
        sm.set_variable("location", "start")
        tree = _expand_projection_bfs(
            sm,
            [a],
            [a, b],
            max_depth=2,
            max_nodes=50,
            time_budget_seconds=5.0,
            session_id="referee-scored",
            root_location="start",
        )
        assert tree["referee_scored"] is True
        assert all(node["confidence"] == 0.77 for node in tree["nodes"])


# ---------------------------------------------------------------------------
# Step 4: Integration with prefetch pipeline
# ---------------------------------------------------------------------------


class TestPrefetchIntegration:
    def test_prefetch_includes_projection_tree(self, db_session, monkeypatch):
        monkeypatch.setattr("src.services.prefetch_service.settings.enable_frontier_prefetch", True)
        monkeypatch.setattr("src.services.prefetch_service.settings.enable_v3_projection_expansion", True)
        monkeypatch.setattr("src.services.prefetch_service.settings.v3_projection_max_depth", 2)
        monkeypatch.setattr("src.services.prefetch_service.settings.v3_projection_max_nodes", 20)
        monkeypatch.setattr("src.services.prefetch_service.settings.v3_projection_time_budget_ms", 5000)
        monkeypatch.setattr("src.services.prefetch_service.settings.prefetch_max_per_session", 10)
        monkeypatch.setattr("src.services.prefetch_service.settings.prefetch_ttl_seconds", 60)

        _make_storylet(
            db_session,
            "proj-int-a",
            requires={},
            choices=[{"label": "Open", "set": {"opened": True}}],
        )
        _make_storylet(
            db_session,
            "proj-int-b",
            requires={"opened": True},
            choices=[{"label": "Enter", "set": {}}],
        )

        sm = get_state_manager("proj-int", db_session)
        sm.set_variable("location", "start")
        save_state(sm, db_session)

        result = refresh_frontier_for_session("proj-int", trigger="test", db=db_session)
        assert result is not None

        # The projection tree should be present and non-canon.
        projection_tree = result.get("projection_tree")
        assert isinstance(projection_tree, dict)
        assert int(projection_tree.get("total_nodes", 0)) >= 1
        assert all(bool(node.get("non_canon", False)) for node in projection_tree.get("nodes", []))

        # Context summary should expose BFS metadata for diagnostics.
        ctx = result.get("context_summary", {})
        assert ctx.get("projection_tree_node_count", 0) >= 1


# ---------------------------------------------------------------------------
# Step 5: Adaptive pruning + pressure scoring (Major 107 + Minor 109)
# ---------------------------------------------------------------------------


class TestPressureScoring:
    def test_zero_pressure_at_start(self):
        p = _compute_projection_pressure(
            elapsed_seconds=0.0,
            time_budget_seconds=5.0,
            node_count=0,
            max_nodes=50,
        )
        assert p == 0.0

    def test_full_time_consumption_gives_high_pressure(self):
        p = _compute_projection_pressure(
            elapsed_seconds=5.0,
            time_budget_seconds=5.0,
            node_count=0,
            max_nodes=50,
        )
        assert p >= 1.0

    def test_node_cap_gives_high_pressure(self):
        p = _compute_projection_pressure(
            elapsed_seconds=0.0,
            time_budget_seconds=5.0,
            node_count=50,
            max_nodes=50,
        )
        assert p >= 1.0

    def test_queue_depth_adds_minor_signal(self):
        p_no_queue = _compute_projection_pressure(elapsed_seconds=0.0, time_budget_seconds=5.0, node_count=0, max_nodes=50, queue_depth=0)
        p_with_queue = _compute_projection_pressure(elapsed_seconds=0.0, time_budget_seconds=5.0, node_count=0, max_nodes=50, queue_depth=50)
        assert p_with_queue > p_no_queue
        assert p_with_queue <= 0.11  # minor signal only

    def test_pressure_clamped_at_one(self):
        p = _compute_projection_pressure(
            elapsed_seconds=100.0,
            time_budget_seconds=1.0,
            node_count=1000,
            max_nodes=10,
        )
        assert p == 1.0


class TestPressureTier:
    def test_tier_full_below_prune_threshold(self):
        assert _pressure_tier(0.3, prune_threshold=0.6, stubs_only_threshold=0.85) == "full"

    def test_tier_trimmed_between_thresholds(self):
        assert _pressure_tier(0.7, prune_threshold=0.6, stubs_only_threshold=0.85) == "trimmed"

    def test_tier_stubs_only_at_top(self):
        assert _pressure_tier(0.9, prune_threshold=0.6, stubs_only_threshold=0.85) == "stubs_only"

    def test_tier_at_exact_prune_boundary(self):
        assert _pressure_tier(0.6, prune_threshold=0.6, stubs_only_threshold=0.85) == "trimmed"

    def test_tier_at_exact_stubs_only_boundary(self):
        assert _pressure_tier(0.85, prune_threshold=0.6, stubs_only_threshold=0.85) == "stubs_only"


class TestShouldPruneBfsNode:
    def test_full_tier_never_prunes(self):
        pruned, _ = _should_prune_bfs_node(depth=2, semantic_score=None, tier="full")
        assert not pruned

    def test_depth_zero_never_pruned(self):
        pruned, _ = _should_prune_bfs_node(depth=0, semantic_score=None, tier="trimmed")
        assert not pruned

    def test_trimmed_prunes_no_semantic_signal(self):
        pruned, reason = _should_prune_bfs_node(depth=1, semantic_score=None, tier="trimmed")
        assert pruned
        assert reason == "no_semantic_signal"

    def test_trimmed_prunes_low_semantic_score(self):
        pruned, reason = _should_prune_bfs_node(depth=1, semantic_score=0.1, tier="trimmed")
        assert pruned
        assert reason == "low_semantic_score"

    def test_trimmed_keeps_good_semantic_score(self):
        pruned, _ = _should_prune_bfs_node(depth=1, semantic_score=0.7, tier="trimmed")
        assert not pruned


class TestAdaptivePruningBFS:
    def test_bfs_emits_pressure_tier_full_by_default(self, db_session):
        a = _make_storylet(db_session, "AP-A", requires={}, choices=[{"label": "Go", "set": {"x": 1}}])
        b = _make_storylet(db_session, "AP-B", requires={"x": 1})
        sm = AdvancedStateManager("ap-full")
        tree = _expand_projection_bfs(sm, [a], [a, b], max_depth=2, max_nodes=50, time_budget_seconds=5.0)
        assert tree["pressure_tier"] == "full"
        assert tree["nodes_pruned"] == 0
        assert isinstance(tree["prune_reason_distribution"], dict)

    def test_bfs_emits_budget_exhaustion_cause_node_cap(self, db_session):
        storylets = [_make_storylet(db_session, f"EC-{i}", requires={}, choices=[{"label": "Go", "set": {f"k{i}": True}}]) for i in range(5)]
        sm = AdvancedStateManager("ec-nodecap")
        tree = _expand_projection_bfs(sm, storylets[:3], storylets, max_depth=3, max_nodes=2, time_budget_seconds=5.0)
        assert tree["budget_exhausted"] is True
        assert tree["budget_exhaustion_cause"] == "node_cap"

    def test_bfs_emits_budget_exhaustion_cause_time_cap(self, db_session):
        storylets = [_make_storylet(db_session, f"TC-{i}", requires={}) for i in range(3)]
        sm = AdvancedStateManager("ec-timecap")
        tree = _expand_projection_bfs(sm, storylets, storylets, max_depth=3, max_nodes=100, time_budget_seconds=0.0)
        assert tree["budget_exhausted"] is True
        assert tree["budget_exhaustion_cause"] in ("disabled_time_budget", "time_cap")

    def test_adaptive_pruning_prunes_no_signal_nodes(self, db_session):
        """With trimmed pressure and no semantic scores, depth>0 nodes are pruned."""
        a = _make_storylet(db_session, "Prune-A", requires={}, choices=[{"label": "Go", "set": {"step": 1}}])
        b = _make_storylet(db_session, "Prune-B", requires={"step": 1})
        sm = AdvancedStateManager("ap-prune")
        # Force trimmed tier by setting very tight node budget (50% of 2 = 1.0 node_pressure → prune)
        # Use semantic_scores=None so all depth>0 nodes lack signal
        tree = _expand_projection_bfs(
            sm,
            [a],
            [a, b],
            max_depth=2,
            max_nodes=100,
            time_budget_seconds=5.0,
            adaptive_pruning=True,
            prune_threshold=0.0,  # everything above 0% pressure triggers trimmed
            stubs_only_threshold=1.0,  # never stubs_only
        )
        # With prune_threshold=0, tier is always trimmed; depth>0 nodes with no signal are pruned
        assert tree["nodes_pruned"] >= 1
        assert "no_semantic_signal" in tree["prune_reason_distribution"]

    def test_stubs_only_tier_skips_bfs_loop(self, db_session):
        """stubs_only_threshold=0.0 → all pressure ≥ threshold → BFS skipped immediately."""
        a = _make_storylet(db_session, "SO-A", requires={}, choices=[{"label": "Go", "set": {"x": 1}}])
        b = _make_storylet(db_session, "SO-B", requires={"x": 1})
        sm = AdvancedStateManager("ap-stubsonly")
        tree = _expand_projection_bfs(
            sm,
            [a],
            [a, b],
            max_depth=2,
            max_nodes=100,
            time_budget_seconds=5.0,
            adaptive_pruning=True,
            prune_threshold=0.0,
            stubs_only_threshold=0.0,  # stubs_only from the start
        )
        assert tree["pressure_tier"] == "stubs_only"
        assert tree["budget_exhaustion_cause"] == "stubs_only_tier"
        # Depth-0 nodes still seeded; no BFS children added
        depth_1_plus = [n for n in tree["nodes"] if n["depth"] > 0]
        assert depth_1_plus == []
