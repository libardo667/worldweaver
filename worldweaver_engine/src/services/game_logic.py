"""Core game logic and utilities."""

import logging
import random
from typing import Any, Dict, List, Optional, cast

from sqlalchemy.orm import Session

from ..models import Storylet
from .requirements import evaluate_requirements

logger = logging.getLogger(__name__)


class SafeDict(dict):
    """Dictionary that returns placeholder for missing keys in template rendering."""

    def __missing__(self, key):
        return "{" + key + "}"


def render(template: str, vars: Dict[str, Any]) -> str:
    """Render a template string with variables, handling missing keys gracefully."""
    return template.format_map(SafeDict(vars))


def meets_requirements(vars: Dict[str, Any], req: Dict[str, Any]) -> bool:
    """
    Check if current variables meet storylet requirements.

    Supports:
      - Plain equality: {'location': 'mineshaft'}
      - Booleans: {'has_key': True}
      - Numeric comparisons: {'danger': {'lte': 2}} (supports gte, gt, lte, lt, eq, ne)
    """
    return evaluate_requirements(req or {}, vars)


def ensure_storylets(db: Session, vars: Dict[str, Any], min_count: int = 3) -> None:
    """Generate new storylets via LLM if too few are eligible.

    This is the side-effectful half of the old pick_storylet: it checks how
    many storylets meet the current requirements, and if fewer than
    *min_count* are eligible it asks the LLM to create more, then runs
    auto-improvement.
    """
    all_rows = db.query(Storylet).all()
    eligible_count = sum(1 for s in all_rows if meets_requirements(vars, cast(Dict[str, Any], s.requires or {})))

    if eligible_count >= min_count:
        return

    try:
        from ..services.llm_service import generate_contextual_storylets

        new_storylets_data = generate_contextual_storylets(vars, n=5)
        storylets_added = 0
        existing_titles = {row.title.lower() for row in all_rows}
        for storylet_data in new_storylets_data:
            title = (storylet_data.get("title") or "Generated Story").strip()
            if title.lower() in existing_titles:
                logger.debug("ensure_storylets: skipping duplicate title '%s'", title)
                continue
            new_storylet = Storylet(
                title=title,
                text_template=storylet_data.get("text_template", "Something happens..."),
                requires=storylet_data.get("requires", {}),
                choices=storylet_data.get("choices", []),
                weight=storylet_data.get("weight", 1.0),
            )
            db.add(new_storylet)
            existing_titles.add(title.lower())
            storylets_added += 1

        db.commit()

    except Exception as e:
        db.rollback()
        logger.error("Error generating new storylets: %s", e)


def pick_storylet(db: Session, vars: Dict[str, Any]) -> Optional[Storylet]:
    """Pick a random eligible storylet based on requirements and weights.

    This is a pure selection function with no LLM side effects.  Call
    ``ensure_storylets`` beforehand if you want automatic generation
    when the eligible pool is small.
    """
    all_rows = db.query(Storylet).all()
    eligible = [s for s in all_rows if meets_requirements(vars, cast(Dict[str, Any], s.requires or {}))]

    if not eligible:
        return None
    weights = [max(0.0, cast(float, s.weight or 0.0)) for s in eligible]
    return random.choices(eligible, weights=weights, k=1)[0]


def apply_choice_set(vars: Dict[str, Any], set_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply choice effects to variables.

    Supports:
        - direct assignment: {'has_key': True, "notes": "Msg"}
        - numeric inc/dec: {'ore': {'inc': 1}, 'danger': {'dec': 1}}
    """
    out = dict(vars)
    for key, val in (set_obj or {}).items():
        if isinstance(val, dict) and ("inc" in val or "dec" in val):
            curr = out.get(key, 0)
            if not isinstance(curr, (int, float)):
                curr = 0
            try:
                inc = int(val.get("inc", 0))
                dec = int(val.get("dec", 0))
            except (TypeError, ValueError) as e:
                logger.warning("Bad inc/dec value for key %r: %s", key, e)
                continue
            out[key] = curr + inc - dec
        else:
            out[key] = val
    return out


def auto_populate_storylets(
    db: Session,
    target_count: int = 20,
    world_bible: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Automatically populate the database with AI-generated storylets if below target.

    Returns:
        Number of storylets added
    """
    current_count = db.query(Storylet).count()
    if current_count >= target_count:
        return 0

    try:
        from ..services.llm_service import llm_suggest_storylets

        default_world_bible: Dict[str, Any] = {
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
        active_world_bible = world_bible or default_world_bible

        # Keep theme generation broad so this helper is setting-neutral.
        themes_sets = [
            ["exploration", "discovery", "mystery"],
            ["danger", "survival", "escape"],
            ["resource_management", "crafting", "preparation"],
            ["social", "encounter", "story_development"],
            ["puzzle", "challenge", "skill"],
        ]

        added_count = 0
        for theme_set in themes_sets:
            if current_count + added_count >= target_count:
                break

            new_storylets = llm_suggest_storylets(3, theme_set, active_world_bible)

            for storylet_data in new_storylets:
                if current_count + added_count >= target_count:
                    break

                new_storylet = Storylet(
                    title=storylet_data.get("title", "Generated Story"),
                    text_template=storylet_data.get("text_template", "Something happens..."),
                    requires=storylet_data.get("requires", {}),
                    choices=storylet_data.get("choices", []),
                    weight=storylet_data.get("weight", 1.0),
                )
                db.add(new_storylet)
                added_count += 1

        db.commit()

        return added_count

    except Exception as e:
        logger.error("Error auto-populating storylets: %s", e)
        return 0


def ensure_storylet_connectivity(db: Session) -> Dict[str, Any]:
    """
    Analyze and improve storylet connectivity by ensuring logical flow.

    Returns:
        Analysis report of connectivity issues and improvements
    """
    all_storylets = db.query(Storylet).all()

    # Track variable usage
    variables_required = set()
    variables_set = set()

    for storylet in all_storylets:
        # Analyze requirements
        requires = cast(Dict[str, Any], storylet.requires or {})
        for key in requires.keys():
            variables_required.add(key)

        # Analyze what variables are set by choices
        choices = cast(List[Dict[str, Any]], storylet.choices or [])
        for choice in choices:
            set_data = choice.get("set", {})
            for key in set_data.keys():
                variables_set.add(key)

    # Find gaps in storylet flow
    missing_setters = variables_required - variables_set
    unused_setters = variables_set - variables_required

    report = {
        "total_storylets": len(all_storylets),
        "variables_required": sorted(variables_required),
        "variables_set": sorted(variables_set),
        "missing_setters": sorted(missing_setters),
        "unused_setters": sorted(unused_setters),
        "connectivity_score": len(variables_set & variables_required) / max(len(variables_required), 1),
    }

    return report
