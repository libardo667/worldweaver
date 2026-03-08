from src.services.rules.reducer import reduce_event
from src.services.rules.schema import (
    ChoiceSelectedIntent,
    SystemTickIntent,
    FreeformActionCommittedIntent,
)
from src.models.schemas import ActionDeltaContract, ActionDeltaSetOperation, ActionDeltaIncrementOperation, ActionFactAppendOperation
from src.services.state_manager import AdvancedStateManager
from typing import Any


def test_reducer_applies_sets_and_increments(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-1")
    delta = ActionDeltaContract(set=[ActionDeltaSetOperation(key="location", value="tavern")], increment=[ActionDeltaIncrementOperation(key="tension", amount=2.0)])
    intent = ChoiceSelectedIntent(label="Enter Tavern", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    assert receipt.applied_changes["location"] == "tavern"
    assert receipt.applied_changes["tension"] == 2.0
    assert manager.get_variable("location") == "tavern"
    assert manager.get_variable("tension") == 2.0


def test_reducer_canonicalizes_danger_and_clamps(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-2")
    manager.set_variable("environment.danger_level", 8.0)

    delta = ActionDeltaContract(increment=[ActionDeltaIncrementOperation(key="danger", amount=5.0)])
    intent = FreeformActionCommittedIntent(action_text="I scream loudly", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    # "danger" should canonicalize to "environment.danger_level"
    assert "environment.danger_level" in receipt.applied_changes
    # Clapped to 10
    assert receipt.applied_changes["environment.danger_level"] == 10.0
    assert receipt.applied_changes["danger"] == 10.0
    assert manager.get_variable("environment.danger_level") == 10.0
    assert manager.get_variable("danger") == 10.0
    assert manager.environment.danger_level == 10


def test_reducer_clamps_out_of_bounds_sets(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-schema-1")
    delta = ActionDeltaContract(
        set=[
            ActionDeltaSetOperation(key="tension", value=15.0),  # max 10
            ActionDeltaSetOperation(key="fear", value=-50.0),  # min 0
        ]
    )
    intent = ChoiceSelectedIntent(label="Scream", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    assert receipt.applied_changes["tension"] == 10.0
    assert receipt.applied_changes["fear"] == 0.0
    assert "tension_clamped" in receipt.rejection_reasons
    assert "fear_clamped" in receipt.rejection_reasons
    assert manager.get_variable("tension") == 10.0
    assert manager.get_variable("fear") == 0.0


def test_reducer_blocks_system_keys(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-3")
    delta = ActionDeltaContract(set=[ActionDeltaSetOperation(key="session_id", value="hacked")])
    intent = ChoiceSelectedIntent(label="Hack", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    assert "session_id" in receipt.rejected_changes
    assert receipt.rejection_reasons["session_id"].startswith("Blocked")
    # Underlying session ID is unmodified
    assert manager.session_id == "test-reducer-3"


def test_reducer_blocks_projection_only_keys(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-projection-guard")
    delta = ActionDeltaContract(
        set=[
            ActionDeltaSetOperation(key="projection_depth", value=99),
            ActionDeltaSetOperation(key="non_canon", value=False),
            ActionDeltaSetOperation(key="selected_projection_id", value=123),
        ]
    )
    intent = ChoiceSelectedIntent(label="Inject projection metadata", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    assert "projection_depth" in receipt.rejected_changes
    assert "non_canon" in receipt.rejected_changes
    assert "selected_projection_id" in receipt.rejected_changes
    assert manager.get_variable("projection_depth") is None
    assert manager.get_variable("non_canon") is None
    assert manager.get_variable("selected_projection_id") is None


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


def test_reducer_preserves_internal_keys(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-5")
    manager.set_variable("_world_bible", {"foo": "bar"})
    manager.set_variable("_story_arc", {"act": "rising_action"})
    manager.set_variable("_pokedex_functionality", 1)
    manager.set_variable("_ghost_secret", "delete_me")

    tick = SystemTickIntent()
    receipt = reduce_event(db_session, manager, tick)

    assert "_ghost_secret" in receipt.facts_decayed
    assert "_world_bible" not in receipt.facts_decayed
    assert "_story_arc" not in receipt.facts_decayed

    assert manager.get_variable("_world_bible") == {"foo": "bar"}
    assert manager.get_variable("_story_arc") == {"act": "rising_action"}
    assert manager.get_variable("_ghost_secret") is None


def test_reducer_maps_legacy_stance_boolean_to_structured_enum(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-structured-1")
    delta = ActionDeltaContract(set=[ActionDeltaSetOperation(key="is_hiding", value=True)])
    intent = FreeformActionCommittedIntent(action_text="I duck behind crates", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    assert receipt.applied_changes["stance"] == "hiding"
    assert manager.get_variable("stance") == "hiding"


def test_reducer_rejects_conflicting_stance_without_multi_actor_scene(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-structured-2")
    delta = ActionDeltaContract(
        set=[
            ActionDeltaSetOperation(key="is_hiding", value=True),
            ActionDeltaSetOperation(key="is_negotiating", value=True),
        ]
    )
    intent = ChoiceSelectedIntent(label="Conflict stance", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    assert manager.get_variable("stance") == "hiding"
    assert "stance" in receipt.rejected_changes
    assert "Mutually exclusive stance conflict" in receipt.rejection_reasons["stance"]


def test_reducer_allows_conflicting_stance_in_multi_actor_scene(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-structured-3")
    manager.set_variable("scene.multi_actor", True)
    delta = ActionDeltaContract(
        set=[
            ActionDeltaSetOperation(key="is_hiding", value=True),
            ActionDeltaSetOperation(key="is_negotiating", value=True),
        ]
    )
    intent = ChoiceSelectedIntent(label="Multi actor conflict", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    assert "stance" not in receipt.rejected_changes
    assert manager.get_variable("stance") == "negotiating"


def test_reducer_shunts_unrecognized_state_key_into_namespaced_bag(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-structured-4")
    delta = ActionDeltaContract(set=[ActionDeltaSetOperation(key="state.custom_flag", value=True)])
    intent = ChoiceSelectedIntent(label="Unknown state key", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    bag = manager.get_variable("state.unstructured")
    assert isinstance(bag, dict)
    assert bag.get("state.custom_flag") is True
    assert manager.get_variable("state.custom_flag") is None
    assert receipt.applied_changes["state.unstructured.state.custom_flag"] is True


def test_reducer_validates_tactics_and_decays_ttl_on_tick(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-structured-5")
    set_delta = ActionDeltaContract(
        set=[
            ActionDeltaSetOperation(
                key="tactics",
                value=[
                    {"name": "decoy_active", "ttl": 2},
                    {"name": "decoy_active", "ttl": 4},
                    "smoke_bomb",
                ],
            )
        ]
    )
    reduce_event(db_session, manager, ChoiceSelectedIntent(label="Set tactics", delta=set_delta))

    tactics_after_set = manager.get_variable("tactics")
    assert tactics_after_set == [
        {"name": "decoy_active", "ttl": 2},
        {"name": "smoke_bomb", "ttl": 1},
    ]

    tick_receipt = reduce_event(db_session, manager, SystemTickIntent())
    assert manager.get_variable("tactics") == [{"name": "decoy_active", "ttl": 1}]
    assert "tactic:smoke_bomb" in tick_receipt.facts_decayed


def test_reducer_rejects_invalid_injury_state(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-structured-6")
    delta = ActionDeltaContract(set=[ActionDeltaSetOperation(key="injury_state", value="mangled")])
    intent = ChoiceSelectedIntent(label="Bad injury state", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    assert "injury_state" in receipt.rejected_changes
    assert manager.get_variable("injury_state") == "healthy"


def test_reducer_emits_location_fact_on_set(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-facts-1")
    delta = ActionDeltaContract(set=[ActionDeltaSetOperation(key="location", value="the_red_spool_sanctum")])
    intent = ChoiceSelectedIntent(label="Move to sanctum", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    assert receipt.applied_changes["location"] == "the_red_spool_sanctum"
    location_facts = [f for f in receipt.facts_written if f.predicate == "at_location"]
    assert len(location_facts) == 1
    assert location_facts[0].subject == "player"
    assert location_facts[0].value == "the_red_spool_sanctum"
    assert location_facts[0].location == "the_red_spool_sanctum"


def test_reducer_emits_stance_and_injury_facts(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-facts-2")
    delta = ActionDeltaContract(set=[
        ActionDeltaSetOperation(key="stance", value="hiding"),
        ActionDeltaSetOperation(key="injury_state", value="injured"),
    ])
    intent = FreeformActionCommittedIntent(action_text="I dive behind cover, wounded", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    stance_facts = [f for f in receipt.facts_written if f.predicate == "stance"]
    injury_facts = [f for f in receipt.facts_written if f.predicate == "injury_state"]
    assert len(stance_facts) == 1 and stance_facts[0].value == "hiding"
    assert len(injury_facts) == 1 and injury_facts[0].value == "injured"


def test_reducer_emits_danger_fact_on_increment(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-facts-3")
    delta = ActionDeltaContract(increment=[ActionDeltaIncrementOperation(key="danger", amount=3.0)])
    intent = FreeformActionCommittedIntent(action_text="Wolves howl nearby", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    danger_facts = [f for f in receipt.facts_written if f.predicate == "danger_level"]
    assert len(danger_facts) == 1
    assert danger_facts[0].subject == "world"
    assert danger_facts[0].value == 3.0


def test_reducer_collects_explicit_append_facts(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-facts-4")
    delta = ActionDeltaContract(append_fact=[
        ActionFactAppendOperation(subject="elara", predicate="met_player", value=True, confidence=0.9),
    ])
    intent = FreeformActionCommittedIntent(action_text="I greet Elara", delta=delta)

    receipt = reduce_event(db_session, manager, intent)

    npc_facts = [f for f in receipt.facts_written if f.subject == "elara"]
    assert len(npc_facts) == 1
    assert npc_facts[0].predicate == "met_player"


def test_reducer_no_facts_emitted_for_system_tick(db_session: Any):
    manager = AdvancedStateManager(session_id="test-reducer-facts-5")
    manager.set_variable("location", "the_ossuary_of_echoes")

    receipt = reduce_event(db_session, manager, SystemTickIntent())

    # SystemTickIntent has no delta, so no facts should be written
    assert receipt.facts_written == []
