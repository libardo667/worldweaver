"""Canonical actor identity helpers shared by shard auth and ww_world routes."""

from __future__ import annotations

import json
import logging
import secrets
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    FederationActor,
    FederationActorAuth,
    FederationActorSecret,
    FederationResident,
    Player,
)
from .auth_service import hash_password, verify_password
from .identity_crypto import encrypt_text

log = logging.getLogger(__name__)

_CITY_SHORT_CODES = {
    "san_francisco": "sfo",
    "portland": "pdx",
    "new_york": "jfk",
    "los_angeles": "lax",
    "seattle": "sea",
    "chicago": "ord",
    "miami": "mia",
    "austin": "aus",
    "denver": "den",
    "boston": "bos",
    "tokyo": "nrt",
    "london": "lhr",
    "paris": "cdg",
    "berlin": "ber",
    "nairobi": "nbo",
    "buenos_aires": "eze",
}


@dataclass
class ActorProjectionBundle:
    actor_id: str
    actor_type: str
    display_name: str
    handle: str
    email: str
    username: str
    password_hash: str
    pass_type: str
    pass_expires_at: Optional[str]
    terms_accepted_at: Optional[str]
    api_key_enc: Optional[str]
    home_shard: str
    current_shard: str
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "display_name": self.display_name,
            "handle": self.handle,
            "email": self.email,
            "username": self.username,
            "password_hash": self.password_hash,
            "pass_type": self.pass_type,
            "pass_expires_at": self.pass_expires_at,
            "terms_accepted_at": self.terms_accepted_at,
            "api_key_enc": self.api_key_enc,
            "home_shard": self.home_shard,
            "current_shard": self.current_shard,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ActorProjectionBundle":
        return cls(
            actor_id=str(payload.get("actor_id") or "").strip(),
            actor_type=str(payload.get("actor_type") or "human").strip() or "human",
            display_name=str(payload.get("display_name") or "").strip(),
            handle=str(payload.get("handle") or "").strip(),
            email=str(payload.get("email") or "").strip(),
            username=str(payload.get("username") or "").strip(),
            password_hash=str(payload.get("password_hash") or "").strip(),
            pass_type=str(payload.get("pass_type") or "visitor_7day").strip() or "visitor_7day",
            pass_expires_at=(str(payload.get("pass_expires_at")).strip() if payload.get("pass_expires_at") else None),
            terms_accepted_at=(str(payload.get("terms_accepted_at")).strip() if payload.get("terms_accepted_at") else None),
            api_key_enc=(str(payload.get("api_key_enc")).strip() if payload.get("api_key_enc") else None),
            home_shard=str(payload.get("home_shard") or "").strip(),
            current_shard=str(payload.get("current_shard") or "").strip(),
            status=str(payload.get("status") or "active").strip() or "active",
        )


def current_shard_id() -> str:
    if settings.shard_type == "world":
        return "ww_world"
    short = _CITY_SHORT_CODES.get(settings.city_id, str(settings.city_id or "")[:3])
    return f"ww_{short}"


def _iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = f"{raw[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _build_bundle(db: Session, actor_id: str) -> ActorProjectionBundle:
    actor = db.get(FederationActor, actor_id)
    auth = db.get(FederationActorAuth, actor_id)
    secret = db.get(FederationActorSecret, actor_id)
    if actor is None or auth is None:
        raise HTTPException(status_code=404, detail="actor_not_found")
    return ActorProjectionBundle(
        actor_id=actor.actor_id,
        actor_type=actor.actor_type,
        display_name=actor.display_name,
        handle=str(actor.handle or auth.username),
        email=auth.email,
        username=auth.username,
        password_hash=auth.password_hash,
        pass_type=auth.pass_type,
        pass_expires_at=_iso(auth.pass_expires_at),
        terms_accepted_at=_iso(auth.terms_accepted_at),
        api_key_enc=(secret.llm_api_key_enc if secret else None),
        home_shard=actor.home_shard,
        current_shard=actor.current_shard,
        status=actor.status,
    )


def register_human_actor_local(
    db: Session,
    *,
    origin_shard: str,
    email: str,
    username: str,
    display_name: str,
    password: str,
    pass_type: str,
    terms_accepted: bool,
) -> ActorProjectionBundle:
    if db.query(FederationActorAuth).filter(FederationActorAuth.email == email).first():
        raise HTTPException(status_code=409, detail="email_taken")
    if db.query(FederationActorAuth).filter(FederationActorAuth.username == username).first():
        raise HTTPException(status_code=409, detail="username_taken")

    actor_id = str(uuid.uuid4())
    expires_at = None
    if pass_type == "visitor_7day":
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    accepted_at = datetime.now(timezone.utc) if terms_accepted else None

    actor = FederationActor(
        actor_id=actor_id,
        actor_type="human",
        display_name=display_name,
        handle=username,
        home_shard=origin_shard,
        current_shard=origin_shard,
        status="active",
        origin="registered",
    )
    auth = FederationActorAuth(
        actor_id=actor_id,
        email=email,
        username=username,
        password_hash=hash_password(password),
        pass_type=pass_type,
        pass_expires_at=expires_at,
        terms_accepted_at=accepted_at,
    )
    db.add(actor)
    db.add(auth)
    db.commit()
    db.refresh(actor)
    db.refresh(auth)
    return _build_bundle(db, actor_id)


def login_human_actor_local(
    db: Session,
    *,
    username: str,
    password: str,
    current_shard: Optional[str] = None,
) -> ActorProjectionBundle:
    identifier = str(username or "").strip().lower()
    auth = (
        db.query(FederationActorAuth)
        .filter(
            (FederationActorAuth.username == identifier)
            | (FederationActorAuth.email == identifier)
        )
        .first()
    )
    if auth is None or not verify_password(password, auth.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    actor = db.get(FederationActor, auth.actor_id)
    if actor is not None and current_shard:
        actor.current_shard = current_shard
        db.commit()
    return _build_bundle(db, auth.actor_id)


def _reset_token_hash(token: str) -> str:
    return sha256(str(token or "").encode("utf-8")).hexdigest()


def request_password_reset_local(db: Session, *, identifier: str) -> dict[str, Any]:
    normalized = str(identifier or "").strip().lower()
    auth = (
        db.query(FederationActorAuth)
        .filter(
            (FederationActorAuth.username == normalized)
            | (FederationActorAuth.email == normalized)
        )
        .first()
    )
    if auth is None:
        return {"ok": True}
    reset_token = secrets.token_urlsafe(24)
    auth.password_reset_token_hash = _reset_token_hash(reset_token)
    auth.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    auth.password_reset_requested_at = datetime.now(timezone.utc)
    db.commit()
    actor = db.get(FederationActor, auth.actor_id)
    return {
        "ok": True,
        "reset_token": reset_token,
        "display_name": str(getattr(actor, "display_name", "") or "").strip() or auth.username,
        "email": auth.email,
    }


def reset_password_local(
    db: Session,
    *,
    token: str,
    new_password: str,
    current_shard: Optional[str] = None,
) -> ActorProjectionBundle:
    hashed_token = _reset_token_hash(token)
    auth = (
        db.query(FederationActorAuth)
        .filter(FederationActorAuth.password_reset_token_hash == hashed_token)
        .first()
    )
    if auth is None:
        raise HTTPException(status_code=401, detail="invalid_reset_token")
    expires_at = auth.password_reset_expires_at
    if expires_at is None:
        raise HTTPException(status_code=401, detail="invalid_reset_token")
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=401, detail="expired_reset_token")
    auth.password_hash = hash_password(new_password)
    auth.password_reset_token_hash = None
    auth.password_reset_expires_at = None
    auth.password_reset_requested_at = None
    actor = db.get(FederationActor, auth.actor_id)
    if actor is not None and current_shard:
        actor.current_shard = current_shard
    db.commit()
    return _build_bundle(db, auth.actor_id)


def get_actor_bundle_local(db: Session, actor_id: str) -> ActorProjectionBundle:
    return _build_bundle(db, actor_id)


def upsert_actor_api_key_local(db: Session, *, actor_id: str, api_key: str) -> ActorProjectionBundle:
    actor = db.get(FederationActor, actor_id)
    auth = db.get(FederationActorAuth, actor_id)
    if actor is None or auth is None:
        raise HTTPException(status_code=404, detail="actor_not_found")

    secret = db.get(FederationActorSecret, actor_id)
    if secret is None:
        secret = FederationActorSecret(actor_id=actor_id)
        db.add(secret)
    secret.llm_api_key_enc = encrypt_text(api_key)
    secret.rotated_at = datetime.now(timezone.utc)
    db.commit()
    return _build_bundle(db, actor_id)


def sync_resident_actor_local(
    db: Session,
    *,
    actor_id: str,
    display_name: str,
    home_shard: str,
    current_shard: str,
    status: str = "active",
) -> None:
    actor = db.get(FederationActor, actor_id)
    if actor is None:
        actor = FederationActor(
            actor_id=actor_id,
            actor_type="agent",
            display_name=display_name,
            handle=None,
            home_shard=home_shard,
            current_shard=current_shard,
            status=status,
            origin="migrated",
        )
        db.add(actor)
    else:
        actor.display_name = display_name
        actor.current_shard = current_shard
        actor.status = status

    resident = db.get(FederationResident, actor_id)
    if resident is None:
        resident = FederationResident(
            resident_id=actor_id,
            name=display_name,
            home_shard=home_shard,
            current_shard=current_shard,
            resident_type="agent",
            status=status,
        )
        db.add(resident)
    else:
        resident.name = display_name
        resident.home_shard = home_shard
        resident.current_shard = current_shard
        resident.status = status


def _federation_request(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not settings.federation_url:
        raise HTTPException(status_code=503, detail="federation_unavailable")
    url = f"{settings.federation_url.rstrip('/')}{path}"
    body: bytes | None = None
    headers = {"Content-Type": "application/json"}
    if settings.federation_token:
        headers["X-Federation-Token"] = settings.federation_token
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="ignore")
        detail = body_text or exc.reason
        raise HTTPException(status_code=exc.code, detail=detail)
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=503, detail=f"federation_unavailable: {exc.reason}")


def register_human_actor_remote(
    *,
    origin_shard: str,
    email: str,
    username: str,
    display_name: str,
    password: str,
    pass_type: str,
    terms_accepted: bool,
) -> ActorProjectionBundle:
    payload = _federation_request(
        "POST",
        "/api/federation/auth/register",
        {
            "origin_shard": origin_shard,
            "email": email,
            "username": username,
            "display_name": display_name,
            "password": password,
            "pass_type": pass_type,
            "terms_accepted": terms_accepted,
        },
    )
    return ActorProjectionBundle.from_dict(payload)


def login_human_actor_remote(*, username: str, password: str, current_shard: str) -> ActorProjectionBundle:
    payload = _federation_request(
        "POST",
        "/api/federation/auth/login",
        {"identifier": username, "password": password, "current_shard": current_shard},
    )
    return ActorProjectionBundle.from_dict(payload)


def request_password_reset_remote(*, identifier: str) -> dict[str, Any]:
    return _federation_request(
        "POST",
        "/api/federation/auth/request-password-reset",
        {"identifier": identifier},
    )


def reset_password_remote(*, token: str, new_password: str, current_shard: str) -> ActorProjectionBundle:
    payload = _federation_request(
        "POST",
        "/api/federation/auth/reset-password",
        {"token": token, "new_password": new_password, "current_shard": current_shard},
    )
    return ActorProjectionBundle.from_dict(payload)


def get_actor_bundle_remote(actor_id: str) -> ActorProjectionBundle:
    payload = _federation_request("GET", f"/api/federation/actors/{actor_id}")
    return ActorProjectionBundle.from_dict(payload)


def upsert_actor_api_key_remote(*, actor_id: str, api_key: str) -> ActorProjectionBundle:
    payload = _federation_request(
        "PUT",
        f"/api/federation/actors/{actor_id}/secret",
        {"api_key": api_key},
    )
    return ActorProjectionBundle.from_dict(payload)


def register_human_actor(
    db: Session,
    *,
    origin_shard: str,
    email: str,
    username: str,
    display_name: str,
    password: str,
    pass_type: str,
    terms_accepted: bool,
) -> ActorProjectionBundle:
    if settings.shard_type == "world" or not str(settings.federation_url or "").strip():
        return register_human_actor_local(
            db,
            origin_shard=origin_shard,
            email=email,
            username=username,
            display_name=display_name,
            password=password,
            pass_type=pass_type,
            terms_accepted=terms_accepted,
        )
    return register_human_actor_remote(
        origin_shard=origin_shard,
        email=email,
        username=username,
        display_name=display_name,
        password=password,
        pass_type=pass_type,
        terms_accepted=terms_accepted,
    )


def login_human_actor(db: Session, *, username: str, password: str) -> ActorProjectionBundle:
    if settings.shard_type == "world" or not str(settings.federation_url or "").strip():
        return login_human_actor_local(
            db,
            username=username,
            password=password,
            current_shard=current_shard_id(),
        )
    return login_human_actor_remote(
        username=username,
        password=password,
        current_shard=current_shard_id(),
    )


def request_password_reset(db: Session, *, identifier: str) -> dict[str, Any]:
    if settings.shard_type == "world" or not str(settings.federation_url or "").strip():
        return request_password_reset_local(db, identifier=identifier)
    return request_password_reset_remote(identifier=identifier)


def reset_password(db: Session, *, token: str, new_password: str) -> ActorProjectionBundle:
    if settings.shard_type == "world" or not str(settings.federation_url or "").strip():
        return reset_password_local(
            db,
            token=token,
            new_password=new_password,
            current_shard=current_shard_id(),
        )
    return reset_password_remote(
        token=token,
        new_password=new_password,
        current_shard=current_shard_id(),
    )


def get_actor_bundle(db: Session, actor_id: str) -> ActorProjectionBundle:
    if settings.shard_type == "world" or not str(settings.federation_url or "").strip():
        return get_actor_bundle_local(db, actor_id)
    return get_actor_bundle_remote(actor_id)


def upsert_actor_api_key(db: Session, *, actor_id: str, api_key: str) -> ActorProjectionBundle:
    if settings.shard_type == "world" or not str(settings.federation_url or "").strip():
        return upsert_actor_api_key_local(db, actor_id=actor_id, api_key=api_key)
    return upsert_actor_api_key_remote(actor_id=actor_id, api_key=api_key)


def ensure_local_player_projection(db: Session, bundle: ActorProjectionBundle) -> Player:
    player = db.query(Player).filter(Player.actor_id == bundle.actor_id).first()
    if player is None:
        player = db.query(Player).filter(Player.username == bundle.username).first()
    if player is None:
        player = Player(
            id=str(uuid.uuid4()),
            actor_id=bundle.actor_id,
            email=bundle.email,
            username=bundle.username,
            display_name=bundle.display_name,
            password_hash=bundle.password_hash,
            api_key_enc=bundle.api_key_enc,
            pass_type=bundle.pass_type,
            pass_expires_at=_parse_iso(bundle.pass_expires_at),
            terms_accepted_at=_parse_iso(bundle.terms_accepted_at),
        )
        db.add(player)
    else:
        player.actor_id = bundle.actor_id
        player.email = bundle.email
        player.username = bundle.username
        player.display_name = bundle.display_name
        player.password_hash = bundle.password_hash
        player.api_key_enc = bundle.api_key_enc
        player.pass_type = bundle.pass_type
        player.pass_expires_at = _parse_iso(bundle.pass_expires_at)
        player.terms_accepted_at = _parse_iso(bundle.terms_accepted_at)
    db.commit()
    db.refresh(player)
    return player


def sync_player_projection_from_actor_id(db: Session, actor_id: str) -> Optional[Player]:
    raw_actor_id = str(actor_id or "").strip()
    if not raw_actor_id:
        return None
    try:
        bundle = get_actor_bundle(db, raw_actor_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            return None
        raise
    return ensure_local_player_projection(db, bundle)
