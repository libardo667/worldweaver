"""
Auto-improvement service.

Runs optional story smoothing and deepening passes after ingest operations.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from ..config import settings
from .story_deepener import StoryDeepener
from .story_smoother import StorySmoother

logger = logging.getLogger(__name__)


def auto_improve_storylets(
    db: Optional[Session] = None,
    trigger: str = "unknown",
    run_smoothing: bool = True,
    run_deepening: bool = True,
) -> Dict[str, Any]:
    """Run configured post-ingest improvement passes and return aggregate results."""
    results: Dict[str, Any] = {
        "trigger": trigger,
        "smoothing_results": {},
        "deepening_results": {},
        "total_improvements": 0,
        "success": True,
    }

    try:
        logger.info("Auto-improvement triggered by: %s", trigger)

        should_smooth = bool(run_smoothing and settings.enable_story_smoothing)
        if run_smoothing and not settings.enable_story_smoothing:
            logger.info("Story smoothing skipped (WW_ENABLE_STORY_SMOOTHING is disabled)")

        if should_smooth:
            logger.info("Running story smoothing...")
            smoother = StorySmoother()
            apply_spatial_fixes = bool(settings.enable_spatial_auto_fixes)
            if apply_spatial_fixes:
                logger.info("Spatial auto-fix smoothing is enabled.")
            smoothing_results = smoother.smooth_story(
                dry_run=False,
                apply_spatial_fixes=apply_spatial_fixes,
            )
            results["smoothing_results"] = smoothing_results
            smoothing_total = int(smoothing_results.get("exit_choices_added", 0)) + int(smoothing_results.get("variable_storylets_created", 0)) + int(smoothing_results.get("bidirectional_connections", 0))
            logger.info("Smoothing complete: %d fixes applied", smoothing_total)

        should_deepen = bool(run_deepening and settings.enable_story_deepening)
        if run_deepening and not settings.enable_story_deepening:
            logger.info("Story deepening skipped (WW_ENABLE_STORY_DEEPENING is disabled)")

        if should_deepen:
            logger.info("Running story deepening...")
            deepener = StoryDeepener()
            deepening_results = deepener.deepen_story(add_previews=True)
            results["deepening_results"] = deepening_results
            deepening_total = sum(v for v in deepening_results.values() if isinstance(v, int))
            logger.info("Deepening complete: %d improvements made", deepening_total)

        smoothing_total = sum(v for v in results["smoothing_results"].values() if isinstance(v, int))
        deepening_total = sum(v for v in results["deepening_results"].values() if isinstance(v, int))
        results["total_improvements"] = smoothing_total + deepening_total

        logger.info(
            "Auto-improvement complete: %d total improvements",
            results["total_improvements"],
        )

        if db:
            logger.info(
                "Auto-improvement completed for %s: %d improvements",
                trigger,
                results["total_improvements"],
            )

    except Exception as exc:
        logger.error("Auto-improvement failed: %s", str(exc))
        results["success"] = False
        results["error"] = str(exc)

        if db:
            logger.error("Auto-improvement failed for %s: %s", trigger, str(exc))

    return results


def should_run_auto_improvement(storylets_added: int, trigger: str) -> bool:
    """Return True when auto-improvement should run for the current ingest trigger."""
    if storylets_added >= 1:
        return True

    improvement_triggers = [
        "world-generation",
        "ai-generation",
        "author-commit",
        "populate-storylets",
        "targeted-generation",
    ]
    return any(token in trigger.lower() for token in improvement_triggers)


def get_improvement_summary(results: Dict[str, Any]) -> str:
    """Return a user-facing summary of auto-improvement results."""
    if not results.get("success", False):
        return f"Auto-improvement failed: {results.get('error', 'Unknown error')}"

    summary_parts: list[str] = []

    smoothing = results.get("smoothing_results", {})
    if smoothing:
        smoothing_items: list[str] = []
        if smoothing.get("exit_choices_added", 0) > 0:
            smoothing_items.append(f"{smoothing['exit_choices_added']} exit choices")
        if smoothing.get("variable_storylets_created", 0) > 0:
            smoothing_items.append(f"{smoothing['variable_storylets_created']} variable storylets")
        if smoothing.get("bidirectional_connections", 0) > 0:
            smoothing_items.append(f"{smoothing['bidirectional_connections']} return paths")

        if smoothing_items:
            summary_parts.append(f"Smoothing: {', '.join(smoothing_items)}")

    deepening = results.get("deepening_results", {})
    if deepening:
        deepening_items: list[str] = []
        if deepening.get("bridge_storylets_created", 0) > 0:
            deepening_items.append(f"{deepening['bridge_storylets_created']} bridge storylets")
        if deepening.get("choice_previews_added", 0) > 0:
            deepening_items.append("choice previews updated")

        if deepening_items:
            summary_parts.append(f"Deepening: {', '.join(deepening_items)}")

    if not summary_parts:
        return "No improvements needed - storylet ecosystem is healthy."

    total = int(results.get("total_improvements", 0))
    return f"Auto-improved ({total} total): {' | '.join(summary_parts)}"
