from __future__ import annotations

from src.models import SessionVars
from src.services import federation_pulse


def test_build_pulse_payload_reads_nested_v2_session_vars(db_session, monkeypatch, tmp_path):
    residents_dir = tmp_path / "residents"
    identity_dir = residents_dir / "sun_li" / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "resident_id.txt").write_text("resident-sun-li\n", encoding="utf-8")

    monkeypatch.setenv("WW_RESIDENTS_DIR", str(residents_dir))
    monkeypatch.setattr(federation_pulse.settings, "city_id", "san_francisco")
    federation_pulse._RESIDENT_ID_CACHE.clear()

    db_session.add(
        SessionVars(
            session_id="sun_li-20260317-120000",
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
    assert resident["name"] == "sun_li"
    assert resident["session_id"] == "sun_li-20260317-120000"
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


def test_initial_pulse_seq_is_large_restart_safe_timestamp():
    pulse_seq = federation_pulse._initial_pulse_seq()
    assert isinstance(pulse_seq, int)
    assert pulse_seq > 1_000_000_000
    assert pulse_seq <= federation_pulse._MAX_PULSE_SEQ


def test_reseat_pulse_seq_advances_past_last_known_seq():
    pulse_seq = federation_pulse._reseat_pulse_seq(1_777_777_777)
    assert pulse_seq >= 1_777_777_778
    assert pulse_seq <= federation_pulse._MAX_PULSE_SEQ
