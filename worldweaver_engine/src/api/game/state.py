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

from ...database import SessionLocal, engine, get_db
from ...config import settings
from ...models import (
    DoulaPoll,
    GuildMemberProfile,
    GuildQuest,
    LocationChat,
    Player,
    ResidentIdentityGrowth,
    RuntimeAdaptationState,
    SessionVars,
    SocialFeedbackEvent,
    Storylet,
    WorldEdge,
    WorldEvent,
    WorldFact,
    WorldNode,
    WorldProjection,
)
from ...services.auth_service import get_current_player_strict, require_player
from ...models.schemas import (
    GoalMilestoneRequest,
    GoalUpdateRequest,
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
from ...services.seed_data import (
    seed_if_empty_sync,
    seed_legacy_storylets_if_empty_sync,
)
from ...services.storylet_selector import _runtime_synthesis_counts
from ...services.prefetch_service import clear_prefetch_cache, clear_prefetch_cache_for_session
from ...services.world_context import build_world_context_header, world_bible_to_context_header
from ...services.guild_service import (
    VALID_FEEDBACK_CHANNELS,
    VALID_FEEDBACK_MODES,
    VALID_QUEST_OBJECTIVE_TYPES,
    VALID_QUEST_STATUSES,
    create_guild_quest,
    ensure_guild_member_profile,
    infer_member_type_for_session,
    normalize_dimension_scores,
    patch_guild_quest,
    patch_guild_member_profile,
    recompute_runtime_adaptation_state,
    serialize_guild_member_profile,
    serialize_guild_quest,
    serialize_runtime_adaptation_state,
    serialize_social_feedback_event,
)
from ...services.starter_quests import (
    STARTER_PACK_ID,
    issue_starter_pack,
    issue_starter_packs_for_eligible_apprentices,
)

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


class GuildMemberProfilePatchRequest(BaseModel):
    member_type: Optional[str] = None
    rank: Optional[str] = None
    branches: Optional[list[str]] = None
    mentor_actor_ids: Optional[list[str]] = None
    quest_band: Optional[str] = None
    review_status: Optional[Dict[str, Any]] = None
    environment_guidance: Optional[Dict[str, Any]] = None


class SocialFeedbackEventPatchRequest(BaseModel):
    source_actor_id: Optional[str] = None
    source_system: Optional[str] = None
    feedback_mode: str = Field(default="inferred")
    channel: str = Field(default="system")
    dimension_scores: Dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(default="")
    evidence_refs: list[Dict[str, Any] | str] = Field(default_factory=list)
    branch_hint: Optional[str] = None


class GuildQuestCreateRequest(BaseModel):
    source_actor_id: Optional[str] = None
    source_system: Optional[str] = None
    title: str = Field(min_length=3, max_length=160)
    brief: str = Field(default="", max_length=2400)
    branch: Optional[str] = None
    quest_band: Optional[str] = None
    status: str = Field(default="assigned")
    progress_note: Optional[str] = None
    outcome_summary: Optional[str] = None
    evidence_refs: list[Dict[str, Any] | str] = Field(default_factory=list)
    objective_type: Optional[str] = None
    target_location: Optional[str] = None
    target_person: Optional[str] = None
    target_item: Optional[str] = None
    success_signals: list[str] = Field(default_factory=list)
    assignment_context: Dict[str, Any] = Field(default_factory=dict)
    review_status: Dict[str, Any] = Field(default_factory=dict)


class GuildQuestPatchRequest(BaseModel):
    title: Optional[str] = None
    brief: Optional[str] = None
    branch: Optional[str] = None
    quest_band: Optional[str] = None
    status: Optional[str] = None
    progress_note: Optional[str] = None
    outcome_summary: Optional[str] = None
    evidence_refs: Optional[list[Dict[str, Any] | str]] = None
    append_evidence_refs: Optional[list[Dict[str, Any] | str]] = None
    activity_entry: Optional[Dict[str, Any]] = None
    assignment_context: Optional[Dict[str, Any]] = None
    review_status: Optional[Dict[str, Any]] = None


class GuildActorQuestCreateRequest(BaseModel):
    target_actor_id: str = Field(min_length=3, max_length=64)
    title: str = Field(min_length=3, max_length=160)
    brief: str = Field(default="", max_length=2400)
    branch: Optional[str] = None
    quest_band: Optional[str] = None
    status: str = Field(default="assigned")
    progress_note: Optional[str] = None
    outcome_summary: Optional[str] = None
    evidence_refs: list[Dict[str, Any] | str] = Field(default_factory=list)
    objective_type: Optional[str] = None
    target_location: Optional[str] = None
    target_person: Optional[str] = None
    target_item: Optional[str] = None
    success_signals: list[str] = Field(default_factory=list)
    assignment_context: Dict[str, Any] = Field(default_factory=dict)
    review_status: Dict[str, Any] = Field(default_factory=dict)


class GuildStarterPackIssueRequest(BaseModel):
    target_actor_id: Optional[str] = Field(default=None, min_length=3, max_length=64)


class GuildMemberGovernancePatchRequest(BaseModel):
    rank: Optional[str] = None
    branches: Optional[list[str]] = None
    mentor_actor_ids: Optional[list[str]] = None
    quest_band: Optional[str] = None
    review_status: Optional[Dict[str, Any]] = None


def _resolve_actor_id_for_session(db: Session, session_id: str) -> str:
    sv = db.get(SessionVars, str(session_id or "").strip())
    actor_id = str(getattr(sv, "actor_id", "") or "").strip()
    if not actor_id:
        raise HTTPException(status_code=404, detail="Session has no actor-scoped identity.")
    return actor_id


def _resolve_session_row(db: Session, session_id: str) -> SessionVars:
    sv = db.get(SessionVars, str(session_id or "").strip())
    if sv is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return sv


def _require_player_actor_id(player: Player) -> str:
    actor_id = str(getattr(player, "actor_id", "") or "").strip()
    if not actor_id:
        raise HTTPException(status_code=422, detail="Authenticated player has no actor id.")
    return actor_id


def _governance_roles_from_review_status(review_status: Dict[str, Any] | None) -> list[str]:
    payload = dict(review_status or {})
    roles: list[str] = []
    raw_roles = payload.get("governance_roles")
    if isinstance(raw_roles, list):
        roles.extend(str(item or "").strip().lower() for item in raw_roles)
    for key in ("guild_role", "role", "access_tier"):
        value = str(payload.get(key) or "").strip().lower()
        if value:
            roles.append(value)
    normalized: list[str] = []
    seen: set[str] = set()
    for role in roles:
        if not role or role in seen:
            continue
        normalized.append(role)
        seen.add(role)
    return normalized


def _has_role_manager(db: Session) -> bool:
    rows = (
        db.query(GuildMemberProfile)
        .filter(GuildMemberProfile.member_type == "human")
        .all()
    )
    for row in rows:
        if bool(_guild_capabilities(row).get("can_manage_roles")):
            return True
    return False


def _guild_capabilities(profile: GuildMemberProfile) -> Dict[str, Any]:
    review_status = dict(getattr(profile, "review_status", {}) or {})
    governance_roles = _governance_roles_from_review_status(review_status)
    is_human = str(getattr(profile, "member_type", "") or "").strip().lower() == "human"
    rank = str(getattr(profile, "rank", "") or "").strip().lower()
    can_assign_quests = bool(
        is_human and (
            rank == "elder"
            or any(role in {"mentor", "elder", "steward"} for role in governance_roles)
            or bool(review_status.get("can_assign_quests"))
        )
    )
    can_manage_roles = bool(
        is_human and (
            "steward" in governance_roles
            or bool(review_status.get("can_manage_roles"))
        )
    )
    return {
        "can_observe": True,
        "can_view_guild_board": True,
        "can_assign_quests": can_assign_quests,
        "can_manage_roles": can_manage_roles,
        "governance_roles": governance_roles,
    }


def _normalize_quest_list(values: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in list(values or []):
        value = str(item or "").strip()
        key = value.lower()
        if not value or key in seen:
            continue
        seen.add(key)
        cleaned.append(value[:160])
    return cleaned


def _resolve_place_name(db: Session, raw_name: str) -> tuple[str, str] | tuple[None, None]:
    candidate = str(raw_name or "").strip()
    if not candidate:
        return (None, None)
    rows = db.query(WorldNode.name, WorldNode.node_type).all()
    exact = [
        (str(name or "").strip(), str(node_type or "").strip())
        for name, node_type in rows
        if str(name or "").strip().lower() == candidate.lower()
    ]
    if len(exact) == 1:
        return exact[0]
    return (None, None)


def _resolve_board_actor_by_name(db: Session, raw_name: str) -> tuple[str | None, str | None]:
    candidate = str(raw_name or "").strip()
    if not candidate:
        return (None, None)
    board = _active_guild_board_payload(db)
    all_members = list(board["residents"]) + list(board["humans"])
    exact = [
        item for item in all_members
        if str(item.get("display_name") or "").strip().lower() == candidate.lower()
    ]
    if len(exact) == 1:
        match = exact[0]
        return (
            str(match.get("actor_id") or "").strip() or None,
            str(match.get("display_name") or "").strip() or None,
        )
    actor_exact = [
        item for item in all_members
        if str(item.get("actor_id") or "").strip() == candidate
    ]
    if len(actor_exact) == 1:
        match = actor_exact[0]
        return (
            str(match.get("actor_id") or "").strip() or None,
            str(match.get("display_name") or "").strip() or None,
        )
    return (None, None)


def _default_success_signals_for_objective(
    objective_type: str,
    *,
    target_location: str = "",
    target_person: str = "",
    target_item: str = "",
) -> list[str]:
    if objective_type == "visit_location":
        return [f"arrive at {target_location}"] if target_location else ["arrive at the target location"]
    if objective_type == "observe_location":
        signals = []
        if target_location:
            signals.append(f"arrive at {target_location}")
            signals.append(f"observe conditions at {target_location}")
        return signals or ["observe the target location"]
    if objective_type == "speak_with_person":
        return [f"speak with {target_person}"] if target_person else ["speak with the target person"]
    if objective_type == "meet_person":
        signals = []
        if target_location:
            signals.append(f"arrive at {target_location}")
        if target_person:
            signals.append(f"meet with {target_person}")
        return signals or ["meet the target person"]
    if objective_type == "deliver_message":
        return [f"deliver a message to {target_person}"] if target_person else ["deliver the message"]
    if objective_type == "find_item":
        signals = [f"find {target_item}"] if target_item else ["find the target item"]
        if target_location:
            signals.insert(0, f"search at {target_location}")
        return signals
    return []


def _preferred_intents_for_objective(objective_type: str) -> list[str]:
    return {
        "visit_location": ["move"],
        "observe_location": ["move", "ground", "act"],
        "speak_with_person": ["chat", "mail_draft"],
        "meet_person": ["move", "chat", "mail_draft"],
        "deliver_message": ["mail_draft", "chat"],
        "find_item": ["move", "act", "ground", "chat"],
        "open_ended": [],
    }.get(objective_type, [])


def _normalize_quest_assignment_context(
    db: Session,
    *,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    objective_type = str(payload.get("objective_type") or "").strip().lower()
    raw_target_location = str(payload.get("target_location") or "").strip()
    raw_target_person = str(payload.get("target_person") or "").strip()
    raw_target_item = str(payload.get("target_item") or "").strip()
    success_signals = _normalize_quest_list(list(payload.get("success_signals") or []))
    assignment_context = dict(payload.get("assignment_context") or {})

    if not objective_type:
        if raw_target_item:
            objective_type = "find_item"
        elif raw_target_person and raw_target_location:
            objective_type = "meet_person"
        elif raw_target_person:
            objective_type = "speak_with_person"
        elif raw_target_location:
            objective_type = "visit_location"
        else:
            objective_type = "open_ended"
    if objective_type not in VALID_QUEST_OBJECTIVE_TYPES:
        raise HTTPException(status_code=422, detail="Invalid objective_type.")

    target_location = ""
    target_location_type = ""
    if raw_target_location:
        target_location, target_location_type = _resolve_place_name(db, raw_target_location)
        if not target_location:
            raise HTTPException(status_code=422, detail=f"Unknown target location '{raw_target_location}'.")

    target_person = ""
    target_person_actor_id = ""
    if raw_target_person:
        target_person_actor_id, target_person = _resolve_board_actor_by_name(db, raw_target_person)
        if not target_person_actor_id or not target_person:
            raise HTTPException(status_code=422, detail=f"Unknown target person '{raw_target_person}'.")

    if objective_type in {"visit_location", "observe_location"} and not target_location:
        raise HTTPException(status_code=422, detail=f"{objective_type} quests require a valid target_location.")
    if objective_type in {"speak_with_person", "deliver_message"} and not target_person:
        raise HTTPException(status_code=422, detail=f"{objective_type} quests require a valid target_person.")
    if objective_type == "meet_person" and (not target_person or not target_location):
        raise HTTPException(status_code=422, detail="meet_person quests require both target_person and target_location.")
    if objective_type == "find_item" and not raw_target_item:
        raise HTTPException(status_code=422, detail="find_item quests require a target_item.")

    objective = {
        "objective_type": objective_type,
        "target_location": target_location,
        "target_location_type": target_location_type or None,
        "target_person": target_person,
        "target_person_actor_id": target_person_actor_id or None,
        "target_item": raw_target_item[:160] if raw_target_item else "",
        "success_signals": success_signals or _default_success_signals_for_objective(
            objective_type,
            target_location=target_location,
            target_person=target_person,
            target_item=raw_target_item,
        ),
    }
    preferred = _preferred_intents_for_objective(objective_type)
    if preferred:
        assignment_context["preferred_intent_types"] = preferred
    assignment_context["objective"] = {key: value for key, value in objective.items() if value not in (None, "", [], {})}
    return assignment_context


def _display_name_for_session_row(session_row: SessionVars) -> str:
    from .world import _session_display_details

    _, display_name = _session_display_details(
        str(getattr(session_row, "session_id", "") or ""),
        dict(getattr(session_row, "vars", {}) or {}),
    )
    return str(display_name or getattr(session_row, "session_id", "") or "").strip()


def _session_location_for_board(session_row: SessionVars) -> str | None:
    try:
        location = resolve_current_location(dict(getattr(session_row, "vars", {}) or {}))
    except Exception:
        location = None
    normalized = str(location or "").strip()
    return normalized or None


def _serialize_board_member(
    *,
    actor_id: str,
    display_name: str,
    profile: GuildMemberProfile,
    latest_session: SessionVars | None,
) -> Dict[str, Any]:
    return {
        "actor_id": actor_id,
        "display_name": display_name,
        "member_type": str(getattr(profile, "member_type", "") or "resident").strip(),
        "rank": str(getattr(profile, "rank", "") or "apprentice").strip(),
        "branches": list(getattr(profile, "branches", []) or []),
        "quest_band": str(getattr(profile, "quest_band", "") or "foundations").strip(),
        "mentor_actor_ids": list(getattr(profile, "mentor_actor_ids", []) or []),
        "review_status": dict(getattr(profile, "review_status", {}) or {}),
        "environment_guidance": dict(getattr(profile, "environment_guidance", {}) or {}),
        "session_id": str(getattr(latest_session, "session_id", "") or "").strip() or None,
        "location": _session_location_for_board(latest_session) if latest_session is not None else None,
        "last_updated_at": (
            latest_session.updated_at.isoformat()
            if latest_session is not None and getattr(latest_session, "updated_at", None)
            else None
        ),
    }


def _active_guild_board_payload(db: Session) -> Dict[str, Any]:
    latest_session_by_actor: Dict[str, SessionVars] = {}
    session_rows = (
        db.query(SessionVars)
        .filter(SessionVars.actor_id.isnot(None))
        .order_by(SessionVars.updated_at.desc(), SessionVars.session_id.desc())
        .all()
    )
    for row in session_rows:
        actor_id = str(getattr(row, "actor_id", "") or "").strip()
        if actor_id and actor_id not in latest_session_by_actor:
            latest_session_by_actor[actor_id] = row

    profiles = db.query(GuildMemberProfile).order_by(GuildMemberProfile.updated_at.desc()).all()
    players = db.query(Player).filter(Player.actor_id.isnot(None)).all()
    player_name_by_actor = {
        str(getattr(player, "actor_id", "") or "").strip(): str(getattr(player, "display_name", "") or "").strip()
        for player in players
        if str(getattr(player, "actor_id", "") or "").strip()
    }

    actor_ids: set[str] = set(player_name_by_actor) | set(latest_session_by_actor)
    actor_ids.update(str(getattr(profile, "actor_id", "") or "").strip() for profile in profiles)
    actor_ids.discard("")

    profile_by_actor: Dict[str, GuildMemberProfile] = {}
    for actor_id in sorted(actor_ids):
        existing = next(
            (
                profile
                for profile in profiles
                if str(getattr(profile, "actor_id", "") or "").strip() == actor_id
            ),
            None,
        )
        if existing is not None:
            if actor_id in player_name_by_actor and str(getattr(existing, "member_type", "") or "").strip().lower() != "human":
                existing.member_type = "human"
            profile_by_actor[actor_id] = existing
            continue
        session_row = latest_session_by_actor.get(actor_id)
        profile_by_actor[actor_id] = ensure_guild_member_profile(
            db,
            actor_id=actor_id,
            member_type="human" if actor_id in player_name_by_actor else infer_member_type_for_session(session_row),
        )

    residents: list[Dict[str, Any]] = []
    humans: list[Dict[str, Any]] = []
    display_name_by_actor: Dict[str, str] = {}

    for actor_id in sorted(actor_ids):
        profile = profile_by_actor.get(actor_id)
        if profile is None:
            continue
        session_row = latest_session_by_actor.get(actor_id)
        display_name = (
            player_name_by_actor.get(actor_id)
            or (_display_name_for_session_row(session_row) if session_row is not None else "")
            or actor_id
        )
        display_name_by_actor[actor_id] = display_name
        payload = _serialize_board_member(
            actor_id=actor_id,
            display_name=display_name,
            profile=profile,
            latest_session=session_row,
        )
        if str(getattr(profile, "member_type", "") or "").strip().lower() == "human":
            humans.append(payload)
        else:
            residents.append(payload)

    active_quests = (
        db.query(GuildQuest)
        .filter(GuildQuest.status.in_(["assigned", "accepted", "in_progress"]))
        .order_by(GuildQuest.created_at.desc(), GuildQuest.id.desc())
        .limit(200)
        .all()
    )
    recently_resolved_quests = (
        db.query(GuildQuest)
        .filter(GuildQuest.status.in_(["completed", "reviewed"]))
        .order_by(GuildQuest.updated_at.desc(), GuildQuest.id.desc())
        .limit(80)
        .all()
    )
    serialized_quests: list[Dict[str, Any]] = []
    for quest in active_quests:
        payload = serialize_guild_quest(quest)
        payload["target_display_name"] = display_name_by_actor.get(payload["target_actor_id"]) or payload["target_actor_id"]
        source_actor_id = str(payload.get("source_actor_id") or "").strip()
        payload["source_display_name"] = display_name_by_actor.get(source_actor_id) if source_actor_id else None
        serialized_quests.append(payload)
    serialized_resolved: list[Dict[str, Any]] = []
    for quest in recently_resolved_quests:
        payload = serialize_guild_quest(quest)
        payload["target_display_name"] = display_name_by_actor.get(payload["target_actor_id"]) or payload["target_actor_id"]
        source_actor_id = str(payload.get("source_actor_id") or "").strip()
        payload["source_display_name"] = display_name_by_actor.get(source_actor_id) if source_actor_id else None
        serialized_resolved.append(payload)

    return {
        "residents": sorted(residents, key=lambda item: (item["display_name"].lower(), item["actor_id"])),
        "humans": sorted(humans, key=lambda item: (item["display_name"].lower(), item["actor_id"])),
        "active_quests": serialized_quests,
        "recently_resolved_quests": serialized_resolved,
    }


def _guild_me_payload(db: Session, player: Player) -> Dict[str, Any]:
    actor_id = _require_player_actor_id(player)
    profile = ensure_guild_member_profile(db, actor_id=actor_id, member_type="human")
    capabilities = _guild_capabilities(profile)
    capabilities["can_bootstrap_steward"] = bool(not _has_role_manager(db) or capabilities.get("can_manage_roles"))
    db.flush()
    return {
        "actor_id": actor_id,
        "username": str(getattr(player, "username", "") or "").strip(),
        "display_name": str(getattr(player, "display_name", "") or "").strip(),
        "profile": serialize_guild_member_profile(profile),
        "capabilities": capabilities,
    }


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
        vars_payload = {
            key: value for key, value in vars_payload.items() if str(key).startswith(prefix)
        }
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
    if payload.growth_proposals is not None:
        row.growth_proposals = list(payload.growth_proposals or [])
    db.commit()
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        "growth_text": str(row.growth_text or ""),
        "growth_metadata": dict(row.growth_metadata or {}),
        "note_records": list(row.note_records or []),
        "growth_proposals": list(row.growth_proposals or []),
    }


@router.get("/state/{session_id}/guild-profile")
def get_guild_profile_state(
    session_id: SessionId,
    db: Session = Depends(get_db),
):
    session_row = _resolve_session_row(db, session_id)
    actor_id = _resolve_actor_id_for_session(db, session_id)
    row = ensure_guild_member_profile(
        db,
        actor_id=actor_id,
        member_type=infer_member_type_for_session(session_row),
    )
    db.commit()
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        **serialize_guild_member_profile(row),
    }


@router.post("/state/{session_id}/guild-profile")
def patch_guild_profile_state(
    session_id: SessionId,
    payload: GuildMemberProfilePatchRequest,
    db: Session = Depends(get_db),
):
    session_row = _resolve_session_row(db, session_id)
    actor_id = _resolve_actor_id_for_session(db, session_id)
    row = ensure_guild_member_profile(
        db,
        actor_id=actor_id,
        member_type=infer_member_type_for_session(session_row),
    )
    patch_guild_member_profile(row, payload.model_dump(exclude_none=True))
    db.commit()
    db.refresh(row)
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        **serialize_guild_member_profile(row),
    }


@router.get("/state/{session_id}/social-feedback")
def get_social_feedback_state(
    session_id: SessionId,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    actor_id = _resolve_actor_id_for_session(db, session_id)
    rows = (
        db.query(SocialFeedbackEvent)
        .filter(SocialFeedbackEvent.target_actor_id == actor_id)
        .order_by(SocialFeedbackEvent.created_at.desc(), SocialFeedbackEvent.id.desc())
        .limit(max(1, min(int(limit or 50), 200)))
        .all()
    )
    events = [serialize_social_feedback_event(row) for row in rows]
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        "events": events,
        "count": len(events),
    }


@router.post("/state/{session_id}/social-feedback")
def post_social_feedback_state(
    session_id: SessionId,
    payload: SocialFeedbackEventPatchRequest,
    db: Session = Depends(get_db),
):
    actor_id = _resolve_actor_id_for_session(db, session_id)
    feedback_mode = str(payload.feedback_mode or "inferred").strip().lower()
    if feedback_mode not in VALID_FEEDBACK_MODES:
        raise HTTPException(status_code=422, detail="Invalid feedback_mode.")
    channel = str(payload.channel or "system").strip().lower()
    if channel not in VALID_FEEDBACK_CHANNELS:
        raise HTTPException(status_code=422, detail="Invalid feedback channel.")

    row = SocialFeedbackEvent(
        target_actor_id=actor_id,
        source_actor_id=str(payload.source_actor_id or "").strip() or None,
        source_system=str(payload.source_system or "").strip() or None,
        feedback_mode=feedback_mode,
        channel=channel,
        dimension_scores=normalize_dimension_scores(dict(payload.dimension_scores or {})),
        summary=str(payload.summary or "").strip(),
        evidence_refs=list(payload.evidence_refs or []),
        branch_hint=str(payload.branch_hint or "").strip() or None,
    )
    db.add(row)

    member = ensure_guild_member_profile(db, actor_id=actor_id)
    adaptation = recompute_runtime_adaptation_state(
        db,
        actor_id=actor_id,
        quest_band=str(getattr(member, "quest_band", "") or "foundations"),
    )
    db.commit()
    db.refresh(row)
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        "event": serialize_social_feedback_event(row),
        "adaptation": serialize_runtime_adaptation_state(adaptation),
    }


@router.get("/state/{session_id}/adaptation")
def get_runtime_adaptation_state(
    session_id: SessionId,
    db: Session = Depends(get_db),
):
    actor_id = _resolve_actor_id_for_session(db, session_id)
    member = ensure_guild_member_profile(db, actor_id=actor_id)
    row = recompute_runtime_adaptation_state(
        db,
        actor_id=actor_id,
        quest_band=str(getattr(member, "quest_band", "") or "foundations"),
    )
    db.commit()
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        **serialize_runtime_adaptation_state(row),
    }


@router.get("/state/{session_id}/guild-quests")
def get_guild_quests_state(
    session_id: SessionId,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    actor_id = _resolve_actor_id_for_session(db, session_id)
    query = db.query(GuildQuest).filter(GuildQuest.target_actor_id == actor_id)
    requested_status = str(status or "").strip().lower()
    if requested_status:
        if requested_status == "active":
            query = query.filter(GuildQuest.status.in_(["assigned", "accepted", "in_progress"]))
        elif requested_status in VALID_QUEST_STATUSES:
            query = query.filter(GuildQuest.status == requested_status)
        else:
            raise HTTPException(status_code=422, detail="Invalid quest status filter.")
    rows = (
        query.order_by(GuildQuest.created_at.desc(), GuildQuest.id.desc())
        .limit(max(1, min(int(limit or 50), 200)))
        .all()
    )
    quests = [serialize_guild_quest(row) for row in rows]
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        "quests": quests,
        "count": len(quests),
    }


@router.post("/state/{session_id}/guild-quests")
def post_guild_quest_state(
    session_id: SessionId,
    payload: GuildQuestCreateRequest,
    db: Session = Depends(get_db),
):
    actor_id = _resolve_actor_id_for_session(db, session_id)
    member = ensure_guild_member_profile(db, actor_id=actor_id)
    normalized_payload = payload.model_dump(exclude_none=True)
    normalized_payload["assignment_context"] = _normalize_quest_assignment_context(
        db,
        payload=normalized_payload,
    )
    row = create_guild_quest(
        db,
        actor_id=actor_id,
        payload=normalized_payload,
        default_quest_band=str(getattr(member, "quest_band", "") or "foundations"),
    )
    db.commit()
    db.refresh(row)
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        "quest": serialize_guild_quest(row),
    }


@router.post("/state/{session_id}/guild-quests/{quest_id}")
def patch_guild_quest_state(
    session_id: SessionId,
    quest_id: int,
    payload: GuildQuestPatchRequest,
    db: Session = Depends(get_db),
):
    actor_id = _resolve_actor_id_for_session(db, session_id)
    row = db.get(GuildQuest, int(quest_id))
    if row is None or str(row.target_actor_id or "").strip() != actor_id:
        raise HTTPException(status_code=404, detail="Quest not found.")
    if payload.status is not None and str(payload.status or "").strip().lower() not in VALID_QUEST_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid quest status.")
    patch_guild_quest(row, payload.model_dump(exclude_none=True))
    db.commit()
    db.refresh(row)
    return {
        "session_id": session_id,
        "actor_id": actor_id,
        "quest": serialize_guild_quest(row),
    }


@router.get("/guild/me")
def get_guild_me(
    player: Player = Depends(require_player),
    db: Session = Depends(get_db),
):
    payload = _guild_me_payload(db, player)
    db.commit()
    return payload


@router.get("/guild/board")
def get_guild_board(
    player: Player = Depends(require_player),
    db: Session = Depends(get_db),
):
    me = _guild_me_payload(db, player)
    board = _active_guild_board_payload(db)
    db.commit()
    return {
        "me": me,
        "residents": board["residents"],
        "humans": board["humans"],
        "active_quests": board["active_quests"],
        "recently_resolved_quests": board["recently_resolved_quests"],
        "counts": {
            "resident_members": len(board["residents"]),
            "human_members": len(board["humans"]),
            "active_quests": len(board["active_quests"]),
            "recently_resolved_quests": len(board["recently_resolved_quests"]),
        },
    }


@router.post("/guild/quests")
def post_guild_actor_quest(
    payload: GuildActorQuestCreateRequest,
    player: Player = Depends(require_player),
    db: Session = Depends(get_db),
):
    me = _guild_me_payload(db, player)
    if not bool(me["capabilities"].get("can_assign_quests")):
        raise HTTPException(status_code=403, detail="Guild role cannot assign quests.")
    target_actor_id = str(payload.target_actor_id or "").strip()
    if not target_actor_id:
        raise HTTPException(status_code=422, detail="target_actor_id is required.")
    target_profile = ensure_guild_member_profile(db, actor_id=target_actor_id)
    normalized_payload = payload.model_dump(exclude_none=True, exclude={"target_actor_id"})
    normalized_payload["assignment_context"] = _normalize_quest_assignment_context(
        db,
        payload=normalized_payload,
    )
    quest = create_guild_quest(
        db,
        actor_id=target_actor_id,
        payload={
            **normalized_payload,
            "source_actor_id": str(me["actor_id"]),
        },
        default_quest_band=str(getattr(target_profile, "quest_band", "") or "foundations"),
    )
    db.commit()
    db.refresh(quest)
    board = _active_guild_board_payload(db)
    target_display_name = next(
        (
            item["display_name"]
            for item in (board["residents"] + board["humans"])
            if str(item.get("actor_id") or "") == target_actor_id
        ),
        target_actor_id,
    )
    return {
        "quest": {
            **serialize_guild_quest(quest),
            "target_display_name": target_display_name,
            "source_display_name": str(me["display_name"]),
        }
    }


@router.post("/guild/starter-packs")
def post_guild_starter_packs(
    payload: GuildStarterPackIssueRequest,
    player: Player = Depends(require_player),
    db: Session = Depends(get_db),
):
    me = _guild_me_payload(db, player)
    if not bool(me["capabilities"].get("can_assign_quests")):
        raise HTTPException(status_code=403, detail="Guild role cannot assign starter packs.")
    source_actor_id = str(me["actor_id"] or "").strip()
    if payload.target_actor_id:
        result = issue_starter_pack(
            db,
            target_actor_id=str(payload.target_actor_id).strip(),
            source_actor_id=source_actor_id,
        )
        db.commit()
        issued = [dict(result["issued"])] if result.get("issued") else []
        skipped = [dict(result["skipped"])] if result.get("skipped") else []
        return {
            "pack_id": STARTER_PACK_ID,
            "issued": issued,
            "skipped": skipped,
        }

    result = issue_starter_packs_for_eligible_apprentices(
        db,
        source_actor_id=source_actor_id,
    )
    db.commit()
    return result


@router.post("/guild/bootstrap-steward")
def bootstrap_guild_steward(
    player: Player = Depends(require_player),
    db: Session = Depends(get_db),
):
    me = _guild_me_payload(db, player)
    if _has_role_manager(db) and not bool(me["capabilities"].get("can_manage_roles")):
        raise HTTPException(status_code=409, detail="A guild steward already exists.")
    actor_id = str(me["actor_id"])
    profile = ensure_guild_member_profile(db, actor_id=actor_id, member_type="human")
    review_status = dict(getattr(profile, "review_status", {}) or {})
    review_status.update(
        {
            "guild_role": "steward",
            "governance_roles": ["steward", "mentor"],
            "can_assign_quests": True,
            "can_manage_roles": True,
            "bootstrap_granted_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    patch_guild_member_profile(
        profile,
        {
            "rank": "elder",
            "review_status": review_status,
        },
    )
    db.commit()
    return _guild_me_payload(db, player)


@router.post("/guild/members/{actor_id}/profile")
def patch_guild_member_profile_as_steward(
    actor_id: str,
    payload: GuildMemberGovernancePatchRequest,
    player: Player = Depends(require_player),
    db: Session = Depends(get_db),
):
    me = _guild_me_payload(db, player)
    if not bool(me["capabilities"].get("can_manage_roles")):
        raise HTTPException(status_code=403, detail="Guild role cannot manage member profiles.")
    target_actor_id = str(actor_id or "").strip()
    if not target_actor_id:
        raise HTTPException(status_code=422, detail="actor_id is required.")

    session_row = (
        db.query(SessionVars)
        .filter(SessionVars.actor_id == target_actor_id)
        .order_by(SessionVars.updated_at.desc(), SessionVars.session_id.desc())
        .first()
    )
    member_type = infer_member_type_for_session(session_row)
    row = ensure_guild_member_profile(
        db,
        actor_id=target_actor_id,
        member_type=member_type,
    )
    patch_guild_member_profile(row, payload.model_dump(exclude_none=True))
    db.commit()
    db.refresh(row)
    return {
        "actor_id": target_actor_id,
        **serialize_guild_member_profile(row),
        "capabilities": _guild_capabilities(row),
    }


@router.post("/state/{session_id}/relationship")
def update_relationship(
    session_id: SessionId,
    entity_a: str,
    entity_b: str,
    changes: Dict[str, float],
    memory: str | None = None,
    db: Session = Depends(get_db),
):
    """Update a relationship between entities."""
    state_manager = get_state_manager(session_id, db)
    relationship = state_manager.update_relationship(entity_a, entity_b, changes, memory)
    save_state_to_db(state_manager, db)

    return {
        "relationship": f"{entity_a}-{entity_b}",
        "disposition": relationship.get_overall_disposition(),
        "trust": relationship.trust,
        "respect": relationship.respect,
        "interaction_count": relationship.interaction_count,
    }


@router.post("/state/{session_id}/item")
def add_item_to_inventory(
    session_id: SessionId,
    item_id: str,
    name: str,
    quantity: int = 1,
    properties: Dict[str, Any] | None = None,
    db: Session = Depends(get_db),
):
    """Add an item to the player's inventory."""
    state_manager = get_state_manager(session_id, db)
    item = state_manager.add_item(item_id, name, quantity, properties or {})
    save_state_to_db(state_manager, db)

    return {
        "item_id": item.id,
        "name": item.name,
        "quantity": item.quantity,
        "condition": item.condition,
        "available_actions": item.get_available_actions(state_manager.get_contextual_variables()),
    }


@router.post("/state/{session_id}/environment")
def update_environment(
    session_id: SessionId,
    changes: Dict[str, Any],
    db: Session = Depends(get_db),
):
    """Update environmental conditions."""
    state_manager = get_state_manager(session_id, db)
    state_manager.update_environment(changes)
    save_state_to_db(state_manager, db)

    return {
        "environment": {
            "time_of_day": state_manager.environment.time_of_day,
            "weather": state_manager.environment.weather,
            "danger_level": state_manager.environment.danger_level,
            "mood_modifiers": state_manager.environment.get_mood_modifier(),
        }
    }


@router.post("/state/{session_id}/goal")
def update_goal_state(
    session_id: SessionId,
    payload: GoalUpdateRequest,
    db: Session = Depends(get_db),
):
    """Create or update primary goal and goal signals for a session."""
    state_manager = get_state_manager(session_id, db)
    if payload.primary_goal is None and payload.subgoals is None and payload.urgency is None and payload.complication is None:
        raise HTTPException(status_code=422, detail="Goal update payload is empty.")

    goal = state_manager.set_goal_state(
        primary_goal=payload.primary_goal,
        subgoals=payload.subgoals,
        urgency=payload.urgency,
        complication=payload.complication,
        note=payload.note,
        source="api",
    )
    save_state_to_db(state_manager, db)
    return {"goal": goal, "arc_timeline": state_manager.get_arc_timeline(limit=20)}


@router.post("/state/{session_id}/goal/milestone")
def add_goal_milestone(
    session_id: SessionId,
    payload: GoalMilestoneRequest,
    db: Session = Depends(get_db),
):
    """Append a goal milestone and update urgency/complication signals."""
    state_manager = get_state_manager(session_id, db)
    goal = state_manager.mark_goal_milestone(
        payload.title,
        status=payload.status,
        note=str(payload.note or ""),
        source="api",
        urgency_delta=payload.urgency_delta,
        complication_delta=payload.complication_delta,
    )
    save_state_to_db(state_manager, db)
    return {"goal": goal, "arc_timeline": state_manager.get_arc_timeline(limit=20)}


def _seed_if_test_db() -> None:
    """Seed legacy test database file when running spatial tests."""
    try:
        if os.getenv("WW_DB_PATH") == "test_database.db":
            db = SessionLocal()
            seed_legacy_storylets_if_empty_sync(db)
            db.commit()
            db.close()
    except Exception:
        pass


_seed_if_test_db()


def _clear_runtime_caches() -> None:
    _state_managers.clear()
    _runtime_synthesis_counts.clear()
    clear_prefetch_cache()


def _clear_runtime_session_caches(session_id: str) -> None:
    safe_session_id = str(session_id or "").strip()
    if not safe_session_id:
        return
    remove_cached_sessions([safe_session_id])
    _runtime_synthesis_counts.pop(safe_session_id, None)
    clear_prefetch_cache_for_session(safe_session_id)


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
    storylets_deleted = db.query(Storylet).delete(synchronize_session=False)
    db.commit()
    return {
        "storylets": int(storylets_deleted),
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

    This is an admin-only operation. It generates a unique world_id, creates the
    world bible and initial storylets, and stores the world_id server-side so all
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
        world_result: dict = {"storylets_created": 0, "world_bible": None}

        state_manager = get_state_manager(world_id, db)
        state_manager.set_variable("world_theme", payload.world_theme)
        state_manager.set_variable("player_role", payload.player_role)
        state_manager.set_variable("world_tone", tone)
        state_manager.set_variable("_bootstrap_state", "completed")
        state_manager.set_variable("_bootstrap_source", "world-seed")

        world_bible = world_result.get("world_bible")
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
            if world_bible and isinstance(world_bible, dict):
                state_manager.set_world_bible(world_bible)
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
        elif world_bible and isinstance(world_bible, dict):
            state_manager.set_world_bible(world_bible)
            world_context = world_bible_to_context_header(
                world_bible,
                fallback_world_name=payload.world_theme,
                fallback_theme=payload.world_theme,
                fallback_tone=tone,
            )
        state_manager.set_world_context(world_context)
        save_state(state_manager, db)

        _write_world_id(world_id)

        return WorldSeedResponse(
            success=True,
            world_id=world_id,
            storylets_created=int(world_result.get("storylets_created", 0)),
            world_bible_generated=bool(world_bible),
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
    """Initialize world content + onboarding vars before first /api/next turn.

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
                cp_nodes = (
                    db.query(WorldNode)
                    .filter(WorldNode.node_type == "location")
                    .limit(500)
                    .all()
                )
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
    include_legacy_seed: bool = False,
    db: Session = Depends(get_db),
):
    """Hard-reset world/session data; optionally reseed legacy test storylets."""
    try:
        deleted = _delete_all_world_rows(db)

        # Legacy seeding is isolated behind explicit request + feature flag.
        should_seed_legacy = bool(include_legacy_seed and settings.enable_legacy_test_seeds)
        storylets_seeded = 0
        if should_seed_legacy:
            storylets_seeded = seed_if_empty_sync(db, allow_legacy_seed=True)
            db.commit()

        _clear_runtime_caches()

        return {
            "success": True,
            "message": "World reset complete.",
            "deleted": deleted,
            "storylets_seeded": int(storylets_seeded),
            "legacy_seed_mode": should_seed_legacy,
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


@router.get("/world/{world_id}/events")
def get_world_events(
    world_id: SessionId,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Return recent events for a shared world — readable by all residents.

    Any resident or observer can call this to perceive what other residents
    have done in the shared world.  Pass ``limit`` to control how many events
    are returned (default 50, max 200).
    """
    from ...services import world_memory

    limit = max(1, min(int(limit), 200))
    try:
        events = world_memory.get_world_history(db, session_id=str(world_id), limit=limit)
        return {
            "world_id": str(world_id),
            "event_count": len(events),
            "events": [
                {
                    "id": e.id,
                    "session_id": e.session_id,
                    "event_type": e.event_type,
                    "summary": e.summary,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ],
        }
    except Exception as exc:
        logging.error("get_world_events failed for world_id=%s: %s", world_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to fetch world events: {str(exc)}")


@router.get("/dev/jit-test")
def dev_jit_test(
    theme: str = "solarpunk",
    player_role: str = "local troublemaker",
    tone: str = "adventure",
):
    """Developer-only: call generate_world_bible directly and return raw result or error."""
    if not settings.enable_dev_reset:
        raise HTTPException(status_code=404, detail="Not found")

    import os
    import traceback
    from ...services.llm_service import generate_world_bible
    from ...services.llm_client import (
        get_api_key,
        get_llm_client,
        get_model,
        is_ai_disabled,
        platform_shared_policy,
    )

    # Inline diagnostics
    diag = {
        "is_ai_disabled": is_ai_disabled(),
        "get_model": get_model(),
        "get_api_key_prefix": (get_api_key() or "NONE")[:20],
        "client_is_none": get_llm_client(policy=platform_shared_policy(owner_id="debug_llm")) is None,
        "llm_timeout": settings.llm_timeout_seconds,
        "v3_runtime": settings.get_v3_runtime_settings(),
        "WW_DISABLE_AI": os.getenv("WW_DISABLE_AI"),
        "WW_FAST_TEST": os.getenv("WW_FAST_TEST"),
        "PYTEST_CURRENT_TEST": os.getenv("PYTEST_CURRENT_TEST"),
    }

    try:
        bible = generate_world_bible(
            description=f"A {tone} world in a {theme} setting.",
            theme=theme,
            player_role=player_role,
            tone=tone,
        )
        return {
            "success": True,
            "world_bible": bible,
            "locations_count": len(bible.get("locations", [])),
            "npcs_count": len(bible.get("npcs", [])),
            "_diag": diag,
        }
    except Exception as exc:
        return {
            "success": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "_diag": diag,
        }
