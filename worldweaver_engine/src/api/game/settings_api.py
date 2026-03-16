"""Settings and model configuration API endpoints.

Lets the game client display available models, estimated costs, and
switch models at runtime without restarting the server.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...models import Player
from ...services.auth_service import get_current_player_strict
from ...services.federation_identity import upsert_actor_api_key
from ...services.identity_crypto import decrypt_text
from ...services.llm_client import get_model, is_ai_disabled
from ...services.model_registry import (
    MODEL_REGISTRY,
    estimate_session_cost,
    get_model_info,
    list_available_models,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------


class ModelSummary(BaseModel):
    model_id: str
    label: str
    tier: str
    creative_quality: int
    context_window: int
    estimated_10_turn_cost_usd: float
    notes: str


class CurrentModelResponse(BaseModel):
    model_id: str
    label: str
    tier: str
    creative_quality: int
    context_window: int
    ai_enabled: bool
    api_key_configured: bool
    estimated_session_cost: dict


class ModelSwitchRequest(BaseModel):
    model_id: str = Field(
        ...,
        description="OpenRouter model ID, e.g. 'arcee-ai/trinity-large-preview:free'",
    )


class ModelSwitchResponse(BaseModel):
    success: bool
    previous_model: str
    current_model: str
    label: str
    tier: str
    estimated_10_turn_cost_usd: float
    message: str


class ReadinessCheck(BaseModel):
    code: str
    label: str
    ok: bool
    severity: Literal["error", "warn", "info"]
    message: str


class ShardReadinessSummary(BaseModel):
    shard_id: str
    city_id: str | None = None
    shard_type: str
    public_url: str | None = None
    federation_url: str | None = None
    demo_key_expires_at: str | None = None


class SettingsReadinessResponse(BaseModel):
    ready: bool
    startup_ready: bool
    missing: list[str]
    v3_runtime: Dict[str, Any] = Field(default_factory=dict)
    runtime_missing: list[str] = Field(default_factory=list)
    checks: list[ReadinessCheck] = Field(default_factory=list)
    shard: ShardReadinessSummary


class ApiKeyUpdateRequest(BaseModel):
    api_key: str = Field(..., description="OpenRouter API key")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/settings/readiness", response_model=SettingsReadinessResponse)
def get_settings_readiness():
    """Check if the system has a valid API key and model configured."""
    missing = []
    effective_api_key = bool(settings.get_effective_api_key())
    model_configured = bool(settings.llm_model)

    if not effective_api_key:
        missing.append("api_key")
    if not model_configured:
        missing.append("model")

    jwt_ready = bool(str(settings.jwt_secret or "").strip()) and str(settings.jwt_secret or "").strip() != "CHANGE_ME_IN_PRODUCTION"
    encryption_ready = bool(str(settings.data_encryption_key or "").strip())
    federation_url_ready = settings.shard_type != "city" or bool(str(settings.federation_url or "").strip())
    public_url_ready = settings.shard_type != "city" or bool(str(settings.public_url or "").strip())
    federation_token_ready = settings.shard_type != "city" or bool(str(settings.federation_token or "").strip())
    resend_ready = bool(str(settings.resend_api_key or "").strip()) and bool(str(settings.resend_from_email or "").strip())
    demo_active = datetime.now(timezone.utc) <= settings.get_demo_key_expiry()
    observer_mode_required = not effective_api_key and not demo_active
    demo_access_ready = effective_api_key or demo_active
    agent_inference_key_ready = bool(
        str(os.environ.get("WW_INFERENCE_KEY") or "").strip()
        or str(os.environ.get("OPENROUTER_API_KEY") or "").strip()
        or str(settings.openrouter_api_key or "").strip()
    )
    agent_inference_model_ready = bool(
        str(os.environ.get("WW_INFERENCE_MODEL") or "").strip()
        or str(settings.llm_model or "").strip()
    )

    runtime_missing = []
    if not jwt_ready:
        runtime_missing.append("jwt_secret")
    if not encryption_ready:
        runtime_missing.append("data_encryption_key")
    if settings.shard_type == "city":
        if not federation_url_ready:
            runtime_missing.append("federation_url")
        if not public_url_ready:
            runtime_missing.append("public_url")

    checks = [
        ReadinessCheck(
            code="api_key",
            label="Narration key",
            ok=effective_api_key,
            severity="error",
            message=(
                "A runtime API key is configured."
                if effective_api_key
                else "No runtime API key is configured for narration."
            ),
        ),
        ReadinessCheck(
            code="model",
            label="Narration model",
            ok=model_configured,
            severity="error",
            message=(
                f"Narration model set to {settings.llm_model}."
                if model_configured
                else "No narration model is configured."
            ),
        ),
        ReadinessCheck(
            code="jwt_secret",
            label="JWT signing",
            ok=jwt_ready,
            severity="error",
            message=(
                "JWT signing secret is configured."
                if jwt_ready
                else "JWT signing secret is still using the placeholder value."
            ),
        ),
        ReadinessCheck(
            code="data_encryption_key",
            label="Data encryption",
            ok=encryption_ready,
            severity="error",
            message=(
                "Data encryption key is configured."
                if encryption_ready
                else "Data encryption key is missing."
            ),
        ),
        ReadinessCheck(
            code="federation_url",
            label="Federation root",
            ok=federation_url_ready,
            severity="error",
            message=(
                "Not required on the world shard."
                if settings.shard_type != "city"
                else (
                    f"Federation root set to {settings.federation_url}."
                    if federation_url_ready
                    else "City shard has no federation root URL configured."
                )
            ),
        ),
        ReadinessCheck(
            code="public_url",
            label="Public shard URL",
            ok=public_url_ready,
            severity="error",
            message=(
                "Not required on the world shard."
                if settings.shard_type != "city"
                else (
                    f"Public shard URL set to {settings.public_url}."
                    if public_url_ready
                    else "City shard has no public URL configured."
                )
            ),
        ),
        ReadinessCheck(
            code="federation_token",
            label="Federation token",
            ok=federation_token_ready,
            severity="warn",
            message=(
                "Not required on the world shard."
                if settings.shard_type != "city"
                else (
                    "Federation auth token is configured."
                    if federation_token_ready
                    else "Federation auth token is missing."
                )
            ),
        ),
        ReadinessCheck(
            code="email_delivery",
            label="Welcome email",
            ok=resend_ready,
            severity="warn",
            message=(
                f"Welcome email configured from {settings.resend_from_email}."
                if resend_ready
                else "Welcome email delivery is not configured."
            ),
        ),
        ReadinessCheck(
            code="demo_access",
            label="Demo access window",
            ok=demo_access_ready,
            severity="warn",
            message=(
                "Runtime API key is configured, so demo access is not required."
                if effective_api_key
                else (
                    f"Demo access remains active until {settings.get_demo_key_expiry().isoformat()}."
                    if demo_active
                    else f"Demo access expired on {settings.get_demo_key_expiry().isoformat()}."
                )
            ),
        ),
        ReadinessCheck(
            code="observer_mode",
            label="Observer mode fallback",
            ok=not observer_mode_required,
            severity="warn",
            message=(
                "Human players can still act without supplying a personal key."
                if not observer_mode_required
                else "Players need their own API key to act; otherwise they enter observer mode."
            ),
        ),
        ReadinessCheck(
            code="agent_inference_key",
            label="Agent inference key",
            ok=agent_inference_key_ready,
            severity="warn",
            message=(
                "Agent inference key is configured."
                if agent_inference_key_ready
                else "Agent inference key is missing from the shard runtime."
            ),
        ),
        ReadinessCheck(
            code="agent_inference_model",
            label="Agent inference model",
            ok=agent_inference_model_ready,
            severity="warn",
            message=(
                "Agent inference model is configured."
                if agent_inference_model_ready
                else "Agent inference model is missing from the shard runtime."
            ),
        ),
    ]
    startup_ready = all(check.ok for check in checks if check.severity == "error")

    return SettingsReadinessResponse(
        ready=len(missing) == 0,
        startup_ready=startup_ready,
        missing=missing,
        v3_runtime=settings.get_v3_runtime_settings(),
        runtime_missing=runtime_missing,
        checks=checks,
        shard=ShardReadinessSummary(
            shard_id=settings.city_id if settings.shard_type != "world" else "ww_world",
            city_id=settings.city_id,
            shard_type=settings.shard_type,
            public_url=settings.public_url,
            federation_url=settings.federation_url,
            demo_key_expires_at=settings.get_demo_key_expiry().isoformat(),
        ),
    )


@router.post("/settings/key")
def update_api_key(
    request: ApiKeyUpdateRequest,
    db: Session = Depends(get_db),
    player: Player | None = Depends(get_current_player_strict),
):
    """Update the OpenRouter API key at runtime.

    Authenticated players store a personal federation-bound key; unauthenticated
    callers keep the legacy in-memory admin override path.
    """
    key = request.api_key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="API key must not be blank.")

    if player is not None and str(player.actor_id or "").strip():
        bundle = upsert_actor_api_key(db, actor_id=str(player.actor_id), api_key=key)
        player.api_key_enc = bundle.api_key_enc
        db.commit()
        return {"success": True, "message": "Personal API key updated."}

    settings.openrouter_api_key = key
    logger.info("OpenRouter API key updated at runtime.")
    return {"success": True, "message": "API key updated."}


@router.get("/models", response_model=list[ModelSummary])
def list_models():
    """List all available models with pricing and quality info.

    Returns models sorted by cost (free first, then ascending).
    """
    return list_available_models()


@router.get("/model", response_model=CurrentModelResponse)
def get_current_model(player: Player | None = Depends(get_current_player_strict)):
    """Get the currently active model with cost estimate."""
    model_id = get_model()
    info = get_model_info(model_id) or {}
    player_api_key = decrypt_text(player.api_key_enc) if player is not None else None

    return CurrentModelResponse(
        model_id=model_id,
        label=info.get("label", model_id),
        tier=info.get("tier", "unknown"),
        creative_quality=info.get("creative_quality", 0),
        context_window=info.get("context_window", 0),
        ai_enabled=not is_ai_disabled(),
        api_key_configured=bool(player_api_key or settings.get_effective_api_key()),
        estimated_session_cost=estimate_session_cost(model_id, turns=10),
    )


@router.put("/model", response_model=ModelSwitchResponse)
def switch_model(request: ModelSwitchRequest):
    """Switch the active LLM model at runtime.

    The new model takes effect immediately for all subsequent LLM calls.
    Models not in the registry are allowed (for custom/new models) but
    will show $0.00 estimated cost.
    """
    new_model_id = request.model_id.strip()
    if not new_model_id:
        raise HTTPException(status_code=422, detail="model_id must not be blank.")

    previous_model = get_model()

    # Mutate the global settings — this is safe because Pydantic settings
    # objects are mutable and get_model() reads settings.llm_model directly.
    settings.llm_model = new_model_id

    info = get_model_info(new_model_id) or {}
    estimate = estimate_session_cost(new_model_id, turns=10)

    in_registry = new_model_id in MODEL_REGISTRY
    label = info.get("label", new_model_id)

    logger.info(
        "Model switched: %s → %s (%s)",
        previous_model,
        new_model_id,
        label,
    )

    return ModelSwitchResponse(
        success=True,
        previous_model=previous_model,
        current_model=new_model_id,
        label=label,
        tier=info.get("tier", "custom"),
        estimated_10_turn_cost_usd=estimate["total_cost_usd"],
        message=(f"Model switched to {label}." if in_registry else f"Model switched to {new_model_id} (not in registry — cost estimate unavailable)."),
    )
