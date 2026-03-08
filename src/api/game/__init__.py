"""Game API package composed from topic-focused subrouters."""

from fastapi import APIRouter

from ...services import session_service
from . import action, entities, metrics, prefetch, settings_api, spatial, state, story, turn, world

router = APIRouter()
router.include_router(story.router)
router.include_router(state.router)
router.include_router(spatial.router)
router.include_router(world.router)
router.include_router(action.router)
router.include_router(turn.router)
router.include_router(prefetch.router)
router.include_router(settings_api.router)
router.include_router(metrics.router)
router.include_router(entities.router)

# Minimal compatibility exports retained for shared tests/fixtures.
_state_managers = session_service._state_managers
_spatial_navigators = session_service._spatial_navigators
cleanup_old_sessions = state.cleanup_old_sessions
