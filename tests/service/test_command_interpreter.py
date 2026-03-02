"""Tests for src/services/command_interpreter.py."""

from unittest.mock import MagicMock

from src.services.command_interpreter import (
    ActionResult,
    _build_action_prompt,
    _fallback_result,
    interpret_action,
)


class TestActionResult:

    def test_defaults(self):
        r = ActionResult(narrative_text="Hello")
        assert r.narrative_text == "Hello"
        assert r.state_deltas == {}
        assert r.should_trigger_storylet is False
        assert r.follow_up_choices == []
        assert r.plausible is True

    def test_custom_values(self):
        r = ActionResult(
            narrative_text="You burned the bridge.",
            state_deltas={"bridge": "burned"},
            should_trigger_storylet=True,
            follow_up_choices=[{"label": "Cross", "set": {}}],
            plausible=False,
        )
        assert r.state_deltas == {"bridge": "burned"}
        assert r.should_trigger_storylet is True
        assert r.plausible is False


class TestFallbackResult:

    def test_includes_action(self):
        r = _fallback_result("look around")
        assert "look around" in r.narrative_text

    def test_has_choices(self):
        r = _fallback_result("open door")
        assert len(r.follow_up_choices) == 2

    def test_is_plausible(self):
        r = _fallback_result("anything")
        assert r.plausible is True

    def test_empty_state_deltas(self):
        r = _fallback_result("test")
        assert r.state_deltas == {}


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
            "test", {"variables": {}, "inventory": {}},
            "The merchant's stall", [],
        )
        assert "merchant" in prompt.lower()

    def test_includes_recent_events(self):
        prompt = _build_action_prompt(
            "test", {"variables": {}, "inventory": {}},
            None, ["Bridge was burned", "Key found"],
        )
        assert "Bridge was burned" in prompt


class TestInterpretAction:

    def test_fallback_under_test_env(self, db_session):
        sm = MagicMock()
        sm.get_state_summary.return_value = {"variables": {}, "inventory": {}}
        sm.session_id = "test"
        wm = MagicMock()

        result = interpret_action("look around", sm, wm, None, db_session)
        assert isinstance(result, ActionResult)
        assert "look around" in result.narrative_text
        assert result.plausible is True
