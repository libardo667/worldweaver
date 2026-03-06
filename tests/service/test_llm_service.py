"""Tests for src/services/llm_service.py — no live API key needed."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from src.models import Storylet
from src.services.llm_service import (
    _FALLBACK_STORYLETS,
    _chat_completion_with_retry,
    adapt_storylet_to_context,
    build_feedback_aware_prompt,
    generate_runtime_storylet_candidates,
    generate_starting_storylet,
    extract_feedback_requirements,
    generate_contextual_storylets,
    generate_world_storylets,
    llm_suggest_storylets,
    validate_runtime_storylet_candidates,
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

    def test_generate_contextual_storylets_includes_onboarding_theme_and_character(self):
        with patch(
            "src.services.llm_service.llm_suggest_storylets",
            return_value=[{"title": "seed"}],
        ) as mock_suggest:
            result = generate_contextual_storylets(
                {
                    "location": "start",
                    "danger": 0,
                    "world_theme": "Occult City Noir",
                    "player_role": "Exiled Cartographer",
                },
                n=2,
            )

        assert result == [{"title": "seed"}]
        _, themes, bible = mock_suggest.call_args.args
        assert "occult_city_noir" in themes
        assert "exiled_cartographer" in themes
        assert bible["player_setup"]["world_theme"] == "Occult City Noir"
        assert bible["player_setup"]["character_profile"] == "Exiled Cartographer"

    def test_generate_world_storylets_fallback(self):
        result = generate_world_storylets("A fantasy realm", "fantasy")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert "title" in result[0]

    def test_adapt_storylet_uses_recent_events_and_environment(self):
        storylet = Storylet(
            title="Adapt Test",
            text_template="You stand in the square.",
            requires={},
            choices=[{"label": "Wait", "set": {}}],
            weight=1.0,
        )
        context = {
            "variables": {"location": "square"},
            "environment": {"weather": "stormy", "danger_level": 7},
            "recent_events": ["Player action: I cheated the merchant."],
        }
        adapted = adapt_storylet_to_context(storylet, context)

        assert "cheated the merchant" in adapted["text"].lower()
        assert "stormy" in adapted["text"].lower()
        assert "danger" in adapted["text"].lower() or "tension" in adapted["text"].lower()

    def test_adapt_storylet_rewrites_choice_label_with_context(self):
        storylet = Storylet(
            title="Merchant Adapt",
            text_template="The merchant blocks your path.",
            requires={},
            choices=[{"label": "Attack the merchant", "set": {"danger": 1}}],
            weight=1.0,
        )
        context = {
            "variables": {"location": "market"},
            "environment": {"weather": "clear", "danger_level": 1},
            "recent_events": ["Player action: I cheated the merchant."],
        }
        adapted = adapt_storylet_to_context(storylet, context)

        assert "just cheated" in adapted["choices"][0]["label"].lower()

    def test_runtime_adaptation_flag_off_returns_base_render(self):
        storylet = Storylet(
            title="No Runtime Adapt",
            text_template="Hello {name}.",
            requires={},
            choices=[{"label": "Continue", "set": {}}],
            weight=1.0,
        )
        context = {
            "variables": {"name": "Ari"},
            "environment": {"weather": "stormy", "danger_level": 8},
            "recent_events": ["Player action: something loud happened."],
        }
        with patch("src.services.llm_service.settings.enable_runtime_adaptation", False):
            adapted = adapt_storylet_to_context(storylet, context)

        assert adapted["text"] == "Hello Ari."
        assert adapted["choices"][0]["label"] == "Continue"

    def test_adapt_storylet_runs_motif_audit_and_single_revise_pass(self):
        storylet = Storylet(
            title="Motif Audit",
            text_template="Neon rain spills over the alley.",
            requires={},
            choices=[{"label": "Continue", "set": {}}],
            weight=1.0,
        )
        context = {
            "variables": {"location": "alley"},
            "environment": {"weather": "rainy", "danger_level": 5},
            "recent_events": ["You chased a signal through the gutters."],
            "scene_card_now": {
                "location": "rust_gutters",
                "cast_on_stage": ["Kora-7"],
                "immediate_stakes": "Signal loss is imminent.",
                "constraints_or_affordances": ["Weather hazard: acid rain"],
            },
            "motifs_recent": ["neon", "rain", "copper"],
            "sensory_palette": {
                "smell": "Burnt ozone and wet concrete",
                "sound": "Drainage pipes clattering overhead",
            },
        }
        operations: list[str] = []

        def _fake_chat_completion(_client, **kwargs):
            operations.append(str(kwargs.get("metric_operation")))
            operation = str(kwargs.get("metric_operation"))
            if operation == "adapt_storylet_to_context":
                return _mock_llm_response(
                    json.dumps(
                        {
                            "text": "Neon rain and copper rain flood the alley again.",
                            "choice_labels": ["Push deeper"],
                        }
                    )
                )
            if operation == "adapt_storylet_motif_audit":
                return _mock_llm_response(
                    json.dumps(
                        {
                            "decision": "revise",
                            "overused_motifs": ["neon", "rain"],
                            "replacement_anchors": ["ozone haze", "pipe chatter"],
                            "rationale": "Motifs are over-repeated.",
                        }
                    )
                )
            if operation == "adapt_storylet_motif_revise":
                return _mock_llm_response(
                    json.dumps(
                        {
                            "text": "Ozone haze rolls through the alley while pipe chatter marks the narrowing window.",
                        }
                    )
                )
            raise AssertionError(f"unexpected operation: {operation}")

        with (
            patch("src.services.llm_service.is_ai_disabled", return_value=False),
            patch("src.services.llm_service.get_llm_client", return_value=object()),
            patch("src.services.llm_service._chat_completion_with_retry", side_effect=_fake_chat_completion),
            patch("src.services.llm_service.get_narrator_model", return_value="nar-model"),
            patch("src.services.llm_service.get_referee_model", return_value="ref-model"),
            patch("src.services.llm_service.settings.enable_motif_referee_audit", True),
            patch("src.services.llm_service.settings.motif_referee_revise_budget", 1),
        ):
            adapted = adapt_storylet_to_context(storylet, context)

        assert adapted["text"].startswith("Ozone haze")
        assert adapted["choices"][0]["label"] == "Push deeper"
        assert adapted["motif_governance"]["motif_referee_decision"] == "revised"
        assert operations == [
            "adapt_storylet_to_context",
            "adapt_storylet_motif_audit",
            "adapt_storylet_motif_revise",
        ]


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


class TestRuntimeSynthesisValidation:

    def test_validate_runtime_storylet_candidates_normalizes_payload(self):
        payload = {
            "storylets": [
                {
                    "title": "Runtime lead",
                    "text_template": "A new lead emerges.",
                    "requires": {"location": "start"},
                    "choices": [{"text": "Follow it", "set_vars": {"clue": 1}}],
                    "weight": "1.2",
                }
            ]
        }

        validated = validate_runtime_storylet_candidates(payload, max_candidates=3)
        assert len(validated) == 1
        assert validated[0]["choices"] == [{"label": "Follow it", "set": {"clue": 1}}]
        assert validated[0]["weight"] == 1.2

    def test_validate_runtime_storylet_candidates_rejects_invalid_schema(self):
        with pytest.raises(ValueError):
            validate_runtime_storylet_candidates({"storylets": [{"title": ""}]})

    def test_generate_runtime_storylet_candidates_fallback_uses_context(self):
        with patch("src.services.llm_service.is_ai_disabled", return_value=True):
            generated = generate_runtime_storylet_candidates(
                {"location": "dock"},
                ["The dock crane is damaged."],
                "find spare parts",
                n=2,
            )

        assert len(generated) == 2
        assert all(item["requires"]["location"] == "dock" for item in generated)


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

        with patch("src.services.llm_service.is_ai_disabled", return_value=False), patch("src.services.llm_service.get_llm_client", return_value=client), patch("src.services.llm_service.time.sleep", return_value=None), patch("src.services.llm_service.settings.llm_retries", 2):
            result = llm_suggest_storylets(2, ["theme"], {})

        assert len(result) == 2
        assert result[0]["title"] == _FALLBACK_STORYLETS[0]["title"]
        assert client.chat.completions.create.call_count == 3

    def test_rate_limit_retries_then_fallback(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = _RateLimitError("429")

        with patch("src.services.llm_service.is_ai_disabled", return_value=False), patch("src.services.llm_service.get_llm_client", return_value=client), patch("src.services.llm_service.time.sleep", return_value=None), patch("src.services.llm_service.settings.llm_retries", 2):
            result = llm_suggest_storylets(2, ["theme"], {})

        assert len(result) == 2
        assert client.chat.completions.create.call_count == 3

    def test_malformed_world_json_falls_back(self):
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_llm_response("not json")

        with patch("src.services.llm_service.is_ai_disabled", return_value=False), patch("src.services.llm_service.get_llm_client", return_value=client):
            result = generate_world_storylets("A world", "fantasy", count=3)

        assert isinstance(result, list)
        assert result[0]["title"] == "A New Beginning"

    def test_malformed_world_json_logs_machine_readable_category(self, caplog):
        client = MagicMock()
        client.chat.completions.create.return_value = _mock_llm_response("not json")

        caplog.set_level("WARNING")
        with patch("src.services.llm_service.is_ai_disabled", return_value=False), patch("src.services.llm_service.get_llm_client", return_value=client):
            generate_world_storylets("A world", "fantasy", count=3)

        assert any("category=json_decode_failed" in rec.message for rec in caplog.records)

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

        with patch("src.services.llm_service.is_ai_disabled", return_value=False), patch("src.services.llm_service.get_llm_client", return_value=client), patch.dict(os.environ, {"PYTEST_CURRENT_TEST": ""}):
            result = generate_starting_storylet(_WorldDescription(), ["atrium"], ["mystery"])

        assert result["title"] == "Glass Dawn"

    def test_chat_completion_metrics_capture_token_usage(self, caplog):
        response = MagicMock()
        response.usage = {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
        }
        response.choices = [MagicMock(message=MagicMock(content='{"ok": true}'))]

        client = MagicMock()
        client.chat.completions.create.return_value = response

        caplog.set_level("INFO")
        with patch("src.services.llm_service.get_trace_id", return_value="trace-metrics"):
            _chat_completion_with_retry(
                client,
                model="test-model",
                messages=[{"role": "user", "content": "hello"}],
                temperature=0.1,
                max_tokens=100,
                timeout=4,
                metric_operation="unit_test_metric_capture",
            )

        metric_records = [record.message for record in caplog.records if '"event":"llm_service_call_metrics"' in record.message]
        assert metric_records
        payload = json.loads(metric_records[-1])
        assert payload["status"] == "ok"
        assert payload["operation"] == "unit_test_metric_capture"
        assert payload["input_tokens"] == 11
        assert payload["output_tokens"] == 7
        assert payload["total_tokens"] == 18
