"""Tests for src/services/command_interpreter.py."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.services.command_interpreter import (
    ActionResult,
    _build_action_prompt,
    _fallback_result,
    interpret_action,
)


class TestActionResult:

    def test_defaults(self):
        result = ActionResult(narrative_text="Hello")
        assert result.narrative_text == "Hello"
        assert result.state_deltas == {}
        assert result.should_trigger_storylet is False
        assert result.follow_up_choices == []
        assert result.plausible is True
        assert result.reasoning_metadata == {}

    def test_custom_values(self):
        result = ActionResult(
            narrative_text="You burned the bridge.",
            state_deltas={"bridge": "burned"},
            should_trigger_storylet=True,
            follow_up_choices=[{"label": "Cross", "set": {}}],
            plausible=False,
            reasoning_metadata={"rationale": "test"},
        )
        assert result.state_deltas == {"bridge": "burned"}
        assert result.should_trigger_storylet is True
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
