import pytest
from src.services.rules.reducer import reduce_event
from src.services.rules.schema import (
    ChoiceSelectedIntent,
    SystemTickIntent,
    FreeformActionCommittedIntent,
)
from src.models.schemas import ActionDeltaContract, ActionDeltaSetOperation, ActionDeltaIncrementOperation
from src.services.state_manager import AdvancedStateManager
from typing import Any

def test_reducer_applies_sets_and_increments(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-1")
    delta = ActionDeltaContract(
        set=[ActionDeltaSetOperation(key="location", value="tavern")],
        increment=[ActionDeltaIncrementOperation(key="tension", amount=2.0)]
    )
    intent = ChoiceSelectedIntent(label="Enter Tavern", delta=delta)
    
    receipt = reduce_event(db_session, manager, intent)
    
    assert receipt.applied_changes["location"] == "tavern"
    assert receipt.applied_changes["tension"] == 2.0
    assert manager.get_variable("location") == "tavern"
    assert manager.get_variable("tension") == 2.0

def test_reducer_canonicalizes_danger_and_clamps(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-2")
    manager.set_variable("environment.danger_level", 8.0)
    
    delta = ActionDeltaContract(
        increment=[ActionDeltaIncrementOperation(key="danger", amount=5.0)]
    )
    intent = FreeformActionCommittedIntent(action_text="I scream loudly", delta=delta)
    
    receipt = reduce_event(db_session, manager, intent)
    
    # "danger" should canonicalize to "environment.danger_level"
    assert "environment.danger_level" in receipt.applied_changes
    # Clapped to 10
    assert receipt.applied_changes["environment.danger_level"] == 10.0
    assert manager.get_variable("environment.danger_level") == 10.0

def test_reducer_blocks_system_keys(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-3")
    delta = ActionDeltaContract(
        set=[ActionDeltaSetOperation(key="session_id", value="hacked")]
    )
    intent = ChoiceSelectedIntent(label="Hack", delta=delta)
    
    receipt = reduce_event(db_session, manager, intent)
    
    assert "session_id" in receipt.rejected_changes
    assert receipt.rejection_reasons["session_id"].startswith("Blocked")
    # Underlying session ID is unmodified
    assert manager.session_id == "test-reducer-3"

def test_reducer_decays_flavor_facts_on_tick(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-4")
    manager.set_variable("flavor_muddy_shoes", True)
    manager.set_variable("descriptive_weather", "raining")
    manager.set_variable("location", "inn")
    
    tick = SystemTickIntent()
    receipt = reduce_event(db_session, manager, tick)
    
    assert "flavor_muddy_shoes" in receipt.facts_decayed
    assert "descriptive_weather" in receipt.facts_decayed
    assert "location" not in receipt.facts_decayed
    
    assert manager.get_variable("flavor_muddy_shoes") is None
    assert manager.get_variable("descriptive_weather") is None
    assert manager.get_variable("location") == "inn"
