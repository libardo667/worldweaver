"""Settings and model configuration API endpoints.

Lets the game client display available models, estimated costs, and
switch models at runtime without restarting the server.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...config import settings
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


class SettingsReadinessResponse(BaseModel):
    ready: bool
    missing: list[str]


class ApiKeyUpdateRequest(BaseModel):
    api_key: str = Field(..., description="OpenRouter API key")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/settings/readiness", response_model=SettingsReadinessResponse)
def get_settings_readiness():
    """Check if the system has a valid API key and model configured."""
    missing = []
    if not settings.get_effective_api_key():
        missing.append("api_key")
    if not settings.llm_model:
        missing.append("model")

    return SettingsReadinessResponse(ready=len(missing) == 0, missing=missing)


@router.post("/settings/key")
def update_api_key(request: ApiKeyUpdateRequest):
    """Update the OpenRouter API key at runtime.

    The key is stored in memory and takes effect immediately.
    """
    key = request.api_key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="API key must not be blank.")

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
def get_current_model():
    """Get the currently active model with cost estimate."""
    model_id = get_model()
    info = get_model_info(model_id) or {}

    return CurrentModelResponse(
        model_id=model_id,
        label=info.get("label", model_id),
        tier=info.get("tier", "unknown"),
        creative_quality=info.get("creative_quality", 0),
        context_window=info.get("context_window", 0),
        ai_enabled=not is_ai_disabled(),
        api_key_configured=bool(settings.get_effective_api_key()),
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
