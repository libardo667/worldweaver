"""
Intelligent storylet analysis and feedback system.
This module analyzes existing storylets and provides targeted feedback to improve AI generation.
"""

import logging
from typing import Dict, List, Any, Tuple
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
from ..models import Storylet
from ..services.llm_service import llm_suggest_storylets
import json


def analyze_storylet_gaps(db: Session) -> Dict[str, Any]:
    """
    Perform deep analysis of storylet connectivity and identify specific gaps.

    Returns:
        Comprehensive analysis with actionable feedback for AI generation
    """
    all_storylets = db.query(Storylet).all()

    # Track variable usage patterns
    variables_required = {}  # variable -> list of storylets that require it
    variables_set = {}  # variable -> list of storylets that set it
    location_flow = {}  # location -> {from: [], to: []}
    danger_distribution = {"low": 0, "medium": 0, "high": 0}

    for storylet in all_storylets:
        # Analyze requirements
        requires = storylet.requires or {}
        if isinstance(requires, str):
            requires = json.loads(requires)

        for key, value in requires.items():
            if key not in variables_required:
                variables_required[key] = []
            variables_required[key].append(
                {"title": storylet.title, "id": storylet.id, "requirement": value}
            )

            # Track location flow
            if key == "location" and isinstance(value, str):
                if value not in location_flow:
                    location_flow[value] = {"required_by": [], "transitions_to": []}
                location_flow[value]["required_by"].append(storylet.title)

        # Analyze danger levels
        if "danger" in requires:
            danger_req = requires["danger"]
            if isinstance(danger_req, dict):
                if "lte" in danger_req and danger_req["lte"] <= 1:
                    danger_distribution["low"] += 1
                elif "gte" in danger_req and danger_req["gte"] >= 4:
                    danger_distribution["high"] += 1
                else:
                    danger_distribution["medium"] += 1

        # Analyze what variables are set by choices
        choices = storylet.choices or []
        if isinstance(choices, str):
            choices = json.loads(choices)

        for choice in choices:
            set_data = choice.get("set", {})
            for key, value in set_data.items():
                if key not in variables_set:
                    variables_set[key] = []
                variables_set[key].append(
                    {
                        "title": storylet.title,
                        "choice": choice.get("label", "Unknown choice"),
                        "sets": value,
                    }
                )

                # Track location transitions
                if key == "location" and isinstance(value, str):
                    if value not in location_flow:
                        location_flow[value] = {"required_by": [], "transitions_to": []}
                    location_flow[value]["transitions_to"].append(
                        f"{storylet.title} -> {value}"
                    )

    # Identify critical gaps
    missing_setters = set(variables_required.keys()) - set(variables_set.keys())
    unused_setters = set(variables_set.keys()) - set(variables_required.keys())

    # Analyze location connectivity
    orphaned_locations = []
    poorly_connected_locations = []

    for location, data in location_flow.items():
        if not data["transitions_to"]:  # No way to get TO this location
            orphaned_locations.append(location)
        elif (
            len(data["required_by"]) > len(data["transitions_to"]) * 2
        ):  # More demand than supply
            poorly_connected_locations.append(location)

    return {
        "total_storylets": len(all_storylets),
        "variables_required": variables_required,
        "variables_set": variables_set,
        "missing_setters": list(missing_setters),
        "unused_setters": list(unused_setters),
        "location_flow": location_flow,
        "orphaned_locations": orphaned_locations,
        "poorly_connected_locations": poorly_connected_locations,
        "danger_distribution": danger_distribution,
        "connectivity_score": len(
            set(variables_set.keys()) & set(variables_required.keys())
        )
        / max(len(variables_required), 1),
        "recommendations": generate_gap_recommendations(
            missing_setters, unused_setters, location_flow, danger_distribution
        ),
    }


def generate_gap_recommendations(
    missing_setters: set,
    unused_setters: set,
    location_flow: Dict,
    danger_distribution: Dict,
) -> List[Dict[str, Any]]:
    """Generate specific recommendations for filling storylet gaps."""
    recommendations = []

    # Missing variable setters
    for var in missing_setters:
        if var == "has_key":
            recommendations.append(
                {
                    "type": "missing_setter",
                    "variable": var,
                    "priority": "high",
                    "suggestion": "Create storylets where players can find or earn keys (treasure chests, NPCs, solving puzzles)",
                    "themes": ["discovery", "puzzle", "reward"],
                    "example_choice": {
                        "label": "Take the rusty key",
                        "set": {"has_key": True},
                    },
                }
            )
        elif var == "has_torch":
            recommendations.append(
                {
                    "type": "missing_setter",
                    "variable": var,
                    "priority": "high",
                    "suggestion": "Create storylets where players can acquire torches (supply caches, crafting, trading)",
                    "themes": ["preparation", "resource_management", "social"],
                    "example_choice": {
                        "label": "Light a torch from the fire",
                        "set": {"has_torch": True},
                    },
                }
            )

    # Unused variable usage
    for var in unused_setters:
        if var == "gold":
            recommendations.append(
                {
                    "type": "unused_variable",
                    "variable": var,
                    "priority": "medium",
                    "suggestion": "Create storylets that require gold (trading, bribes, special purchases)",
                    "themes": ["social", "trade", "upgrade"],
                    "example_requirement": {"gold": {"gte": 10}},
                }
            )
        elif var == "notes":
            recommendations.append(
                {
                    "type": "unused_variable",
                    "variable": var,
                    "priority": "medium",
                    "suggestion": "Create storylets that reference or require specific notes (lore, puzzle solutions, maps)",
                    "themes": ["mystery", "puzzle", "story_development"],
                    "example_requirement": {"notes": "Marked a vein"},
                }
            )

    # Location connectivity issues
    poorly_connected = [
        loc
        for loc, data in location_flow.items()
        if len(data.get("required_by", [])) > len(data.get("transitions_to", [])) * 2
    ]

    for location in poorly_connected:
        recommendations.append(
            {
                "type": "location_connectivity",
                "location": location,
                "priority": "medium",
                "suggestion": f"Create more storylets that lead TO {location} - players need it but can't easily get there",
                "themes": ["exploration", "transition"],
                "example_choice": {
                    "label": f"Head to the {location}",
                    "set": {"location": location},
                },
            }
        )

    return recommendations


def generate_targeted_storylets(
    db: Session, max_storylets: int = 5
) -> List[Dict[str, Any]]:
    """
    Generate storylets specifically targeted at filling identified gaps.

    Args:
        db: Database session
        max_storylets: Maximum number of storylets to generate

    Returns:
        List of targeted storylet data
    """
    analysis = analyze_storylet_gaps(db)
    recommendations = analysis["recommendations"]

    if not recommendations:
        return []

    # Build targeted prompts based on recommendations
    targeted_prompts = []

    # Group recommendations by priority
    high_priority = [r for r in recommendations if r.get("priority") == "high"]
    medium_priority = [r for r in recommendations if r.get("priority") == "medium"]

    # Create prompts for high priority gaps first
    for rec in high_priority[:3]:  # Limit to top 3 high priority
        if rec["type"] == "missing_setter":
            targeted_prompts.append(
                {
                    "themes": rec["themes"],
                    "bible": {
                        "urgent_need": f"CRITICAL: Must create storylets that set {rec['variable']} = True",
                        "gap_analysis": f"Players need {rec['variable']} but no storylets currently provide it",
                        "suggestion": rec["suggestion"],
                        "required_choice_example": rec["example_choice"],
                        "connectivity_focus": "high_priority_gap_filling",
                    },
                }
            )

    # Add medium priority recommendations
    for rec in medium_priority[:2]:  # Limit to top 2 medium priority
        if rec["type"] == "unused_variable":
            targeted_prompts.append(
                {
                    "themes": rec["themes"],
                    "bible": {
                        "optimization_need": f"Create storylets that USE {rec['variable']} in requirements",
                        "gap_analysis": f"{rec['variable']} is set by choices but never required - wasted narrative potential",
                        "suggestion": rec["suggestion"],
                        "required_requirement_example": rec.get(
                            "example_requirement", {}
                        ),
                        "connectivity_focus": "variable_utilization",
                    },
                }
            )
        elif rec["type"] == "location_connectivity":
            targeted_prompts.append(
                {
                    "themes": rec["themes"],
                    "bible": {
                        "location_need": f"Create storylets that transition TO {rec['location']}",
                        "gap_analysis": f"{rec['location']} is required by many storylets but hard to reach",
                        "suggestion": rec["suggestion"],
                        "required_choice_example": rec.get("example_choice", {}),
                        "connectivity_focus": "location_flow_improvement",
                    },
                }
            )

    # Generate storylets for each targeted prompt
    all_generated = []
    for prompt in targeted_prompts[:max_storylets]:
        try:
            storylets = llm_suggest_storylets(1, prompt["themes"], prompt["bible"])
            all_generated.extend(storylets)
        except Exception as e:
            logger.error(f"Error generating targeted storylet: {e}")

    return all_generated[:max_storylets]


def get_ai_learning_context(db: Session) -> Dict[str, Any]:
    """
    Create a comprehensive context for AI learning from current storylet state.

    Returns:
        Rich context data that helps AI understand the current story world
    """
    analysis = analyze_storylet_gaps(db)

    return {
        "world_state_analysis": {
            "total_content": analysis["total_storylets"],
            "connectivity_health": analysis["connectivity_score"],
            "story_flow_issues": analysis["missing_setters"]
            + analysis["orphaned_locations"],
        },
        "variable_ecosystem": {
            "well_connected": list(
                set(analysis["variables_set"].keys())
                & set(analysis["variables_required"].keys())
            ),
            "needs_sources": analysis["missing_setters"],
            "needs_usage": analysis["unused_setters"],
        },
        "location_network": {
            "established_locations": list(analysis["location_flow"].keys()),
            "flow_problems": analysis["poorly_connected_locations"],
            "isolated_locations": analysis["orphaned_locations"],
        },
        "narrative_balance": analysis["danger_distribution"],
        "improvement_priorities": analysis["recommendations"][
            :3
        ],  # Top 3 most important
        "successful_patterns": _identify_successful_patterns(analysis),
    }


def _identify_successful_patterns(analysis: Dict) -> List[str]:
    """Identify what's working well in the current storylets."""
    patterns = []

    # Well-connected variables
    connected_vars = set(analysis["variables_set"].keys()) & set(
        analysis["variables_required"].keys()
    )
    if connected_vars:
        patterns.append(f"Good variable flow for: {', '.join(connected_vars)}")

    # Balanced danger levels
    danger_dist = analysis["danger_distribution"]
    total_danger_storylets = sum(danger_dist.values())
    if total_danger_storylets > 0:
        balance_score = (
            min(danger_dist.values()) / max(danger_dist.values())
            if max(danger_dist.values()) > 0
            else 0
        )
        if balance_score > 0.3:  # Reasonably balanced
            patterns.append("Well-balanced danger progression")

    # Active locations
    active_locations = [
        loc
        for loc, data in analysis["location_flow"].items()
        if data["required_by"] and data["transitions_to"]
    ]
    if active_locations:
        patterns.append(f"Active location network: {', '.join(active_locations[:3])}")

    return patterns
