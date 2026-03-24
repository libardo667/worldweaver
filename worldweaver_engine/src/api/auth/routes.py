"""Auth endpoints: register, login, me."""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Player
from ...services.auth_service import (
    create_access_token,
    require_player,
)
from ...services.email_service import send_password_reset_email, send_welcome_email
from ...services.federation_identity import (
    current_shard_id,
    ensure_local_player_projection,
    login_human_actor,
    request_password_reset,
    register_human_actor,
    reset_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,40}$")

TERMS_TEXT = (
    "WorldWeaver is a shared, mixed-intelligence space. "
    "By registering you agree not to harass other players or agents, "
    "to respect the collaborative fiction, and to participate in good faith."
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=40)
    display_name: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)
    pass_type: str = Field(default="citizen")
    terms_accepted: bool

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not _USERNAME_RE.match(v):
            raise ValueError("username must be 3–40 alphanumeric characters or underscores")
        return v.lower()

    @field_validator("terms_accepted")
    @classmethod
    def must_accept_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the terms to register")
        return v

    @field_validator("pass_type")
    @classmethod
    def validate_pass_type(cls, v: str) -> str:
        if v not in ("visitor_7day", "citizen"):
            raise ValueError("pass_type must be visitor_7day or citizen")
        return "citizen"


class LoginRequest(BaseModel):
    identifier: Optional[str] = None
    username: Optional[str] = None
    password: str

    @property
    def normalized_identifier(self) -> str:
        return str(self.identifier or self.username or "").strip().lower()


class PasswordResetRequest(BaseModel):
    identifier: str

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        value = str(v or "").strip().lower()
        if not value:
            raise ValueError("identifier is required")
        return value


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(..., min_length=12, max_length=256)
    new_password: str = Field(..., min_length=8, max_length=128)


class AuthResponse(BaseModel):
    token: str
    actor_id: str
    player_id: str
    username: str
    display_name: str
    pass_type: str
    pass_expires_at: Optional[str]
    terms_text: str = TERMS_TEXT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(player: Player, token: str) -> AuthResponse:
    return AuthResponse(
        token=token,
        actor_id=str(player.actor_id or ""),
        player_id=player.id,
        username=player.username,
        display_name=player.display_name,
        pass_type=player.pass_type,
        pass_expires_at=player.pass_expires_at.isoformat() if player.pass_expires_at else None,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/terms")
def get_terms():
    """Return the terms of service text."""
    return {"terms": TERMS_TEXT}


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    bundle = register_human_actor(
        db,
        origin_shard=current_shard_id(),
        email=str(payload.email).strip().lower(),
        username=payload.username,
        display_name=payload.display_name,
        password=payload.password,
        pass_type=payload.pass_type,
        terms_accepted=bool(payload.terms_accepted),
    )
    player = ensure_local_player_projection(db, bundle)

    send_welcome_email(str(payload.email), payload.display_name)

    return _make_response(player, create_access_token(str(player.actor_id or player.id)))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    if not payload.normalized_identifier:
        raise HTTPException(status_code=422, detail="identifier is required")
    bundle = login_human_actor(
        db,
        username=payload.normalized_identifier,
        password=payload.password,
    )
    player = ensure_local_player_projection(db, bundle)

    return _make_response(player, create_access_token(str(player.actor_id or player.id)))


@router.post("/request-password-reset")
def request_password_reset_route(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    result = request_password_reset(db, identifier=payload.identifier)
    reset_token = str(result.get("reset_token") or "").strip()
    email = str(result.get("email") or "").strip()
    display_name = str(result.get("display_name") or "").strip()
    if reset_token and email:
        send_password_reset_email(email, display_name or payload.identifier, reset_token)
    return {"ok": True}


@router.post("/reset-password", response_model=AuthResponse)
def reset_password_route(payload: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    bundle = reset_password(
        db,
        token=payload.token.strip(),
        new_password=payload.new_password,
    )
    player = ensure_local_player_projection(db, bundle)
    return _make_response(player, create_access_token(str(player.actor_id or player.id)))


@router.get("/me", response_model=AuthResponse)
def me(player: Player = Depends(require_player)):
    # Re-issue a fresh token so long-lived sessions stay alive
    return _make_response(player, create_access_token(str(player.actor_id or player.id)))
