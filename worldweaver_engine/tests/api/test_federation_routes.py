from __future__ import annotations

from src.api.federation.routes import PulseRequest, PulseResidentItem, receive_pulse
from src.models import FederationResident, FederationShard


def test_receive_pulse_upserts_existing_resident_without_duplicate(db_session):
    db_session.add(
        FederationShard(
            shard_id="san_francisco",
            shard_url="https://world-weaver.org/ww-sfo",
            shard_type="city",
            city_id="san_francisco",
            last_pulse_seq=0,
        )
    )
    db_session.commit()

    first = PulseRequest(
        shard_id="san_francisco",
        shard_url="https://world-weaver.org/ww-sfo",
        pulse_seq=1,
        residents=[
            PulseResidentItem(
                resident_id="resident-sun-li",
                name="sun_li",
                session_id="sun_li-20260317-120000",
                location="Chinatown",
                status="active",
            )
        ],
    )
    second = PulseRequest(
        shard_id="san_francisco",
        shard_url="https://world-weaver.org/ww-sfo",
        pulse_seq=2,
        residents=[
            PulseResidentItem(
                resident_id="resident-sun-li",
                name="sun_li",
                session_id="sun_li-20260317-120000",
                location="Inner Richmond",
                status="active",
            )
        ],
    )

    first_response = receive_pulse(first, db_session, None)
    second_response = receive_pulse(second, db_session, None)

    assert first_response["accepted"] is True
    assert second_response["accepted"] is True

    residents = db_session.query(FederationResident).all()
    assert len(residents) == 1
    assert residents[0].resident_id == "resident-sun-li"
    assert residents[0].last_location == "Inner Richmond"


def test_receive_pulse_rejects_stale_seq_with_last_seq(db_session):
    db_session.add(
        FederationShard(
            shard_id="san_francisco",
            shard_url="https://world-weaver.org/ww-sfo",
            shard_type="city",
            city_id="san_francisco",
            last_pulse_seq=4242,
        )
    )
    db_session.commit()

    payload = PulseRequest(
        shard_id="san_francisco",
        shard_url="https://world-weaver.org/ww-sfo",
        pulse_seq=4242,
        residents=[],
    )

    response = receive_pulse(payload, db_session, None)

    assert response["accepted"] is False
    assert response["reason"] == "stale_pulse"
    assert response["last_seq"] == 4242


def test_receive_pulse_rejects_oversized_seq_without_500(db_session):
    db_session.add(
        FederationShard(
            shard_id="portland",
            shard_url="https://world-weaver.org/ww-pdx",
            shard_type="city",
            city_id="portland",
            last_pulse_seq=100,
        )
    )
    db_session.commit()

    payload = PulseRequest(
        shard_id="portland",
        shard_url="https://world-weaver.org/ww-pdx",
        pulse_seq=9_999_999_999,
        residents=[],
    )

    response = receive_pulse(payload, db_session, None)

    assert response["accepted"] is False
    assert response["reason"] == "invalid_pulse_seq"
    assert response["last_seq"] == 100
