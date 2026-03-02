"""Author population endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Storylet
from ...services.game_logic import auto_populate_storylets
from ...services.storylet_ingest import run_auto_improvements

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/populate")
def populate_storylets(target_count: int = 20, db: Session = Depends(get_db)):
    """Auto-populate the database with AI-generated storylets."""
    if target_count < 1:
        raise HTTPException(status_code=400, detail="target_count must be at least 1")
    if target_count > 100:
        raise HTTPException(status_code=400, detail="target_count cannot exceed 100")

    try:
        added = auto_populate_storylets(db, target_count)
        current_count = db.query(Storylet).count()

        if added > 0:
            from ...services.spatial_navigator import SpatialNavigator

            updates = SpatialNavigator.auto_assign_coordinates(db)
            if updates > 0:
                logger.info("Auto-assigned coordinates to %s populated storylets", updates)

        base_response = {
            "success": True,
            "added": added,
            "total_storylets": current_count,
            "message": f"Added {added} new storylets. Total: {current_count}",
        }

        improvement_results = run_auto_improvements(db, added, "populate-storylets")
        if improvement_results:
            from ...services.auto_improvement import get_improvement_summary

            base_response["auto_improvements"] = get_improvement_summary(improvement_results)
            base_response["improvement_details"] = improvement_results

        return base_response
    except Exception as exc:
        logger.exception("Error populating storylets")
        raise HTTPException(
            status_code=500,
            detail={"error": str(exc), "type": type(exc).__name__},
        )
