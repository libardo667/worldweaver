from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.identity.loader import LoopTuning
from src.runtime import rest as rest_module
from src.runtime.rest import RestAssessment, RestState


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

    assert rest._rest_duration_seconds_for_kind("break") == 45.0 * 60.0
    assert rest._rest_duration_seconds_for_kind("sleep") == 8.0 * 3600.0


def test_circadian_profile_marks_sleep_window_for_day_chronotype(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 18, 10, 0, tzinfo=timezone.utc)  # 3 AM PDT

    rest = RestState(ww_client=None, session_id="test", tuning=LoopTuning(rest_chronotype="day"))
    profile = rest.circadian_profile()

    assert profile.local_hour == 3
    assert profile.phase == "sleep_window"
    assert profile.quiet_hours is True
    assert profile.pressure >= 0.9


def test_circadian_bias_can_trigger_rest_without_explicit_sleep_language(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 18, 10, 0, tzinfo=timezone.utc)  # 3 AM PDT

    rest = RestState(ww_client=None, session_id="test", tuning=LoopTuning(rest_chronotype="day"))
    biased = rest.apply_circadian_bias(
        RestAssessment(
            should_rest=False,
            rest_kind="none",
            confidence=0.2,
            reason="ambient quiet only",
        ),
        direct_engagement=False,
    )

    assert biased.should_rest is True
    assert biased.rest_kind == "sleep"
    assert biased.confidence >= 0.7


def test_night_chronotype_softens_circadian_bias(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 18, 7, 0, tzinfo=timezone.utc)  # midnight PDT

    rest = RestState(ww_client=None, session_id="test", tuning=LoopTuning(rest_chronotype="night"))
    profile = rest.circadian_profile()

    assert profile.local_hour == 0
    assert profile.pressure < 0.6


def test_rest_requires_confirmation_before_begin(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 16, 1, 0, tzinfo=timezone.utc)
    ww = _FakeWorldClient()

    rest = RestState(ww_client=ww, session_id="test", tuning=LoopTuning())
    assessment = RestAssessment(
        should_rest=True,
        rest_kind="break",
        confidence=0.9,
        reason="needs a minute alone",
    )

    first = rest_module.asyncio.run(
        rest.maybe_trigger_from_assessment(assessment, "Tea House")
    )

    assert first is False
    assert ww.vars["_rest_pending_hits"] == 1
    assert ww.vars["_rest_state"] is None if "_rest_state" in ww.vars else True

    second = rest_module.asyncio.run(
        rest.maybe_trigger_from_assessment(assessment, "Tea House")
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
    assessment = RestAssessment(
        should_rest=False,
        rest_kind="none",
        confidence=0.2,
        reason="ambient quiet only",
    )

    started = rest_module.asyncio.run(
        rest.maybe_trigger_from_assessment(assessment, "Tea House")
    )

    assert started is False
    assert ww.vars.get("_rest_pending_hits") is None
    assert ww.vars.get("_rest_state") is None


def test_low_confidence_rest_assessment_does_not_stage_rest(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 16, 1, 0, tzinfo=timezone.utc)
    ww = _FakeWorldClient()

    rest = RestState(ww_client=ww, session_id="test", tuning=LoopTuning())
    assessment = RestAssessment(
        should_rest=True,
        rest_kind="break",
        confidence=0.3,
        reason="maybe wants a pause",
    )

    started = rest_module.asyncio.run(
        rest.maybe_trigger_from_assessment(assessment, "Tea House")
    )

    assert started is False
    assert ww.vars.get("_rest_pending_hits") is None
    assert ww.vars.get("_rest_state") is None


def test_sleep_assessment_uses_sleep_duration(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 16, 1, 0, tzinfo=timezone.utc)
    ww = _FakeWorldClient()

    tuning = LoopTuning(rest_confirmations_required=1)
    rest = RestState(ww_client=ww, session_id="test", tuning=tuning)
    assessment = RestAssessment(
        should_rest=True,
        rest_kind="sleep",
        confidence=0.95,
        reason="wants to go lie down for the night",
    )

    started = rest_module.asyncio.run(
        rest.maybe_trigger_from_assessment(assessment, "Tea House")
    )

    assert started is True
    assert ww.vars["_rest_state"] == "resting"
    until = datetime.fromisoformat(str(ww.vars["_rest_until"]))
    started_at = datetime.fromisoformat(str(ww.vars["_rest_started_at"]))
    assert (until - started_at).total_seconds() == 8.0 * 3600.0


def test_recent_rest_completion_blocks_immediate_rerest(monkeypatch):
    monkeypatch.delenv("WW_CITY_TIMEZONE", raising=False)
    monkeypatch.setenv("CITY_ID", "san_francisco")
    monkeypatch.setattr(rest_module, "datetime", _FrozenDateTime)
    _FrozenDateTime.current = datetime(2026, 3, 16, 1, 0, tzinfo=timezone.utc)
    ww = _FakeWorldClient()
    ww.vars["_rest_last_completed_at"] = (_FrozenDateTime.current - timedelta(minutes=15)).isoformat()

    rest = RestState(ww_client=ww, session_id="test", tuning=LoopTuning())
    assessment = RestAssessment(
        should_rest=True,
        rest_kind="break",
        confidence=0.9,
        reason="needs a minute alone",
    )

    started = rest_module.asyncio.run(
        rest.maybe_trigger_from_assessment(assessment, "Tea House")
    )

    assert started is False
    assert "_rest_state" not in ww.vars
    assert ww.vars.get("_rest_pending_hits") is None
