"""Author world/debug endpoints."""

import logging
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Storylet
from ...models.schemas import WorldDescription
from ...services.llm_service import generate_world_storylets
from ...services.storylet_ingest import postprocess_new_storylets, run_auto_improvements

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/debug")
def debug_game_state(db: Session = Depends(get_db)):
    """Debug endpoint to inspect session and storylet data."""
    try:
        # Import from package for compatibility with patching `src.api.author.SessionVars`.
        from . import SessionVars, Storylet as StoryletModel

        session_vars = db.query(SessionVars).first()
        session_dict = cast(Dict[str, Any], session_vars.vars) if session_vars else {}

        total_storylets = db.query(StoryletModel).count()
        all_storylets = db.query(StoryletModel).all()

        return {
            "session_variables": session_dict,
            "total_storylets": total_storylets,
            "available_storylets": len(all_storylets),
            "sample_storylet_titles": [storylet.title for storylet in all_storylets[:5]],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/generate-world")
def generate_world_from_description(
    world_description: WorldDescription,
    db: Session = Depends(get_db),
):
    """Generate a complete storylet ecosystem from a world description."""
    try:
        if not world_description.confirm_delete:
            raise HTTPException(
                status_code=422,
                detail=(
                    "World generation replaces all existing storylets. "
                    "Set confirm_delete=true to proceed."
                ),
            )

        existing_count = db.query(Storylet).count()
        if existing_count > 0:
            db.query(Storylet).delete()
            db.commit()
            logger.info("Cleared %s existing storylets", existing_count)

        storylets = generate_world_storylets(
            description=world_description.description,
            theme=world_description.theme,
            player_role=world_description.player_role,
            key_elements=world_description.key_elements,
            tone=world_description.tone,
            count=world_description.storylet_count,
        )

        storylet_dicts: list[dict[str, Any]] = []
        for storylet_data in storylets:
            if not storylet_data.get("title"):
                continue
            storylet_dicts.append(
                {
                    "title": storylet_data.get("title"),
                    "text_template": storylet_data.get("text"),
                    "choices": storylet_data.get("choices", []),
                    "requires": storylet_data.get("requires", {}),
                    "weight": float(storylet_data.get("weight", 1.0)),
                }
            )

        save_result = postprocess_new_storylets(
            db=db,
            storylets=storylet_dicts,
            improvement_trigger="",
            assign_spatial=False,
        )

        created_storylets = save_result.get("storylets", [])

        generated_locations = set()
        generated_themes = set()

        for storylet_data in storylets:
            requires = storylet_data.get("requires", {})
            if "location" in requires:
                generated_locations.add(requires["location"])

            title_lower = str(storylet_data.get("title", "")).lower()
            text_lower = str(storylet_data.get("text", "")).lower()

            if any(word in title_lower or word in text_lower for word in ["forge", "craft", "create", "build"]):
                generated_themes.add("crafting")
            if any(word in title_lower or word in text_lower for word in ["market", "trade", "vendor", "buy", "sell"]):
                generated_themes.add("commerce")
            if any(word in title_lower or word in text_lower for word in ["ancient", "artifact", "old", "relic"]):
                generated_themes.add("history")
            if any(word in title_lower or word in text_lower for word in ["danger", "threat", "risk", "escape"]):
                generated_themes.add("danger")
            if any(word in title_lower or word in text_lower for word in ["clan", "rival", "family", "group"]):
                generated_themes.add("social")

        from ...services.llm_service import generate_starting_storylet

        starting_storylet_data = generate_starting_storylet(
            world_description=world_description,
            available_locations=list(generated_locations),
            world_themes=list(generated_themes),
        )

        starting_storylet = Storylet(
            title=starting_storylet_data["title"],
            text_template=starting_storylet_data["text"],
            choices=starting_storylet_data["choices"],
            requires={},
            weight=2.0,
            position={"x": 0, "y": 0},
        )
        db.add(starting_storylet)
        created_storylets.append(
            {
                "title": starting_storylet.title,
                "text_template": starting_storylet.text_template,
                "requires": {},
                "choices": starting_storylet.choices,
                "weight": starting_storylet.weight,
            }
        )

        db.commit()

        new_storylet_ids: list[int] = []
        for created in db.query(Storylet).filter(
            Storylet.title.in_([storylet["title"] for storylet in created_storylets])
        ):
            new_storylet_ids.append(created.id)

        from ...services.spatial_navigator import SpatialNavigator

        try:
            spatial_nav = SpatialNavigator(db)
            positions = spatial_nav.assign_spatial_positions(created_storylets)
            logger.info("Assigned spatial positions to %s storylets", len(positions))

            additional_updates = SpatialNavigator.auto_assign_coordinates(db, new_storylet_ids)
            if additional_updates > 0:
                logger.info("Auto-assigned coordinates to %s additional storylets", additional_updates)
        except Exception as exc:
            logger.warning("Warning: Could not assign spatial positions: %s", exc)
            try:
                updates = SpatialNavigator.auto_assign_coordinates(db, new_storylet_ids)
                if updates > 0:
                    logger.info("Fallback: Auto-assigned coordinates to %s storylets", updates)
            except Exception as fallback_exc:
                logger.warning("Fallback also failed: %s", fallback_exc)

        logger.info(
            "Generated world with %s locations: %s",
            len(generated_locations),
            ", ".join(generated_locations),
        )
        logger.info("Identified themes: %s", ", ".join(generated_themes))

        total_storylets = len(storylets) + 1
        base_response: dict[str, Any] = {
            "success": True,
            "message": (
                f"Generated {total_storylets} storylets for your {world_description.theme} world!"
            ),
            "storylets_created": total_storylets,
            "theme": world_description.theme,
            "player_role": world_description.player_role,
            "tone": world_description.tone,
            "storylets": created_storylets[:3],
        }

        improvement_results = run_auto_improvements(db, total_storylets, "world-generation")
        if improvement_results:
            from ...services.auto_improvement import get_improvement_summary

            base_response["auto_improvements"] = get_improvement_summary(improvement_results)
            base_response["improvement_details"] = improvement_results
            logger.info(get_improvement_summary(improvement_results))

        return base_response
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"World generation failed: {str(exc)}")
