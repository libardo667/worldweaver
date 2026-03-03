"""Tests for src/services/command_interpreter.py."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.services.command_interpreter import (
    ActionResult,
    _build_action_prompt,
    _fallback_result,
    interpret_action,
    interpret_action_intent,
    render_validated_action_narration,
)


class TestActionResult:

    def test_defaults(self):
        result = ActionResult(narrative_text="Hello")
        assert result.narrative_text == "Hello"
        assert result.state_deltas == {}
        assert result.should_trigger_storylet is False
        assert result.follow_up_choices == []
        assert result.suggested_beats == []
        assert result.plausible is True
        assert result.reasoning_metadata == {}

    def test_custom_values(self):
        result = ActionResult(
            narrative_text="You burned the bridge.",
            state_deltas={"bridge": "burned"},
            should_trigger_storylet=True,
            follow_up_choices=[{"label": "Cross", "set": {}}],
            suggested_beats=[{"name": "IncreasingTension"}],
            plausible=False,
            reasoning_metadata={"rationale": "test"},
        )
        assert result.state_deltas == {"bridge": "burned"}
        assert result.should_trigger_storylet is True
        assert result.suggested_beats[0]["name"] == "IncreasingTension"
        assert result.plausible is False
        assert result.reasoning_metadata["rationale"] == "test"


class TestFallbackResult:

    def test_includes_action(self):
        result = _fallback_result("look around")
        assert "look around" in result.narrative_text

    def test_has_choices(self):
        result = _fallback_result("open door")
        assert len(result.follow_up_choices) == 2

    def test_is_plausible(self):
        result = _fallback_result("anything")
        assert result.plausible is True

    def test_empty_state_deltas(self):
        result = _fallback_result("test")
        assert result.state_deltas == {}

    def test_can_carry_suggested_beats(self):
        result = _fallback_result(
            "burn bridge",
            suggested_beats=[{"name": "IncreasingTension"}],
        )
        assert result.suggested_beats == [{"name": "IncreasingTension"}]


class TestBuildActionPrompt:

    def test_includes_location(self):
        prompt = _build_action_prompt(
            "look around",
            {"variables": {"location": "forest"}, "inventory": {}},
            "A dark forest path.",
            [],
        )
        assert "forest" in prompt
        assert "look around" in prompt

    def test_includes_scene(self):
        prompt = _build_action_prompt(
            "test",
            {"variables": {}, "inventory": {}},
            "The merchant's stall",
            [],
        )
        assert "merchant" in prompt.lower()

    def test_includes_recent_events(self):
        prompt = _build_action_prompt(
            "test",
            {"variables": {}, "inventory": {}},
            None,
            ["Bridge was burned", "Key found"],
        )
        assert "Bridge was burned" in prompt

    def test_prompt_mentions_following_beat_contract(self):
        prompt = _build_action_prompt(
            "burn bridge",
            {"variables": {}, "inventory": {}},
            None,
            [],
        )
        assert "following_beat" in prompt
        assert "IncreasingTension" in prompt

    def test_prompt_includes_goal_arc_context(self):
        prompt = _build_action_prompt(
            "advance mission",
            {"variables": {}, "inventory": {}},
            None,
            [],
            goal_context="Primary goal: Recover the sigil",
        )
        assert "Goal arc context" in prompt
        assert "Recover the sigil" in prompt


class _FakeCompletions:
    def __init__(self, payload: dict):
        self.payload = payload
        self.last_create_kwargs = None

    def create(self, **kwargs):
        self.last_create_kwargs = kwargs
        content = json.dumps(self.payload)
        message = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeClient:
    def __init__(self, payload: dict):
        self.completions = _FakeCompletions(payload)
        self.chat = SimpleNamespace(completions=self.completions)


class TestInterpretAction:

    def test_fallback_under_test_env(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {"variables": {}, "inventory": {}}
        state_manager.session_id = "test"
        world_memory = MagicMock()

        result = interpret_action("look around", state_manager, world_memory, None, db_session)
        assert isinstance(result, ActionResult)
        assert "look around" in result.narrative_text
        assert result.plausible is True

    def test_injects_relevant_world_facts_into_prompt(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {
            "variables": {"location": "bridge"},
            "inventory": {},
        }
        state_manager.session_id = "facts-session"

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = [SimpleNamespace(summary="A storm hit")]
        world_memory.get_relevant_action_facts.return_value = [
            "The old bridge is already damaged.",
            "locations.bridge.status=blocked",
        ]

        fake_client = _FakeClient(
            {
                "narrative": "You inspect the bridge supports.",
                "state_changes": {},
                "choices": [{"label": "Continue", "set": {}}],
                "plausible": True,
            }
        )

        with (
            patch("src.services.command_interpreter._is_ai_disabled", return_value=False),
            patch("src.services.command_interpreter.get_llm_client", return_value=fake_client),
            patch("src.services.command_interpreter.get_model", return_value="test-model"),
        ):
            interpret_action("inspect bridge", state_manager, world_memory, None, db_session)

        prompt = fake_client.completions.last_create_kwargs["messages"][1]["content"]
        assert "Known world facts" in prompt
        assert "already damaged" in prompt

    def test_relevant_fact_lookup_uses_session_scope(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {
            "variables": {"location": "bridge"},
            "inventory": {},
        }
        state_manager.session_id = "scope-session"

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = []
        world_memory.get_relevant_action_facts.return_value = []

        with patch("src.services.command_interpreter._is_ai_disabled", return_value=True):
            interpret_action(
                "inspect bridge",
                state_manager,
                world_memory,
                None,
                db_session,
            )

        world_memory.get_relevant_action_facts.assert_called_once()
        kwargs = world_memory.get_relevant_action_facts.call_args.kwargs
        assert kwargs["session_id"] == "scope-session"
        assert kwargs["action"] == "inspect bridge"
        assert kwargs["location"] == "bridge"

    def test_prompt_fact_context_is_bounded(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {
            "variables": {"location": "bridge"},
            "inventory": {},
        }
        state_manager.session_id = "facts-limit-session"

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = []
        world_memory.get_relevant_action_facts.return_value = [
            f"fact-{idx} " + ("x" * 420)
            for idx in range(12)
        ]

        fake_client = _FakeClient(
            {
                "narrative": "You inspect the area.",
                "state_changes": {},
                "choices": [{"label": "Continue", "set": {}}],
                "plausible": True,
            }
        )

        with (
            patch("src.services.command_interpreter._is_ai_disabled", return_value=False),
            patch("src.services.command_interpreter.get_llm_client", return_value=fake_client),
            patch("src.services.command_interpreter.get_model", return_value="test-model"),
        ):
            interpret_action("inspect bridge", state_manager, world_memory, None, db_session)

        prompt = fake_client.completions.last_create_kwargs["messages"][1]["content"]
        assert "fact-0" in prompt
        assert "fact-3" in prompt
        assert "fact-4" not in prompt
        assert ("x" * 250) not in prompt

    def test_sanitizes_malformed_output_and_blocks_unknown_keys(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {
            "variables": {"gold": 2, "location": "town"},
            "inventory": {},
        }
        state_manager.session_id = "sanitize-session"

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = []
        world_memory.get_relevant_action_facts.return_value = []

        fake_client = _FakeClient(
            {
                "narrative": "You haggle successfully.",
                "state_changes": {
                    "variables": {"good_key": 1, "bad key": 2},
                    "environment": {"danger_level": "9", "weather": "stormy"},
                    "set": {"favor": "3"},
                    "increment": {"gold": "3"},
                    "append_fact": [
                        {
                            "subject": "merchant",
                            "predicate": "opinion",
                            "value": "impressed",
                        }
                    ],
                },
                "choices": "not-a-list",
                "plausible": True,
            }
        )

        with (
            patch("src.services.command_interpreter._is_ai_disabled", return_value=False),
            patch("src.services.command_interpreter.get_llm_client", return_value=fake_client),
            patch("src.services.command_interpreter.get_model", return_value="test-model"),
        ):
            result = interpret_action("barter hard", state_manager, world_memory, None, db_session)

        assert result.state_deltas["good_key"] == 1
        assert "bad key" not in result.state_deltas
        assert result.state_deltas["gold"] == 5
        assert result.state_deltas["environment"]["danger_level"] == 9
        assert result.follow_up_choices[0]["label"] == "Continue"
        assert "bad key" in result.reasoning_metadata["rejected_keys"]

    def test_returns_contradiction_refusal_for_conflicting_action(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {
            "variables": {"location": "bridge"},
            "inventory": {},
        }
        state_manager.session_id = "contradiction-session"

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = []
        world_memory.get_relevant_action_facts.return_value = [
            "The bridge is already destroyed."
        ]

        with patch("src.services.command_interpreter._is_ai_disabled", return_value=True):
            result = interpret_action(
                "I destroy the bridge",
                state_manager,
                world_memory,
                None,
                db_session,
            )

        assert result.plausible is False
        assert result.state_deltas == {}
        assert "already destroyed" in result.narrative_text.lower()
        assert result.reasoning_metadata.get("contradiction")

    def test_destructive_action_fallback_suggests_tension_beat(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {
            "variables": {"location": "bridge"},
            "inventory": {},
        }
        state_manager.session_id = "beat-fallback-session"

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = []
        world_memory.get_relevant_action_facts.return_value = []

        with patch("src.services.command_interpreter._is_ai_disabled", return_value=True):
            result = interpret_action(
                "I burn the bridge",
                state_manager,
                world_memory,
                None,
                db_session,
            )

        assert result.suggested_beats
        assert result.suggested_beats[0]["name"] == "IncreasingTension"

    def test_llm_following_beat_is_sanitized(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {
            "variables": {"location": "market"},
            "inventory": {},
        }
        state_manager.session_id = "beat-llm-session"

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = []
        world_memory.get_relevant_action_facts.return_value = []

        fake_client = _FakeClient(
            {
                "narrative": "Tension rises in the square.",
                "state_changes": {},
                "choices": [{"label": "Continue", "set": {}}],
                "plausible": True,
                "following_beat": {
                    "name": "IncreasingTension",
                    "intensity": 0.4,
                    "turns": 2,
                    "decay": 0.5,
                },
            }
        )

        with (
            patch("src.services.command_interpreter._is_ai_disabled", return_value=False),
            patch("src.services.command_interpreter.get_llm_client", return_value=fake_client),
            patch("src.services.command_interpreter.get_model", return_value="test-model"),
        ):
            result = interpret_action("I threaten the guard", state_manager, world_memory, None, db_session)

        assert result.suggested_beats == [
            {
                "name": "IncreasingTension",
                "intensity": 0.4,
                "turns_remaining": 2,
                "decay": 0.5,
                "source": "llm",
            }
        ]

    def test_goal_update_heuristic_added_for_progress_actions(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {
            "variables": {"location": "market"},
            "inventory": {},
            "goal": {
                "primary_goal": "Deliver medicine",
                "subgoals": [],
                "urgency": 0.6,
                "complication": 0.1,
            },
        }
        state_manager.session_id = "goal-heuristic-session"

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = []
        world_memory.get_relevant_action_facts.return_value = []

        with patch("src.services.command_interpreter._is_ai_disabled", return_value=True):
            result = interpret_action(
                "I deliver the medicine to the clinic",
                state_manager,
                world_memory,
                None,
                db_session,
            )

        goal_update = result.reasoning_metadata.get("goal_update")
        assert isinstance(goal_update, dict)
        assert goal_update["status"] in {"progressed", "completed"}

    def test_llm_goal_update_is_sanitized(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {
            "variables": {"location": "market"},
            "inventory": {},
            "goal": {
                "primary_goal": "Recover the sigil",
                "subgoals": [],
                "urgency": 0.4,
                "complication": 0.2,
            },
        }
        state_manager.session_id = "goal-llm-session"

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = []
        world_memory.get_relevant_action_facts.return_value = []

        fake_client = _FakeClient(
            {
                "narrative": "You find a new lead.",
                "state_changes": {},
                "choices": [{"label": "Continue", "set": {}}],
                "plausible": True,
                "goal_update": {
                    "status": "branched",
                    "milestone": "New contact offers an alternate route",
                    "subgoal": "Meet the smuggler",
                    "urgency_delta": 0.2,
                    "complication_delta": 0.3,
                },
            }
        )

        with (
            patch("src.services.command_interpreter._is_ai_disabled", return_value=False),
            patch("src.services.command_interpreter.get_llm_client", return_value=fake_client),
            patch("src.services.command_interpreter.get_model", return_value="test-model"),
        ):
            result = interpret_action("I follow the new lead", state_manager, world_memory, None, db_session)

        goal_update = result.reasoning_metadata.get("goal_update")
        assert goal_update["status"] == "branched"
        assert goal_update["subgoal"] == "Meet the smuggler"


class TestStagedActionPipeline:

    def test_interpret_action_intent_returns_validated_delta_contract(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {
            "variables": {"location": "market", "gold": 3},
            "inventory": {},
        }
        state_manager.session_id = "staged-intent-session"

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = [SimpleNamespace(summary="The market is restless.")]
        world_memory.get_relevant_action_facts.return_value = ["The market guards watch for smugglers."]

        fake_client = _FakeClient(
            {
                "ack_line": "You test the vendor's resolve.",
                "plausible": True,
                "delta": {
                    "set": [{"key": "vendor_trust", "value": "warming"}],
                    "increment": [{"key": "gold", "amount": -1}],
                    "append_fact": [
                        {
                            "subject": "vendor",
                            "predicate": "attitude",
                            "value": "warming",
                        }
                    ],
                },
                "following_beat": {
                    "name": "ThematicResonance",
                    "intensity": 0.3,
                    "turns": 2,
                    "decay": 0.6,
                },
            }
        )

        with (
            patch("src.services.command_interpreter._is_ai_disabled", return_value=False),
            patch("src.services.command_interpreter.get_llm_client", return_value=fake_client),
            patch("src.services.command_interpreter.get_model", return_value="test-model"),
        ):
            staged = interpret_action_intent(
                action="I bargain with the vendor",
                state_manager=state_manager,
                world_memory_module=world_memory,
                current_storylet=None,
                db=db_session,
            )

        assert staged is not None
        assert staged.ack_line.startswith("You test")
        assert staged.result.state_deltas["vendor_trust"] == "warming"
        assert staged.result.state_deltas["gold"] == 2
        assert staged.result.reasoning_metadata["staged_pipeline"] == "intent"
        assert staged.result.reasoning_metadata["appended_facts"][0]["subject"] == "vendor"

    def test_render_validated_action_narration_uses_validated_state_only(self, db_session):
        state_manager = MagicMock()
        state_manager.get_state_summary.return_value = {
            "variables": {"location": "bridge"},
            "inventory": {},
        }
        state_manager.session_id = "staged-narration-session"

        world_memory = MagicMock()
        world_memory.get_world_history.return_value = [SimpleNamespace(summary="Rain lashes the old span.")]
        world_memory.get_relevant_action_facts.return_value = ["The bridge is brittle."]

        validated = ActionResult(
            narrative_text="You brace at the bridge rail.",
            state_deltas={"bridge_stability": "fragile"},
            should_trigger_storylet=False,
            follow_up_choices=[{"label": "Continue", "set": {}}],
            plausible=True,
            reasoning_metadata={"validation_warnings": []},
        )
        fake_client = _FakeClient(
            {
                "narrative": "You press your weight carefully and hear timber groan.",
                "choices": [{"label": "Retreat", "set": {}}, {"label": "Step forward", "set": {}}],
                "state_changes": {"ignored": True},
            }
        )

        with (
            patch("src.services.command_interpreter._is_ai_disabled", return_value=False),
            patch("src.services.command_interpreter.get_llm_client", return_value=fake_client),
            patch("src.services.command_interpreter.get_model", return_value="test-model"),
        ):
            narrated = render_validated_action_narration(
                action="I test the bridge",
                ack_line="You commit to crossing.",
                validated_result=validated,
                state_manager=state_manager,
                world_memory_module=world_memory,
                current_storylet=None,
                db=db_session,
            )

        assert narrated.state_deltas == {"bridge_stability": "fragile"}
        assert narrated.follow_up_choices[0]["label"] == "Retreat"
        assert narrated.reasoning_metadata["staged_pipeline"] == "narrate"

        prompt = fake_client.completions.last_create_kwargs["messages"][1]["content"]
        prompt_payload = json.loads(prompt)
        assert prompt_payload["validated_state_changes"] == {"bridge_stability": "fragile"}
