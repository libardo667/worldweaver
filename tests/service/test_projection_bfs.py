"""Tests for the non-canon projection BFS planner (Major 101)."""

import pytest

from src.models import Storylet
from src.models.schemas import ProjectionNode, ProjectionTree
from src.services.prefetch_service import (
    _expand_projection_bfs,
    _generate_risk_tags,
    _extract_seed_anchors,
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
