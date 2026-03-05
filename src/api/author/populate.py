"""Author population endpoints."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Storylet
from ...services.storylet_ingest import AuthorPipelineError, postprocess_new_storylets

logger = logging.getLogger(__name__)
router = APIRouter()


def _default_world_bible() -> Dict[str, Any]:
    return {
        "setting": "dynamic_world",
        "focus": "player_driven_story_progression",
        "variables": [
            "location",
            "danger",
            "reputation",
            "resources",
            "progress",
        ],
    }


def _generate_population_candidates(target_count: int) -> List[Dict[str, Any]]:
    """Generate candidate storylets for populate flow without mutating DB."""
    from ...services.llm_service import llm_suggest_storylets

    themes_sets = [
        ["exploration", "discovery", "mystery"],
        ["danger", "survival", "escape"],
        ["resource_management", "crafting", "preparation"],
        ["social", "encounter", "story_development"],
        ["puzzle", "challenge", "skill"],
    ]
    world_bible = _default_world_bible()
    candidates: List[Dict[str, Any]] = []
    remaining = max(0, int(target_count))

    for theme_set in themes_sets:
        if remaining <= 0:
            break
        generated = llm_suggest_storylets(min(3, remaining), theme_set, world_bible)
        for payload in generated:
            if remaining <= 0:
                break
            candidates.append(
                {
                    "title": payload.get("title", "Generated Story"),
                    "text_template": payload.get("text_template", "Something happens..."),
                    "requires": payload.get("requires", {}),
                    "choices": payload.get("choices", []),
                    "weight": float(payload.get("weight", 1.0)),
                }
            )
            remaining -= 1

    return candidates


@router.post("/populate")
def populate_storylets(target_count: int = 20, db: Session = Depends(get_db)):
    """Auto-populate the database with AI-generated storylets."""
    if target_count < 1:
        raise HTTPException(status_code=400, detail="target_count must be at least 1")
    if target_count > 100:
        raise HTTPException(status_code=400, detail="target_count cannot exceed 100")

    try:
        current_count = db.query(Storylet).count()
        needed = max(0, int(target_count) - int(current_count))
        if needed == 0:
            return {
                "success": True,
                "added": 0,
                "total_storylets": current_count,
                "message": f"Added 0 new storylets. Total: {current_count}",
            }

        candidates = _generate_population_candidates(needed)
        save_result = postprocess_new_storylets(
            db=db,
            storylets=candidates,
            improvement_trigger="populate-storylets",
            assign_spatial=True,
            operation_name="author-populate",
        )
        added = int(save_result.get("added", 0))
        current_count = db.query(Storylet).count()

        base_response = {
            "success": True,
            "added": added,
            "total_storylets": current_count,
            "message": f"Added {added} new storylets. Total: {current_count}",
        }

        if save_result.get("auto_improvements"):
            base_response["auto_improvements"] = save_result.get("auto_improvements")
            base_response["improvement_details"] = save_result.get("improvement_details")
        if save_result.get("operation_receipt"):
            base_response["operation_receipt"] = save_result.get("operation_receipt")
        if save_result.get("warnings"):
            base_response["warnings"] = save_result.get("warnings")

        return base_response
    except AuthorPipelineError as exc:
        logger.exception("Populate pipeline failed")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(exc),
                "type": type(exc).__name__,
                "operation_receipt": exc.receipt,
            },
        )
    except Exception as exc:
        logger.exception("Error populating storylets")
        raise HTTPException(
            status_code=500,
            detail={"error": str(exc), "type": type(exc).__name__},
        )
