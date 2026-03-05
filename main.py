"""Main FastAPI application."""

import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from alembic.config import Config as AlembicConfig
from alembic import command as alembic_command

from src.config import settings
from src.services.seed_data import seed_if_empty
from src.services import runtime_metrics
from src.services.llm_client import reset_trace_id, set_trace_id
from src.api import author, game, semantic


def _run_migrations() -> None:
    """Run Alembic migrations to bring the database schema up to date.

    Skipped during pytest runs — tests create their own in-memory databases
    via conftest fixtures and don't need file-based migrations.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return

    cfg = AlembicConfig(os.path.join(os.path.dirname(__file__), "alembic.ini"))
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
app = FastAPI(title="WorldWeaver Backend", version="0.1", lifespan=lifespan)

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


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    """Bind a correlation id for each request and emit lifecycle logs."""
    incoming = request.headers.get("X-WW-Trace-Id") or request.headers.get("X-Correlation-Id") or request.headers.get("X-Request-Id")
    trace_id = str(incoming or "").strip() or uuid.uuid4().hex
    route = str(request.url.path or "")
    request.state.trace_id = trace_id
    request.state.correlation_id = trace_id

    trace_token = set_trace_id(trace_id)
    metrics_route_token = runtime_metrics.bind_metrics_route(route)
    started = time.perf_counter()
    logger = logging.getLogger("worldweaver.request")
    logger.info(
        json.dumps(
            {
                "event": "request_start",
                "trace_id": trace_id,
                "correlation_id": trace_id,
                "route": route,
                "method": request.method,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )

    status_code = 500
    try:
        response = await call_next(request)
        status_code = int(getattr(response, "status_code", 200) or 200)
    except Exception:
        logger.exception(
            json.dumps(
                {
                    "event": "request_error",
                    "trace_id": trace_id,
                    "correlation_id": trace_id,
                    "route": route,
                    "method": request.method,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        raise
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
        logger.info(
            json.dumps(
                {
                    "event": "request_end",
                    "trace_id": trace_id,
                    "correlation_id": trace_id,
                    "route": route,
                    "method": request.method,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
        runtime_metrics.reset_metrics_route(metrics_route_token)
        reset_trace_id(trace_token)

    response.headers.setdefault("X-WW-Trace-Id", trace_id)
    response.headers.setdefault("X-Correlation-Id", trace_id)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler so unhandled exceptions return 500 with a safe message."""
    logging.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat() + "Z"}
