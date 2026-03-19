import importlib.util
import json
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
    from src.models import DirectMessage, LocationChat, ResidentIdentityGrowth, SessionVars, WorldEvent

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
                    updated_at=now - timedelta(hours=2),
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
    assert report["intent_heartbeat"]["current_top_pulls"][0]["intent_type"] == "move"
    assert report["intent_heartbeat"]["high_priority_moments"][0]["intent_type"] == "move"
    assert report["intent_heartbeat"]["dominant_triggers"][0][0] == "chat_heard"

    markdown = digest.render_markdown(report)
    assert "## Test City" in markdown
    assert "North Beach" in markdown
    assert "Mariko Tanaka" in markdown
    assert "**Intent Heartbeat**" in markdown


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
