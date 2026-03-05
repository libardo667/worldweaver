from typing import Any, Dict, List
from pydantic import BaseModel, ConfigDict
from src.services.state_manager import AdvancedStateManager
from src.services.spatial_navigator import SpatialNavigator
from src.database import get_db

class SceneCardOut(BaseModel):
    """A concise, immediate context bundle for the LLM to focus current generation."""
    model_config = ConfigDict(extra="ignore")
    
    location: str
    sublocation: str
    cast_on_stage: List[str]
    immediate_stakes: str
    constraints: List[str]
    active_goal: str
    goal_urgency: float
    goal_complication: float

def build_scene_card(
    state_manager: AdvancedStateManager,
    spatial_nav: SpatialNavigator,
) -> SceneCardOut:
    """Extract a focused SceneCard from the sprawling global state."""
    
    # 1. Location Data
    location = str(state_manager.get_variable("location", "unknown"))
    sublocation = "immediate surroundings"
    
    # Try to derive sublocation from storylet if we have a spatial map
    current_storylet_id = spatial_nav.storylet_positions.get(location)
    
    # 2. Cast on Stage (Who is actually here right now?)
    # We grab known relationships but filter to those recently interacted with or strongly tied
    known_people = []
    for rel_key, rel in state_manager.relationships.items():
        person = rel.entity_a if rel.entity_a != "player" else rel.entity_b
        # Simplistic heuristic: if there's high tension or recent interaction, they are "on stage"
        if rel.fear > 50 or rel.trust > 50 or rel.interaction_count > 3:
            known_people.append(person)
            
    # 3. Active Goals & Stakes
    primary_goal = state_manager.goal_state.primary_goal or "survive and explore"
    urgency = state_manager.goal_state.urgency
    complication = state_manager.goal_state.complication
    
    stakes = "Low stakes. Time to regroup."
    if state_manager.environment.danger_level > 6:
        stakes = "High immediate physical danger. Survival is the priority."
    elif complication > 0.6:
        stakes = "High narrative complication. Things are tangling rapidly."
        
    # 4. Affordances and Constraints
    constraints: List[str] = []
    if state_manager.environment.weather != "clear":
        constraints.append(f"Weather hazard: {state_manager.environment.weather}")
    if state_manager.environment.time_of_day == "night":
        constraints.append("Visibility: Low (Nighttime)")
        
    for item in state_manager.inventory.values():
        if item.quantity > 0:
            constraints.append(f"Carrying: {item.name}")
            
    # Default fallback if empty
    if not constraints:
        constraints.append("No immediate physical constraints apparent.")

    return SceneCardOut(
        location=location,
        sublocation=sublocation,
        cast_on_stage=known_people[:3],  # Keep it tight
        immediate_stakes=stakes,
        constraints=constraints,
        active_goal=primary_goal,
        goal_urgency=urgency,
        goal_complication=complication,
    )
