"""World bootstrap orchestration shared by author and game onboarding flows."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List

from sqlalchemy.orm import Session

from ..models import Storylet
from ..models.schemas import WorldDescription
from ..config import settings
from .llm_service import generate_starting_storylet, generate_world_bible, generate_world_storylets
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

    # ------------------------------------------------------------------
    # JIT PATH: generate a world bible + starting storylet only
    # ------------------------------------------------------------------
    # Always attempt world bible generation when JIT is enabled so that
    # api_next can use it for per-turn beat generation, even if the rest
    # of the bootstrap falls through to the classic storylet batch.
    _world_bible: Dict[str, Any] | None = None

    if settings.enable_jit_beat_generation and improvement_trigger != "world-generation":
        # Step 1: World bible (this is fast and usually succeeds)
        try:
            _world_bible = generate_world_bible(
                description=description,
                theme=theme,
                player_role=player_role,
                tone=tone,
            )
            logger.info(
                "World bible generated: %s locations, tension: %.80s",
                len(_world_bible.get("locations", [])),
                _world_bible.get("central_tension", ""),
            )
        except Exception as exc:
            logger.error(
                "World bible generation failed (%s): %s",
                type(exc).__name__,
                exc,
            )

        # Step 2: If we have a bible, try the fast JIT bootstrap
        if _world_bible is not None:
            try:
                bible_locations = [loc["name"] for loc in _world_bible.get("locations", []) if isinstance(loc, dict) and loc.get("name")]
                world_description = WorldDescription(
                    description=description,
                    theme=theme,
                    player_role=player_role,
                    key_elements=key_elements,
                    tone=tone,
                    storylet_count=5,  # minimum allowed by WorldDescription.ge=5
                    confirm_delete=False,
                )
                starting_storylet_data = generate_starting_storylet(
                    world_description=world_description,
                    available_locations=bible_locations,
                    world_themes=list(_world_bible.get("npcs", []) and [theme]),
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
                if replace_existing:
                    db.query(Storylet).delete()
                else:
                    existing = db.query(Storylet).filter(Storylet.title == starting_storylet.title).first()
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
                    "world_bible": _world_bible,
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
                logger.error(
                    "JIT starting storylet failed (%s) — falling back to classic path (bible preserved): %s",
                    type(exc).__name__,
                    exc,
                )
                # Fall through to classic path — but _world_bible is preserved!

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
    storylet_dicts.append(
        {
            "title": starting_storylet_data["title"],
            "text_template": starting_storylet_data["text"],
            "choices": starting_storylet_data["choices"],
            "requires": {},
            "weight": 2.0,
        }
    )

    save_result = postprocess_new_storylets(
        db=db,
        storylets=storylet_dicts,
        improvement_trigger="",
        assign_spatial=True,
        replace_existing=replace_existing,
        operation_name=("author-generate-world" if improvement_trigger == "world-generation" else "session-bootstrap-generate"),
    )
    created_storylets = save_result.get("storylets", [])

    logger.info(
        "Generated world with %s locations: %s",
        len(generated_locations),
        ", ".join(generated_locations),
    )
    logger.info("Identified themes: %s", ", ".join(generated_themes))

    total_storylets = int(save_result.get("added", len(created_storylets)))
    base_response: dict[str, Any] = {
        "success": True,
        "message": f"Generated {total_storylets} storylets for your {theme} world!",
        "storylets_created": total_storylets,
        "theme": theme,
        "player_role": player_role,
        "tone": tone,
        "storylets": created_storylets[:3],
    }
    # Propagate world bible from JIT attempt even when classic path runs.
    # This ensures api_next can still use JIT beat generation per-turn.
    if _world_bible is not None:
        base_response["world_bible"] = _world_bible

    improvement_results = None
    if run_improvements and str(improvement_trigger or "").strip() and total_storylets > 0:
        improvement_results = run_auto_improvements(db, total_storylets, improvement_trigger)
    if save_result.get("operation_receipt"):
        base_response["operation_receipt"] = save_result.get("operation_receipt")
    if save_result.get("warnings"):
        base_response["warnings"] = save_result.get("warnings")
    if improvement_results:
        from .auto_improvement import get_improvement_summary

        base_response["auto_improvements"] = get_improvement_summary(improvement_results)
        base_response["improvement_details"] = improvement_results
        logger.info(get_improvement_summary(improvement_results))

    return base_response
