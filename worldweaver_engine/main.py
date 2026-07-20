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
from src.services.request_limits import AUTH_RATE_LIMITED_PATHS, FixedWindowRateLimiter
from src.services import runtime_metrics
from src.services.llm_client import reset_trace_id, set_trace_id
from src.api import game
from src.api.auth import router as auth_router
from src.api.shard import router as shard_router
from src.database import SessionLocal
from src.services.shard_experience import configured_shard_experience


def _validate_runtime_settings() -> None:
    logger = logging.getLogger(__name__)
    missing: list[str] = []
    if settings.jwt_secret == "CHANGE_ME_IN_PRODUCTION":
        missing.append("WW_JWT_SECRET")
    if not str(settings.data_encryption_key or settings.jwt_secret or "").strip():
        missing.append("WW_DATA_ENCRYPTION_KEY")
    if settings.require_email_verification:
        if not str(settings.resend_api_key or "").strip():
            missing.append("RESEND_API_KEY")
        if not str(settings.resend_from_email or "").strip():
            missing.append("RESEND_FROM_EMAIL")
    if settings.shard_type == "city":
        if not str(settings.federation_url or "").strip():
            missing.append("FEDERATION_URL")
        if not str(settings.public_url or "").strip():
            missing.append("WW_PUBLIC_URL")
    if missing:
        logger.error("Runtime configuration incomplete: %s", ", ".join(sorted(set(missing))))


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
    import asyncio

    _validate_runtime_settings()
    experience = configured_shard_experience()
    if experience.game_rules_active:
        logging.getLogger(__name__).info(
            "Game shard declaration active: ruleset=%s version=%s",
            experience.ruleset.id if experience.ruleset else "unknown",
            experience.ruleset.version if experience.ruleset else "unknown",
        )
    # Startup code — run Alembic migrations (creates tables on fresh DB,
    # applies pending migrations on existing DB).
    _run_migrations()

    active_capabilities = {item.id for item in experience.entry_disclosure.capabilities}
    if experience.game_rules_active and "replenishing_materials" in active_capabilities:
        from src.services.material_making import initialize_material_pools

        material_db = SessionLocal()
        try:
            initialize_material_pools(material_db)
        finally:
            material_db.close()

    # Federation pulse loop — city shards only, when FEDERATION_URL is set
    _pulse_task = None
    if settings.shard_type == "city" and settings.federation_url:
        from src.services.federation_pulse import run_pulse_loop

        _pulse_task = asyncio.create_task(run_pulse_loop(SessionLocal, settings.federation_pulse_interval))
        logging.getLogger(__name__).info("Federation pulse loop started → %s", settings.federation_url)

    yield

    # Shutdown code
    if _pulse_task is not None:
        _pulse_task.cancel()


# FastAPI Setup
app = FastAPI(title="WorldWeaver Backend", version="0.1", lifespan=lifespan)

# Browser origins are permissive for local development and explicit in public folders.
cors_origins = settings.get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_auth_rate_limiter = FixedWindowRateLimiter()


@app.middleware("http")
async def limit_public_account_entry(request, call_next):
    """Slow password and account probing without affecting ordinary world actions."""
    if request.url.path in AUTH_RATE_LIMITED_PATHS:
        remote = request.client.host if request.client else "unknown"
        if settings.trust_cloudflare_proxy:
            remote = str(request.headers.get("CF-Connecting-IP") or remote).strip()
        allowed, retry_after = _auth_rate_limiter.allow(
            f"{request.url.path}:{remote}",
            limit=settings.auth_rate_limit_per_minute,
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many account requests. Try again shortly."},
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)


# Include routers
app.include_router(game.router, prefix="/api", tags=["game"])
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(shard_router)

# Federation router — only active on world shard
if settings.shard_type == "world":
    from src.api.federation.routes import router as federation_router

    app.include_router(federation_router)


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
