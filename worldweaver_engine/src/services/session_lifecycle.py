# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Canonical rules for joining and leaving one shard session."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..models import FederationActorAuth, Player, SessionVars, WorldNode
from .event_submission import WorldEventCommand, submit_world_event
from .federation_identity import current_shard_id, get_actor_bundle
from .resident_authority import (
    ResidentAuthorityError,
    bind_resident_session,
)
from .session_service import (
    get_state_manager,
    remove_cached_sessions,
    stage_state,
)
from .world_memory import EVENT_TYPE_SESSION_BOOTSTRAP

_AGENT_SLUG_RE = re.compile(r"^([a-z][a-z0-9_]*)[-_]\d{8}")


class SessionLifecycleError(ValueError):
    """A safe, typed refusal from the session-lifecycle boundary."""

    def __init__(
        self,
        code: str,
        detail: str | dict[str, str],
        *,
        status_code: int,
    ):
        message = detail if isinstance(detail, str) else detail.get("message", code)
        super().__init__(message)
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class SessionBootstrapCommand:
    session_id: str
    player_role: str
    world_id: str | None
    actor_id: str | None = None
    world_theme: str = ""
    key_elements: tuple[str, ...] = field(default_factory=tuple)
    tone: str = ""
    bootstrap_source: str = "onboarding"
    entry_location: str | None = None


@dataclass(frozen=True)
class ResidentSessionBinding:
    actor_id: str
    runtime_generation: int


@dataclass(frozen=True)
class SessionBootstrapReceipt:
    success: bool
    message: str
    session_id: str
    vars: dict[str, Any]
    theme: str
    player_role: str
    bootstrap_state: str
    bootstrap_diagnostics: dict[str, Any]

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SessionRetirementReceipt:
    success: bool
    message: str
    session_id: str
    deleted: dict[str, int]

    def as_payload(self) -> dict[str, Any]:
        return asdict(self)


def _slug_display_name(session_id: str) -> str | None:
    match = _AGENT_SLUG_RE.match(str(session_id or ""))
    if not match:
        return None
    return " ".join(part.capitalize() for part in match.group(1).split("_"))


def _require_ordinary_player_attachment(
    db: Session,
    *,
    session_id: str,
    bootstrap_source: str,
    player: Player | None,
) -> None:
    if player is None or str(bootstrap_source or "").strip() == "federation-travel":
        return

    actor_id = str(player.actor_id or "").strip()
    if not actor_id:
        raise SessionLifecycleError(
            "actor_identity_missing",
            "This player has no durable actor identity.",
            status_code=409,
        )

    actor_auth = db.get(FederationActorAuth, actor_id)
    if (
        settings.require_email_verification
        and actor_auth is not None
        and actor_auth.email_verified_at is None
    ):
        raise SessionLifecycleError(
            "email_unverified", "email_unverified", status_code=409
        )
    if actor_auth is not None and actor_auth.profile_completed_at is None:
        raise SessionLifecycleError(
            "profile_incomplete", "profile_incomplete", status_code=409
        )

    live_session = (
        db.query(SessionVars).filter(SessionVars.actor_id == actor_id).first()
    )
    if live_session is not None and str(live_session.session_id) != session_id:
        raise SessionLifecycleError(
            "actor_already_present",
            f"This actor is already present in local session '{live_session.session_id}'.",
            status_code=409,
        )

    attachment = get_actor_bundle(db, actor_id)
    local_shard = current_shard_id()
    if attachment.status == "traveling":
        raise SessionLifecycleError(
            "actor_traveling",
            "This actor is currently traveling and must finish that trip before ordinary entry.",
            status_code=409,
        )
    if attachment.current_shard != local_shard:
        raise SessionLifecycleError(
            "actor_attached_elsewhere",
            (
                f"This actor is attached to '{attachment.current_shard}', not "
                f"'{local_shard}'. Enter through federation travel rather than "
                "opening a second city presence."
            ),
            status_code=409,
        )


def stage_retire_session_presence(db: Session, session_id: str) -> dict[str, int]:
    """Stage removal of one live presence without erasing public history."""

    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return {"sessions": 0}
    sessions_deleted = (
        db.query(SessionVars)
        .filter(SessionVars.session_id == normalized_session_id)
        .delete(synchronize_session=False)
    )
    db.flush()
    return {"sessions": int(sessions_deleted)}


def retire_session_presence(
    db: Session,
    *,
    session_id: str,
) -> SessionRetirementReceipt:
    """Commit retirement of one live presence and clear its local cache."""

    normalized_session_id = str(session_id or "").strip()
    deleted = stage_retire_session_presence(db, normalized_session_id)
    db.commit()
    remove_cached_sessions([normalized_session_id])
    return SessionRetirementReceipt(
        success=True,
        message="Session removed from shard.",
        session_id=normalized_session_id,
        deleted=deleted,
    )


def _stage_duplicate_agent_retirement(
    db: Session,
    *,
    keep_session_id: str,
    display_name: str,
) -> tuple[dict[str, Any], list[str]]:
    target_name = str(display_name or "").strip().lower()
    groups: dict[str, list[tuple[str, datetime | None]]] = {}

    for row in db.query(SessionVars).all():
        session_id = str(row.session_id or "").strip()
        agent_name = _slug_display_name(session_id)
        if not session_id or not agent_name:
            continue
        normalized_name = agent_name.lower()
        if target_name and normalized_name != target_name:
            continue
        groups.setdefault(normalized_name, []).append((session_id, row.updated_at))

    pruned: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    retired_session_ids: list[str] = []
    for normalized_name, entries in groups.items():
        if len(entries) <= 1:
            continue
        display = " ".join(part.capitalize() for part in normalized_name.split(" "))
        if any(session_id == keep_session_id for session_id, _ in entries):
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
            deleted = stage_retire_session_presence(db, stale_session_id)
            retired_session_ids.append(stale_session_id)
            pruned.append(
                {
                    "display_name": display,
                    "session_id": stale_session_id,
                    "deleted": deleted,
                }
            )

    return (
        {
            "groups_considered": len(groups),
            "kept": kept,
            "pruned": pruned,
            "pruned_count": len(pruned),
        },
        retired_session_ids,
    )


def bootstrap_session(
    db: Session,
    *,
    command: SessionBootstrapCommand,
    player: Player | None = None,
    resident_binding: ResidentSessionBinding | None = None,
) -> SessionBootstrapReceipt:
    """Join one existing world and commit the complete local session together."""

    session_id = str(command.session_id or "").strip()
    if not session_id or len(session_id) > 64:
        raise SessionLifecycleError(
            "invalid_session",
            "Session ID must contain 1 to 64 characters.",
            status_code=422,
        )
    if db.get(SessionVars, session_id) is not None:
        raise SessionLifecycleError(
            "session_id_in_use",
            f"Session ID '{session_id}' is already in use on this node.",
            status_code=409,
        )

    _require_ordinary_player_attachment(
        db,
        session_id=session_id,
        bootstrap_source=command.bootstrap_source,
        player=player,
    )

    player_role = str(command.player_role or "").strip()
    if not player_role:
        raise SessionLifecycleError(
            "player_role_required",
            "player_role must not be blank.",
            status_code=422,
        )
    world_id = str(command.world_id or "").strip()
    if not world_id:
        raise SessionLifecycleError(
            "world_id_required",
            (
                "world_id is required. Seed the world first via POST "
                "/api/world/seed, then pass the returned world_id here."
            ),
            status_code=422,
        )

    try:
        host_state = get_state_manager(world_id, db)
        inherited_context = host_state.get_world_context()
        world_theme = str(command.world_theme or "").strip()
        if not world_theme:
            world_theme = str(host_state.get_variable("world_theme") or "")

        state_manager = get_state_manager(session_id, db)
        bootstrap_completed_at = datetime.now(timezone.utc).isoformat()
        state_manager.set_world_id(world_id)
        state_manager.set_variable("world_theme", world_theme)
        state_manager.set_variable("player_role", player_role)
        state_manager.set_variable("character_profile", player_role)
        display_name = (
            player_role.split(" — ", 1)[0].strip()
            if " — " in player_role
            else player_role
        )
        state_manager.set_variable("name", display_name)
        state_manager.set_variable(
            "world_tone", str(command.tone or "").strip() or "adventure"
        )
        key_elements = [
            str(item).strip() for item in command.key_elements if str(item).strip()
        ][:20]
        if key_elements:
            state_manager.set_variable("world_key_elements", key_elements)
        state_manager.set_variable("_bootstrap_state", "completed")
        state_manager.set_variable("_bootstrap_source", command.bootstrap_source)
        state_manager.set_variable("_bootstrap_completed_at", bootstrap_completed_at)

        resolved_location = str(command.entry_location or "").strip()
        if inherited_context:
            state_manager.set_world_context(inherited_context)
        if not resolved_location:
            city_pack_locations = (
                db.query(WorldNode)
                .filter(WorldNode.node_type == "location")
                .limit(500)
                .all()
            )
            resolved_location = str(
                next(
                    (
                        node.name
                        for node in city_pack_locations
                        if (node.metadata_json or {}).get("source") == "city_pack"
                    ),
                    "",
                )
                or ""
            ).strip()
        if resolved_location:
            state_manager.set_variable("location", resolved_location)

        session_row = stage_state(state_manager, db)
        if player is not None:
            session_row.player_id = player.id
            player_actor_id = str(player.actor_id or "").strip()
            if player_actor_id:
                session_row.actor_id = player_actor_id
        else:
            actor_id = str(command.actor_id or "").strip()
            if actor_id:
                session_row.actor_id = actor_id

        submit_world_event(
            db,
            WorldEventCommand(
                session_id=session_id,
                event_type=EVENT_TYPE_SESSION_BOOTSTRAP,
                summary=f"{display_name} arrived at {resolved_location or 'the world'}.",
                delta={"location": resolved_location} if resolved_location else {},
                metadata={"surface": "session_bootstrap"},
                preserve_event_type=True,
                defer_commit=True,
            ),
        )

        if resident_binding is not None:
            bind_resident_session(
                db,
                session_id=session_id,
                actor_id=resident_binding.actor_id,
                runtime_generation=resident_binding.runtime_generation,
            )

        pruned_duplicates: dict[str, Any] = {}
        retired_session_ids: list[str] = []
        if player is None:
            pruned_duplicates, retired_session_ids = _stage_duplicate_agent_retirement(
                db,
                keep_session_id=session_id,
                display_name=player_role,
            )

        db.commit()
        remove_cached_sessions(retired_session_ids)
    except SessionLifecycleError:
        db.rollback()
        remove_cached_sessions([session_id])
        raise
    except ResidentAuthorityError as exc:
        db.rollback()
        remove_cached_sessions([session_id])
        raise SessionLifecycleError(
            exc.code,
            {"code": exc.code, "message": str(exc)},
            status_code=409,
        ) from exc
    except Exception as exc:
        db.rollback()
        remove_cached_sessions([session_id])
        raise SessionLifecycleError(
            "session_bootstrap_failed",
            "Session bootstrap failed.",
            status_code=500,
        ) from exc

    return SessionBootstrapReceipt(
        success=True,
        message=f"Resident session joined world {world_id}.",
        session_id=session_id,
        vars=state_manager.get_contextual_variables(),
        theme=world_theme,
        player_role=player_role,
        bootstrap_state="completed",
        bootstrap_diagnostics={
            "bootstrap_mode": "resident_join",
            "world_id": world_id,
            "world_context_inherited": bool(inherited_context),
            "bootstrap_source": str(command.bootstrap_source),
            "duplicate_agent_sessions_pruned": int(
                pruned_duplicates.get("pruned_count") or 0
            ),
        },
    )
