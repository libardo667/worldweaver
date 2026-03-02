"""Storylet ingest/postprocessing service for author workflows."""

import logging
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Storylet

logger = logging.getLogger(__name__)


def deduplicate_and_insert(db: Session, storylets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Validate, deduplicate, and insert storylets into the database."""
    required_keys = ["title", "text_template", "requires", "choices", "weight"]
    created_storylets: list[dict[str, Any]] = []
    skipped_count = 0

    for data in storylets:
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            logger.warning(
                "Skipping storylet '%s': missing required keys: %s",
                (data.get("title") or "<untitled>"),
                ", ".join(missing_keys),
            )
            skipped_count += 1
            continue

        normalized = (data.get("title") or "").strip()
        exists = (
            db.query(Storylet)
            .filter(func.lower(Storylet.title) == func.lower(normalized))
            .first()
        )
        if exists:
            logger.warning("Skipped storylet '%s': duplicate title", normalized)
            skipped_count += 1
            continue

        storylet = Storylet(
            title=normalized,
            text_template=data["text_template"],
            requires=data["requires"],
            choices=data["choices"],
            weight=float(data["weight"]),
        )
        db.add(storylet)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            logger.warning(
                "Skipped storylet '%s': integrity error (likely duplicate)",
                normalized,
            )
            skipped_count += 1
            continue

        created_storylets.append(
            {
                "title": storylet.title,
                "text_template": storylet.text_template,
                "requires": data["requires"],
                "choices": data["choices"],
                "weight": storylet.weight,
            }
        )

    db.commit()
    return created_storylets, skipped_count


def assign_spatial_to_storylets(
    db: Session,
    storylet_titles: list[str],
    spatial_ids: Optional[list[int]] = None,
) -> int:
    """Assign spatial coordinates to newly created storylets."""
    from ..services.spatial_navigator import SpatialNavigator

    new_storylet_ids = [
        storylet.id
        for storylet in db.query(Storylet).filter(Storylet.title.in_(storylet_titles))
    ]

    updates = SpatialNavigator.auto_assign_coordinates(db, spatial_ids or new_storylet_ids)
    if updates > 0:
        logger.info("Auto-assigned coordinates to %d storylets", updates)
    return updates


def run_auto_improvements(db: Session, storylet_count: int, trigger: str) -> Optional[dict[str, Any]]:
    """Run auto-improvement if the trigger warrants it."""
    from ..services.auto_improvement import (
        auto_improve_storylets,
        should_run_auto_improvement,
    )

    if not should_run_auto_improvement(storylet_count, trigger):
        return None

    return auto_improve_storylets(
        db=db,
        trigger=f"{trigger} ({storylet_count} storylets)",
        run_smoothing=True,
        run_deepening=True,
    )


def postprocess_new_storylets(
    db: Session,
    storylets: list[dict[str, Any]],
    improvement_trigger: str = "",
    assign_spatial: bool = True,
    spatial_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Insert storylets and run optional spatial/embedding/improvement stages."""
    from ..services.auto_improvement import get_improvement_summary

    created_storylets, skipped_count = deduplicate_and_insert(db, storylets)

    updates = 0
    if assign_spatial and created_storylets:
        titles = [storylet["title"] for storylet in created_storylets]
        updates = assign_spatial_to_storylets(db, titles, spatial_ids)

    if created_storylets:
        try:
            from ..services.embedding_service import embed_all_storylets

            embedded = embed_all_storylets(db)
            if embedded:
                logger.info("Embedded %d new storylets", embedded)
        except Exception as exc:
            logger.warning("Embedding failed (non-fatal): %s", exc)

    improvement_results = run_auto_improvements(db, len(created_storylets), improvement_trigger)

    return {
        "added": len(created_storylets),
        "skipped": skipped_count,
        "storylets": created_storylets,
        "spatial_updates": updates,
        "auto_improvements": get_improvement_summary(improvement_results)
        if improvement_results
        else None,
        "improvement_details": improvement_results,
    }


def save_storylets_with_postprocessing(
    db: Session,
    storylets: list[dict[str, Any]],
    improvement_trigger: str = "",
    assign_spatial: bool = True,
    spatial_ids: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Compatibility alias for pre-refactor call sites/tests."""
    return postprocess_new_storylets(
        db=db,
        storylets=storylets,
        improvement_trigger=improvement_trigger,
        assign_spatial=assign_spatial,
        spatial_ids=spatial_ids,
    )
