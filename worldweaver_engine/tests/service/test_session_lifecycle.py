# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from datetime import datetime, timezone

import pytest

from src.models import SessionVars, WorldEvent
from src.services import session_lifecycle as lifecycle_module
from src.services.resident_authority import ResidentAuthorityError
from src.services.session_lifecycle import (
    ResidentSessionBinding,
    SessionBootstrapCommand,
    SessionLifecycleError,
    bootstrap_session,
)
from src.services.session_service import get_state_manager, save_state


def _seed_host_state(db_session) -> None:
    host = get_state_manager("test-world", db_session)
    host.set_variable("world_theme", "A test town")
    save_state(host, db_session)


def _command(session_id: str) -> SessionBootstrapCommand:
    return SessionBootstrapCommand(
        session_id=session_id,
        actor_id="actor-new",
        player_role="New Resident",
        world_id="test-world",
        entry_location="Town Square",
    )


def test_bootstrap_rolls_back_session_when_event_write_fails(db_session, monkeypatch):
    _seed_host_state(db_session)

    def fail_event_write(*_args, **_kwargs):
        raise RuntimeError("event write failed")

    monkeypatch.setattr(lifecycle_module, "submit_world_event", fail_event_write)

    with pytest.raises(SessionLifecycleError) as captured:
        bootstrap_session(db_session, command=_command("failed-bootstrap"))

    assert captured.value.code == "session_bootstrap_failed"
    assert db_session.get(SessionVars, "failed-bootstrap") is None
    assert (
        db_session.query(WorldEvent)
        .filter(WorldEvent.session_id == "failed-bootstrap")
        .count()
        == 0
    )


def test_bootstrap_keeps_explicit_world_time_after_actor_attachment(db_session):
    _seed_host_state(db_session)
    world_now = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)

    bootstrap_session(
        db_session,
        command=_command("controlled-bootstrap"),
        now=world_now,
    )
    db_session.expire_all()

    row = db_session.get(SessionVars, "controlled-bootstrap")
    assert row is not None
    assert row.updated_at == world_now.replace(tzinfo=None)


def test_bootstrap_rolls_back_session_and_event_when_authority_binding_fails(
    db_session, monkeypatch
):
    _seed_host_state(db_session)

    def fail_binding(*_args, **_kwargs):
        raise ResidentAuthorityError("session_mismatch", "binding failed")

    monkeypatch.setattr(lifecycle_module, "bind_resident_session", fail_binding)

    with pytest.raises(SessionLifecycleError) as captured:
        bootstrap_session(
            db_session,
            command=_command("failed-binding"),
            resident_binding=ResidentSessionBinding(
                actor_id="actor-new",
                runtime_generation=1,
            ),
        )

    assert captured.value.code == "session_mismatch"
    assert db_session.get(SessionVars, "failed-binding") is None
    assert (
        db_session.query(WorldEvent)
        .filter(WorldEvent.session_id == "failed-binding")
        .count()
        == 0
    )


def test_bootstrap_refuses_to_replace_an_existing_session_or_history(db_session):
    _seed_host_state(db_session)
    db_session.add(
        SessionVars(
            session_id="occupied-session",
            actor_id="actor-existing",
            vars={"location": "Old Square"},
        )
    )
    db_session.add(
        WorldEvent(
            session_id="occupied-session",
            event_type="movement",
            summary="Existing history.",
            world_state_delta={"location": "Old Square"},
        )
    )
    db_session.commit()

    with pytest.raises(SessionLifecycleError) as captured:
        bootstrap_session(db_session, command=_command("occupied-session"))

    assert captured.value.code == "session_id_in_use"
    assert db_session.get(SessionVars, "occupied-session").actor_id == "actor-existing"
    assert (
        db_session.query(WorldEvent)
        .filter(WorldEvent.session_id == "occupied-session")
        .count()
        == 1
    )
