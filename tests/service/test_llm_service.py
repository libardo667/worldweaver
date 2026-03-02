"""Tests for src/services/llm_service.py — no live API key needed."""

import os
from unittest.mock import MagicMock, patch

from src.services.llm_service import (
    _FALLBACK_STORYLETS,
    build_feedback_aware_prompt,
    generate_starting_storylet,
    extract_feedback_requirements,
    generate_contextual_storylets,
    generate_world_storylets,
    llm_suggest_storylets,
)


class TestFallbackBehavior:

    def test_fallback_under_pytest(self):
        """PYTEST_CURRENT_TEST is set by pytest, so fallback should trigger."""
        result = llm_suggest_storylets(2, ["exploration"], {})
        assert isinstance(result, list)
        assert len(result) >= 1
        assert result[0]["title"] == _FALLBACK_STORYLETS[0]["title"]

    def test_fallback_with_disable_ai(self):
        with patch.dict(os.environ, {"DW_DISABLE_AI": "1"}):
            result = llm_suggest_storylets(3, ["test"], {})
        assert len(result) >= 1

    def test_fallback_n_clamped_to_available(self):
        result = llm_suggest_storylets(100, ["test"], {})
        assert len(result) == len(_FALLBACK_STORYLETS)

    def test_generate_contextual_storylets_returns_list(self):
        result = generate_contextual_storylets({"location": "forest", "danger": 0})
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_generate_world_storylets_fallback(self):
        result = generate_world_storylets("A fantasy realm", "fantasy")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "title" in result[0]


class TestBuildFeedbackAwarePrompt:

    def test_base_prompt_always_present(self):
        prompt = build_feedback_aware_prompt({})
        assert "master storyteller" in prompt
        assert "STRICT FORMAT REQUIREMENTS" in prompt

    def test_urgent_need_included(self):
        bible = {"urgent_need": "Need more combat storylets"}
        prompt = build_feedback_aware_prompt(bible)
        assert "CRITICAL PRIORITY" in prompt
        assert "Need more combat storylets" in prompt

    def test_optimization_need_included(self):
        bible = {"optimization_need": "Use gold variable"}
        prompt = build_feedback_aware_prompt(bible)
        assert "OPTIMIZATION FOCUS" in prompt

    def test_location_need_included(self):
        bible = {"location_need": "Add path to cave"}
        prompt = build_feedback_aware_prompt(bible)
        assert "LOCATION CONNECTIVITY" in prompt

    def test_world_state_analysis_included(self):
        bible = {
            "world_state_analysis": {
                "total_content": 20,
                "connectivity_health": 0.75,
                "story_flow_issues": ["missing keys"],
            }
        }
        prompt = build_feedback_aware_prompt(bible)
        assert "CURRENT STORY STATE" in prompt
        assert "20" in prompt

    def test_improvement_priorities_included(self):
        bible = {
            "improvement_priorities": [
                {"suggestion": "Add key acquisition storylets"},
                {"suggestion": "Balance danger levels"},
            ]
        }
        prompt = build_feedback_aware_prompt(bible)
        assert "TOP IMPROVEMENT PRIORITIES" in prompt
        assert "Add key acquisition" in prompt

    def test_successful_patterns_included(self):
        bible = {"successful_patterns": ["Good location flow"]}
        prompt = build_feedback_aware_prompt(bible)
        assert "MAINTAIN THESE SUCCESSFUL PATTERNS" in prompt
        assert "Good location flow" in prompt


class TestExtractFeedbackRequirements:

    def test_empty_bible_returns_empty(self):
        assert extract_feedback_requirements({}) == {}

    def test_required_choice_example(self):
        bible = {"required_choice_example": {"label": "Pick up key", "set": {"has_key": True}}}
        result = extract_feedback_requirements(bible)
        assert "must_include_choice_type" in result

    def test_required_requirement_example(self):
        bible = {"required_requirement_example": {"gold": {"gte": 10}}}
        result = extract_feedback_requirements(bible)
        assert "must_include_requirement_type" in result

    def test_connectivity_focus(self):
        bible = {"connectivity_focus": "gap_filling"}
        result = extract_feedback_requirements(bible)
        assert result["primary_focus"] == "gap_filling"

    def test_variable_ecosystem(self):
        bible = {
            "variable_ecosystem": {
                "needs_sources": ["has_key"],
                "needs_usage": ["gold"],
                "well_connected": ["location"],
            }
        }
        result = extract_feedback_requirements(bible)
        assert "variable_priorities" in result
        assert result["variable_priorities"]["create_sources_for"] == ["has_key"]


def _mock_llm_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


class _RateLimitError(Exception):
    status_code = 429


class TestLLMResilience:

    def test_timeout_retries_then_fallback(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = TimeoutError("timed out")

        with patch("src.services.llm_service.is_ai_disabled", return_value=False), patch(
            "src.services.llm_service.get_llm_client", return_value=client
        ), patch("src.services.llm_service.time.sleep", return_value=None):
            result = llm_suggest_storylets(2, ["theme"], {})

        assert len(result) == 2
        assert result[0]["title"] == _FALLBACK_STORYLETS[0]["title"]
        assert client.chat.completions.create.call_count == 3

    def test_rate_limit_retries_then_fallback(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = _RateLimitError("429")

        with patch("src.services.llm_service.is_ai_disabled", return_value=False), patch(
            "src.services.llm_service.get_llm_client", return_value=client
        ), patch("src.services.llm_service.time.sleep", return_value=None):
            result = llm_suggest_storylets(2, ["theme"], {})

        assert len(result) == 2
        assert client.chat.completions.create.call_count == 3

    def test_malformed_world_json_falls_back(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_llm_response("not json")

        with patch("src.services.llm_service.is_ai_disabled", return_value=False), patch(
            "src.services.llm_service.get_llm_client", return_value=client
        ):
            result = generate_world_storylets("A world", "fantasy", count=3)

        assert isinstance(result, list)
        assert result[0]["title"] == "A New Beginning"

    def test_markdown_wrapped_json_object_parses(self):
        class _WorldDescription:
            description = "A city of glass towers"
            theme = "science fantasy"
            player_role = "scout"
            tone = "mysterious"

        content = """```json
        {
          "title": "Glass Dawn",
          "text": "You step into mirrored alleys as a {player_role}.",
          "choices": [{"label": "Begin", "set": {"location": "atrium", "player_role": "scout"}}]
        }
        ```"""
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_llm_response(content)

        with patch("src.services.llm_service.is_ai_disabled", return_value=False), patch(
            "src.services.llm_service.get_llm_client", return_value=client
        ), patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}):
            result = generate_starting_storylet(
                _WorldDescription(), ["atrium"], ["mystery"]
            )

        assert result["title"] == "Glass Dawn"
