# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Read-only shard readiness for the public client and steward diagnostics."""

import os
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ...config import settings
from ...services.federation_identity import current_shard_id

router = APIRouter()


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


class SettingsReadinessResponse(BaseModel):
    ready: bool
    startup_ready: bool
    missing: list[str]
    runtime_missing: list[str] = Field(default_factory=list)
    checks: list[ReadinessCheck] = Field(default_factory=list)
    shard: ShardReadinessSummary


@router.get("/settings/readiness", response_model=SettingsReadinessResponse)
def get_settings_readiness():
    """Report shard infrastructure without making human play depend on an LLM key."""
    jwt_ready = bool(str(settings.jwt_secret or "").strip()) and str(settings.jwt_secret or "").strip() != "CHANGE_ME_IN_PRODUCTION"
    encryption_ready = bool(str(settings.data_encryption_key or "").strip())
    federation_url_ready = settings.shard_type != "city" or bool(str(settings.federation_url or "").strip())
    public_url_ready = settings.shard_type != "city" or bool(str(settings.public_url or "").strip())
    federation_token_ready = settings.shard_type != "city" or bool(str(settings.federation_token or "").strip())
    resend_ready = bool(str(settings.resend_api_key or "").strip()) and bool(str(settings.resend_from_email or "").strip())
    agent_inference_key_ready = bool(str(os.environ.get("WW_INFERENCE_KEY") or "").strip() or str(os.environ.get("OPENROUTER_API_KEY") or "").strip() or str(settings.openrouter_api_key or "").strip())
    agent_inference_model_ready = bool(str(os.environ.get("WW_INFERENCE_MODEL") or "").strip() or str(settings.llm_model or "").strip())

    runtime_missing: list[str] = []
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
            code="jwt_secret",
            label="JWT signing",
            ok=jwt_ready,
            severity="error",
            message="JWT signing secret is configured." if jwt_ready else "JWT signing secret is still using the placeholder value.",
        ),
        ReadinessCheck(
            code="data_encryption_key",
            label="Data encryption",
            ok=encryption_ready,
            severity="error",
            message="Data encryption key is configured." if encryption_ready else "Data encryption key is missing.",
        ),
        ReadinessCheck(
            code="federation_url",
            label="Federation root",
            ok=federation_url_ready,
            severity="error",
            message=("Not required on the world shard." if settings.shard_type != "city" else f"Federation root set to {settings.federation_url}." if federation_url_ready else "City shard has no federation root URL configured."),
        ),
        ReadinessCheck(
            code="public_url",
            label="Public shard URL",
            ok=public_url_ready,
            severity="error",
            message=("Not required on the world shard." if settings.shard_type != "city" else f"Public shard URL set to {settings.public_url}." if public_url_ready else "City shard has no public URL configured."),
        ),
        ReadinessCheck(
            code="federation_token",
            label="Federation token",
            ok=federation_token_ready,
            severity="warn",
            message=("Not required on the world shard." if settings.shard_type != "city" else "Federation auth token is configured." if federation_token_ready else "Federation auth token is missing."),
        ),
        ReadinessCheck(
            code="email_delivery",
            label="Welcome email",
            ok=resend_ready,
            severity="warn",
            message=(f"Welcome email configured from {settings.resend_from_email}." if resend_ready else "Welcome email delivery is not configured."),
        ),
        ReadinessCheck(
            code="agent_inference_key",
            label="Resident inference key",
            ok=agent_inference_key_ready,
            severity="warn",
            message=("Resident inference key is configured." if agent_inference_key_ready else "Resident inference key is missing from the shard runtime. Human world actions still work."),
        ),
        ReadinessCheck(
            code="agent_inference_model",
            label="Resident inference model",
            ok=agent_inference_model_ready,
            severity="warn",
            message=("Resident inference model is configured." if agent_inference_model_ready else "Resident inference model is missing from the shard runtime. Human world actions still work."),
        ),
    ]
    startup_ready = all(check.ok for check in checks if check.severity == "error")

    return SettingsReadinessResponse(
        ready=startup_ready,
        startup_ready=startup_ready,
        missing=list(runtime_missing),
        runtime_missing=runtime_missing,
        checks=checks,
        shard=ShardReadinessSummary(
            shard_id=current_shard_id(),
            city_id=settings.city_id,
            shard_type=settings.shard_type,
            public_url=settings.public_url,
            federation_url=settings.federation_url,
        ),
    )
