"""Main FastAPI application."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

from src.database import create_tables
from src.config import settings
from src.services.seed_data import seed_if_empty
from src.api import author, game, semantic


def _run_migrations() -> None:
    """Run Alembic migrations to bring the database schema up to date.

    Skipped during pytest runs — tests create their own in-memory databases
    via conftest fixtures and don't need file-based migrations.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return

    cfg = AlembicConfig(
        os.path.join(os.path.dirname(__file__), "alembic.ini")
    )
    cfg.set_main_option(
        "script_location",
        os.path.join(os.path.dirname(__file__), "alembic"),
    )
    alembic_command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup code — run Alembic migrations (creates tables on fresh DB,
    # applies pending migrations on existing DB).
    _run_migrations()
    # Run seeding in a background worker so it creates/commits its own session
    # (keeps startup non-blocking and ensures seeds persist).
    await seed_if_empty(
        in_background=True,
        allow_legacy_seed=settings.enable_legacy_test_seeds,
    )
    yield
    # Shutdown code
    # (none for now)


# FastAPI Setup
app = FastAPI(title="DwarfWeave Backend", version="0.1", lifespan=lifespan)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(game.router, prefix="/api", tags=["game"])
app.include_router(author.router, prefix="/author", tags=["author"])
app.include_router(semantic.router, prefix="/api/semantic", tags=["semantic"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler so unhandled exceptions return 500 with a safe message."""
    logging.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat() + "Z"}
