# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Public information a person or resident can inspect before entering."""

from fastapi import APIRouter

from ...config import settings
from ...services.city_pack_service import get_city_pack_preview
from ...services.shard_experience import PublicShardExperience, configured_shard_experience

router = APIRouter(prefix="/api/shard", tags=["shard"])


@router.get("/experience", response_model=PublicShardExperience)
def get_shard_experience() -> PublicShardExperience:
    """Describe any optional game rules without exposing steward internals."""

    return configured_shard_experience()


@router.get("/city-pack/preview")
def get_current_city_pack_preview() -> dict:
    """Preview this node's published place pack before anyone enters it."""

    return get_city_pack_preview(settings.city_id)
