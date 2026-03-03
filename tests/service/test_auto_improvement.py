"""Unit tests for auto-improvement policy controls."""

from unittest.mock import patch

from src.config import settings
from src.services.auto_improvement import auto_improve_storylets


def _smoothing_result() -> dict:
    return {
        "exit_choices_added": 0,
        "variable_storylets_created": 0,
        "bidirectional_connections": 0,
        "spatial_locations_assigned": 0,
        "spatial_connections_created": 0,
    }


@patch("src.services.auto_improvement.StorySmoother")
def test_auto_improvement_keeps_spatial_fixes_disabled_by_default(
    mock_smoother,
    monkeypatch,
):
    smoother_instance = mock_smoother.return_value
    smoother_instance.smooth_story.return_value = _smoothing_result()

    monkeypatch.setattr(settings, "enable_story_smoothing", True)
    monkeypatch.setattr(settings, "enable_spatial_auto_fixes", False)

    result = auto_improve_storylets(
        trigger="policy-default",
        run_smoothing=True,
        run_deepening=False,
    )

    smoother_instance.smooth_story.assert_called_once_with(
        dry_run=False,
        apply_spatial_fixes=False,
    )
    assert result["success"] is True


@patch("src.services.auto_improvement.StorySmoother")
def test_auto_improvement_only_runs_spatial_fixes_when_explicitly_enabled(
    mock_smoother,
    monkeypatch,
):
    smoother_instance = mock_smoother.return_value
    smoother_instance.smooth_story.return_value = _smoothing_result()

    monkeypatch.setattr(settings, "enable_story_smoothing", True)
    monkeypatch.setattr(settings, "enable_spatial_auto_fixes", True)

    result = auto_improve_storylets(
        trigger="policy-opt-in",
        run_smoothing=True,
        run_deepening=False,
    )

    smoother_instance.smooth_story.assert_called_once_with(
        dry_run=False,
        apply_spatial_fixes=True,
    )
    assert result["success"] is True
