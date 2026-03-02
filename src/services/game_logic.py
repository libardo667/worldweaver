"""Core game logic and utilities."""

import logging
import random
from typing import Any, Dict, List, Optional, cast
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ..models import Storylet


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
      - Booleans: {'has_pickaxe': True}
      - Numeric comparisons: {'danger': {'lte': 2}} (supports gte, gt, lte, lt, eq, ne)
    """
    for key, need in (req or {}).items():
        have = vars.get(key, None)
        if isinstance(need, dict):
            # numeric or comparable operators — require a numeric value
            if not isinstance(have, (int, float)):
                logger.warning(
                    "Non-numeric value %r for key %r in numeric comparison", have, key
                )
                return False
            for op, val in need.items():
                if op == "gte" and not (have >= val):
                    return False
                if op == "gt" and not (have > val):
                    return False
                if op == "lte" and not (have <= val):
                    return False
                if op == "lt" and not (have < val):
                    return False
                if op == "eq" and not (have == val):
                    return False
                if op == "ne" and not (have != val):
                    return False
        else:
            if have != need:
                return False
    return True


def pick_storylet(db: Session, vars: Dict[str, Any]) -> Optional[Storylet]:
    """Pick a random storylet based on requirements and weights."""
    all_rows = db.query(Storylet).all()
    eligible = [
        s
        for s in all_rows
        if meets_requirements(vars, cast(Dict[str, Any], s.requires or {}))
    ]

    # If we have very few eligible storylets, try to generate some new ones
    if len(eligible) < 3:
        try:
            from ..services.llm_service import generate_contextual_storylets

            new_storylets_data = generate_contextual_storylets(vars, n=5)

            # Add new storylets to database
            storylets_added = 0
            for storylet_data in new_storylets_data:
                new_storylet = Storylet(
                    title=storylet_data.get("title", "Generated Story"),
                    text_template=storylet_data.get(
                        "text_template", "Something happens..."
                    ),
                    requires=storylet_data.get("requires", {}),
                    choices=storylet_data.get("choices", []),
                    weight=storylet_data.get("weight", 1.0),
                )
                db.add(new_storylet)
                storylets_added += 1

            # Commit and refresh our query
            db.commit()

            # Auto-improve storylets if we added a significant number
            if storylets_added >= 3:
                try:
                    from ..services.auto_improvement import auto_improve_storylets

                    auto_improve_storylets(
                        db=db,
                        trigger=f"contextual-generation ({storylets_added} storylets)",
                        run_smoothing=True,
                        run_deepening=True,
                    )
                    logger.info(
                        f"🤖 Auto-improved storylets after adding {storylets_added} contextual storylets"
                    )
                except Exception as improve_error:
                    logger.warning(f"⚠️  Auto-improvement failed: {improve_error}")

            all_rows = db.query(Storylet).all()
            eligible = [
                s
                for s in all_rows
                if meets_requirements(vars, cast(Dict[str, Any], s.requires or {}))
            ]

        except Exception as e:
            # Log the error but continue with existing storylets
            logger.error(f"Error generating new storylets: {e}")

    if not eligible:
        return None
    weights = [max(0.0, cast(float, s.weight or 0.0)) for s in eligible]
    return random.choices(eligible, weights=weights, k=1)[0]


def apply_choice_set(vars: Dict[str, Any], set_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply choice effects to variables.

    Supports:
        - direct assignment: {'has_pickaxe': True, "notes": "Msg"}
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


def auto_populate_storylets(db: Session, target_count: int = 20) -> int:
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

        # Generate storylets with better thematic and logical coherence
        themes_sets = [
            # Exploration and Discovery
            {
                "themes": ["exploration", "discovery", "mystery"],
                "bible": {
                    "setting": "cave_system",
                    "focus": "finding_new_areas",
                    "variables": ["danger", "location", "has_pickaxe", "ore"],
                },
            },
            # Danger and Survival
            {
                "themes": ["danger", "survival", "escape"],
                "bible": {
                    "setting": "dangerous_situations",
                    "focus": "managing_threats",
                    "variables": ["danger", "health", "location"],
                },
            },
            # Resource Management
            {
                "themes": ["resource_management", "crafting", "preparation"],
                "bible": {
                    "setting": "strategic_planning",
                    "focus": "gathering_resources",
                    "variables": ["ore", "food", "has_pickaxe", "gold"],
                },
            },
            # Social and Story
            {
                "themes": ["social", "encounter", "story_development"],
                "bible": {
                    "setting": "character_interactions",
                    "focus": "narrative_progression",
                    "variables": ["reputation", "location", "met_stranger"],
                },
            },
            # Puzzle and Challenge
            {
                "themes": ["puzzle", "challenge", "skill"],
                "bible": {
                    "setting": "problem_solving",
                    "focus": "overcoming_obstacles",
                    "variables": ["danger", "has_pickaxe", "location"],
                },
            },
        ]

        added_count = 0
        for theme_set in themes_sets:
            if current_count + added_count >= target_count:
                break

            new_storylets = llm_suggest_storylets(
                3, theme_set["themes"], theme_set["bible"]
            )

            for storylet_data in new_storylets:
                if current_count + added_count >= target_count:
                    break

                new_storylet = Storylet(
                    title=storylet_data.get("title", "Generated Story"),
                    text_template=storylet_data.get(
                        "text_template", "Something happens..."
                    ),
                    requires=storylet_data.get("requires", {}),
                    choices=storylet_data.get("choices", []),
                    weight=storylet_data.get("weight", 1.0),
                )
                db.add(new_storylet)
                added_count += 1

        db.commit()

        # Auto-improve storylets if we added a significant number
        if added_count >= 3:
            try:
                from ..services.auto_improvement import auto_improve_storylets

                auto_improve_storylets(
                    db=db,
                    trigger=f"auto-populate ({added_count} storylets)",
                    run_smoothing=True,
                    run_deepening=True,
                )
                logger.info(
                    f"🤖 Auto-improved storylets after populating {added_count} storylets"
                )
            except Exception as improve_error:
                logger.warning(f"⚠️  Auto-improvement failed: {improve_error}")

        return added_count

    except Exception as e:
        logger.error(f"Error auto-populating storylets: {e}")
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
    location_flow = {}

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
        "connectivity_score": len(variables_set & variables_required)
        / max(len(variables_required), 1),
    }

    return report
