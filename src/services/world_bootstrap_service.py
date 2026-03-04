"""World bootstrap orchestration shared by author and game onboarding flows."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List

from sqlalchemy.orm import Session

from ..models import Storylet
from ..models.schemas import WorldDescription
from ..config import settings
from .llm_service import generate_starting_storylet, generate_world_bible, generate_world_storylets
from .spatial_navigator import SpatialNavigator
from .storylet_ingest import postprocess_new_storylets, run_auto_improvements

logger = logging.getLogger(__name__)


def _collect_generated_signals(storylets: Iterable[Dict[str, Any]]) -> tuple[set[str], set[str]]:
    locations: set[str] = set()
    themes: set[str] = set()

    for storylet_data in storylets:
        requires = storylet_data.get("requires", {})
        if isinstance(requires, dict):
            location = requires.get("location")
            if isinstance(location, str) and location.strip():
                locations.add(location.strip())

        title_lower = str(storylet_data.get("title", "")).lower()
        text_lower = str(storylet_data.get("text", "")).lower()
        if any(word in title_lower or word in text_lower for word in ["forge", "craft", "create", "build"]):
            themes.add("crafting")
        if any(word in title_lower or word in text_lower for word in ["market", "trade", "vendor", "buy", "sell"]):
            themes.add("commerce")
        if any(word in title_lower or word in text_lower for word in ["ancient", "artifact", "old", "relic"]):
            themes.add("history")
        if any(word in title_lower or word in text_lower for word in ["danger", "threat", "risk", "escape"]):
            themes.add("danger")
        if any(word in title_lower or word in text_lower for word in ["clan", "rival", "family", "group"]):
            themes.add("social")

    return locations, themes


def bootstrap_world_storylets(
    db: Session,
    *,
    description: str,
    theme: str,
    player_role: str = "adventurer",
    key_elements: List[str] | None = None,
    tone: str = "adventure",
    storylet_count: int = 15,
    replace_existing: bool = True,
    improvement_trigger: str = "world-generation",
    run_improvements: bool = True,
) -> Dict[str, Any]:
    """Generate and persist a world storylet ecosystem.

    Returns a response-shaped payload used by both onboarding bootstrap and
    `/author/generate-world`.

    When ``settings.enable_jit_beat_generation`` is True (and this is not
    called from the author API), generates a compact world bible instead of
    the 15-storylet batch. Falls back to the classic path on any error.
    """
    if key_elements is None:
        key_elements = []

    if replace_existing:
        existing_count = db.query(Storylet).count()
        if existing_count > 0:
            db.query(Storylet).delete()
            db.commit()
            logger.info("Cleared %s existing storylets", existing_count)

    # ------------------------------------------------------------------
    # JIT PATH: generate a world bible + starting storylet only
    # ------------------------------------------------------------------
    if settings.enable_jit_beat_generation:
        try:
            bible = generate_world_bible(
                description=description,
                theme=theme,
                player_role=player_role,
                tone=tone,
            )
            bible_locations = [
                loc["name"]
                for loc in bible.get("locations", [])
                if isinstance(loc, dict) and loc.get("name")
            ]
            world_description = WorldDescription(
                description=description,
                theme=theme,
                player_role=player_role,
                key_elements=key_elements,
                tone=tone,
                storylet_count=1,
                confirm_delete=False,
            )
            starting_storylet_data = generate_starting_storylet(
                world_description=world_description,
                available_locations=bible_locations,
                world_themes=list(bible.get("npcs", []) and [theme]),
            )
            starting_storylet = Storylet(
                title=starting_storylet_data["title"],
                text_template=starting_storylet_data["text"],
                choices=starting_storylet_data["choices"],
                requires={},
                weight=2.0,
                position={"x": 0, "y": 0},
            )
            # Defensively remove any existing storylet with the same title
            # before inserting (guards against partial prior runs and the
            # UNIQUE constraint on storylets.title).
            existing = db.query(Storylet).filter(
                Storylet.title == starting_storylet.title
            ).first()
            if existing:
                db.delete(existing)
                db.flush()
            db.add(starting_storylet)
            db.commit()
            logger.info(
                "JIT bootstrap complete: world_bible generated with %s locations",
                len(bible_locations),
            )
            return {
                "success": True,
                "message": f"Generated world bible for your {theme} world!",
                "storylets_created": 1,
                "theme": theme,
                "player_role": player_role,
                "tone": tone,
                "world_bible": bible,
                "storylets": [
                    {
                        "title": starting_storylet.title,
                        "text_template": starting_storylet.text_template,
                        "requires": {},
                        "choices": starting_storylet.choices,
                        "weight": starting_storylet.weight,
                    }
                ],
            }
        except Exception as exc:
            logger.warning(
                "JIT world bible generation failed (%s) — falling back to classic path: %s",
                type(exc).__name__,
                exc,
            )
            # Fall through to the classic 15-storylet path below

    # ------------------------------------------------------------------
    # CLASSIC PATH: 15-storylet batch (author API + JIT fallback)
    # ------------------------------------------------------------------
    storylets = generate_world_storylets(
        description=description,
        theme=theme,
        player_role=player_role,
        key_elements=key_elements,
        tone=tone,
        count=storylet_count,
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

    generated_locations, generated_themes = _collect_generated_signals(storylets)
    world_description = WorldDescription(
        description=description,
        theme=theme,
        player_role=player_role,
        key_elements=key_elements,
        tone=tone,
        storylet_count=storylet_count,
        confirm_delete=False,
    )
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
    # Defensively remove any existing storylet with the same title (e.g. a
    # batch storylet that was named "A New Beginning" by the LLM, or a
    # partial prior run that already committed a starting storylet).
    existing_start = db.query(Storylet).filter(
        Storylet.title == starting_storylet.title
    ).first()
    if existing_start:
        db.delete(existing_start)
        db.flush()
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
        "message": f"Generated {total_storylets} storylets for your {theme} world!",
        "storylets_created": total_storylets,
        "theme": theme,
        "player_role": player_role,
        "tone": tone,
        "storylets": created_storylets[:3],
    }

    improvement_results = None
    if run_improvements and str(improvement_trigger or "").strip() and total_storylets > 0:
        improvement_results = run_auto_improvements(db, total_storylets, improvement_trigger)
    if improvement_results:
        from .auto_improvement import get_improvement_summary

        base_response["auto_improvements"] = get_improvement_summary(improvement_results)
        base_response["improvement_details"] = improvement_results
        logger.info(get_improvement_summary(improvement_results))

    return base_response
