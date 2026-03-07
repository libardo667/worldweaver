"""Domain isolation tests for GoalDomain (Minor 106)."""

from src.services.state.goals import GoalDomain
from tests.helpers.state_assertions import assert_goal_parity


class TestGoalDomainBasics:
    def test_set_primary_goal(self):
        domain = GoalDomain()
        result = domain.set_goal_state(primary_goal="Find the artifact")
        assert result["primary_goal"] == "Find the artifact"

    def test_set_primary_goal_records_milestone(self):
        domain = GoalDomain()
        domain.set_goal_state(primary_goal="Find the artifact")
        assert len(domain.state.milestones) == 1
        assert domain.state.milestones[0].status == "branched"

    def test_urgency_clamped_at_one(self):
        domain = GoalDomain()
        domain.set_goal_state(urgency=5.0)
        assert domain.state.urgency == 1.0

    def test_complication_clamped_at_zero(self):
        domain = GoalDomain()
        domain.set_goal_state(complication=-0.5)
        assert domain.state.complication == 0.0

    def test_add_subgoal(self):
        domain = GoalDomain()
        domain.add_subgoal("Gather supplies")
        assert "Gather supplies" in domain.state.subgoals

    def test_add_subgoal_no_duplicates(self):
        domain = GoalDomain()
        domain.add_subgoal("Gather supplies")
        domain.add_subgoal("Gather supplies")
        assert domain.state.subgoals.count("Gather supplies") == 1

    def test_mark_milestone_updates_signals(self):
        domain = GoalDomain()
        domain.mark_milestone(
            "Clue discovered",
            status="progressed",
            urgency_delta=0.1,
            complication_delta=0.05,
        )
        assert abs(domain.state.urgency - 0.1) < 1e-6
        assert abs(domain.state.complication - 0.05) < 1e-6

    def test_backfill_noop_when_goal_present(self):
        domain = GoalDomain()
        domain.set_goal_state(primary_goal="Existing goal")
        variables = {"_story_arc": {"turn_count": 5}}
        result = domain.backfill_primary_goal_if_empty(variables=variables)
        assert result["applied"] is False
        assert result["reason"] == "primary_goal_present"

    def test_backfill_noop_below_turn_threshold(self):
        domain = GoalDomain()
        variables = {"_story_arc": {"turn_count": 0}}
        result = domain.backfill_primary_goal_if_empty(variables=variables, minimum_turn_count=2)
        assert result["applied"] is False
        assert result["reason"] == "below_turn_threshold"

    def test_backfill_applies_fallback_goal(self):
        domain = GoalDomain()
        variables = {
            "_story_arc": {"turn_count": 2},
            "player_role": "ranger",
            "world_theme": "dark forest",
        }
        result = domain.backfill_primary_goal_if_empty(variables=variables, minimum_turn_count=1)
        assert result["applied"] is True
        assert "ranger" in result["primary_goal"]

    def test_to_dict_from_dict_roundtrip(self):
        domain = GoalDomain()
        domain.set_goal_state(primary_goal="Find relic", urgency=0.4, complication=0.2)
        domain.add_subgoal("Talk to locals")
        data = domain.to_dict()
        restored = GoalDomain.from_dict(data)
        assert restored.state.primary_goal == "Find relic"
        assert abs(restored.state.urgency - 0.4) < 1e-6
        assert "Talk to locals" in restored.state.subgoals

    def test_assert_goal_parity_helper(self):
        domain = GoalDomain()
        domain.set_goal_state(primary_goal="Escape the dungeon", urgency=0.3)
        assert_goal_parity(
            domain,
            {"primary_goal": "Escape the dungeon", "urgency": 0.3},
        )

    def test_get_lens_payload_structure(self):
        domain = GoalDomain()
        domain.set_goal_state(primary_goal="Find relic", urgency=0.5)
        payload = domain.get_lens_payload()
        assert "primary_goal" in payload
        assert "urgency" in payload
        assert "recent_milestones" in payload

    def test_get_arc_timeline_newest_first(self):
        domain = GoalDomain()
        domain.mark_milestone("First", status="progressed")
        domain.mark_milestone("Second", status="complicated")
        timeline = domain.get_arc_timeline(limit=10)
        assert timeline[0]["title"] == "Second"
        assert timeline[1]["title"] == "First"

    def test_get_embedding_context_empty_when_no_goal(self):
        domain = GoalDomain()
        assert domain.get_embedding_context() == ""

    def test_milestones_capped_at_fifty(self):
        domain = GoalDomain()
        for i in range(55):
            domain.mark_milestone(f"Event {i}")
        assert len(domain.state.milestones) <= 50
