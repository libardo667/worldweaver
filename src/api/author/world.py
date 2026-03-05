"""Author world/debug endpoints."""

import logging
from typing import Any, Dict, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...models.schemas import WorldDescription
from ...services.storylet_ingest import AuthorPipelineError
from ...services.world_bootstrap_service import bootstrap_world_storylets

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

        return bootstrap_world_storylets(
            db,
            description=world_description.description,
            theme=world_description.theme,
            player_role=world_description.player_role,
            key_elements=world_description.key_elements,
            tone=world_description.tone,
            storylet_count=world_description.storylet_count,
            replace_existing=True,
            improvement_trigger="world-generation",
        )
    except HTTPException:
        raise
    except AuthorPipelineError as exc:
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
        db.rollback()
        raise HTTPException(status_code=500, detail=f"World generation failed: {str(exc)}")
