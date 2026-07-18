from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.config import settings
from src.models import ConsequenceReceipt, DurableObject, MaterialPool, SessionVars, WorldEvent
from src.services.consequence_objects import ConsequenceDomainError
from src.services.material_making import initialize_material_pools, make_durable_object, making_catalog


@pytest.fixture()
def game_rules(monkeypatch):
    example = Path(__file__).resolve().parents[2] / "data" / "rulesets" / "private_constructive_game.v1.example.json"
    monkeypatch.setattr(settings, "shard_experience_path", str(example))
    monkeypatch.setattr(settings, "shard_id", "test-game-shard")


def _session(db, session_id: str = "maker-session", actor_id: str = "actor-maker", location: str = "Alderbank Workshop") -> None:
    db.add(
        SessionVars(
            session_id=session_id,
            actor_id=actor_id,
            vars={"_v": 2, "variables": {"location": location}},
        )
    )
    db.commit()


def test_material_pools_initialize_from_versioned_ruleset(db_session, game_rules):
    started = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)

    first = initialize_material_pools(db_session, now=started)
    retry = initialize_material_pools(db_session, now=started + timedelta(hours=1))

    assert len(first) == 2
    assert len(retry) == 2
    assert db_session.query(MaterialPool).count() == 2
    clay = db_session.query(MaterialPool).filter(MaterialPool.material_id == "reclaimed_clay").one()
    assert clay.ruleset_id == "private-constructive-town"
    assert clay.ruleset_version == "0.1.0"
    assert clay.location == "Alderbank Workshop"
    assert clay.available_units == 8
    assert clay.capacity_units == 12
    assert clay.replenish_units == 2


def test_catalog_is_elective_and_exact_location_scoped(db_session, game_rules):
    _session(db_session)

    catalog = making_catalog(db_session, session_id="maker-session")

    assert catalog["location"] == "Alderbank Workshop"
    assert {item["material_id"] for item in catalog["materials"]} == {"reclaimed_clay", "fallen_wood"}
    assert {item["recipe_id"] for item in catalog["recipes"]} == {"small_clay_cup", "wooden_token"}
    assert all(item["essential"] is False for item in catalog["materials"])
    assert all(item["used_for_resident_need"] is False for item in catalog["materials"])

    session = db_session.get(SessionVars, "maker-session")
    session.vars = {"_v": 2, "variables": {"location": "quiet-square"}}
    db_session.commit()
    elsewhere = making_catalog(db_session, session_id="maker-session")
    assert elsewhere["materials"] == []
    assert elsewhere["recipes"] == []


def test_making_consumes_material_and_creates_evidence_backed_object(db_session, game_rules):
    _session(db_session)
    initialize_material_pools(db_session)

    result = make_durable_object(
        db_session,
        session_id="maker-session",
        recipe_id="small_clay_cup",
        idempotency_key="make-cup-1",
    )

    clay = db_session.query(MaterialPool).filter(MaterialPool.material_id == "reclaimed_clay").one()
    object_row = db_session.get(DurableObject, result.object["object_id"])
    receipt = db_session.query(ConsequenceReceipt).one()
    event = db_session.query(WorldEvent).one()
    assert clay.available_units == 6
    assert object_row is not None
    assert object_row.custodian_actor_id == "actor-maker"
    assert object_row.provenance_kind == "recipe"
    assert object_row.provenance_ref == "private-constructive-town@0.1.0:small_clay_cup"
    assert object_row.provenance_event_id == event.id
    assert event.event_type == "object_made"
    assert receipt.operation == "object_made"
    assert receipt.payload_json["details"]["materials"]["reclaimed_clay"] == {
        "before_units": 8,
        "consumed_units": 2,
        "after_units": 6,
    }


def test_making_retry_does_not_consume_twice(db_session, game_rules):
    _session(db_session)
    payload = {
        "session_id": "maker-session",
        "recipe_id": "wooden_token",
        "idempotency_key": "make-token-1",
    }

    first = make_durable_object(db_session, **payload)
    retry = make_durable_object(db_session, **payload)

    wood = db_session.query(MaterialPool).filter(MaterialPool.material_id == "fallen_wood").one()
    assert retry.replayed is True
    assert retry.object["object_id"] == first.object["object_id"]
    assert wood.available_units == 5
    assert db_session.query(DurableObject).count() == 1
    assert db_session.query(ConsequenceReceipt).count() == 1
    assert db_session.query(WorldEvent).count() == 1


def test_insufficient_materials_create_nothing(db_session, game_rules):
    _session(db_session)
    initialize_material_pools(db_session)
    clay = db_session.query(MaterialPool).filter(MaterialPool.material_id == "reclaimed_clay").one()
    clay.available_units = 1
    db_session.commit()

    with pytest.raises(ConsequenceDomainError) as caught:
        make_durable_object(
            db_session,
            session_id="maker-session",
            recipe_id="small_clay_cup",
            idempotency_key="too-little-clay",
        )

    assert caught.value.code == "insufficient_materials"
    db_session.expire_all()
    assert db_session.query(MaterialPool).filter(MaterialPool.material_id == "reclaimed_clay").one().available_units == 1
    assert db_session.query(DurableObject).count() == 0
    assert db_session.query(ConsequenceReceipt).count() == 0
    assert db_session.query(WorldEvent).count() == 0


def test_materials_replenish_by_bounded_elapsed_intervals(db_session, game_rules):
    _session(db_session)
    now = datetime(2026, 7, 18, 15, 0, tzinfo=timezone.utc)
    initialize_material_pools(db_session, now=now - timedelta(hours=2))
    clay = db_session.query(MaterialPool).filter(MaterialPool.material_id == "reclaimed_clay").one()
    clay.available_units = 0
    db_session.commit()

    make_durable_object(
        db_session,
        session_id="maker-session",
        recipe_id="small_clay_cup",
        idempotency_key="replenished-cup",
        now=now,
    )

    db_session.expire_all()
    clay = db_session.query(MaterialPool).filter(MaterialPool.material_id == "reclaimed_clay").one()
    assert clay.available_units == 2  # two intervals added four units; the cup consumed two
    assert clay.last_replenished_at == now.replace(tzinfo=None)


def test_event_failure_rolls_back_materials_and_object(db_session, game_rules, monkeypatch):
    _session(db_session)
    initialize_material_pools(db_session)

    def fail_event(*_args, **_kwargs):
        raise RuntimeError("event store unavailable")

    monkeypatch.setattr("src.services.consequence_objects.submit_world_event", fail_event)

    with pytest.raises(RuntimeError, match="event store unavailable"):
        make_durable_object(
            db_session,
            session_id="maker-session",
            recipe_id="small_clay_cup",
            idempotency_key="failed-make",
        )

    db_session.expire_all()
    clay = db_session.query(MaterialPool).filter(MaterialPool.material_id == "reclaimed_clay").one()
    assert clay.available_units == 8
    assert db_session.query(DurableObject).count() == 0
    assert db_session.query(ConsequenceReceipt).count() == 0
    assert db_session.query(WorldEvent).count() == 0


def test_recipe_cannot_be_used_away_from_its_declared_place(db_session, game_rules):
    _session(db_session, location="quiet-square")

    with pytest.raises(ConsequenceDomainError) as caught:
        make_durable_object(
            db_session,
            session_id="maker-session",
            recipe_id="small_clay_cup",
            idempotency_key="wrong-place",
        )

    assert caught.value.code == "recipe_not_available_here"
    assert db_session.query(DurableObject).count() == 0


def test_ordinary_shard_has_no_material_or_making_system(db_session, monkeypatch):
    monkeypatch.setattr(settings, "shard_experience_path", None)
    _session(db_session)

    with pytest.raises(ConsequenceDomainError) as caught:
        making_catalog(db_session, session_id="maker-session")

    assert caught.value.code == "game_capability_unavailable"
    assert db_session.query(MaterialPool).count() == 0
