"""Author API package composed from focused subrouters."""

import logging

from fastapi import APIRouter

from ...models import SessionVars, Storylet
from ...services.storylet_ingest import (
    assign_spatial_to_storylets,
    deduplicate_and_insert,
    postprocess_new_storylets,
    run_auto_improvements,
    save_storylets_with_postprocessing,
)
from . import generate, populate, suggest, world

logger = logging.getLogger(__name__)

router = APIRouter()
router.include_router(suggest.router)
router.include_router(populate.router)
router.include_router(generate.router)
router.include_router(world.router)

# Compatibility re-exports for pre-refactor tests/imports.
author_suggest = suggest.author_suggest
populate_storylets = populate.populate_storylets
debug_game_state = world.debug_game_state
generate_intelligent_storylets = generate.generate_intelligent_storylets
get_storylet_analysis = generate.get_storylet_analysis
generate_targeted_storylets = generate.generate_targeted_storylets
generate_world_from_description = world.generate_world_from_description
