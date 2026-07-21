from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.identity.loader import LoopTuning, ResidentIdentity
from src.runtime.ledger import load_runtime_events
from src.runtime.reference_core import (
    ReferenceDecision,
    ReferenceDecisionError,
    ReferenceResidentCore,
    classify_action_outcome,
    observe_reference_world,
)
from src.world.client import LiveSignal


def _identity() -> ResidentIdentity:
    return ResidentIdentity(
        name="test_resident",
        actor_id="actor-test-resident",
        soul="You are Test Resident.",
        canonical_soul="You are Test Resident.",
        growth_soul="",
        vibe="",
        core="",
        voice_seed=[],
        tuning=LoopTuning(),
    )


class _FakeLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def complete_json(self, system_prompt, user_prompt, **kwargs):
        self.calls.append((system_prompt, user_prompt, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeWorld:
    def __init__(self, *, scene_error=None, chat_error=None):
        self.scene_error = scene_error
        self.chat_error = chat_error
        self.scene = SimpleNamespace(
            location="Alderbank Commons",
            present=[
                SimpleNamespace(
                    name="test_resident",
                    role="Test Resident",
                    actor_id="actor-test-resident",
                    session_id="test-session",
                ),
                SimpleNamespace(
                    name="Riley",
                    role="Riley",
                    actor_id="actor-riley",
                    session_id="riley-session",
                ),
            ],
            ambient_presence=[SimpleNamespace(label="Rain ticks on the awning")],
            recent_events_here=[SimpleNamespace(summary="A cup changed hands")],
            traces_here=[SimpleNamespace(author_name="Riley", body="a chalk arrow")],
            affordances=[
                SimpleNamespace(name="library", description="Read a local shelf")
            ],
            location_graph={
                "nodes": [
                    {"key": "commons", "name": "Alderbank Commons"},
                    {"key": "bank", "name": "Commons Bank"},
                ],
                "edges": [{"from": "commons", "to": "bank"}],
            },
        )
        self.chat = [
            SimpleNamespace(
                id=1,
                session_id="riley-session",
                actor_id="actor-riley",
                display_name="Riley",
                message="Test Resident, are you staying for tea?",
            )
        ]

    async def get_scene(self, session_id):
        if self.scene_error:
            raise self.scene_error
        return self.scene

    async def get_location_chat(self, location, *, session_id):
        if self.chat_error:
            raise self.chat_error
        return self.chat


def _core(tmp_path, *, responses, effector_result=None, information_result=None):
    acted = []
    reads = []

    async def effector(act, *, now=None):
        acted.append(act)
        if isinstance(effector_result, Exception):
            raise effector_result
        return effector_result or {"executed": True}

    async def information_access(reach, *, now=None):
        reads.append(reach)
        return information_result or {
            "accessed": True,
            "detail": "The shelf holds a river atlas.",
        }

    memory_dir = tmp_path / "memory"
    core = ReferenceResidentCore(
        identity=_identity(),
        memory_dir=memory_dir,
        world=_FakeWorld(),
        llm=_FakeLLM(*responses),
        session_id="test-session",
        effector=effector,
        information_access=information_access,
        tick_seconds=2,
    )
    return core, memory_dir, acted, reads


def test_read_decision_cannot_smuggle_durable_fields():
    with pytest.raises(ReferenceDecisionError, match="unexpected fields"):
        ReferenceDecision.from_dict(
            {
                "choice": "read",
                "source": "library",
                "query": "river",
                "action": {"kind": "speak", "body": "already decided"},
            },
            allow_read=True,
            source_names={"library"},
        )


def test_read_then_action_commits_only_the_final_action(tmp_path):
    core, memory_dir, acted, reads = _core(
        tmp_path,
        responses=[
            {"choice": "read", "source": "library", "query": "river"},
            {
                "choice": "act",
                "action": {
                    "kind": "speak",
                    "body": "The river atlas may help.",
                    "target": "Riley",
                },
            },
        ],
    )

    result = asyncio.run(core.tick_once())

    assert result["action_outcome"] == "confirmed"
    assert len(reads) == 1
    assert len(acted) == 1
    assert acted[0].body == "The river atlas may help."
    events = load_runtime_events(memory_dir)
    assert [event["event_type"] for event in events].count(
        "reference_information_requested"
    ) == 1
    outcome = next(
        event for event in events if event["event_type"] == "reference_action_outcome"
    )
    assert outcome["payload"] == {
        "kind": "speak",
        "outcome": "confirmed",
        "reason": "",
    }
    serialized = str(events)
    assert "river atlas may help" not in serialized.lower()
    assert "The shelf holds a river atlas" not in serialized


def test_failed_after_read_inference_promotes_no_provisional_choice(tmp_path):
    core, memory_dir, acted, reads = _core(
        tmp_path,
        responses=[
            {"choice": "read", "source": "library", "query": "river"},
            RuntimeError("provider unavailable"),
        ],
    )

    result = asyncio.run(core.tick_once())

    assert result["status"] == "inference_failed"
    assert result["reads"] == 1
    assert reads
    assert not acted
    event_types = [event["event_type"] for event in load_runtime_events(memory_dir)]
    assert "reference_action_outcome" not in event_types
    assert "reference_activity_continued" not in event_types


@pytest.mark.parametrize(
    ("effector_result", "expected"),
    [
        ({"executed": True}, "confirmed"),
        ({"executed": False, "reason": "not_present"}, "declined"),
        ({"executed": False, "reason": "timeout"}, "unknown"),
        (None, "unknown"),
    ],
)
def test_action_outcome_has_three_honest_states(effector_result, expected):
    assert classify_action_outcome(effector_result) == expected


def test_wait_is_a_complete_choice_and_calls_no_effector(tmp_path):
    core, memory_dir, acted, reads = _core(
        tmp_path,
        responses=[{"choice": "wait"}],
    )

    result = asyncio.run(core.tick_once())

    assert result == {"status": "completed", "choice": "wait", "reads": 0}
    assert not acted
    assert not reads
    assert load_runtime_events(memory_dir)[-1]["payload"]["outcome"] == "no_action"


def test_no_new_signal_does_not_call_the_model_again_before_baseline(tmp_path):
    core, _memory_dir, acted, reads = _core(
        tmp_path,
        responses=[{"choice": "wait"}],
    )
    start = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)

    first = asyncio.run(core.tick_once(now=start))
    second = asyncio.run(core.tick_once(now=start + timedelta(seconds=20)))

    assert first["status"] == "completed"
    assert second == {
        "status": "idle",
        "choice": "none",
        "reason": "no_new_local_signal_and_baseline_not_due",
    }
    assert not acted
    assert not reads


def test_new_local_speech_wakes_before_the_slow_baseline(tmp_path):
    core, _memory_dir, _acted, _reads = _core(
        tmp_path,
        responses=[{"choice": "wait"}, {"choice": "wait"}],
    )
    start = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    asyncio.run(core.tick_once(now=start))
    core._world.chat.append(
        SimpleNamespace(
            id=2,
            session_id="riley-session",
            actor_id="actor-riley",
            display_name="Riley",
            message="One more thing, Test Resident.",
        )
    )

    result = asyncio.run(core.tick_once(now=start + timedelta(seconds=20)))

    assert result["status"] == "completed"


def test_slow_baseline_does_not_replay_old_speech_as_new(tmp_path):
    core, _memory_dir, _acted, _reads = _core(
        tmp_path,
        responses=[{"choice": "wait"}, {"choice": "wait"}],
    )
    start = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)

    asyncio.run(core.tick_once(now=start))
    asyncio.run(core.tick_once(now=start + timedelta(minutes=5)))

    assert "Recently said here" in core._llm.calls[0][1]
    assert "Recently said here" not in core._llm.calls[1][1]


def test_observation_does_not_turn_unavailable_into_empty():
    unavailable = asyncio.run(
        observe_reference_world(
            _FakeWorld(scene_error=RuntimeError("offline")),
            session_id="test-session",
            identity=_identity(),
        )
    )
    speech_unavailable = asyncio.run(
        observe_reference_world(
            _FakeWorld(chat_error=RuntimeError("offline")),
            session_id="test-session",
            identity=_identity(),
        )
    )

    assert unavailable.availability["scene"] == "unavailable"
    assert speech_unavailable.availability["scene"] == "available"
    assert speech_unavailable.availability["local_speech"] == "unavailable"


def test_unavoidable_hearing_excludes_archived_room_chat():
    world = _FakeWorld()
    world.chat = [
        SimpleNamespace(
            id=1,
            session_id="old-session",
            actor_id="actor-old",
            display_name="Old Speaker",
            message="A conversation from two days ago.",
            ts="2026-07-18T12:00:00+00:00",
        ),
        SimpleNamespace(
            id=2,
            session_id="riley-session",
            actor_id="actor-riley",
            display_name="Riley",
            message="Test Resident, are you here?",
            ts="2026-07-20T12:00:05+00:00",
        ),
    ]

    observation = asyncio.run(
        observe_reference_world(
            world,
            session_id="test-session",
            identity=_identity(),
            local_speech_since=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        )
    )

    assert observation.local_speech == ("Riley: Test Resident, are you here?",)
    assert observation.heard == (("Riley", "2", "chat:Alderbank Commons:2"),)


def test_automatic_prompt_excludes_ambient_narration_and_event_summaries(tmp_path):
    core, _memory_dir, _acted, _reads = _core(
        tmp_path,
        responses=[{"choice": "wait"}],
    )

    asyncio.run(core.tick_once())

    prompt = core._llm.calls[0][1]
    assert "Rain ticks on the awning" not in prompt
    assert "A cup changed hands" not in prompt
    assert "Visible marks: Riley: a chalk arrow" in prompt


def test_local_direct_speech_is_in_the_unavoidable_observation():
    observation = asyncio.run(
        observe_reference_world(
            _FakeWorld(), session_id="test-session", identity=_identity()
        )
    )

    assert observation.present == ("Riley",)
    assert observation.co_present == (("actor-riley", "riley-session", "Riley"),)
    assert observation.local_speech == (
        "Riley: Test Resident, are you staying for tea?",
    )
    assert observation.reachable == ("Commons Bank",)
    assert observation.source_names == {"library"}
    assert observation.heard == (("Riley", "1", "chat:Alderbank Commons:1"),)


def test_cursor_delivered_speech_is_observed_and_acknowledged_without_refetch(
    tmp_path,
):
    core, _memory_dir, _acted, _reads = _core(
        tmp_path,
        responses=[{"choice": "wait"}],
    )
    core._world.chat_error = AssertionError("cursor delivery should avoid chat fetch")
    signal = LiveSignal(
        id=7,
        kind="local_speech",
        location="Alderbank Commons",
        session_id="riley-session",
        actor_id="actor-riley",
        display_name="Riley",
        message="Test Resident, the kettle is ready.",
        occurred_at="2026-07-20T12:00:05",
    )
    core.offer_live_signals((signal,))

    result = asyncio.run(core.tick_once(force_ignite=True))

    assert result["choice"] == "wait"
    assert "Riley: Test Resident, the kettle is ready." in core._llm.calls[0][1]
    assert core.take_acknowledged_live_signal_ids() == (7,)
    assert core.has_seen_live_signals((signal,)) is True


def test_reference_prompt_does_not_name_attention_machinery(tmp_path):
    core, _memory_dir, _acted, _reads = _core(
        tmp_path,
        responses=[{"choice": "wait"}],
    )

    asyncio.run(core.tick_once())

    system_prompt = core._llm.calls[0][0]
    assert "attention" not in system_prompt.casefold()
    assert "Someone speaking here does not require a reply." in system_prompt
