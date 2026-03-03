"""Author API package composed from focused subrouters."""

from fastapi import APIRouter

from ...models import SessionVars as SessionVars, Storylet as Storylet
from . import generate, populate, suggest, world

router = APIRouter()
router.include_router(suggest.router)
router.include_router(populate.router)
router.include_router(generate.router)
router.include_router(world.router)
