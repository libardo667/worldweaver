from __future__ import annotations

import asyncio

import pytest

from src.models import SessionVars
from src.services import federation_pulse
from src.services.federation_identity import current_shard_id


def test_build_pulse_payload_reads_nested_v2_session_vars(db_session, monkeypatch, tmp_path):
    residents_dir = tmp_path / "residents"
    identity_dir = residents_dir / "test_resident" / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "resident_id.txt").write_text("resident-sun-li\n", encoding="utf-8")

    monkeypatch.setenv("WW_RESIDENTS_DIR", str(residents_dir))
    monkeypatch.setattr(federation_pulse.settings, "city_id", "san_francisco")
    federation_pulse._RESIDENT_ID_CACHE.clear()

    db_session.add(
        SessionVars(
            session_id="test_resident-20260317-120000",
            vars={
                "_v": 2,
                "variables": {
                    "city_id": "san_francisco",
                    "location": "Chinatown",
                    "_dormant_state": "active",
                },
            },
        )
    )
    db_session.commit()

    payload = federation_pulse._build_pulse_payload(db_session, 4242)

    assert payload["pulse_seq"] == 4242
    assert len(payload["residents"]) == 1
    resident = payload["residents"][0]
    assert resident["resident_id"] == "resident-sun-li"
    assert resident["name"] == "test_resident"
    assert resident["session_id"] == "test_resident-20260317-120000"
    assert resident["location"] == "Chinatown"
    assert resident["status"] == "active"


def test_build_pulse_payload_resolves_resident_dirs_with_spaces(db_session, monkeypatch, tmp_path):
    residents_dir = tmp_path / "residents"
    identity_dir = residents_dir / "Diana Chen" / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "resident_id.txt").write_text("resident-diana-chen\n", encoding="utf-8")

    monkeypatch.setenv("WW_RESIDENTS_DIR", str(residents_dir))
    monkeypatch.setattr(federation_pulse.settings, "city_id", "san_francisco")
    federation_pulse._RESIDENT_ID_CACHE.clear()

    db_session.add(
        SessionVars(
            session_id="diana_chen-20260317-120000",
            vars={
                "_v": 2,
                "variables": {
                    "city_id": "san_francisco",
                    "location": "Inner Richmond",
                    "_dormant_state": "active",
                },
            },
        )
    )
    db_session.commit()

    payload = federation_pulse._build_pulse_payload(db_session, 4243)

    assert len(payload["residents"]) == 1
    resident = payload["residents"][0]
    assert resident["resident_id"] == "resident-diana-chen"
    assert resident["name"] == "diana_chen"
    assert resident["location"] == "Inner Richmond"


def test_pulse_keeps_independent_shard_and_city_identity_separate(db_session, monkeypatch, tmp_path):
    residents_dir = tmp_path / "residents"
    identity_dir = residents_dir / "test_resident" / "identity"
    identity_dir.mkdir(parents=True)
    (identity_dir / "resident_id.txt").write_text("stale-file-id\n", encoding="utf-8")
    monkeypatch.setenv("WW_RESIDENTS_DIR", str(residents_dir))
    monkeypatch.setattr(federation_pulse.settings, "city_id", "portland")
    monkeypatch.setattr(federation_pulse.settings, "shard_id", "rose-city-coop-1")
    federation_pulse._RESIDENT_ID_CACHE.clear()
    db_session.add(
        SessionVars(
            session_id="test_resident-20260717-120000",
            actor_id="canonical-actor-id",
            vars={"city_id": "portland", "location": "Kerns"},
        )
    )
    db_session.commit()

    payload = federation_pulse._build_pulse_payload(db_session, 5000)

    assert payload["shard_id"] == "rose-city-coop-1"
    assert payload["residents"][0]["resident_id"] == "canonical-actor-id"


def test_current_shard_id_uses_explicit_node_id_with_legacy_city_fallback(monkeypatch):
    monkeypatch.setattr(federation_pulse.settings, "shard_type", "city")
    monkeypatch.setattr(federation_pulse.settings, "city_id", "portland")
    monkeypatch.setattr(federation_pulse.settings, "shard_id", "rose-city-coop-1")

    assert current_shard_id() == "rose-city-coop-1"

    monkeypatch.setattr(federation_pulse.settings, "shard_id", None)
    assert current_shard_id() == "portland"

    monkeypatch.setattr(federation_pulse.settings, "shard_type", "world")
    assert current_shard_id() == "ww_world"


def test_initial_pulse_seq_is_large_restart_safe_timestamp():
    pulse_seq = federation_pulse._initial_pulse_seq()
    assert isinstance(pulse_seq, int)
    assert pulse_seq > 1_000_000_000
    assert pulse_seq <= federation_pulse._MAX_PULSE_SEQ


def test_reseat_pulse_seq_advances_past_last_known_seq():
    pulse_seq = federation_pulse._reseat_pulse_seq(1_777_777_777)
    assert pulse_seq >= 1_777_777_778
    assert pulse_seq <= federation_pulse._MAX_PULSE_SEQ


def test_failed_startup_pulse_retries_before_the_normal_interval(monkeypatch):
    sleeps: list[int] = []

    class _DB:
        def query(self, *_args):
            raise RuntimeError("no sessions")

        def close(self):
            return None

    async def stop_after_first_sleep(delay: int):
        sleeps.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(federation_pulse.settings, "federation_url", "https://federation.example")
    monkeypatch.setattr(federation_pulse, "_post_pulse_sync", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(federation_pulse.asyncio, "sleep", stop_after_first_sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(federation_pulse.run_pulse_loop(_DB, 300))

    assert sleeps == [5]
