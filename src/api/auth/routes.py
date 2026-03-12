"""Auth endpoints: register, login, me."""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from ...database import get_db
from ...models import Player, SessionVars
from ...services.auth_service import (
    create_access_token,
    get_current_player,
    hash_password,
    require_player,
    verify_password,
)
from ...services.email_service import send_welcome_email

router = APIRouter(prefix="/auth", tags=["auth"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,40}$")

TERMS_TEXT = (
    "WorldWeaver is a shared, mixed-intelligence space. "
    "By registering you agree not to harass other players or agents, "
    "to respect the collaborative fiction, and to the 7-day visitor pass terms. "
    "You may upgrade to a permanent citizen pass at any time."
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=40)
    display_name: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)
    pass_type: str = Field(default="visitor_7day")
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
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
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
    if db.query(Player).filter(Player.email == str(payload.email)).first():
        raise HTTPException(status_code=409, detail="email_taken")
    if db.query(Player).filter(Player.username == payload.username).first():
        raise HTTPException(status_code=409, detail="username_taken")

    expires_at = None
    if payload.pass_type == "visitor_7day":
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    player = Player(
        id=str(uuid.uuid4()),
        email=str(payload.email),
        username=payload.username,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        pass_type=payload.pass_type,
        pass_expires_at=expires_at,
        terms_accepted_at=datetime.now(timezone.utc),
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    send_welcome_email(str(payload.email), payload.display_name)

    return _make_response(player, create_access_token(player.id))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    player = db.query(Player).filter(Player.username == payload.username.lower()).first()
    if not player or not verify_password(payload.password, player.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")

    return _make_response(player, create_access_token(player.id))


@router.get("/me", response_model=AuthResponse)
def me(player: Player = Depends(require_player)):
    # Re-issue a fresh token so long-lived sessions stay alive
    return _make_response(player, create_access_token(player.id))
