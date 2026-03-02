"""Tests for src/services/llm_service.py — no live API key needed."""

import os
from unittest.mock import patch

from src.services.llm_service import (
    _FALLBACK_STORYLETS,
    build_feedback_aware_prompt,
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
