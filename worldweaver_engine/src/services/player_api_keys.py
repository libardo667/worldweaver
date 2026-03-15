"""Player-specific API key resolution and demo-expiry enforcement."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Player
from .identity_crypto import decrypt_text
from .llm_client import reset_request_api_key, set_request_api_key
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


def bind_request_api_key(db: Session, player: Optional[Player]):
    player_key = ensure_actor_key_or_demo_access(db, player)
    if not player_key:
        return None
    return set_request_api_key(player_key)


def reset_bound_request_api_key(token) -> None:
    if token is None:
        return
    reset_request_api_key(token)
