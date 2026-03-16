from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.identity.loader import LoopTuning
from src.runtime import rest as rest_module
from src.runtime.rest import RestState


class _FrozenDateTime(datetime):
    current = datetime(2026, 3, 16, 1, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        fixed_utc = cls.fromisoformat(cls.current.isoformat())
        if tz is None:
            return fixed_utc
        return fixed_utc.astimezone(tz)


class _FakeWorldClient:
    def __init__(self):
        self.vars: dict[str, object] = {}

    async def get_session_vars(self, session_id: str) -> dict:
        return {"session_id": session_id, "vars": dict(self.vars)}

    async def update_session_vars(self, session_id: str, updates: dict[str, object]) -> dict:
        for key, value in updates.items():
            self.vars[key] = value
        return {"session_id": session_id, "vars": dict(self.vars)}


def test_resolve_rest_timezone_from_city_config(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")

    tz = rest_module._resolve_rest_timezone()

    assert getattr(tz, "key", None) == "America/Los_Angeles"


def test_rest_duration_uses_city_timezone(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 16, 1, 0, tzinfo=timezone.utc)

    rest = RestState(ww_client=None, session_id="test", tuning=LoopTuning())

    assert rest._rest_duration_seconds("needed quiet") == 45.0 * 60.0


def test_rest_requires_confirmation_before_begin(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 16, 1, 0, tzinfo=timezone.utc)
    ww = _FakeWorldClient()

    rest = RestState(ww_client=ww, session_id="test", tuning=LoopTuning())

    first = rest_module.asyncio.run(
        rest.maybe_trigger_from_reflection("I need some quiet.", "They want to pause.", "Tea House")
    )

    assert first is False
    assert ww.vars["_rest_pending_hits"] == 1
    assert ww.vars["_rest_state"] is None if "_rest_state" in ww.vars else True

    second = rest_module.asyncio.run(
        rest.maybe_trigger_from_reflection("I still need some quiet.", "They should step away.", "Tea House")
    )

    assert second is True
    assert ww.vars["_rest_state"] == "resting"
    assert ww.vars["_rest_pending_hits"] is None


def test_ambient_quiet_language_does_not_stage_rest(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 16, 1, 0, tzinfo=timezone.utc)
    ww = _FakeWorldClient()

    rest = RestState(ww_client=ww, session_id="test", tuning=LoopTuning())

    started = rest_module.asyncio.run(
        rest.maybe_trigger_from_reflection(
            "The room is quiet and the evening feels still.",
            "They seem calm and deliberate.",
            "Tea House",
        )
    )

    assert started is False
    assert ww.vars.get("_rest_pending_hits") is None
    assert ww.vars.get("_rest_state") is None


def test_night_word_alone_does_not_force_sleep_duration(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 16, 1, 0, tzinfo=timezone.utc)

    rest = RestState(ww_client=None, session_id="test", tuning=LoopTuning())

    assert rest._rest_duration_seconds("The night air is cold.") == 45.0 * 60.0


def test_recent_rest_completion_blocks_immediate_rerest(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 16, 1, 0, tzinfo=timezone.utc)
    ww = _FakeWorldClient()
    ww.vars["_rest_last_completed_at"] = (_FrozenDateTime.current - timedelta(minutes=15)).isoformat()

    rest = RestState(ww_client=ww, session_id="test", tuning=LoopTuning())

    started = rest_module.asyncio.run(
        rest.maybe_trigger_from_reflection("I need some quiet.", "They want to pause.", "Tea House")
    )

    assert started is False
    assert "_rest_state" not in ww.vars
    assert ww.vars.get("_rest_pending_hits") is None
