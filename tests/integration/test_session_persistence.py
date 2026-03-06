"""Integration tests for full session state persistence."""

from src.models import SessionVars
from src.services.session_service import get_state_manager, save_state, _state_managers
from src.services.world_memory import record_event


def _roundtrip(session_id, db):
    manager = _state_managers[session_id]
    save_state(manager, db)
    del _state_managers[session_id]
    return get_state_manager(session_id, db)


def test_variables_survive_restart(db_session):
    sid = "test-vars"
    m = get_state_manager(sid, db_session)
    m.set_variable("gold", 42)
    m.set_variable("location", "deep_mine")
    m2 = _roundtrip(sid, db_session)
    assert m2.get_variable("gold") == 42 and m2.get_variable("location") == "deep_mine"


def test_inventory_survives_restart(db_session):
    sid = "test-inventory"
    m = get_state_manager(sid, db_session)
    m.add_item("sword_001", "Iron Sword", quantity=1, properties={"damage": 15})
    m.add_item("potion_red", "Health Potion", quantity=3)
    m2 = _roundtrip(sid, db_session)
    assert m2.inventory["sword_001"].properties["damage"] == 15
    assert m2.inventory["potion_red"].quantity == 3


def test_inventory_quantity_change_survives(db_session):
    sid = "test-qty"
    m = get_state_manager(sid, db_session)
    m.add_item("arrow", "Arrow", quantity=20)
    m.inventory["arrow"].quantity = 17
    m2 = _roundtrip(sid, db_session)
    assert m2.inventory["arrow"].quantity == 17


def test_empty_inventory_survives(db_session):
    sid = "test-empty-inv"
    m = get_state_manager(sid, db_session)
    m.set_variable("name", "Ghost")
    m2 = _roundtrip(sid, db_session)
    assert m2.inventory == {} and m2.get_variable("name") == "Ghost"


def test_relationship_survives_restart(db_session):
    sid = "test-rel"
    m = get_state_manager(sid, db_session)
    m.update_relationship("player", "Greta", {"trust": 40.0, "respect": 25.0}, memory="She saved you.")
    m2 = _roundtrip(sid, db_session)
    rel = m2.get_relationship("player", "Greta")
    assert rel.trust == 40.0 and rel.respect == 25.0


def test_multiple_relationships_survive(db_session):
    sid = "test-multi-rel"
    m = get_state_manager(sid, db_session)
    m.update_relationship("player", "Finn", {"trust": 60.0})
    m.update_relationship("player", "Mira", {"fear": 30.0, "trust": -20.0})
    m2 = _roundtrip(sid, db_session)
    assert m2.get_relationship("player", "Finn").trust == 60.0
    assert m2.get_relationship("player", "Mira").fear == 30.0


def test_environment_survives_restart(db_session):
    sid = "test-env"
    m = get_state_manager(sid, db_session)
    m.update_environment({"weather": "stormy", "time_of_day": "night", "danger_level": 7})
    m2 = _roundtrip(sid, db_session)
    assert m2.environment.weather == "stormy" and m2.environment.danger_level == 7


def test_full_state_survives_restart(db_session):
    sid = "test-full"
    m = get_state_manager(sid, db_session)
    m.set_variable("chapter", 3)
    m.add_item("lantern", "Brass Lantern", quantity=1, properties={"lit": True})
    m.update_relationship("player", "Elder", {"trust": 80.0, "respect": 60.0})
    m.update_environment({"time_of_day": "evening", "danger_level": 2})
    m2 = _roundtrip(sid, db_session)
    assert m2.get_variable("chapter") == 3
    assert m2.inventory["lantern"].properties["lit"] is True
    assert m2.get_relationship("player", "Elder").trust == 80.0
    assert m2.environment.time_of_day == "evening"


def test_narrative_beats_survive_restart(db_session):
    sid = "test-beats"
    m = get_state_manager(sid, db_session)
    m.add_narrative_beat(
        {
            "name": "IncreasingTension",
            "intensity": 0.5,
            "turns_remaining": 3,
            "decay": 0.65,
        }
    )
    m2 = _roundtrip(sid, db_session)
    beats = m2.get_active_narrative_beats()
    assert len(beats) == 1
    assert beats[0].name == "IncreasingTension"
    assert beats[0].turns_remaining == 3


def test_goal_state_survives_restart(db_session):
    sid = "test-goal-restart"
    m = get_state_manager(sid, db_session)
    m.set_goal_state(
        primary_goal="Recover the stolen sigil",
        subgoals=["Trace the smuggler route"],
        urgency=0.8,
        complication=0.2,
        source="test",
    )
    m.mark_goal_milestone(
        "A witness was bribed into silence",
        status="complicated",
        complication_delta=0.2,
        source="test",
    )
    m2 = _roundtrip(sid, db_session)
    assert m2.goal_state.primary_goal == "Recover the stolen sigil"
    assert "Trace the smuggler route" in m2.goal_state.subgoals
    assert m2.goal_state.complication >= 0.4
    assert m2.get_arc_timeline(limit=5)


def test_legacy_v1_session_still_loads(db_session):
    sid = "test-legacy"
    row = SessionVars(session_id=sid, vars={"gold": 99, "name": "OldSave"})
    db_session.add(row)
    db_session.commit()
    m = get_state_manager(sid, db_session)
    assert m.get_variable("gold") == 99 and m.get_variable("name") == "OldSave"
    assert m.inventory == {} and m.environment.weather == "clear"


def test_version_marker_written_on_save(db_session):
    sid = "test-version"
    m = get_state_manager(sid, db_session)
    m.set_variable("x", 1)
    save_state(m, db_session)
    row = db_session.get(SessionVars, sid)
    assert row is not None and row.vars.get("_v") == 2


def test_default_vars_applied_to_new_session(db_session):
    sid = "test-defaults"
    m = get_state_manager(sid, db_session)
    assert m.get_variable("name") == "Adventurer"
    assert m.get_variable("danger") == 0


def test_default_vars_not_overwrite_loaded_state(db_session):
    sid = "test-no-overwrite"
    m = get_state_manager(sid, db_session)
    m.set_variable("name", "Theron")
    m.set_variable("danger", 5)
    m2 = _roundtrip(sid, db_session)
    assert m2.get_variable("name") == "Theron" and m2.get_variable("danger") == 5


def test_new_session_inherits_projected_world_state(db_session):
    record_event(
        db_session,
        "seed-session",
        None,
        "freeform_action",
        "A storm closes the north gate.",
        delta={
            "environment": {"weather": "stormy"},
            "spatial_nodes": {"north gate": {"status": "closed"}},
            "variables": {"world_alert_level": 3},
        },
    )

    m = get_state_manager("fresh-player", db_session)
    assert m.environment.weather == "stormy"
    assert m.get_variable("world_alert_level") == 3
    spatial_nodes = m.get_variable("spatial_nodes", {})
    assert spatial_nodes.get("north_gate", {}).get("status") == "closed"


def test_existing_session_syncs_shared_world_keys_from_projection(db_session):
    sid = "shared-sync"
    m = get_state_manager(sid, db_session)
    m.set_variable("world_alarm", 1)
    save_state(m, db_session)

    record_event(
        db_session,
        "seed-shared",
        None,
        "freeform_action",
        "World alarm rises.",
        delta={"variables": {"world_alarm": 4}},
    )

    # Should re-sync from projection even though manager is cached.
    m2 = get_state_manager(sid, db_session)
    assert m2.get_variable("world_alarm") == 4


def test_existing_session_keeps_player_scoped_location(db_session):
    sid = "player-location"
    m = get_state_manager(sid, db_session)
    m.set_variable("location", "deep_mine")
    save_state(m, db_session)

    record_event(
        db_session,
        "seed-location",
        None,
        "freeform_action",
        "Projection writes a location key.",
        delta={"variables": {"location": "city_square"}},
    )

    m2 = get_state_manager(sid, db_session)
    assert m2.get_variable("location") == "deep_mine"
