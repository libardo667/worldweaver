"""Integration tests for full session state persistence.

Simulates a server restart by clearing the in-memory cache between
save and load, verifying that inventory, relationships, and environment
all survive the round-trip through the database.
"""

import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Point at a fresh temp DB before importing anything that touches the DB.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DW_DB_PATH"] = _tmp_db.name

from src.database import Base  # noqa: E402
from src.models import SessionVars  # noqa: E402
from src.services.state_manager import AdvancedStateManager  # noqa: E402
from src.api.game import (  # noqa: E402
    get_state_manager,
    save_state_to_db,
    _state_managers,
)


@pytest.fixture(autouse=True)
def isolated_db():
    """Create a fresh in-memory SQLite for every test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Clear the global in-memory cache before each test.
    _state_managers.clear()

    yield db

    db.close()
    _state_managers.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _roundtrip(session_id: str, db) -> AdvancedStateManager:
    """Save the manager, evict it from cache, reload it from the DB."""
    manager = _state_managers[session_id]
    save_state_to_db(manager, db)
    # Evict from cache to simulate restart.
    del _state_managers[session_id]
    return get_state_manager(session_id, db)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_variables_survive_restart(isolated_db):
    """Basic variables persist across the save/load cycle."""
    sid = "test-vars"
    m = get_state_manager(sid, isolated_db)
    m.set_variable("gold", 42)
    m.set_variable("location", "deep_mine")

    m2 = _roundtrip(sid, isolated_db)

    assert m2.get_variable("gold") == 42
    assert m2.get_variable("location") == "deep_mine"


def test_inventory_survives_restart(isolated_db):
    """Inventory items (with properties) persist across restart."""
    sid = "test-inventory"
    m = get_state_manager(sid, isolated_db)
    m.add_item("sword_001", "Iron Sword", quantity=1, properties={"damage": 15, "equippable": True})
    m.add_item("potion_red", "Health Potion", quantity=3, properties={"consumable": True})

    m2 = _roundtrip(sid, isolated_db)

    assert "sword_001" in m2.inventory
    assert m2.inventory["sword_001"].name == "Iron Sword"
    assert m2.inventory["sword_001"].quantity == 1
    assert m2.inventory["sword_001"].properties["damage"] == 15

    assert "potion_red" in m2.inventory
    assert m2.inventory["potion_red"].quantity == 3


def test_inventory_quantity_change_survives(isolated_db):
    """Quantity changes to existing inventory items are persisted."""
    sid = "test-qty"
    m = get_state_manager(sid, isolated_db)
    m.add_item("arrow", "Arrow", quantity=20)

    # Simulate using some arrows.
    m.inventory["arrow"].quantity = 17

    m2 = _roundtrip(sid, isolated_db)
    assert m2.inventory["arrow"].quantity == 17


def test_empty_inventory_survives(isolated_db):
    """A session with no inventory items round-trips cleanly."""
    sid = "test-empty-inv"
    m = get_state_manager(sid, isolated_db)
    m.set_variable("name", "Ghost")

    m2 = _roundtrip(sid, isolated_db)
    assert m2.inventory == {}
    assert m2.get_variable("name") == "Ghost"


def test_relationship_survives_restart(isolated_db):
    """NPC relationships (trust, fear, memories) persist across restart."""
    sid = "test-rel"
    m = get_state_manager(sid, isolated_db)
    m.update_relationship(
        "player", "Greta",
        {"trust": 40.0, "respect": 25.0},
        memory="She saved you from the cave-in."
    )

    m2 = _roundtrip(sid, isolated_db)

    rel = m2.get_relationship("player", "Greta")
    assert rel is not None
    assert rel.trust == 40.0
    assert rel.respect == 25.0
    assert rel.interaction_count == 1
    assert "cave-in" in rel.memory_fragments[0]


def test_multiple_relationships_survive(isolated_db):
    """Multiple distinct NPC relationships all persist correctly."""
    sid = "test-multi-rel"
    m = get_state_manager(sid, isolated_db)
    m.update_relationship("player", "Finn", {"trust": 60.0})
    m.update_relationship("player", "Mira", {"fear": 30.0, "trust": -20.0})

    m2 = _roundtrip(sid, isolated_db)

    assert m2.get_relationship("player", "Finn").trust == 60.0
    mira = m2.get_relationship("player", "Mira")
    assert mira.fear == 30.0
    assert mira.trust == -20.0


def test_environment_survives_restart(isolated_db):
    """Environmental state (weather, time, danger) persists across restart."""
    sid = "test-env"
    m = get_state_manager(sid, isolated_db)
    m.update_environment({
        "weather": "stormy",
        "time_of_day": "night",
        "danger_level": 7,
    })

    m2 = _roundtrip(sid, isolated_db)

    assert m2.environment.weather == "stormy"
    assert m2.environment.time_of_day == "night"
    assert m2.environment.danger_level == 7


def test_full_state_survives_restart(isolated_db):
    """Variables + inventory + relationships + environment all persist together."""
    sid = "test-full"
    m = get_state_manager(sid, isolated_db)

    m.set_variable("chapter", 3)
    m.set_variable("player_class", "ranger")
    m.add_item("lantern", "Brass Lantern", quantity=1, properties={"lit": True})
    m.update_relationship("player", "Elder", {"trust": 80.0, "respect": 60.0})
    m.update_environment({"time_of_day": "evening", "danger_level": 2})

    m2 = _roundtrip(sid, isolated_db)

    assert m2.get_variable("chapter") == 3
    assert m2.get_variable("player_class") == "ranger"
    assert "lantern" in m2.inventory
    assert m2.inventory["lantern"].properties["lit"] is True
    elder = m2.get_relationship("player", "Elder")
    assert elder.trust == 80.0
    assert m2.environment.time_of_day == "evening"
    assert m2.environment.danger_level == 2


def test_legacy_v1_session_still_loads(isolated_db):
    """A session stored in the old flat-variable format (v1) loads correctly."""
    sid = "test-legacy"

    # Write a v1 payload directly to the DB (bypassing the new save logic).
    row = SessionVars(session_id=sid, vars={"gold": 99, "name": "OldSave"})
    isolated_db.add(row)
    isolated_db.commit()

    m = get_state_manager(sid, isolated_db)

    assert m.get_variable("gold") == 99
    assert m.get_variable("name") == "OldSave"
    # Inventory and environment should be at defaults, not errored.
    assert m.inventory == {}
    assert m.environment.weather == "clear"


def test_version_marker_written_on_save(isolated_db):
    """Saved payload is tagged with '_v': 2 so future loads are unambiguous."""
    sid = "test-version"
    m = get_state_manager(sid, isolated_db)
    m.set_variable("x", 1)
    save_state_to_db(m, isolated_db)

    row = isolated_db.get(SessionVars, sid)
    assert row is not None
    assert row.vars.get("_v") == 2  # type: ignore[union-attr]


def test_default_vars_applied_to_new_session(isolated_db):
    """Brand-new sessions get default variables without touching the DB."""
    sid = "test-defaults"
    m = get_state_manager(sid, isolated_db)

    assert m.get_variable("name") == "Adventurer"
    assert m.get_variable("danger") == 0
    assert m.get_variable("has_pickaxe") is True


def test_default_vars_not_overwrite_loaded_state(isolated_db):
    """Defaults don't clobber loaded values when a v2 session is restored."""
    sid = "test-defaults-no-overwrite"
    m = get_state_manager(sid, isolated_db)
    m.set_variable("name", "Theron")
    m.set_variable("danger", 5)

    m2 = _roundtrip(sid, isolated_db)

    assert m2.get_variable("name") == "Theron"
    assert m2.get_variable("danger") == 5
