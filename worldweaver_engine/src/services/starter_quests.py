"""Starter quest packs for new guild apprentices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models import GuildMemberProfile, GuildQuest, Player, SessionVars, WorldNode
from .guild_service import create_guild_quest, ensure_guild_member_profile, patch_guild_member_profile
STARTER_PACK_ID = "apprentice_foundations_v1"
STARTER_PACK_LABEL = "Apprentice Foundations"
STARTER_PACK_DESCRIPTION = "A first quest track for grounded observation, contact, and movement."

_PREFERRED_INTENTS = {
    "visit_location": ["move"],
    "observe_location": ["move", "ground", "act"],
    "speak_with_person": ["chat", "mail_draft"],
    "meet_person": ["move", "chat", "mail_draft"],
    "deliver_message": ["mail_draft", "chat"],
    "find_item": ["move", "act", "ground", "chat"],
    "open_ended": [],
}


@dataclass(frozen=True)
class _MemberSnapshot:
    actor_id: str
    display_name: str
    member_type: str
    rank: str
    quest_band: str
    location: str
    review_status: dict[str, Any]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_name_for_member(
    *,
    actor_id: str,
    session_row: SessionVars | None,
    player_name: str,
) -> str:
    if player_name:
        return player_name
    if session_row is not None:
        vars_payload = dict(getattr(session_row, "vars", {}) or {})
        session_name = str(vars_payload.get("player_role") or vars_payload.get("display_name") or "").strip()
        if session_name:
            return session_name
    return actor_id


def _location_for_member(session_row: SessionVars | None) -> str:
    if session_row is None:
        return ""
    payload = dict(getattr(session_row, "vars", {}) or {})
    if payload.get("_v") == 2 and isinstance(payload.get("variables"), dict):
        variables = dict(payload.get("variables") or {})
        location = variables.get("location")
        return str(location or "").strip()
    return str(payload.get("location") or "").strip()


def _member_snapshots(db: Session) -> list[_MemberSnapshot]:
    latest_session_by_actor: dict[str, SessionVars] = {}
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

    profiles = db.query(GuildMemberProfile).all()
    players = db.query(Player).filter(Player.actor_id.isnot(None)).all()

    player_name_by_actor = {
        str(getattr(player, "actor_id", "") or "").strip(): str(getattr(player, "display_name", "") or "").strip()
        for player in players
        if str(getattr(player, "actor_id", "") or "").strip()
    }
    profile_by_actor = {
        str(getattr(profile, "actor_id", "") or "").strip(): profile
        for profile in profiles
        if str(getattr(profile, "actor_id", "") or "").strip()
    }
    actor_ids = set(latest_session_by_actor) | set(player_name_by_actor) | set(profile_by_actor)
    actor_ids.discard("")

    snapshots: list[_MemberSnapshot] = []
    for actor_id in sorted(actor_ids):
        profile = profile_by_actor.get(actor_id)
        session_row = latest_session_by_actor.get(actor_id)
        member_type = str(getattr(profile, "member_type", "") or "").strip() or ("human" if actor_id in player_name_by_actor else "resident")
        snapshots.append(
            _MemberSnapshot(
                actor_id=actor_id,
                display_name=_display_name_for_member(
                    actor_id=actor_id,
                    session_row=session_row,
                    player_name=player_name_by_actor.get(actor_id, ""),
                ),
                member_type=member_type,
                rank=str(getattr(profile, "rank", "") or "apprentice").strip() or "apprentice",
                quest_band=str(getattr(profile, "quest_band", "") or "foundations").strip() or "foundations",
                location=_location_for_member(session_row),
                review_status=dict(getattr(profile, "review_status", {}) or {}),
            )
        )
    return snapshots


def _world_places(db: Session) -> list[str]:
    rows = (
        db.query(WorldNode.name)
        .filter(WorldNode.node_type.in_(["location", "landmark"]))
        .order_by(WorldNode.name.asc())
        .all()
    )
    places: list[str] = []
    seen: set[str] = set()
    for (name,) in rows:
        candidate = str(name or "").strip()
        key = candidate.lower()
        if not candidate or key in seen:
            continue
        seen.add(key)
        places.append(candidate)
    return places


def _starter_pack_meta(review_status: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(review_status or {})
    starter = payload.get("starter_pack")
    return dict(starter) if isinstance(starter, dict) else {}


def _is_eligible_for_starter_pack(member: _MemberSnapshot) -> tuple[bool, str]:
    if str(member.rank or "").strip().lower() != "apprentice":
        return (False, "not_apprentice")
    existing = _starter_pack_meta(member.review_status)
    if str(existing.get("pack_id") or "").strip():
        return (False, "already_issued")
    return (True, "")


def _choose_contact(target: _MemberSnapshot, members: list[_MemberSnapshot]) -> _MemberSnapshot | None:
    candidates = [member for member in members if member.actor_id != target.actor_id]
    if not candidates:
        return None
    candidates.sort(key=lambda member: (
        0 if member.location and target.location and member.location.lower() != target.location.lower() else 1,
        0 if member.member_type == "human" else 1,
        member.display_name.lower(),
    ))
    return candidates[0]


def _choose_destination(target: _MemberSnapshot, members: list[_MemberSnapshot], places: list[str]) -> str:
    target_location_key = target.location.lower()
    for member in sorted(members, key=lambda item: item.display_name.lower()):
        location = str(member.location or "").strip()
        if location and location.lower() != target_location_key:
            return location
    for place in places:
        if place.lower() != target_location_key:
            return place
    return ""


def _objective_context(
    *,
    objective_type: str,
    target_location: str = "",
    target_person: str = "",
    target_person_actor_id: str = "",
    target_item: str = "",
    success_signals: list[str],
    starter_step_id: str,
    starter_label: str,
    issued_at: str,
) -> dict[str, Any]:
    objective = {
        "objective_type": objective_type,
        "target_location": target_location or None,
        "target_person": target_person or None,
        "target_person_actor_id": target_person_actor_id or None,
        "target_item": target_item or None,
        "success_signals": [signal for signal in success_signals if str(signal or "").strip()],
    }
    preferred = list(_PREFERRED_INTENTS.get(objective_type, []))
    context: dict[str, Any] = {
        "starter_pack": {
            "pack_id": STARTER_PACK_ID,
            "step_id": starter_step_id,
            "label": starter_label,
            "issued_at": issued_at,
        },
        "objective": {key: value for key, value in objective.items() if value not in (None, "", [], {})},
    }
    if preferred:
        context["preferred_intent_types"] = preferred
    return context


def _starter_pack_payloads(
    *,
    target: _MemberSnapshot,
    members: list[_MemberSnapshot],
    places: list[str],
    issued_at: str,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    contact = _choose_contact(target, members)
    destination = _choose_destination(target, members, places)

    if target.location:
        payloads.append(
            {
                "title": f"Observe {target.location}",
                "brief": (
                    f"Start with grounded observation. Spend time at {target.location} and report one concrete detail, "
                    "one person or activity you noticed, and one thing that seems different from first glance."
                ),
                "branch": "civic",
                "quest_band": target.quest_band or "foundations",
                "objective_type": "observe_location",
                "target_location": target.location,
                "success_signals": [
                    f"arrive at {target.location}",
                    f"describe conditions at {target.location}",
                    "report one concrete detail from the scene",
                ],
                "assignment_context": _objective_context(
                    objective_type="observe_location",
                    target_location=target.location,
                    success_signals=[
                        f"arrive at {target.location}",
                        f"describe conditions at {target.location}",
                        "report one concrete detail from the scene",
                    ],
                    starter_step_id="observe_local",
                    starter_label="Observe your current surroundings",
                    issued_at=issued_at,
                ),
            }
        )

    if contact is not None:
        payloads.append(
            {
                "title": f"Reach out to {contact.display_name}",
                "brief": (
                    f"Make direct contact with {contact.display_name}. Reach out in local chat or by message and bring back "
                    "one concrete thing they said or asked for."
                ),
                "branch": "social",
                "quest_band": target.quest_band or "foundations",
                "objective_type": "speak_with_person",
                "target_person": contact.display_name,
                "success_signals": [
                    f"{contact.display_name} replies",
                    f"report what {contact.display_name} said",
                    "show that direct contact actually happened",
                ],
                "assignment_context": _objective_context(
                    objective_type="speak_with_person",
                    target_person=contact.display_name,
                    target_person_actor_id=contact.actor_id,
                    success_signals=[
                        f"{contact.display_name} replies",
                        f"report what {contact.display_name} said",
                        "show that direct contact actually happened",
                    ],
                    starter_step_id="reach_out",
                    starter_label="Reach out to a known member",
                    issued_at=issued_at,
                ),
            }
        )

    if contact is not None and contact.location and target.location and contact.location.lower() != target.location.lower():
        payloads.append(
            {
                "title": f"Meet {contact.display_name} at {contact.location}",
                "brief": (
                    f"Leave your current loop and meet {contact.display_name} at {contact.location}. Confirm that the meeting happened "
                    "and report one concrete detail from the exchange."
                ),
                "branch": "social",
                "quest_band": target.quest_band or "foundations",
                "objective_type": "meet_person",
                "target_location": contact.location,
                "target_person": contact.display_name,
                "success_signals": [
                    f"arrive at {contact.location}",
                    f"meet with {contact.display_name}",
                    "report one concrete detail from the meeting",
                ],
                "assignment_context": _objective_context(
                    objective_type="meet_person",
                    target_location=contact.location,
                    target_person=contact.display_name,
                    target_person_actor_id=contact.actor_id,
                    success_signals=[
                        f"arrive at {contact.location}",
                        f"meet with {contact.display_name}",
                        "report one concrete detail from the meeting",
                    ],
                    starter_step_id="cross_contact",
                    starter_label="Travel and meet someone outside your current loop",
                    issued_at=issued_at,
                ),
            }
        )
    elif destination:
        payloads.append(
            {
                "title": f"Visit {destination}",
                "brief": (
                    f"Go to {destination} for a concrete look around. Bring back one grounded detail about what is happening there "
                    "and why this place feels different from where you started."
                ),
                "branch": "civic",
                "quest_band": target.quest_band or "foundations",
                "objective_type": "visit_location",
                "target_location": destination,
                "success_signals": [
                    f"arrive at {destination}",
                    f"report one grounded detail from {destination}",
                    "note how the destination differs from where you began",
                ],
                "assignment_context": _objective_context(
                    objective_type="visit_location",
                    target_location=destination,
                    success_signals=[
                        f"arrive at {destination}",
                        f"report one grounded detail from {destination}",
                        "note how the destination differs from where you began",
                    ],
                    starter_step_id="move_elsewhere",
                    starter_label="Travel to a different part of the world",
                    issued_at=issued_at,
                ),
            }
        )

    return payloads[:3]


def issue_starter_pack(
    db: Session,
    *,
    target_actor_id: str,
    source_actor_id: str,
) -> dict[str, Any]:
    snapshots = _member_snapshots(db)
    target = next((member for member in snapshots if member.actor_id == target_actor_id), None)
    if target is None:
        return {"issued": None, "skipped": {"actor_id": target_actor_id, "display_name": target_actor_id, "reason": "unknown_member"}}

    eligible, reason = _is_eligible_for_starter_pack(target)
    if not eligible:
        return {"issued": None, "skipped": {"actor_id": target.actor_id, "display_name": target.display_name, "reason": reason}}

    issued_at = _iso_now()
    payloads = _starter_pack_payloads(
        target=target,
        members=snapshots,
        places=_world_places(db),
        issued_at=issued_at,
    )
    if not payloads:
        return {
            "issued": None,
            "skipped": {
                "actor_id": target.actor_id,
                "display_name": target.display_name,
                "reason": "insufficient_world_context",
            },
        }

    profile = ensure_guild_member_profile(db, actor_id=target.actor_id, member_type=target.member_type)
    quest_ids: list[int] = []
    for payload in payloads:
        row = create_guild_quest(
            db,
            actor_id=target.actor_id,
            payload={
                **payload,
                "source_actor_id": source_actor_id,
                "source_system": "guild_starter_pack",
                "review_status": {
                    "starter_pack_id": STARTER_PACK_ID,
                },
            },
            default_quest_band=str(getattr(profile, "quest_band", "") or target.quest_band or "foundations"),
        )
        quest_ids.append(int(row.id))

    next_review_status = dict(getattr(profile, "review_status", {}) or {})
    next_review_status["starter_pack"] = {
        "pack_id": STARTER_PACK_ID,
        "label": STARTER_PACK_LABEL,
        "description": STARTER_PACK_DESCRIPTION,
        "issued_at": issued_at,
        "issued_by_actor_id": source_actor_id,
        "quest_ids": quest_ids,
        "quest_count": len(quest_ids),
    }
    patch_guild_member_profile(profile, {"review_status": next_review_status})

    return {
        "issued": {
            "actor_id": target.actor_id,
            "display_name": target.display_name,
            "quest_ids": quest_ids,
            "quest_count": len(quest_ids),
        },
        "skipped": None,
    }


def issue_starter_packs_for_eligible_apprentices(
    db: Session,
    *,
    source_actor_id: str,
) -> dict[str, Any]:
    issued: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    snapshots = _member_snapshots(db)
    for member in snapshots:
        eligible, reason = _is_eligible_for_starter_pack(member)
        if not eligible:
            skipped.append(
                {
                    "actor_id": member.actor_id,
                    "display_name": member.display_name,
                    "reason": reason,
                }
            )
            continue
        result = issue_starter_pack(db, target_actor_id=member.actor_id, source_actor_id=source_actor_id)
        if result.get("issued"):
            issued.append(dict(result["issued"]))
        elif result.get("skipped"):
            skipped.append(dict(result["skipped"]))
    return {
        "pack_id": STARTER_PACK_ID,
        "issued": issued,
        "skipped": skipped,
    }


def reset_starter_pack(
    db: Session,
    *,
    target_actor_id: str,
) -> dict[str, Any]:
    snapshots = _member_snapshots(db)
    target = next((member for member in snapshots if member.actor_id == target_actor_id), None)
    if target is None:
        return {"reset": None, "skipped": {"actor_id": target_actor_id, "display_name": target_actor_id, "reason": "unknown_member"}}

    profile = db.get(GuildMemberProfile, target.actor_id)
    review_status = dict(getattr(profile, "review_status", {}) or {}) if profile is not None else {}
    starter_pack = _starter_pack_meta(review_status)
    if str(starter_pack.get("pack_id") or "").strip() != STARTER_PACK_ID:
        return {"reset": None, "skipped": {"actor_id": target.actor_id, "display_name": target.display_name, "reason": "no_starter_pack"}}

    issued_quest_ids = [
        int(item)
        for item in list(starter_pack.get("quest_ids") or [])
        if str(item or "").strip().isdigit() and int(item) > 0
    ]
    deleted_quest_ids: list[int] = []
    if issued_quest_ids:
        rows = (
            db.query(GuildQuest)
            .filter(GuildQuest.target_actor_id == target.actor_id, GuildQuest.id.in_(issued_quest_ids))
            .all()
        )
        deleted_quest_ids = [int(row.id) for row in rows]
        for row in rows:
            db.delete(row)
    else:
        rows = (
            db.query(GuildQuest)
            .filter(
                GuildQuest.target_actor_id == target.actor_id,
                GuildQuest.source_system == "guild_starter_pack",
            )
            .all()
        )
        deleted_quest_ids = [int(row.id) for row in rows]
        for row in rows:
            db.delete(row)

    next_review_status = dict(review_status)
    next_review_status.pop("starter_pack", None)
    if profile is not None:
        patch_guild_member_profile(profile, {"review_status": next_review_status})

    return {
        "reset": {
            "actor_id": target.actor_id,
            "display_name": target.display_name,
            "quest_ids": deleted_quest_ids,
            "quest_count": len(deleted_quest_ids),
        },
        "skipped": None,
    }


def reset_starter_packs_for_issued_members(db: Session) -> dict[str, Any]:
    reset: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    snapshots = _member_snapshots(db)
    for member in snapshots:
        starter_pack = _starter_pack_meta(member.review_status)
        if str(starter_pack.get("pack_id") or "").strip() != STARTER_PACK_ID:
            continue
        result = reset_starter_pack(db, target_actor_id=member.actor_id)
        if result.get("reset"):
            reset.append(dict(result["reset"]))
        elif result.get("skipped"):
            skipped.append(dict(result["skipped"]))
    return {
        "pack_id": STARTER_PACK_ID,
        "reset": reset,
        "skipped": skipped,
    }
