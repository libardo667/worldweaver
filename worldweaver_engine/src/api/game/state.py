# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Session state and maintenance endpoints."""

import logging
import os
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from ...database import engine, get_db
from ...config import settings
from ...models import (
    ConsequenceReceipt,
    DurableObject,
    DoulaPoll,
    ExchangeReceipt,
    LocationChat,
    MaterialPool,
    ObjectExchange,
    Player,
    SessionVars,
    ShardTravelHandoff,
    SpaceAccessGrant,
    SpaceAccessPolicy,
    SpaceAccessReceipt,
    SpaceAccessRequest,
    StoopObjectEntry,
    StoopReceipt,
    WorldEdge,
    WorldEvent,
    WorldFact,
    WorldNode,
    WorldProjection,
    WorldTrace,
    WorldStoop,
)
from ...services.auth_service import get_current_player_strict, require_player
from ...services.clock import Clock, get_world_clock
from ...models.schemas import (
    CurrentSessionResponse,
    SessionBootstrapRequest,
    SessionBootstrapResponse,
    SessionId,
    WorldSeedRequest,
    WorldSeedResponse,
)
from ...services import session_service
from ...services.actor_authority import (
    ActorAuthorizationError,
    RequestActorCredentials,
    actor_authorization_http_error,
    authorize_bound_session_actor,
    authorize_session_actor,
    get_request_actor_credentials,
)
from ...services.resident_authority import (
    ResidentAuthorityError,
    authorize_resident_actor_request,
    authorize_resident_bootstrap_request,
    authorize_resident_generation_request,
)
from ...services.session_lifecycle import (
    ResidentSessionBinding,
    SessionBootstrapCommand,
    SessionLifecycleError,
    bootstrap_session,
    find_resident_session_retirement,
    resident_session_retirement_result,
    retire_resident_session_presence,
    retire_session_presence,
)
from ...services.shard_travel import (
    ShardTravelError,
    ShardTravelReceipt,
    arrive_session,
    depart_session,
    finish_destination_arrival,
    finish_source_departure,
    federated_trip,
    require_handoff_owner,
)
from ...services.session_service import (
    remove_cached_sessions,
    save_state,
    get_state_manager,
)
from ...services.federation_identity import current_shard_id
from ...services.world_context import build_world_context_header

router = APIRouter()

# Re-export shared caches for compatibility with existing tests/fixtures.
_state_managers = session_service._state_managers

# Compatibility aliases for existing imports/tests while keeping internals in services.
save_state_to_db = save_state


class SessionLeaveRequest(BaseModel):
    """Retire one live session without deleting the history it produced."""

    session_id: SessionId
    transition_id: Optional[str] = Field(default=None, min_length=1, max_length=64)


class SessionTravelDepartureRequest(BaseModel):
    """Depart one local incarnation through a discovered inter-city route."""

    session_id: SessionId
    route_id: str = Field(min_length=1, max_length=80)
    destination_shard: str = Field(min_length=1, max_length=80)
    travel_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), min_length=1, max_length=64
    )
    reason: Optional[str] = Field(default=None, max_length=255)


class SessionTravelArrivalRequest(BaseModel):
    """Create one destination-local incarnation for a federated trip."""

    travel_id: str = Field(min_length=1, max_length=64)
    session_id: SessionId


def _clear_runtime_caches() -> None:
    _state_managers.clear()


def _clear_runtime_session_caches(session_id: str) -> None:
    safe_session_id = str(session_id or "").strip()
    if not safe_session_id:
        return
    remove_cached_sessions([safe_session_id])


def _travel_http_response(receipt: ShardTravelReceipt):
    if receipt.status_code == 200:
        return receipt.payload
    return JSONResponse(status_code=receipt.status_code, content=receipt.payload)


def _raise_travel_http(exc: ShardTravelError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _authorize_travel_request(
    db: Session,
    *,
    credentials: RequestActorCredentials,
    actor_id: str,
    session_id: str | None = None,
) -> ResidentSessionBinding | None:
    """Prove control of a traveler before a local or cross-node transition."""

    if credentials.player is not None:
        if str(credentials.player.actor_id or "").strip() != actor_id:
            raise HTTPException(
                status_code=403, detail="This trip belongs to another actor."
            )
        if session_id:
            try:
                authorize_session_actor(
                    db,
                    credentials=credentials,
                    session_id=session_id,
                    required_scope="session.lifecycle",
                )
            except ActorAuthorizationError as exc:
                raise actor_authorization_http_error(exc) from exc
        return None

    if not credentials.has_resident_proof:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "actor_proof_required",
                "message": "Travel requires human login or resident request proof.",
            },
        )

    if session_id and db.get(SessionVars, session_id) is not None:
        try:
            authorized = authorize_session_actor(
                db,
                credentials=credentials,
                session_id=session_id,
                required_scope="session.lifecycle",
            )
        except ActorAuthorizationError as exc:
            raise actor_authorization_http_error(exc) from exc
        if authorized.actor_id != actor_id or authorized.runtime_generation is None:
            raise HTTPException(
                status_code=403, detail="This trip belongs to another actor."
            )
        return ResidentSessionBinding(
            actor_id=authorized.actor_id,
            runtime_generation=authorized.runtime_generation,
        )

    try:
        verified = authorize_resident_actor_request(
            db,
            actor_id=actor_id,
            expected_audience=current_shard_id(),
            required_scope="session.lifecycle",
            method=credentials.method,
            target=credentials.target,
            body=credentials.body,
            headers=credentials.resident_headers,
        )
    except ResidentAuthorityError as exc:
        status_code = (
            409 if exc.code in {"replayed_request", "retired_generation"} else 401
        )
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    return ResidentSessionBinding(
        actor_id=verified.actor_id,
        runtime_generation=verified.runtime_generation,
    )


def _delete_session_world_rows(db: Session, session_id: str) -> Dict[str, int]:
    safe_session_id = str(session_id or "").strip()
    if not safe_session_id:
        return {
            "sessions": 0,
            "world_events": 0,
            "world_facts": 0,
            "world_edges": 0,
            "world_projection": 0,
            "consequence_events_preserved": 0,
        }

    all_session_event_ids = [
        int(row[0])
        for row in db.query(WorldEvent.id)
        .filter(WorldEvent.session_id == safe_session_id)
        .all()
        if row[0] is not None
    ]
    protected_event_ids = {
        int(row[0])
        for row in db.query(ConsequenceReceipt.world_event_id)
        .filter(ConsequenceReceipt.world_event_id.in_(all_session_event_ids))
        .all()
        if row[0] is not None
    }
    protected_event_ids.update(
        int(row[0])
        for row in db.query(ExchangeReceipt.world_event_id)
        .filter(ExchangeReceipt.world_event_id.in_(all_session_event_ids))
        .all()
        if row[0] is not None
    )
    protected_event_ids.update(
        int(row[0])
        for row in db.query(StoopReceipt.world_event_id)
        .filter(StoopReceipt.world_event_id.in_(all_session_event_ids))
        .all()
        if row[0] is not None
    )
    protected_event_ids.update(
        int(row[0])
        for row in db.query(SpaceAccessReceipt.world_event_id)
        .filter(SpaceAccessReceipt.world_event_id.in_(all_session_event_ids))
        .all()
        if row[0] is not None
    )
    session_event_ids = [
        event_id
        for event_id in all_session_event_ids
        if event_id not in protected_event_ids
    ]

    projection_rows_deleted = 0
    edge_rows_deleted = 0
    if session_event_ids:
        projection_rows_deleted = (
            db.query(WorldProjection)
            .filter(WorldProjection.source_event_id.in_(session_event_ids))
            .delete(synchronize_session=False)
        )
        edge_rows_deleted = (
            db.query(WorldEdge)
            .filter(WorldEdge.source_event_id.in_(session_event_ids))
            .delete(synchronize_session=False)
        )

    fact_filter = WorldFact.session_id == safe_session_id
    if session_event_ids:
        fact_filter = or_(fact_filter, WorldFact.source_event_id.in_(session_event_ids))
    fact_query = db.query(WorldFact).filter(fact_filter)
    if protected_event_ids:
        fact_query = fact_query.filter(
            or_(
                WorldFact.source_event_id.is_(None),
                WorldFact.source_event_id.notin_(protected_event_ids),
            )
        )
    world_facts_deleted = fact_query.delete(synchronize_session=False)

    event_query = db.query(WorldEvent).filter(WorldEvent.session_id == safe_session_id)
    if protected_event_ids:
        event_query = event_query.filter(WorldEvent.id.notin_(protected_event_ids))
    world_events_deleted = event_query.delete(synchronize_session=False)
    sessions_deleted = (
        db.query(SessionVars)
        .filter(SessionVars.session_id == safe_session_id)
        .delete(synchronize_session=False)
    )
    db.commit()

    return {
        "sessions": int(sessions_deleted),
        "world_events": int(world_events_deleted),
        "world_facts": int(world_facts_deleted),
        "world_edges": int(edge_rows_deleted),
        "world_projection": int(projection_rows_deleted),
        "consequence_events_preserved": len(protected_event_ids),
    }


def _delete_all_world_rows(db: Session) -> Dict[str, int]:
    doula_polls_deleted = db.query(DoulaPoll).delete(synchronize_session=False)
    location_chat_deleted = db.query(LocationChat).delete(synchronize_session=False)
    world_traces_deleted = db.query(WorldTrace).delete(synchronize_session=False)
    exchange_receipts_deleted = db.query(ExchangeReceipt).delete(
        synchronize_session=False
    )
    object_exchanges_deleted = db.query(ObjectExchange).delete(
        synchronize_session=False
    )
    stoop_receipts_deleted = db.query(StoopReceipt).delete(synchronize_session=False)
    stoop_entries_deleted = db.query(StoopObjectEntry).delete(synchronize_session=False)
    world_stoops_deleted = db.query(WorldStoop).delete(synchronize_session=False)
    space_access_receipts_deleted = db.query(SpaceAccessReceipt).delete(
        synchronize_session=False
    )
    space_access_requests_deleted = db.query(SpaceAccessRequest).delete(
        synchronize_session=False
    )
    space_access_grants_deleted = db.query(SpaceAccessGrant).delete(
        synchronize_session=False
    )
    space_access_policies_deleted = db.query(SpaceAccessPolicy).delete(
        synchronize_session=False
    )
    consequence_receipts_deleted = db.query(ConsequenceReceipt).delete(
        synchronize_session=False
    )
    durable_objects_deleted = db.query(DurableObject).delete(synchronize_session=False)
    material_pools_deleted = db.query(MaterialPool).delete(synchronize_session=False)
    world_facts_deleted = db.query(WorldFact).delete(synchronize_session=False)
    world_edges_deleted = db.query(WorldEdge).delete(synchronize_session=False)
    projection_rows_deleted = db.query(WorldProjection).delete(
        synchronize_session=False
    )
    world_nodes_deleted = db.query(WorldNode).delete(synchronize_session=False)
    world_events_deleted = db.query(WorldEvent).delete(synchronize_session=False)
    sessions_deleted = db.query(SessionVars).delete(synchronize_session=False)
    db.commit()
    return {
        "sessions": int(sessions_deleted),
        "world_events": int(world_events_deleted),
        "world_nodes": int(world_nodes_deleted),
        "world_edges": int(world_edges_deleted),
        "world_facts": int(world_facts_deleted),
        "world_projection": int(projection_rows_deleted),
        "location_chat": int(location_chat_deleted),
        "world_traces": int(world_traces_deleted),
        "exchange_receipts": int(exchange_receipts_deleted),
        "object_exchanges": int(object_exchanges_deleted),
        "stoop_receipts": int(stoop_receipts_deleted),
        "stoop_entries": int(stoop_entries_deleted),
        "world_stoops": int(world_stoops_deleted),
        "space_access_receipts": int(space_access_receipts_deleted),
        "space_access_requests": int(space_access_requests_deleted),
        "space_access_grants": int(space_access_grants_deleted),
        "space_access_policies": int(space_access_policies_deleted),
        "consequence_receipts": int(consequence_receipts_deleted),
        "durable_objects": int(durable_objects_deleted),
        "material_pools": int(material_pools_deleted),
        "doula_polls": int(doula_polls_deleted),
    }


def _reset_world_sequences(db: Session) -> None:
    if engine.dialect.name != "sqlite":
        return
    try:
        sequence_names = (
            "world_events",
            "world_traces",
            "consequence_receipts",
            "exchange_receipts",
            "stoop_receipts",
            "material_pools",
            "space_access_grants",
            "space_access_receipts",
        )
        quoted_names = ", ".join(f"'{name}'" for name in sequence_names)
        db.execute(text(f"DELETE FROM sqlite_sequence WHERE name IN ({quoted_names})"))
        db.commit()
    except Exception:
        db.rollback()


_WORLD_ID_FILE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "data",
    f"world_id_{settings.city_id}.txt",
)


def _read_world_id() -> str:
    try:
        with open(_WORLD_ID_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def _write_world_id(world_id: str) -> None:
    os.makedirs(os.path.dirname(_WORLD_ID_FILE), exist_ok=True)
    with open(_WORLD_ID_FILE, "w", encoding="utf-8") as f:
        f.write(world_id)


@router.post("/world/seed", response_model=WorldSeedResponse)
def seed_world(
    payload: WorldSeedRequest,
    db: Session = Depends(get_db),
    world_clock: Clock = Depends(get_world_clock),
):
    """Seed the world once before any agents bootstrap.

    This is an admin-only operation. It generates a unique world_id, seeds the
    world graph from a city pack, and stores the world_id server-side so all
    agents can discover it via GET /api/world/id without depending on any character
    workspace.

    Requires WW_ENABLE_DEV_RESET=true (default in dev).
    """
    if not settings.enable_dev_reset:
        raise HTTPException(status_code=404, detail="Not found.")

    import uuid
    from datetime import timezone as _tz

    # Reuse an existing world_id (e.g. adding a second city pack) or mint a fresh one.
    current = world_clock.now()
    world_id = (
        payload.world_id or ""
    ).strip() or f"world-{current.strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
    raw_description = (payload.description or "").strip()
    description = raw_description or (
        f"A persistent world shaped by its inhabitants — {payload.world_theme}."
    )
    tone = payload.tone.strip() or "grounded, observational"

    try:
        state_manager = get_state_manager(world_id, db)
        state_manager.set_variable("world_theme", payload.world_theme)
        state_manager.set_variable("player_role", payload.player_role)
        state_manager.set_variable("world_tone", tone)
        state_manager.set_variable("_bootstrap_state", "completed")
        state_manager.set_variable("_bootstrap_source", "world-seed")

        world_context = build_world_context_header(
            world_name=(
                payload.city_id.replace("_", " ").title()
                if payload.seed_from_city_pack
                else payload.world_theme
            ),
            city_id=payload.city_id if payload.seed_from_city_pack else "",
            theme=payload.world_theme,
            tone=tone,
            premise=description,
            source="world_seed",
        )
        nodes_seeded = 0
        city_pack_used = None

        if payload.seed_from_city_pack:
            # ── City-pack path: seed real SF geography ───────────────────────
            from ...services.city_pack_seeder import seed_world_from_city_pack

            seed_result = seed_world_from_city_pack(
                db,
                world_id=world_id,
                city_id=payload.city_id,
                world_theme=payload.world_theme,
                world_description=description,
                tone=tone,
                enrich_descriptions=payload.enrich_city_pack,
            )
            nodes_seeded = seed_result.get("nodes_seeded", 0)
            city_pack_used = payload.city_id
            if isinstance(seed_result.get("world_context"), dict):
                world_context = seed_result["world_context"]
            entry_location = str(world_context.get("entry_point") or "").strip()
            if entry_location:
                state_manager.set_variable("location", entry_location)
            state_manager.set_variable("city_id", payload.city_id)
            logging.info(
                "World seeded from city pack '%s': %d nodes, %d edges",
                payload.city_id,
                nodes_seeded,
                seed_result.get("edges_seeded", 0),
            )
        state_manager.set_world_context(world_context)
        save_state(state_manager, db, now=current)

        _write_world_id(world_id)

        return WorldSeedResponse(
            success=True,
            world_id=world_id,
            seeded_at=current.astimezone(_tz.utc).isoformat(),
            message=f"World seeded. All agents can now join via world_id={world_id}",
            nodes_seeded=nodes_seeded,
            city_pack_used=city_pack_used,
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logging.error("World seed failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"World seed failed: {str(exc)}")


@router.get("/world/id")
def get_world_id():
    """Return the current server-side world_id.

    All agents call this on first setup to discover the world_id without
    depending on any character workspace path.
    """
    wid = _read_world_id()
    return {"world_id": wid, "seeded": bool(wid)}


@router.get("/session/current", response_model=CurrentSessionResponse)
def get_current_human_session(
    db: Session = Depends(get_db),
    player: Player = Depends(require_player),
):
    """Recover this actor's existing local presence after browser state is lost."""

    actor_id = str(player.actor_id or "").strip()
    if not actor_id:
        raise HTTPException(
            status_code=409, detail="This player has no durable actor identity."
        )
    live_session = (
        db.query(SessionVars).filter(SessionVars.actor_id == actor_id).first()
    )
    if live_session is None:
        return CurrentSessionResponse(active=False)
    location = str(
        get_state_manager(str(live_session.session_id), db).get_variable("location")
        or ""
    ).strip()
    return CurrentSessionResponse(
        active=True,
        session_id=str(live_session.session_id),
        location=location or None,
    )


@router.post("/session/bootstrap", response_model=SessionBootstrapResponse)
def bootstrap_session_world(
    payload: SessionBootstrapRequest,
    db: Session = Depends(get_db),
    player: Optional[Player] = Depends(get_current_player_strict),
    world_clock: Clock = Depends(get_world_clock),
):
    """Join one existing shared world through the canonical lifecycle service."""
    try:
        receipt = bootstrap_session(
            db,
            command=SessionBootstrapCommand(
                session_id=str(payload.session_id),
                actor_id=str(payload.actor_id or "").strip() or None,
                world_theme=payload.world_theme,
                player_role=payload.player_role,
                key_elements=tuple(payload.key_elements),
                tone=payload.tone,
                bootstrap_source=payload.bootstrap_source,
                world_id=str(payload.world_id) if payload.world_id else None,
                entry_location=payload.entry_location,
            ),
            player=player,
            now=world_clock.now(),
        )
        return SessionBootstrapResponse(**receipt.as_payload())
    except SessionLifecycleError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc


@router.post("/session/bootstrap/resident", response_model=SessionBootstrapResponse)
async def bootstrap_signed_resident_session(
    payload: SessionBootstrapRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
    world_clock: Clock = Depends(get_world_clock),
):
    """Bootstrap one pre-admitted resident from an exact signed request.

    This transitional endpoint lets a synthetic resident use the new authority
    protocol without changing the unsigned route used by current residents.
    """

    actor_id = str(payload.actor_id or "").strip()
    if not actor_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "actor_id_required",
                "message": "Signed resident bootstrap requires a durable actor ID.",
            },
        )
    if credentials.player is not None or not credentials.has_resident_proof:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "resident_proof_required",
                "message": "This endpoint requires resident request proof.",
            },
        )
    requested_session_id = str(payload.session_id)
    if db.get(SessionVars, requested_session_id) is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "session_id_in_use",
                "message": "Signed bootstrap requires a new local session ID.",
            },
        )
    live_actor_session = (
        db.query(SessionVars).filter(SessionVars.actor_id == actor_id).first()
    )
    if live_actor_session is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "actor_already_present",
                "message": f"This actor is already present in local session '{live_actor_session.session_id}'.",
            },
        )
    try:
        verified = authorize_resident_bootstrap_request(
            db,
            actor_id=actor_id,
            expected_audience=current_shard_id(),
            method=credentials.method,
            target=credentials.target,
            body=credentials.body,
            headers=credentials.resident_headers,
        )
    except ResidentAuthorityError as exc:
        error_status = (
            409 if exc.code in {"replayed_request", "retired_generation"} else 401
        )
        raise HTTPException(
            status_code=error_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    try:
        receipt = bootstrap_session(
            db,
            command=SessionBootstrapCommand(
                session_id=requested_session_id,
                actor_id=actor_id,
                world_theme=payload.world_theme,
                player_role=payload.player_role,
                key_elements=tuple(payload.key_elements),
                tone=payload.tone,
                bootstrap_source=payload.bootstrap_source,
                world_id=str(payload.world_id) if payload.world_id else None,
                entry_location=payload.entry_location,
            ),
            resident_binding=ResidentSessionBinding(
                actor_id=verified.actor_id,
                runtime_generation=verified.runtime_generation,
            ),
            now=world_clock.now(),
        )
    except SessionLifecycleError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
        ) from exc
    return SessionBootstrapResponse(**receipt.as_payload())


@router.post("/session/leave")
def leave_session_world(
    payload: SessionLeaveRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
    world_clock: Clock = Depends(get_world_clock),
):
    """Retire one live incarnation without erasing its public history."""
    transition_id = str(payload.transition_id or "").strip()
    session_id = str(payload.session_id)
    if credentials.has_resident_proof and not transition_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "transition_id_required",
                "message": "Resident hearth departure requires a stable transition ID.",
            },
        )

    if transition_id:
        try:
            existing = find_resident_session_retirement(
                db,
                transition_id=transition_id,
                session_id=session_id,
            )
        except SessionLifecycleError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        if existing is not None:
            if not credentials.has_resident_proof or credentials.player is not None:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "code": "resident_proof_required",
                        "message": "Retirement receipt replay requires resident proof.",
                    },
                )
            try:
                authorize_resident_generation_request(
                    db,
                    actor_id=str(existing.actor_id),
                    runtime_generation=int(existing.runtime_generation),
                    expected_audience=current_shard_id(),
                    required_scope="session.lifecycle",
                    method=credentials.method,
                    target=credentials.target,
                    body=credentials.body,
                    headers=credentials.resident_headers,
                )
            except ResidentAuthorityError as exc:
                status_code = (
                    409
                    if exc.code in {"replayed_request", "retired_generation"}
                    else 401
                )
                raise HTTPException(
                    status_code=status_code,
                    detail={"code": exc.code, "message": str(exc)},
                ) from exc
            if (
                str(existing.transition_id) != transition_id
                or str(existing.session_id) != session_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "departure_receipt_mismatch",
                        "message": "Departure identifiers do not match the durable receipt.",
                    },
                )
            return resident_session_retirement_result(existing).as_payload()

    try:
        actor = authorize_bound_session_actor(
            db,
            credentials=credentials,
            session_id=payload.session_id,
            required_scope="session.lifecycle",
        )
    except ActorAuthorizationError as exc:
        raise actor_authorization_http_error(exc) from exc

    if transition_id and actor is not None and actor.proof_kind == "resident_signature":
        try:
            return retire_resident_session_presence(
                db,
                transition_id=transition_id,
                session_id=session_id,
                actor_id=actor.actor_id,
                runtime_generation=int(actor.runtime_generation or 0),
                now=world_clock.now(),
            ).as_payload()
        except SessionLifecycleError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return retire_session_presence(db, session_id=session_id).as_payload()


@router.post("/session/travel/depart")
def depart_session_for_travel(
    payload: SessionTravelDepartureRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Retire a source session through the recoverable federation handoff."""
    existing = db.get(ShardTravelHandoff, payload.travel_id.strip())
    session = db.get(SessionVars, str(payload.session_id))
    actor_id = str(
        (existing.actor_id if existing is not None else None)
        or (session.actor_id if session is not None else None)
        or ""
    ).strip()
    if actor_id:
        _authorize_travel_request(
            db,
            credentials=credentials,
            actor_id=actor_id,
            session_id=(str(payload.session_id) if session is not None else None),
        )
    try:
        receipt = depart_session(
            db,
            session_id=str(payload.session_id),
            route_id=payload.route_id.strip(),
            destination_shard=payload.destination_shard.strip(),
            travel_id=payload.travel_id.strip(),
            reason=payload.reason,
            player=credentials.player,
        )
    except ShardTravelError as exc:
        _raise_travel_http(exc)
    return _travel_http_response(receipt)


@router.post("/session/travel/{travel_id}/retry-departure")
def retry_session_travel_departure(
    travel_id: str,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Retry federation confirmation after a recoverable source-side outage."""
    handoff = db.get(ShardTravelHandoff, travel_id)
    if handoff is None or handoff.role != "source":
        raise HTTPException(
            status_code=404, detail=f"Source travel handoff '{travel_id}' not found."
        )
    _authorize_travel_request(
        db,
        credentials=credentials,
        actor_id=str(handoff.actor_id),
        session_id=(
            str(handoff.session_id)
            if db.get(SessionVars, str(handoff.session_id or "")) is not None
            else None
        ),
    )
    try:
        require_handoff_owner(handoff, credentials.player)
        return _travel_http_response(finish_source_departure(db, handoff))
    except ShardTravelError as exc:
        _raise_travel_http(exc)


@router.post("/session/travel/arrive")
def arrive_session_from_travel(
    payload: SessionTravelArrivalRequest,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Receive one actor into a fresh local session at a city-owned travel hub."""
    try:
        existing = db.get(ShardTravelHandoff, payload.travel_id.strip())
        trip = (
            None if existing is not None else federated_trip(payload.travel_id.strip())
        )
        actor_id = str(
            existing.actor_id if existing is not None else (trip or {}).get("actor_id")
        ).strip()
        if not actor_id:
            raise ShardTravelError(
                "actor_identity_missing",
                "The federation travel record has no actor identity.",
                status_code=502,
            )
        resident_binding = _authorize_travel_request(
            db,
            credentials=credentials,
            actor_id=actor_id,
            session_id=(
                str(existing.session_id)
                if existing is not None
                and db.get(SessionVars, str(existing.session_id or "")) is not None
                else None
            ),
        )
        receipt = arrive_session(
            db,
            travel_id=payload.travel_id.strip(),
            session_id=str(payload.session_id).strip(),
            player=credentials.player,
            world_id=_read_world_id(),
            trip=trip,
            resident_binding=resident_binding,
        )
    except ShardTravelError as exc:
        _raise_travel_http(exc)
    return _travel_http_response(receipt)


@router.post("/session/travel/{travel_id}/retry-arrival")
def retry_session_travel_arrival(
    travel_id: str,
    db: Session = Depends(get_db),
    credentials: RequestActorCredentials = Depends(get_request_actor_credentials),
):
    """Retry local boot or federation confirmation for a destination handoff."""
    handoff = db.get(ShardTravelHandoff, travel_id)
    if handoff is None or handoff.role != "destination":
        raise HTTPException(
            status_code=404,
            detail=f"Destination travel handoff '{travel_id}' not found.",
        )
    resident_binding = _authorize_travel_request(
        db,
        credentials=credentials,
        actor_id=str(handoff.actor_id),
        session_id=(
            str(handoff.session_id)
            if db.get(SessionVars, str(handoff.session_id or "")) is not None
            else None
        ),
    )
    try:
        require_handoff_owner(handoff, credentials.player)
        receipt = finish_destination_arrival(
            db,
            handoff,
            player=credentials.player,
            world_id=_read_world_id(),
            resident_binding=resident_binding,
        )
    except ShardTravelError as exc:
        _raise_travel_http(exc)
    return _travel_http_response(receipt)


@router.post("/dev/hard-reset")
def dev_hard_reset_world(db: Session = Depends(get_db)):
    """Developer-only hard reset: wipe world data and reset local id sequences."""
    if not settings.enable_dev_reset:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        deleted = _delete_all_world_rows(db)
        _reset_world_sequences(db)
        _clear_runtime_caches()
        return {
            "success": True,
            "message": "Development hard reset complete. Database world state fully wiped.",
            "deleted": deleted,
        }
    except Exception as exc:
        db.rollback()
        logging.error("Development hard reset failed: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Development hard reset failed: {str(exc)}"
        )
