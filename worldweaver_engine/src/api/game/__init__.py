# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Game API package composed from topic-focused subrouters."""

from fastapi import APIRouter

from ...services import session_service
from . import access, action, exchanges, making, metrics, objects, settings_api, state, stoops, world

router = APIRouter()
router.include_router(state.router)
router.include_router(world.router)
router.include_router(objects.router)
router.include_router(making.router)
router.include_router(access.router)
router.include_router(exchanges.router)
router.include_router(stoops.router)
router.include_router(action.router)
router.include_router(settings_api.router)
router.include_router(metrics.router)

# Minimal compatibility exports retained for shared tests/fixtures.
_state_managers = session_service._state_managers
cleanup_old_sessions = state.cleanup_old_sessions
