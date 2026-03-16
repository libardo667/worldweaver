"""Player-specific API key resolution and demo-expiry enforcement."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Player
from .identity_crypto import decrypt_text
from .llm_client import InferencePolicy, actor_private_policy
from .federation_identity import get_actor_bundle, ensure_local_player_projection


def refresh_player_api_key_cache(db: Session, player: Player) -> Player:
    actor_id = str(player.actor_id or "").strip()
    if not actor_id:
        return player
    bundle = get_actor_bundle(db, actor_id)
    return ensure_local_player_projection(db, bundle)


def resolve_player_api_key(db: Session, player: Optional[Player]) -> str | None:
    if player is None:
        return None
    raw = decrypt_text(player.api_key_enc)
    if raw:
        return raw
    refreshed = refresh_player_api_key_cache(db, player)
    return decrypt_text(refreshed.api_key_enc)


def ensure_actor_key_or_demo_access(db: Session, player: Optional[Player]) -> Optional[str]:
    player_key = resolve_player_api_key(db, player)
    if player_key:
        return player_key
    now = datetime.now(timezone.utc)
    if now > settings.get_demo_key_expiry():
        raise HTTPException(
            status_code=402,
            detail={"error": "observer_mode_required", "message": "Add your own API key to continue acting."},
        )
    return None


def actor_inference_owner_id(player: Optional[Player], *, fallback: str = "") -> str:
    if player is None:
        return str(fallback or "").strip()
    actor_id = str(player.actor_id or "").strip()
    if actor_id:
        return actor_id
    player_id = str(player.id or "").strip()
    if player_id:
        return player_id
    return str(fallback or "").strip()


def build_actor_private_inference_policy(
    db: Session,
    player: Optional[Player],
    *,
    owner_id: str = "",
) -> InferencePolicy:
    actor_key = ensure_actor_key_or_demo_access(db, player)
    resolved_owner_id = actor_inference_owner_id(player, fallback=owner_id)
    return actor_private_policy(
        owner_id=resolved_owner_id,
        actor_api_key=actor_key,
        allow_platform_fallback=not bool(actor_key),
    )
