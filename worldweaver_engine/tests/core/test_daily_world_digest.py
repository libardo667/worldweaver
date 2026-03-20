import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _load_digest_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "daily_world_digest.py"
    spec = importlib.util.spec_from_file_location("daily_world_digest", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_digest_for_shard_summarizes_current_runtime(tmp_path):
    digest = _load_digest_module()

    from src.database import Base
    from src.models import (
        DirectMessage,
        GuildMemberProfile,
        LocationChat,
        ResidentIdentityGrowth,
        RuntimeAdaptationState,
        SessionVars,
        SocialFeedbackEvent,
        WorldEvent,
    )

    db_path = tmp_path / "digest.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    shard_dir = tmp_path / "shards" / "ww_test"
    residents_dir = shard_dir / "residents" / "mariko_tanaka" / "identity"
    residents_dir.mkdir(parents=True, exist_ok=True)
    (residents_dir / "resident_id.txt").write_text("resident-mariko\n", encoding="utf-8")
    now = datetime.now(timezone.utc)
    memory_dir = shard_dir / "residents" / "mariko_tanaka" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    (memory_dir / "runtime_snapshot.json").write_text(
        json.dumps(
            {
                "queued_intents": [
                    {
                        "intent_id": "int-1",
                        "intent_type": "move",
                        "target_loop": "fast",
                        "status": "pending",
                        "priority": 0.82,
                        "validation_state": "unvalidated",
                        "source_packet_ids": ["pkt-1"],
                        "created_at": now.isoformat(),
                        "payload": {"destination": "North Beach"},
                    }
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (memory_dir / "runtime_ledger.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_id": "evt-pkt",
                        "ts": (now - timedelta(minutes=6)).isoformat(),
                        "event_type": "packet_emitted",
                        "payload": {
                            "packet_id": "pkt-1",
                            "packet_type": "chat_heard",
                            "created_at": (now - timedelta(minutes=6)).isoformat(),
                            "source_loop": "fast",
                            "status": "pending",
                            "priority": 0.0,
                        },
                    }
                ),
                json.dumps(
                    {
                        "event_id": "evt-int",
                        "ts": (now - timedelta(minutes=5)).isoformat(),
                        "event_type": "intent_staged",
                        "payload": {
                            "intent_id": "int-1",
                            "intent_type": "move",
                            "created_at": (now - timedelta(minutes=5)).isoformat(),
                            "source_packet_ids": ["pkt-1"],
                            "status": "pending",
                            "priority": 0.82,
                            "target_loop": "fast",
                            "payload": {"destination": "North Beach"},
                            "validation_state": "unvalidated",
                            "expires_at": None,
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with Session.begin() as session:
        session.add(
            SessionVars(
                session_id="mariko_tanaka-20260318-120000",
                actor_id="resident-mariko",
                vars={
                    "variables": {
                        "location": "North Beach",
                        "_rest_state": "resting",
                        "_resident_memory_projection": {"pending_research": ["one", "two"]},
                        "_resident_subjective_projection": {
                            "dialogue_state": {"active_partner": "Elaine Cho", "direct_urgency": 0.9},
                            "state_pressure": {"signals": [{"kind": "crowding"}, {"kind": "event_pull"}]},
                        },
                    }
                },
                updated_at=now,
            )
        )
        session.add_all(
            [
                WorldEvent(
                    session_id="mariko_tanaka-20260318-120000",
                    event_type="movement",
                    summary="Mariko Tanaka arrives at North Beach.",
                    world_state_delta={"destination": "North Beach"},
                    created_at=now - timedelta(hours=1),
                ),
                WorldEvent(
                    session_id="mariko_tanaka-20260318-120000",
                    event_type="utterance",
                    summary="Mariko Tanaka said: The block feels awake.",
                    world_state_delta={"location": "North Beach"},
                    created_at=now - timedelta(minutes=30),
                ),
                WorldEvent(
                    session_id="mariko_tanaka-20260318-120000",
                    event_type="freeform_action",
                    summary="Observed: Mariko Tanaka steps under the awning.",
                    world_state_delta={"location": "North Beach"},
                    created_at=now - timedelta(minutes=20),
                ),
                LocationChat(
                    location="North Beach",
                    session_id="mariko_tanaka-20260318-120000",
                    display_name="Mariko Tanaka",
                    message="The block feels awake.",
                    created_at=now - timedelta(minutes=30),
                ),
                DirectMessage(
                    from_name="Mariko Tanaka",
                    from_session_id="mariko_tanaka-20260318-120000",
                    to_name="Elaine Cho",
                    body="Checking in.",
                    sent_at=now - timedelta(minutes=15),
                    read_at=None,
                ),
                ResidentIdentityGrowth(
                    actor_id="resident-mariko",
                    growth_text="Steadier in crowded places.",
                    growth_metadata={
                        "promoted_at": (now - timedelta(hours=2)).isoformat(),
                        "growth_preview": "Steadier in crowded places.",
                    },
                    note_records=[],
                    growth_proposals=[
                        {
                            "proposal_key": "follow_through:positive",
                            "dimension": "follow_through",
                            "summary": "Carries commitments through.",
                            "status": "proposed",
                        }
                    ],
                    updated_at=now - timedelta(hours=2),
                ),
                GuildMemberProfile(
                    actor_id="resident-mariko",
                    member_type="resident",
                    rank="journeyman",
                    branches=["correspondence"],
                    mentor_actor_ids=["mentor-elaine"],
                    quest_band="steady_practice",
                    review_status={"state": "good_standing"},
                    environment_guidance={"mentor_exposure": "high", "solo_time": "normal", "social_density": "high", "quest_band": "steady_practice", "branch_task_bias": "correspondence"},
                ),
                RuntimeAdaptationState(
                    actor_id="resident-mariko",
                    behavior_knobs={"mail_appetite_bias": 0.6, "social_drive_bias": 0.5},
                    environment_guidance={"mentor_exposure": "high", "solo_time": "normal", "social_density": "high", "quest_band": "steady_practice", "branch_task_bias": "correspondence"},
                    source_feedback_ids=[1],
                ),
                SocialFeedbackEvent(
                    target_actor_id="resident-mariko",
                    source_system="test-suite",
                    feedback_mode="explicit",
                    channel="mentor",
                    dimension_scores={"follow_through": 0.8, "sociability": 0.5},
                    summary="Mariko followed through on a social commitment.",
                    evidence_refs=[{"kind": "mail", "id": "dm-1"}],
                    branch_hint="correspondence",
                    created_at=now - timedelta(minutes=10),
                ),
            ]
        )

    shard = digest.ShardSpec(
        name="ww_test",
        shard_dir=shard_dir,
        env={
            "CITY_ID": "test_city",
            "WW_DB_HOST": "",
            "WW_DB_NAME": "",
        },
    )

    original_compose = digest._compose_postgres_url
    digest._compose_postgres_url = lambda env, host_accessible=True: db_url
    try:
        report = digest.build_digest_for_shard(
            shard=shard,
            lookback_hours=24,
            tz_name="America/Los_Angeles",
        )
    finally:
        digest._compose_postgres_url = original_compose

    assert report["population"]["live_residents"] == 1
    assert report["movement"]["top_clusters"][0][0] == "North Beach"
    assert report["behavioral_health"]["event_counts"]["utterance"] == 1
    assert report["behavioral_health"]["event_counts"]["movement"] == 1
    assert report["behavioral_health"]["event_counts"]["freeform_action"] == 1
    assert report["social"]["direct_messages_sent"] == 1
    assert report["identity"]["promotions"][0]["resident"] == "Mariko Tanaka"
    assert report["guild_watch"]["feedback_active_residents"][0]["resident"] == "Mariko Tanaka"
    assert report["guild_watch"]["branch_distribution"][0][0] == "correspondence"
    assert report["guild_watch"]["growth_proposals"]["proposed"] == 1
    assert report["intent_heartbeat"]["current_top_pulls"][0]["intent_type"] == "move"
    assert report["intent_heartbeat"]["high_priority_moments"][0]["intent_type"] == "move"
    assert report["intent_heartbeat"]["dominant_triggers"][0][0] == "chat_heard"

    markdown = digest.render_markdown(report)
    assert "## Test City" in markdown
    assert "North Beach" in markdown
    assert "Mariko Tanaka" in markdown
    assert "**Intent Heartbeat**" in markdown
    assert "**Guild Watch**" in markdown

    publication = digest.render_publication_markdown(
        [report],
        lookback_hours=24,
        timezone_name="America/Los_Angeles",
    )
    assert "**What The Guild Is Watching**" in publication
    assert "correspondence" in publication


def test_build_digest_for_shard_can_include_conversation_themes(tmp_path):
    digest = _load_digest_module()

    from src.database import Base
    from src.models import LocationChat, SessionVars

    db_path = tmp_path / "digest_themes.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    shard_dir = tmp_path / "shards" / "ww_test"
    residents_dir = shard_dir / "residents" / "elaine_cho" / "identity"
    residents_dir.mkdir(parents=True, exist_ok=True)
    (residents_dir / "resident_id.txt").write_text("resident-elaine\n", encoding="utf-8")

    now = datetime.now(timezone.utc)
    with Session.begin() as session:
        session.add(
            SessionVars(
                session_id="elaine_cho-20260318-120000",
                actor_id="resident-elaine",
                vars={"variables": {"location": "North Beach"}},
                updated_at=now,
            )
        )
        session.add_all(
            [
                LocationChat(
                    location="North Beach",
                    session_id="elaine_cho-20260318-120000",
                    display_name="Elaine Cho",
                    message="The block feels unusually quiet tonight.",
                    created_at=now - timedelta(minutes=20),
                ),
                LocationChat(
                    location="North Beach",
                    session_id="mariko_tanaka-20260318-120000",
                    display_name="Mariko Tanaka",
                    message="Quiet, but not empty. More like everyone's listening.",
                    created_at=now - timedelta(minutes=10),
                ),
            ]
        )

    shard = digest.ShardSpec(
        name="ww_test",
        shard_dir=shard_dir,
        env={
            "CITY_ID": "test_city",
            "WW_DB_HOST": "",
            "WW_DB_NAME": "",
        },
    )

    def fake_theme_summarizer(**kwargs):
        assert kwargs["shard_name"] == "ww_test"
        assert kwargs["city_id"] == "test_city"
        assert len(kwargs["lines"]) == 2
        return {
            "status": "ok",
            "summary": "The conversation centers on quietness as a social mood rather than a mere lack of people.",
            "themes": ["attentive quiet", "shared listening"],
            "tensions": ["quiet vs emptiness"],
            "oddities": ["mildly poetic convergence"],
        }

    original_compose = digest._compose_postgres_url
    digest._compose_postgres_url = lambda env, host_accessible=True: db_url
    try:
        report = digest.build_digest_for_shard(
            shard=shard,
            lookback_hours=24,
            tz_name="America/Los_Angeles",
            include_conversation_themes=True,
            theme_message_limit=10,
            theme_summarizer=fake_theme_summarizer,
        )
    finally:
        digest._compose_postgres_url = original_compose

    themes = report["conversation_themes"]
    assert themes["status"] == "ok"
    assert themes["sample_count"] == 2
    assert "attentive quiet" in themes["themes"]

    markdown = digest.render_markdown(report)
    assert "**Conversation Themes**" in markdown
    assert "attentive quiet" in markdown

    publication = digest.render_publication_markdown(
        [report],
        lookback_hours=24,
        timezone_name="America/Los_Angeles",
    )
    assert "# Guild of the Humane Arts Morning Brief" in publication
    assert "shared listening" in publication
    assert "North Beach" in publication


def test_prime_process_env_loads_without_overwriting(monkeypatch, tmp_path):
    digest = _load_digest_module()

    env_path = tmp_path / ".env"
    env_path.write_text(
        "OPENROUTER_API_KEY=test-key\nLLM_MODEL=test-model\nLLM_TIMEOUT_SECONDS=90  # inline comment\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    digest._prime_process_env([env_path])
    assert os.environ["OPENROUTER_API_KEY"] == "test-key"
    assert os.environ["LLM_MODEL"] == "test-model"
    assert os.environ["LLM_TIMEOUT_SECONDS"] == "90"

    monkeypatch.setenv("OPENROUTER_API_KEY", "keep-key")
    monkeypatch.setenv("LLM_MODEL", "keep-model")
    digest._prime_process_env([env_path])
    assert os.environ["OPENROUTER_API_KEY"] == "keep-key"
    assert os.environ["LLM_MODEL"] == "keep-model"
