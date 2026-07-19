# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Federation endpoints — registered only when SHARD_TYPE=world.

Provides the world-root registry for all shards, residents, and cross-shard DMs.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...models import (
    FederationMessage,
    FederationActor,
    FederationResident,
    FederationShard,
    FederationTraveler,
)
from ...services.federation_identity import (
    current_shard_id,
    get_actor_bundle_local,
    login_human_actor_local,
    request_password_reset_local,
    register_human_actor_local,
    reset_password_local,
    sync_resident_actor_local,
)

router = APIRouter(prefix="/api/federation", tags=["federation"])

log = logging.getLogger(__name__)
_MAX_PULSE_SEQ = 2_147_483_647

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _require_token(x_federation_token: Optional[str] = Header(default=None)) -> None:
    """Require X-Federation-Token to match settings.federation_token."""
    if not settings.federation_token:
        return  # token not configured — open (dev mode)
    if x_federation_token != settings.federation_token:
        raise HTTPException(status_code=401, detail="Invalid or missing federation token.")


# ---------------------------------------------------------------------------
# Shard health helper
# ---------------------------------------------------------------------------

_SHARD_HEALTHY_MULTIPLIER = 2
_SHARD_DEGRADED_MULTIPLIER = 5
_SHARD_OFFLINE_HOURS = 24


def _compute_shard_status(last_pulse_ts: Optional[datetime], interval: int) -> str:
    if last_pulse_ts is None:
        return "offline"
    now = datetime.now(timezone.utc)
    # Ensure comparison works regardless of tz-awareness
    lp = last_pulse_ts.replace(tzinfo=timezone.utc) if last_pulse_ts.tzinfo is None else last_pulse_ts
    age_seconds = (now - lp).total_seconds()
    if age_seconds > _SHARD_OFFLINE_HOURS * 3600:
        return "offline"
    if age_seconds > _SHARD_DEGRADED_MULTIPLIER * interval:
        return "stale"
    if age_seconds > _SHARD_HEALTHY_MULTIPLIER * interval:
        return "degraded"
    return "healthy"


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class RegisterShardRequest(BaseModel):
    shard_id: str
    shard_url: str
    client_url: Optional[str] = None
    shard_type: str = "city"
    city_id: Optional[str] = None


class DeregisterShardRequest(BaseModel):
    shard_id: str


class PulseResidentItem(BaseModel):
    resident_id: str
    name: str
    session_id: Optional[str] = None
    location: Optional[str] = None
    last_act_ts: Optional[str] = None
    status: str = "active"


class PulseTravelerItem(BaseModel):
    resident_id: str
    name: str
    from_shard: Optional[str] = None
    to_shard: Optional[str] = None
    arrived_ts: Optional[str] = None
    departed_ts: Optional[str] = None


class PulseRequest(BaseModel):
    shard_id: str
    shard_url: Optional[str] = None
    client_url: Optional[str] = None
    pulse_seq: int
    sent_at: Optional[str] = None
    residents: List[PulseResidentItem] = []
    travelers_arriving: List[PulseTravelerItem] = []
    travelers_departing: List[PulseTravelerItem] = []


class CrossShardDMRequest(BaseModel):
    from_resident_id: str
    from_shard: str
    to_resident_id: str
    to_shard: str
    body: str


class FederationRegisterHumanRequest(BaseModel):
    origin_shard: str
    email: str
    username: str
    display_name: str
    password: str
    pass_type: str = "citizen"
    terms_accepted: bool


class FederationLoginHumanRequest(BaseModel):
    identifier: Optional[str] = None
    username: Optional[str] = None
    password: str
    current_shard: Optional[str] = None

    @property
    def normalized_identifier(self) -> str:
        return str(self.identifier or self.username or "").strip().lower()


class FederationPasswordResetRequest(BaseModel):
    identifier: str


class FederationPasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str
    current_shard: Optional[str] = None


class StartTravelRequest(BaseModel):
    """Ask the federation root to coordinate one actor's node-to-node trip."""

    travel_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1, max_length=64)
    actor_id: str = Field(min_length=1, max_length=36)
    source_shard: str = Field(min_length=1, max_length=80)
    destination_shard: str = Field(min_length=1, max_length=80)
    departure_hub_id: Optional[str] = Field(default=None, max_length=80)
    departure_hub: Optional[str] = Field(default=None, max_length=200)
    arrival_hub_id: Optional[str] = Field(default=None, max_length=80)
    arrival_hub: Optional[str] = Field(default=None, max_length=200)
    reason: Optional[str] = Field(default=None, max_length=255)


class TravelTransitionRequest(BaseModel):
    """Identify the node reporting its owned part of a travel lifecycle."""

    shard_id: str = Field(min_length=1, max_length=80)


def _travel_payload(record: FederationTraveler) -> Dict[str, Any]:
    return {
        "travel_id": record.travel_id,
        "actor_id": record.resident_id,
        "actor_type": record.actor_type,
        "name": record.name,
        "source_shard": record.from_shard,
        "destination_shard": record.to_shard,
        "departure_hub_id": record.departure_hub_id,
        "departure_hub": record.departure_hub,
        "arrival_hub_id": record.arrival_hub_id,
        "arrival_hub": record.arrival_hub,
        "reason": record.reason,
        "status": record.status,
        "requested_at": record.requested_ts.isoformat() if record.requested_ts else None,
        "departed_at": record.departed_ts.isoformat() if record.departed_ts else None,
        "arrived_at": record.arrived_ts.isoformat() if record.arrived_ts else None,
    }


def _travel_record_or_404(db: Session, travel_id: str) -> FederationTraveler:
    record = db.query(FederationTraveler).filter(FederationTraveler.travel_id == travel_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"Travel '{travel_id}' not found.")
    return record


def _set_actor_travel_state(
    db: Session,
    *,
    actor_id: str,
    status: str,
    current_shard: Optional[str] = None,
) -> None:
    """Update the canonical actor and its legacy resident projection together."""
    actor = db.get(FederationActor, actor_id)
    if actor is not None:
        actor.status = status
        if current_shard:
            actor.current_shard = current_shard
    resident = db.get(FederationResident, actor_id)
    if resident is not None:
        resident.status = status
        if current_shard:
            resident.current_shard = current_shard


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register")
def register_shard(
    payload: RegisterShardRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
):
    """Register or re-register a shard with the federation root."""
    shard = db.get(FederationShard, payload.shard_id)
    if shard is None:
        shard = FederationShard(shard_id=payload.shard_id)
        db.add(shard)
    shard.shard_url = payload.shard_url
    shard.client_url = str(payload.client_url or "").strip() or None
    shard.shard_type = payload.shard_type
    shard.city_id = payload.city_id
    db.commit()
    log.info("Federation: shard registered shard_id=%s url=%s", payload.shard_id, payload.shard_url)
    return {"registered": True, "shard_id": payload.shard_id}


@router.post("/deregister")
def deregister_shard(
    payload: DeregisterShardRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
):
    """Mark a shard as offline (explicit deregistration)."""
    shard = db.get(FederationShard, payload.shard_id)
    if shard is None:
        raise HTTPException(status_code=404, detail=f"Shard '{payload.shard_id}' not found.")
    # Mark offline by clearing last_pulse_ts beyond 24h threshold
    shard.last_pulse_ts = datetime(2000, 1, 1)
    db.commit()
    log.info("Federation: shard deregistered shard_id=%s", payload.shard_id)
    return {"deregistered": True, "shard_id": payload.shard_id}


@router.post("/auth/register")
def register_human_actor(
    payload: FederationRegisterHumanRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    bundle = register_human_actor_local(
        db,
        origin_shard=payload.origin_shard.strip() or current_shard_id(),
        email=str(payload.email).strip().lower(),
        username=str(payload.username).strip().lower(),
        display_name=str(payload.display_name).strip(),
        password=payload.password,
        pass_type=str(payload.pass_type).strip() or "citizen",
        terms_accepted=bool(payload.terms_accepted),
    )
    return bundle.to_dict()


@router.post("/auth/login")
def login_human_actor(
    payload: FederationLoginHumanRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    if not payload.normalized_identifier:
        raise HTTPException(status_code=422, detail="identifier is required")
    bundle = login_human_actor_local(
        db,
        username=payload.normalized_identifier,
        password=payload.password,
        current_shard=str(payload.current_shard or "").strip() or None,
    )
    return bundle.to_dict()


@router.post("/auth/request-password-reset")
def request_password_reset_human_actor(
    payload: FederationPasswordResetRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    return request_password_reset_local(
        db,
        identifier=str(payload.identifier).strip().lower(),
    )


@router.post("/auth/reset-password")
def reset_password_human_actor(
    payload: FederationPasswordResetConfirmRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    bundle = reset_password_local(
        db,
        token=str(payload.token or "").strip(),
        new_password=payload.new_password,
        current_shard=str(payload.current_shard or "").strip() or None,
    )
    return bundle.to_dict()


@router.get("/actors/{actor_id}")
def get_actor_projection(
    actor_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    bundle = get_actor_bundle_local(db, actor_id)
    return bundle.to_dict()


@router.post("/travel/start")
def start_travel(
    payload: StartTravelRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    """Create the source-owned, idempotent start of one cross-node trip."""
    travel_id = payload.travel_id.strip()
    actor_id = payload.actor_id.strip()
    source_shard = payload.source_shard.strip()
    destination_shard = payload.destination_shard.strip()
    if source_shard == destination_shard:
        raise HTTPException(status_code=422, detail="Source and destination nodes must differ.")

    existing = db.query(FederationTraveler).filter(FederationTraveler.travel_id == travel_id).first()
    if existing is not None:
        same_trip = existing.resident_id == actor_id and existing.from_shard == source_shard and existing.to_shard == destination_shard
        if not same_trip:
            raise HTTPException(status_code=409, detail=f"Travel ID '{travel_id}' already describes another trip.")
        return {"travel": _travel_payload(existing), "idempotent": True}

    actor = db.get(FederationActor, actor_id)
    if actor is None:
        raise HTTPException(status_code=404, detail=f"Actor '{actor_id}' not found.")
    if db.get(FederationShard, source_shard) is None:
        raise HTTPException(status_code=404, detail=f"Source node '{source_shard}' is not registered.")
    if db.get(FederationShard, destination_shard) is None:
        raise HTTPException(status_code=404, detail=f"Destination node '{destination_shard}' is not registered.")
    if actor.current_shard != source_shard:
        raise HTTPException(
            status_code=409,
            detail=f"Actor '{actor_id}' is attached to '{actor.current_shard}', not '{source_shard}'.",
        )

    open_trip = (
        db.query(FederationTraveler)
        .filter(
            FederationTraveler.resident_id == actor_id,
            FederationTraveler.status.in_(("departing", "traveling")),
        )
        .first()
    )
    if open_trip is not None:
        raise HTTPException(status_code=409, detail=f"Actor '{actor_id}' already has an open trip.")

    record = FederationTraveler(
        travel_id=travel_id,
        resident_id=actor_id,
        actor_type=actor.actor_type,
        name=actor.display_name,
        from_shard=source_shard,
        to_shard=destination_shard,
        departure_hub_id=str(payload.departure_hub_id or "").strip() or None,
        departure_hub=str(payload.departure_hub or "").strip() or None,
        arrival_hub_id=str(payload.arrival_hub_id or "").strip() or None,
        arrival_hub=str(payload.arrival_hub or "").strip() or None,
        reason=str(payload.reason or "").strip() or None,
        status="departing",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"travel": _travel_payload(record), "idempotent": False}


@router.post("/travel/{travel_id}/depart")
def mark_travel_departed(
    travel_id: str,
    payload: TravelTransitionRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    """Let the source node confirm that its local incarnation has stopped."""
    record = _travel_record_or_404(db, travel_id)
    reporting_shard = payload.shard_id.strip()
    if reporting_shard != record.from_shard:
        raise HTTPException(status_code=403, detail="Only the source node may confirm departure.")
    if record.status == "traveling":
        return {"travel": _travel_payload(record), "idempotent": True}
    if record.status != "departing":
        raise HTTPException(status_code=409, detail=f"Travel is already '{record.status}'.")

    record.status = "traveling"
    record.departed_ts = datetime.now(timezone.utc)
    # While traveling, current_shard remains the source of record. The actor is
    # not attributed to the destination until that node confirms arrival.
    _set_actor_travel_state(db, actor_id=record.resident_id, status="traveling")
    db.commit()
    db.refresh(record)
    return {"travel": _travel_payload(record), "idempotent": False}


@router.post("/travel/{travel_id}/arrive")
def mark_travel_arrived(
    travel_id: str,
    payload: TravelTransitionRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    """Let the destination node confirm it has booted the actor locally."""
    record = _travel_record_or_404(db, travel_id)
    reporting_shard = payload.shard_id.strip()
    if reporting_shard != record.to_shard:
        raise HTTPException(status_code=403, detail="Only the destination node may confirm arrival.")
    if record.status == "arrived":
        return {"travel": _travel_payload(record), "idempotent": True}
    if record.status != "traveling":
        raise HTTPException(status_code=409, detail="Travel must be departed before it can arrive.")

    record.status = "arrived"
    record.arrived_ts = datetime.now(timezone.utc)
    _set_actor_travel_state(
        db,
        actor_id=record.resident_id,
        status="active",
        current_shard=record.to_shard,
    )
    db.commit()
    db.refresh(record)
    return {"travel": _travel_payload(record), "idempotent": False}


@router.get("/travel/{travel_id}")
def get_travel(
    travel_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    """Return the coordinator's current state for one trip."""
    return {"travel": _travel_payload(_travel_record_or_404(db, travel_id))}


@router.post("/pulse")
def receive_pulse(
    payload: PulseRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    """Receive a heartbeat pulse from a city shard. Returns pending mailbox messages."""
    shard = db.get(FederationShard, payload.shard_id)
    if shard is None:
        raise HTTPException(status_code=404, detail=f"Shard '{payload.shard_id}' not registered.")

    # Stale/out-of-order pulse protection
    last_seq = shard.last_pulse_seq or 0
    if payload.pulse_seq > _MAX_PULSE_SEQ:
        log.warning(
            "Federation: rejecting oversized pulse shard=%s seq=%d",
            payload.shard_id,
            payload.pulse_seq,
        )
        return {
            "accepted": False,
            "reason": "invalid_pulse_seq",
            "last_seq": last_seq,
            "pending_messages": [],
        }
    if payload.pulse_seq <= last_seq:
        log.warning(
            "Federation: ignoring stale pulse shard=%s seq=%d (last=%d)",
            payload.shard_id,
            payload.pulse_seq,
            last_seq,
        )
        return {
            "accepted": False,
            "reason": "stale_pulse",
            "last_seq": last_seq,
            "pending_messages": [],
        }

    shard.last_pulse_ts = datetime.now(timezone.utc)
    shard.last_pulse_seq = payload.pulse_seq
    if payload.shard_url:
        shard.shard_url = payload.shard_url
    if payload.client_url:
        shard.client_url = payload.client_url

    # Upsert residents
    for r in payload.residents:
        sync_resident_actor_local(
            db,
            actor_id=r.resident_id,
            display_name=r.name,
            home_shard=payload.shard_id,
            current_shard=payload.shard_id,
            status=r.status,
        )
        db.flush()
        resident = db.get(FederationResident, r.resident_id)
        if resident is None:
            continue
        resident.name = r.name
        resident.current_shard = payload.shard_id
        resident.status = r.status
        if r.location:
            resident.last_location = r.location
        if r.last_act_ts:
            try:
                resident.last_act_ts = datetime.fromisoformat(r.last_act_ts.replace("Z", "+00:00"))
            except ValueError:
                pass

    # Log departing travelers
    for t in payload.travelers_departing:
        departed_at = datetime.now(timezone.utc)
        if t.departed_ts:
            try:
                departed_at = datetime.fromisoformat(t.departed_ts.replace("Z", "+00:00"))
            except ValueError:
                pass
        record = FederationTraveler(
            resident_id=t.resident_id,
            name=t.name,
            from_shard=payload.shard_id,
            to_shard=t.to_shard or "",
            actor_type="agent",
            status="traveling",
            requested_ts=departed_at,
            departed_ts=departed_at,
        )
        db.add(record)
        _set_actor_travel_state(db, actor_id=t.resident_id, status="traveling")

    # Log arriving travelers
    for t in payload.travelers_arriving:
        # Find the most recent open travel record for this resident
        open_record = (
            db.query(FederationTraveler)
            .filter(
                FederationTraveler.resident_id == t.resident_id,
                FederationTraveler.to_shard == payload.shard_id,
                FederationTraveler.arrived_ts.is_(None),
            )
            .order_by(FederationTraveler.id.desc())
            .first()
        )
        if open_record:
            open_record.status = "arrived"
            if t.arrived_ts:
                try:
                    open_record.arrived_ts = datetime.fromisoformat(t.arrived_ts.replace("Z", "+00:00"))
                except ValueError:
                    open_record.arrived_ts = datetime.now(timezone.utc)
            else:
                open_record.arrived_ts = datetime.now(timezone.utc)
        _set_actor_travel_state(
            db,
            actor_id=t.resident_id,
            status="active",
            current_shard=payload.shard_id,
        )

    db.commit()

    # Return pending mailbox messages for this shard
    pending = (
        db.query(FederationMessage)
        .filter(
            FederationMessage.to_shard == payload.shard_id,
            FederationMessage.delivered_at.is_(None),
        )
        .order_by(FederationMessage.sent_at)
        .all()
    )
    pending_data = [
        {
            "id": m.id,
            "from_resident_id": m.from_resident_id,
            "from_shard": m.from_shard,
            "to_resident_id": m.to_resident_id,
            "body": m.body,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        }
        for m in pending
    ]
    # Mark as delivered
    now_ts = datetime.now(timezone.utc)
    for m in pending:
        m.delivered_at = now_ts
    if pending:
        db.commit()

    return {
        "accepted": True,
        "shard_id": payload.shard_id,
        "pulse_seq": payload.pulse_seq,
        "pending_messages": pending_data,
    }


@router.get("/shards")
def list_shards(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """List all registered shards with computed health status."""
    shards = db.query(FederationShard).order_by(FederationShard.shard_id).all()
    interval = settings.federation_pulse_interval
    return {
        "shards": [
            {
                "shard_id": s.shard_id,
                "shard_url": s.shard_url,
                "client_url": s.client_url,
                "shard_type": s.shard_type,
                "city_id": s.city_id,
                "last_pulse_ts": s.last_pulse_ts.isoformat() if s.last_pulse_ts else None,
                "last_pulse_seq": s.last_pulse_seq,
                "status": _compute_shard_status(s.last_pulse_ts, interval),
                "registered_at": s.registered_at.isoformat() if s.registered_at else None,
            }
            for s in shards
        ]
    }


@router.get("/residents")
def list_residents(
    shard: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all federation residents, optionally filtered by shard or status."""
    q = db.query(FederationResident)
    if shard:
        q = q.filter(FederationResident.current_shard == shard)
    if status:
        q = q.filter(FederationResident.status == status)
    residents = q.order_by(FederationResident.name).all()
    return {
        "residents": [
            {
                "resident_id": r.resident_id,
                "name": r.name,
                "home_shard": r.home_shard,
                "current_shard": r.current_shard,
                "last_location": r.last_location,
                "last_act_ts": r.last_act_ts.isoformat() if r.last_act_ts else None,
                "resident_type": r.resident_type,
                "status": r.status,
            }
            for r in residents
        ]
    }


@router.get("/traveler/{resident_id}")
def get_traveler_history(resident_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return cross-shard travel history for an actor (legacy path retained)."""
    actor = db.get(FederationActor, resident_id)
    if actor is None:
        raise HTTPException(status_code=404, detail=f"Actor '{resident_id}' not found.")
    records = db.query(FederationTraveler).filter(FederationTraveler.resident_id == resident_id).order_by(FederationTraveler.id).all()
    return {
        "actor_id": resident_id,
        "resident_id": resident_id,
        "name": actor.display_name,
        "home_shard": actor.home_shard,
        "current_shard": actor.current_shard,
        "travel_history": [_travel_payload(t) for t in records],
    }


@router.get("/mailbox/{shard_id}")
def fetch_mailbox(
    shard_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    """Fetch and mark-delivered all pending cross-shard messages for a shard."""
    pending = (
        db.query(FederationMessage)
        .filter(
            FederationMessage.to_shard == shard_id,
            FederationMessage.delivered_at.is_(None),
        )
        .order_by(FederationMessage.sent_at)
        .all()
    )
    messages = [
        {
            "id": m.id,
            "from_resident_id": m.from_resident_id,
            "from_shard": m.from_shard,
            "to_resident_id": m.to_resident_id,
            "body": m.body,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        }
        for m in pending
    ]
    now_ts = datetime.now(timezone.utc)
    for m in pending:
        m.delivered_at = now_ts
    if pending:
        db.commit()
    return {"shard_id": shard_id, "messages": messages, "count": len(messages)}


@router.post("/dm")
def send_cross_shard_dm(
    payload: CrossShardDMRequest,
    db: Session = Depends(get_db),
    _: None = Depends(_require_token),
) -> Dict[str, Any]:
    """Deposit a cross-shard DM into the federation mailbox."""
    msg = FederationMessage(
        from_resident_id=payload.from_resident_id,
        from_shard=payload.from_shard,
        to_resident_id=payload.to_resident_id,
        to_shard=payload.to_shard,
        body=payload.body,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {"queued": True, "message_id": msg.id, "to_shard": payload.to_shard}
