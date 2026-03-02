"""
Auto-Improvement Service
Automatically runs story smoothing and deepening algorithms whenever storylets are added.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from .story_smoother import StorySmoother
from .story_deepener import StoryDeepener


def auto_improve_storylets(
    db: Optional[Session] = None,
    trigger: str = "unknown",
    run_smoothing: bool = True,
    run_deepening: bool = True,
) -> Dict[str, Any]:
    """
    Automatically run story improvement algorithms after storylets are added.

    Args:
        db: Database session (optional, for logging)
        trigger: Description of what triggered the improvement (for logging)
        run_smoothing: Whether to run the smoothing algorithm
        run_deepening: Whether to run the deepening algorithm

    Returns:
        Dict with results from both algorithms
    """
    results = {
        "trigger": trigger,
        "smoothing_results": {},
        "deepening_results": {},
        "total_improvements": 0,
        "success": True,
    }

    try:
        logger.info(f"🤖 Auto-improvement triggered by: {trigger}")

        # Run story smoothing algorithm
        if run_smoothing:
            logger.info("🔧 Running story smoothing...")
            smoother = StorySmoother()
            smoothing_results = smoother.smooth_story(dry_run=False)
            results["smoothing_results"] = smoothing_results

            smoothing_total = (
                smoothing_results.get("exit_choices_added", 0)
                + smoothing_results.get("variable_storylets_created", 0)
                + smoothing_results.get("bidirectional_connections", 0)
            )

            logger.info(f"✅ Smoothing complete: {smoothing_total} fixes applied")

        # Run story deepening algorithm
        if run_deepening:
            logger.info("🕳️  Running story deepening...")
            deepener = StoryDeepener()
            deepening_results = deepener.deepen_story(add_previews=True)
            results["deepening_results"] = deepening_results

            deepening_total = sum(deepening_results.values())
            logger.info(f"✅ Deepening complete: {deepening_total} improvements made")

        # Calculate total improvements
        smoothing_total = sum(
            [v for k, v in results["smoothing_results"].items() if isinstance(v, int)]
        )
        deepening_total = sum(
            [v for k, v in results["deepening_results"].items() if isinstance(v, int)]
        )

        results["total_improvements"] = smoothing_total + deepening_total

        logger.info(
            f"🎉 Auto-improvement complete! Total improvements: {results['total_improvements']}"
        )

        # Log the improvement for admin visibility
        if db:
            logger.info(
                f"Auto-improvement completed for {trigger}: {results['total_improvements']} improvements"
            )

    except Exception as e:
        logger.error(f"❌ Auto-improvement failed: {str(e)}")
        results["success"] = False
        results["error"] = str(e)

        if db:
            logger.error(f"Auto-improvement failed for {trigger}: {str(e)}")

    return results


def should_run_auto_improvement(storylets_added: int, trigger: str) -> bool:
    """
    Determine if auto-improvement should run based on context.

    Args:
        storylets_added: Number of storylets that were just added
        trigger: What triggered the addition

    Returns:
        True if auto-improvement should run
    """
    # Always run for meaningful additions
    if storylets_added >= 1:
        return True

    # Run for specific triggers
    improvement_triggers = [
        "world-generation",
        "ai-generation",
        "author-commit",
        "populate-storylets",
        "targeted-generation",
    ]

    return any(t in trigger.lower() for t in improvement_triggers)


def get_improvement_summary(results: Dict[str, Any]) -> str:
    """
    Generate a human-readable summary of improvements made.

    Args:
        results: Results from auto_improve_storylets()

    Returns:
        Formatted summary string
    """
    if not results.get("success", False):
        return f"❌ Auto-improvement failed: {results.get('error', 'Unknown error')}"

    summary_parts = []

    # Smoothing results
    smoothing = results.get("smoothing_results", {})
    if smoothing:
        smoothing_items = []
        if smoothing.get("exit_choices_added", 0) > 0:
            smoothing_items.append(f"{smoothing['exit_choices_added']} exit choices")
        if smoothing.get("variable_storylets_created", 0) > 0:
            smoothing_items.append(
                f"{smoothing['variable_storylets_created']} variable storylets"
            )
        if smoothing.get("bidirectional_connections", 0) > 0:
            smoothing_items.append(
                f"{smoothing['bidirectional_connections']} return paths"
            )

        if smoothing_items:
            summary_parts.append(f"🔧 Smoothing: {', '.join(smoothing_items)}")

    # Deepening results
    deepening = results.get("deepening_results", {})
    if deepening:
        deepening_items = []
        if deepening.get("bridge_storylets_created", 0) > 0:
            deepening_items.append(
                f"{deepening['bridge_storylets_created']} bridge storylets"
            )
        if deepening.get("choice_previews_added", 0) > 0:
            deepening_items.append("choice previews updated")

        if deepening_items:
            summary_parts.append(f"🕳️  Deepening: {', '.join(deepening_items)}")

    if not summary_parts:
        return "✨ No improvements needed - storylet ecosystem is healthy!"

    total = results.get("total_improvements", 0)
    return f"🤖 Auto-improved ({total} total): {' | '.join(summary_parts)}"
