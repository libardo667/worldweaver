"""Tests for src/services/prefetch_service.py."""

import time

import pytest

from src.models import SessionVars, Storylet, WorldEvent
from src.services.prefetch_service import (
    clear_prefetch_cache,
    get_cached_frontier,
    get_frontier_status,
    refresh_frontier_for_session,
    schedule_frontier_prefetch,
)
from src.services.session_service import get_state_manager, save_state


def _make_storylet(db, title: str, *, requires=None, embedding=None) -> Storylet:
    storylet = Storylet(
        title=title,
        text_template=f"{title} text.",
        requires=requires if requires is not None else {},
        choices=[{"label": "Continue", "set": {}}],
        weight=1.0,
        embedding=embedding,
    )
    db.add(storylet)
    db.commit()
    db.refresh(storylet)
    return storylet


@pytest.fixture(autouse=True)
def _reset_prefetch_cache():
    clear_prefetch_cache()
    yield
    clear_prefetch_cache()


def test_refresh_frontier_caches_stubs_with_ttl_and_cap(db_session, monkeypatch):
    monkeypatch.setattr("src.services.prefetch_service.settings.enable_frontier_prefetch", True)
    monkeypatch.setattr("src.services.prefetch_service.settings.prefetch_max_per_session", 2)
    monkeypatch.setattr("src.services.prefetch_service.settings.prefetch_ttl_seconds", 60)

    _make_storylet(db_session, "prefetch-cap-a", requires={"location": "start"}, embedding=[1.0, 0.0, 0.0])
    _make_storylet(db_session, "prefetch-cap-b", requires={"location": "start"}, embedding=[0.9, 0.0, 0.0])
    _make_storylet(db_session, "prefetch-cap-c", requires={}, embedding=[0.8, 0.0, 0.0])

    state_manager = get_state_manager("prefetch-cap", db_session)
    state_manager.set_variable("location", "start")
    save_state(state_manager, db_session)

    refreshed = refresh_frontier_for_session("prefetch-cap", trigger="unit-test", db=db_session)
    assert refreshed is not None
    assert len(refreshed["stubs"]) == 2
    assert refreshed["context_summary"]["trigger"] == "unit-test"
    assert refreshed["expires_in_seconds"] > 0

    status = get_frontier_status("prefetch-cap")
    assert status["stubs_cached"] == 2
    assert status["expires_in_seconds"] > 0


def test_prefetch_refresh_is_read_only_for_state_and_world_facts(db_session, monkeypatch):
    monkeypatch.setattr("src.services.prefetch_service.settings.enable_frontier_prefetch", True)
    monkeypatch.setattr("src.services.prefetch_service.settings.prefetch_max_per_session", 3)

    _make_storylet(db_session, "prefetch-readonly", requires={"location": "start"}, embedding=[1.0, 0.0, 0.0])
    state_manager = get_state_manager("prefetch-readonly-session", db_session)
    state_manager.set_variable("location", "start")
    state_manager.set_variable("marker", "unchanged")
    save_state(state_manager, db_session)

    before_row = db_session.get(SessionVars, "prefetch-readonly-session")
    assert before_row is not None
    before_vars = dict(before_row.vars)
    before_events = db_session.query(WorldEvent).count()

    refresh_frontier_for_session("prefetch-readonly-session", trigger="unit-test", db=db_session)

    after_row = db_session.get(SessionVars, "prefetch-readonly-session")
    assert after_row is not None
    assert after_row.vars == before_vars
    assert db_session.query(WorldEvent).count() == before_events


def test_cached_frontier_expires_after_ttl(db_session, monkeypatch):
    monkeypatch.setattr("src.services.prefetch_service.settings.enable_frontier_prefetch", True)
    monkeypatch.setattr("src.services.prefetch_service.settings.prefetch_max_per_session", 1)
    monkeypatch.setattr("src.services.prefetch_service.settings.prefetch_ttl_seconds", 1)

    _make_storylet(db_session, "prefetch-ttl", requires={"location": "start"}, embedding=[1.0, 0.0, 0.0])
    refresh_frontier_for_session("prefetch-ttl-session", trigger="unit-test", db=db_session)
    assert get_cached_frontier("prefetch-ttl-session") is not None

    time.sleep(1.2)

    assert get_cached_frontier("prefetch-ttl-session") is None
    assert get_frontier_status("prefetch-ttl-session") == {
        "stubs_cached": 0,
        "expires_in_seconds": 0,
    }


def test_prefetch_can_be_disabled_via_feature_flag(db_session, monkeypatch):
    monkeypatch.setattr("src.services.prefetch_service.settings.enable_frontier_prefetch", False)
    _make_storylet(db_session, "prefetch-disabled", requires={})

    refreshed = refresh_frontier_for_session("prefetch-disabled-session", trigger="unit-test", db=db_session)
    scheduled = schedule_frontier_prefetch("prefetch-disabled-session", trigger="unit-test")

    assert refreshed is None
    assert scheduled is False


def test_prefetch_respects_v3_projection_node_budget(db_session, monkeypatch):
    monkeypatch.setattr("src.services.prefetch_service.settings.enable_frontier_prefetch", True)
    monkeypatch.setattr("src.services.prefetch_service.settings.enable_v3_projection_expansion", True)
    monkeypatch.setattr("src.services.prefetch_service.settings.prefetch_max_per_session", 4)
    monkeypatch.setattr("src.services.prefetch_service.settings.v3_projection_max_depth", 2)
    monkeypatch.setattr("src.services.prefetch_service.settings.v3_projection_max_nodes", 1)
    monkeypatch.setattr("src.services.prefetch_service.settings.v3_projection_time_budget_ms", 500)

    _make_storylet(db_session, "budget-a", requires={"location": "start"}, embedding=[1.0, 0.0, 0.0])
    _make_storylet(db_session, "budget-b", requires={"location": "start"}, embedding=[0.9, 0.0, 0.0])

    state_manager = get_state_manager("prefetch-node-budget", db_session)
    state_manager.set_variable("location", "start")
    save_state(state_manager, db_session)

    refreshed = refresh_frontier_for_session("prefetch-node-budget", trigger="unit-test", db=db_session)
    assert refreshed is not None
    assert len(refreshed["stubs"]) == 1
    assert refreshed["stubs"][0]["non_canon"] is True
    assert refreshed["stubs"][0]["projection_depth"] == 1

    summary = refreshed["context_summary"]
    assert summary["projection_nodes_examined"] == 1
    assert summary["projection_budget"]["max_projection_nodes"] == 1


def test_prefetch_projection_expansion_flag_can_disable_refresh(db_session, monkeypatch):
    monkeypatch.setattr("src.services.prefetch_service.settings.enable_frontier_prefetch", True)
    monkeypatch.setattr("src.services.prefetch_service.settings.enable_v3_projection_expansion", False)

    _make_storylet(db_session, "projection-disabled", requires={})

    refreshed = refresh_frontier_for_session("projection-disabled-session", trigger="unit-test", db=db_session)
    scheduled = schedule_frontier_prefetch("projection-disabled-session", trigger="unit-test")

    assert refreshed is None
    assert scheduled is False
