"""Game API package composed from topic-focused subrouters."""

import logging

from fastapi import APIRouter

from ...services.session_service import get_state_manager
from ...services.storylet_selector import pick_storylet_enhanced
from . import action, spatial, state, story, world

router = APIRouter()
router.include_router(story.router)
router.include_router(state.router)
router.include_router(spatial.router)
router.include_router(world.router)
router.include_router(action.router)

# Compatibility re-exports for tests and local imports.
_state_managers = state._state_managers
_spatial_navigators = state._spatial_navigators
save_state_to_db = state.save_state_to_db
_resolve_current_location = state._resolve_current_location

api_next = story.api_next
get_state_summary = state.get_state_summary
update_relationship = state.update_relationship
add_item_to_inventory = state.add_item_to_inventory
update_environment = state.update_environment
update_goal_state = state.update_goal_state
add_goal_milestone = state.add_goal_milestone
cleanup_old_sessions = state.cleanup_old_sessions
reset_session_world = state.reset_session_world
bootstrap_session_world = state.bootstrap_session_world

get_spatial_navigation = spatial.get_spatial_navigation
move_in_direction = spatial.move_in_direction
get_spatial_map = spatial.get_spatial_map
assign_spatial_positions = spatial.assign_spatial_positions

get_world_history_endpoint = world.get_world_history_endpoint
query_world_facts_endpoint = world.query_world_facts_endpoint
query_world_graph_facts_endpoint = world.query_world_graph_facts_endpoint
get_world_graph_neighborhood_endpoint = world.get_world_graph_neighborhood_endpoint
get_world_graph_location_facts_endpoint = world.get_world_graph_location_facts_endpoint
get_world_projection_endpoint = world.get_world_projection_endpoint

api_freeform_action = action.api_freeform_action
