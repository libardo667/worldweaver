# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Session state and maintenance endpoints."""

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from ...database import engine, get_db
from ...config import settings
from ...models import (
    DoulaPoll,
    LocationChat,
    Player,
    ResidentIdentityGrowth,
    SessionVars,
    WorldEdge,
    WorldEvent,
    WorldFact,
    WorldNode,
    WorldProjection,
)
from ...services.auth_service import get_current_player_strict
from ...models.schemas import (
    SessionBootstrapRequest,
    SessionBootstrapResponse,
    SessionId,
    WorldSeedRequest,
    WorldSeedResponse,
)
from ...services import session_service
from ...services.session_service import (
    remove_cached_sessions,
    resolve_current_location,
    save_state,
    get_state_manager,
)
from ...services.growth_service import append_growth_proposals, promote_growth
from ...services.world_context import build_world_context_header

router = APIRouter()

# Re-export shared caches for compatibility with existing tests/fixtures.
_state_managers = session_service._state_managers

# Compatibility aliases for existing imports/tests while keeping internals in services.
save_state_to_db = save_state
_resolve_current_location = resolve_current_location


class SessionVarPatchRequest(BaseModel):
    """Merge a small runtime var payload into a session."""

    vars: Dict[str, Any] = Field(default_factory=dict)


class SessionLeaveRequest(BaseModel):
    """Delete one runtime session so a refreshed client does not duplicate it."""

    session_id: SessionId


class DuplicateAgentPruneRequest(BaseModel):
    """Prune stale duplicate agent incarnations, optionally narrowed to one name."""

    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)


class ResidentIdentityGrowthPatchRequest(BaseModel):
    """Patch actor-scoped mutable identity state for a live session."""

    growth_text: Optional[str] = None
    growth_metadata: Optional[Dict[str, Any]] = None
    note_records: Optional[list[Dict[str, Any]]] = None
    growth_proposals: Optional[list[Dict[str, Any]]] = None


def _resolve_actor_id_for_session(db: Session, session_id: str) -> str:
    sv = db.get(SessionVars, str(session_id or "").strip())
    actor_id = str(getattr(sv, "actor_id", "") or "").strip()
    if not actor_id:
        raise HTTPException(status_code=404, detail="Session has no actor-scoped identity.")
    return actor_id


@router.get("/state/{session_id}")
def get_state_summary(session_id: SessionId, db: Session = Depends(get_db)):
    """Get a comprehensive summary of the session state."""
    state_manager = get_state_manager(session_id, db)
    return state_manager.get_state_summary()


@router.get("/state/{session_id}/vars")
def get_state_vars(
    session_id: SessionId,
    prefix: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get raw session vars, optionally filtered by prefix."""
    state_manager = get_state_manager(session_id, db)
    vars_payload = dict(state_manager.get_contextual_variables())
    if prefix:
        vars_payload = {key: value for key, value in vars_payload.items() if str(key).startswith(prefix)}
    return {"session_id": session_id, "vars": vars_payload}


@router.post("/state/{session_id}/vars")
def patch_state_vars(
    session_id: SessionId,
    payload: SessionVarPatchRequest,
    db: Session = Depends(get_db),
):
    """Merge runtime vars into a session and persist immediately."""
    updates = dict(payload.vars or {})
    if not updates:
        raise HTTPException(status_code=422, detail="No session vars provided.")
    state_manager = get_state_manager(session_id, db)
    applied: Dict[str, Any] = {}
    for key, value in updates.items():
        normalized_key = str(key or "").strip()
        if not normalized_key:
            continue
        state_manager.set_variable(normalized_key, value)
        applied[normalized_key] = state_manager.get_variable(normalized_key)
    if not applied:
        raise HTTPException(status_code=422, detail="No valid session vars provided.")
    save_state_to_db(state_manager, db)
    return {"session_id": session_id, "vars": applied}


@router.get("/state/{session_id}/identity-growth")
def get_identity_growth_state(
    session_id: SessionId,
    db: Session = Depends(get_db),
):
    actor_id = _resolve_actor_id_for_session(db, session_id)
    row = db.get(ResidentIdentityGrowth, actor_id)
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        "growth_text": str(getattr(row, "growth_text", "") or ""),
        "growth_metadata": dict(getattr(row, "growth_metadata", {}) or {}),
        "note_records": list(getattr(row, "note_records", []) or []),
        "growth_proposals": list(getattr(row, "growth_proposals", []) or []),
    }


def _population_growth_themes(db: Session, exclude_actor_id: str, *, recent_days: int = 2, cap: int = 30) -> list[dict[str, Any]]:
    """The world-event null hypothesis for the growth gate's persistence rule (Major 61):
    what the rest of the population has been staging *recently*. Returns ``[{body, last_day}]``
    from other residents' growth proposals within the last ``recent_days`` calendar days,
    newest first, capped. Best-effort — any failure yields an empty baseline (rule 1 then
    simply doesn't gate; rules 2 and 3 are unaffected). Bounded to keep the gate's per-theme
    embedding cost small; caching this across residents is a future optimization."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=recent_days)).strftime("%Y-%m-%d")
    themes: list[dict[str, Any]] = []
    try:
        rows = db.query(ResidentIdentityGrowth).filter(ResidentIdentityGrowth.actor_id != exclude_actor_id).all()
    except Exception:
        return []
    for other in rows:
        for proposal in list(other.growth_proposals or []):
            if not isinstance(proposal, dict):
                continue
            body = str(proposal.get("body") or "").strip()
            if not body:
                continue
            raw = str(proposal.get("ts") or proposal.get("day") or "").strip()
            day = raw[:10] if len(raw) >= 10 and raw[4:5] == "-" else ""
            if day and day >= cutoff:
                themes.append({"body": body, "last_day": day})
    themes.sort(key=lambda t: t["last_day"], reverse=True)
    return themes[:cap]


@router.post("/state/{session_id}/identity-growth")
def patch_identity_growth_state(
    session_id: SessionId,
    payload: ResidentIdentityGrowthPatchRequest,
    db: Session = Depends(get_db),
):
    actor_id = _resolve_actor_id_for_session(db, session_id)
    row = db.get(ResidentIdentityGrowth, actor_id)
    if row is None:
        row = ResidentIdentityGrowth(
            actor_id=actor_id,
            growth_text="",
            growth_metadata={},
            note_records=[],
            growth_proposals=[],
        )
        db.add(row)
    if payload.growth_text is not None:
        row.growth_text = str(payload.growth_text or "").strip()
    if payload.growth_metadata is not None:
        row.growth_metadata = dict(payload.growth_metadata or {})
    if payload.note_records is not None:
        row.note_records = list(payload.note_records or [])
    promotion: dict | None = None
    if payload.growth_proposals is not None:
        # The concordance gate: append the agent's accepted self-deltas as proposals,
        # then promote only themes that recur across >=2 calendar days into growth_text.
        # The agent posts proposals, not growth_text — the gate owns what becomes soul.
        # Major 61 provenance: the population baseline is the world-event null hypothesis,
        # so a theme the whole shard is still on (a storm) defers until this mind outlasts it.
        append_growth_proposals(row, list(payload.growth_proposals or []))
        promotion = promote_growth(row, population_themes=_population_growth_themes(db, actor_id))
    db.commit()
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        "growth_text": str(row.growth_text or ""),
        "growth_metadata": dict(row.growth_metadata or {}),
        "note_records": list(row.note_records or []),
        "growth_proposals": list(row.growth_proposals or []),
        "promotion": promotion,
    }


def _clear_runtime_caches() -> None:
    _state_managers.clear()


def _clear_runtime_session_caches(session_id: str) -> None:
    safe_session_id = str(session_id or "").strip()
    if not safe_session_id:
        return
    remove_cached_sessions([safe_session_id])


_AGENT_SLUG_RE = re.compile(r"^([a-z][a-z0-9_]*)[-_]\d{8}")


def _slug_display_name(session_id: str) -> Optional[str]:
    m = _AGENT_SLUG_RE.match(str(session_id or ""))
    if not m:
        return None
    return " ".join(part.capitalize() for part in m.group(1).split("_"))


def _prune_duplicate_agent_sessions(
    db: Session,
    *,
    keep_session_id: Optional[str] = None,
    display_name: Optional[str] = None,
) -> Dict[str, Any]:
    target_name = str(display_name or "").strip().lower()
    groups: Dict[str, list[tuple[str, datetime | None]]] = {}

    for row in db.query(SessionVars).all():
        session_id = str(row.session_id or "").strip()
        agent_name = _slug_display_name(session_id)
        if not session_id or not agent_name:
            continue
        normalized_name = agent_name.lower()
        if target_name and normalized_name != target_name:
            continue
        groups.setdefault(normalized_name, []).append((session_id, row.updated_at))

    pruned: list[Dict[str, Any]] = []
    kept: list[Dict[str, Any]] = []
    for normalized_name, entries in groups.items():
        if len(entries) <= 1:
            continue
        display = " ".join(part.capitalize() for part in normalized_name.split(" "))
        if keep_session_id and any(session_id == keep_session_id for session_id, _ in entries):
            survivor_id = keep_session_id
        else:
            survivor_id = max(
                entries,
                key=lambda item: (
                    item[1].isoformat() if isinstance(item[1], datetime) else "",
                    item[0],
                ),
            )[0]
        kept.append({"display_name": display, "session_id": survivor_id})
        for stale_session_id, _ in entries:
            if stale_session_id == survivor_id:
                continue
            deleted = _delete_session_world_rows(db, stale_session_id)
            _clear_runtime_session_caches(stale_session_id)
            pruned.append(
                {
                    "display_name": display,
                    "session_id": stale_session_id,
                    "deleted": deleted,
                }
            )

    return {
        "groups_considered": len(groups),
        "kept": kept,
        "pruned": pruned,
        "pruned_count": len(pruned),
    }


def _delete_session_world_rows(db: Session, session_id: str) -> Dict[str, int]:
    safe_session_id = str(session_id or "").strip()
    if not safe_session_id:
        return {
            "sessions": 0,
            "world_events": 0,
            "world_facts": 0,
            "world_edges": 0,
            "world_projection": 0,
        }

    session_event_ids = [int(row[0]) for row in db.query(WorldEvent.id).filter(WorldEvent.session_id == safe_session_id).all() if row[0] is not None]

    projection_rows_deleted = 0
    edge_rows_deleted = 0
    if session_event_ids:
        projection_rows_deleted = db.query(WorldProjection).filter(WorldProjection.source_event_id.in_(session_event_ids)).delete(synchronize_session=False)
        edge_rows_deleted = db.query(WorldEdge).filter(WorldEdge.source_event_id.in_(session_event_ids)).delete(synchronize_session=False)

    fact_filter = WorldFact.session_id == safe_session_id
    if session_event_ids:
        fact_filter = or_(fact_filter, WorldFact.source_event_id.in_(session_event_ids))
    world_facts_deleted = db.query(WorldFact).filter(fact_filter).delete(synchronize_session=False)

    world_events_deleted = db.query(WorldEvent).filter(WorldEvent.session_id == safe_session_id).delete(synchronize_session=False)
    sessions_deleted = db.query(SessionVars).filter(SessionVars.session_id == safe_session_id).delete(synchronize_session=False)
    db.commit()

    return {
        "sessions": int(sessions_deleted),
        "world_events": int(world_events_deleted),
        "world_facts": int(world_facts_deleted),
        "world_edges": int(edge_rows_deleted),
        "world_projection": int(projection_rows_deleted),
    }


def _delete_all_world_rows(db: Session) -> Dict[str, int]:
    doula_polls_deleted = db.query(DoulaPoll).delete(synchronize_session=False)
    location_chat_deleted = db.query(LocationChat).delete(synchronize_session=False)
    world_facts_deleted = db.query(WorldFact).delete(synchronize_session=False)
    world_edges_deleted = db.query(WorldEdge).delete(synchronize_session=False)
    projection_rows_deleted = db.query(WorldProjection).delete(synchronize_session=False)
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
        "doula_polls": int(doula_polls_deleted),
    }


def _reset_storylet_sequences(db: Session) -> None:
    if engine.dialect.name != "sqlite":
        return
    try:
        db.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('storylets', 'world_events')"))
        db.commit()
    except Exception:
        db.rollback()


_WORLD_ID_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", f"world_id_{settings.city_id}.txt")


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
    from datetime import datetime as _dt, timezone as _tz

    # Reuse an existing world_id (e.g. adding a second city pack) or mint a fresh one.
    world_id = (payload.world_id or "").strip() or f"world-{_dt.now(_tz.utc).strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
    raw_description = (payload.description or "").strip()
    description = raw_description or (f"A persistent world shaped by its inhabitants — {payload.world_theme}.")
    tone = payload.tone.strip() or "grounded, observational"

    try:
        state_manager = get_state_manager(world_id, db)
        state_manager.set_variable("world_theme", payload.world_theme)
        state_manager.set_variable("player_role", payload.player_role)
        state_manager.set_variable("world_tone", tone)
        state_manager.set_variable("_bootstrap_state", "completed")
        state_manager.set_variable("_bootstrap_source", "world-seed")

        world_context = build_world_context_header(
            world_name=payload.city_id.replace("_", " ").title() if payload.seed_from_city_pack else payload.world_theme,
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
            from ...services.city_pack_seeder import (
                DEFAULT_ENTRY_LOCATION,
                seed_world_from_city_pack,
            )

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
            state_manager.set_variable("location", DEFAULT_ENTRY_LOCATION)
            state_manager.set_variable("city_id", payload.city_id)
            logging.info(
                "World seeded from city pack '%s': %d nodes, %d edges",
                payload.city_id,
                nodes_seeded,
                seed_result.get("edges_seeded", 0),
            )
        state_manager.set_world_context(world_context)
        save_state(state_manager, db)

        _write_world_id(world_id)

        return WorldSeedResponse(
            success=True,
            world_id=world_id,
            seeded_at=_dt.now(_tz.utc).isoformat(),
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


@router.post("/session/bootstrap", response_model=SessionBootstrapResponse)
def bootstrap_session_world(
    payload: SessionBootstrapRequest,
    db: Session = Depends(get_db),
    player: Optional[Player] = Depends(get_current_player_strict),
):
    """Initialize world content + onboarding vars for a new session.

    If ``payload.world_id`` is supplied the session joins an existing shared
    world instead of creating a new one.  World storylets and the world bible
    are inherited from the world session; only resident-private state is
    initialised here.
    """
    try:
        deleted = _delete_session_world_rows(db, payload.session_id)
        _clear_runtime_session_caches(payload.session_id)
        if any(int(count) > 0 for count in deleted.values()):
            logging.info(
                "Bootstrap freshness purge for session %s removed: %s",
                payload.session_id,
                deleted,
            )

        player_role = payload.player_role.strip()
        if not player_role:
            raise HTTPException(status_code=422, detail="player_role must not be blank.")

        joining_world_id = str(payload.world_id).strip() if payload.world_id else None

        if joining_world_id:
            # ── Resident join flow ──────────────────────────────────────────
            # Inherit shared world framing from the host world session so the
            # resident narrator has global grounding immediately.
            host_state = get_state_manager(joining_world_id, db)
            inherited_bible = host_state.get_world_bible()
            inherited_context = host_state.get_world_context()

            # If the resident didn't supply a theme, inherit from the seeded world.
            world_theme = payload.world_theme.strip()
            if not world_theme:
                world_theme = host_state.get_variable("world_theme") or ""

            state_manager = get_state_manager(payload.session_id, db)
            bootstrap_completed_at = datetime.now(timezone.utc).isoformat()
            state_manager.set_world_id(joining_world_id)
            state_manager.set_variable("world_theme", world_theme)
            state_manager.set_variable("player_role", player_role)
            state_manager.set_variable("character_profile", player_role)
            tone = payload.tone.strip() or "adventure"
            state_manager.set_variable("world_tone", tone)
            if payload.key_elements:
                state_manager.set_variable(
                    "world_key_elements",
                    [str(item).strip() for item in payload.key_elements if str(item).strip()][:20],
                )
            state_manager.set_variable("_bootstrap_state", "completed")
            state_manager.set_variable("_bootstrap_source", payload.bootstrap_source)
            state_manager.set_variable("_bootstrap_completed_at", bootstrap_completed_at)
            # Determine entry location: explicit > city_pack node (shared context is descriptive only)
            resolved_location: str = ""
            if payload.entry_location:
                resolved_location = str(payload.entry_location).strip()
            if inherited_bible:
                state_manager.set_world_bible(inherited_bible)
            if inherited_context:
                state_manager.set_world_context(inherited_context)
            if not resolved_location:
                # Fall back to first city-pack location node — shared context is narrative only.
                # Landmarks are not valid entry points (no map coordinates, orphaned from graph).
                cp_nodes = db.query(WorldNode).filter(WorldNode.node_type == "location").limit(500).all()
                cp_loc = next(
                    (n.name for n in cp_nodes if (n.metadata_json or {}).get("source") == "city_pack"),
                    None,
                )
                if cp_loc:
                    resolved_location = cp_loc
            if resolved_location:
                state_manager.set_variable("location", resolved_location)
            save_state(state_manager, db)

            # Log a WorldEvent so the digest roster can show the player's location immediately
            # Extract just the name from player_role ("Name — vibe" format)
            _display = player_role.split(" — ")[0].strip() if " — " in player_role else player_role
            bootstrap_event = WorldEvent(
                session_id=payload.session_id,
                event_type="session_bootstrap",
                summary=f"{_display} arrived at {resolved_location or 'the world'}.",
                world_state_delta={"location": resolved_location} if resolved_location else {},
            )
            db.add(bootstrap_event)
            pruned_duplicates: Dict[str, Any] = {}
            # Link session to authenticated player if present
            if player:
                sv = db.get(SessionVars, payload.session_id)
                if sv:
                    if sv.player_id != player.id:
                        sv.player_id = player.id
                    actor_id = str(player.actor_id or "").strip()
                    if actor_id and sv.actor_id != actor_id:
                        sv.actor_id = actor_id
            else:
                resident_actor_id = str(payload.actor_id or "").strip()
                if resident_actor_id:
                    sv = db.get(SessionVars, payload.session_id)
                    if sv and sv.actor_id != resident_actor_id:
                        sv.actor_id = resident_actor_id
                pruned_duplicates = _prune_duplicate_agent_sessions(
                    db,
                    keep_session_id=payload.session_id,
                    display_name=player_role,
                )
            db.commit()

            contextual_vars = state_manager.get_contextual_variables()
            return SessionBootstrapResponse(
                success=True,
                message=f"Resident session joined world {joining_world_id}.",
                session_id=payload.session_id,
                vars=contextual_vars,
                storylets_created=0,
                theme=world_theme,
                player_role=player_role,
                bootstrap_state="completed",
                bootstrap_diagnostics={
                    "bootstrap_mode": "resident_join",
                    "world_id": joining_world_id,
                    "world_bible_inherited": bool(inherited_bible),
                    "world_context_inherited": bool(inherited_context),
                    "bootstrap_source": str(payload.bootstrap_source),
                    "duplicate_agent_sessions_pruned": int((pruned_duplicates or {}).get("pruned_count") or 0),
                },
            )

        # In V4, the world is seeded once via POST /api/world/seed.
        # All characters join as residents with a world_id. There is no founder flow.
        raise HTTPException(
            status_code=422,
            detail=("world_id is required. Seed the world first via POST /api/world/seed, " "then pass the returned world_id here."),
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logging.error("Session bootstrap failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Session bootstrap failed: {str(exc)}")


@router.post("/cleanup-sessions")
def cleanup_old_sessions(db: Session = Depends(get_db)):
    """Clean up sessions older than 24 hours."""
    try:
        cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=24)).replace(tzinfo=None)

        sessions_to_delete_result = db.execute(
            text("SELECT session_id FROM session_vars WHERE updated_at < :cutoff"),
            {"cutoff": cutoff_time},
        ).fetchall()

        deleted_session_ids = [row[0] for row in sessions_to_delete_result]
        sessions_to_delete_count = len(deleted_session_ids)

        db.execute(
            text("DELETE FROM session_vars WHERE updated_at < :cutoff"),
            {"cutoff": cutoff_time},
        )
        db.commit()

        removed_from_cache = remove_cached_sessions(deleted_session_ids)
        logging.info(
            "Cleaned up %s old sessions (%s removed from cache)",
            sessions_to_delete_count,
            removed_from_cache,
        )

        return {
            "success": True,
            "sessions_removed": sessions_to_delete_count,
            "cache_entries_removed": removed_from_cache,
            "message": f"Cleaned up {sessions_to_delete_count} sessions older than 24 hours",
        }
    except Exception as exc:
        db.rollback()
        logging.error("Session cleanup failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Session cleanup failed: {str(exc)}")


@router.post("/session/prune-duplicate-agents")
def prune_duplicate_agent_sessions(
    payload: DuplicateAgentPruneRequest,
    db: Session = Depends(get_db),
):
    """Remove stale duplicate agent sessions, keeping the freshest incarnation per name."""
    try:
        result = _prune_duplicate_agent_sessions(
            db,
            display_name=payload.display_name,
        )
        return {
            "success": True,
            **result,
        }
    except Exception as exc:
        db.rollback()
        logging.error("Duplicate agent prune failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Duplicate agent prune failed: {str(exc)}")


@router.post("/reset-session")
def reset_session_world(
    db: Session = Depends(get_db),
):
    """Hard-reset world/session data."""
    try:
        deleted = _delete_all_world_rows(db)

        _clear_runtime_caches()

        return {
            "success": True,
            "message": "World reset complete.",
            "deleted": deleted,
        }
    except Exception as exc:
        db.rollback()
        logging.error("Session reset failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Session reset failed: {str(exc)}")


@router.post("/session/leave")
def leave_session_world(
    payload: SessionLeaveRequest,
    db: Session = Depends(get_db),
    player: Optional[Player] = Depends(get_current_player_strict),
):
    """Delete one session's world rows and runtime caches."""
    row = db.get(SessionVars, payload.session_id)
    if row is not None and row.player_id and (player is None or row.player_id != player.id):
        raise HTTPException(status_code=403, detail="Cannot leave a session owned by another player.")

    deleted = _delete_session_world_rows(db, payload.session_id)
    _clear_runtime_session_caches(payload.session_id)
    return {
        "success": True,
        "message": "Session removed from shard.",
        "session_id": payload.session_id,
        "deleted": deleted,
    }


@router.post("/dev/hard-reset")
def dev_hard_reset_world(db: Session = Depends(get_db)):
    """Developer-only hard reset: wipe world data and reset local id sequences."""
    if not settings.enable_dev_reset:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        deleted = _delete_all_world_rows(db)
        _reset_storylet_sequences(db)
        _clear_runtime_caches()
        return {
            "success": True,
            "message": "Development hard reset complete. Database world state fully wiped.",
            "deleted": deleted,
            "storylets_seeded": 0,
            "legacy_seed_mode": False,
        }
    except Exception as exc:
        db.rollback()
        logging.error("Development hard reset failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Development hard reset failed: {str(exc)}")
