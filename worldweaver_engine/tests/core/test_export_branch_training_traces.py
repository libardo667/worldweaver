import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _load_export_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "export_branch_training_traces.py"
    spec = importlib.util.spec_from_file_location("export_branch_training_traces", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_traces_for_shard_exports_branch_labeled_records(tmp_path):
    export_module = _load_export_module()

    from src.database import Base
    from src.models import GuildMemberProfile, SocialFeedbackEvent

    db_path = tmp_path / "branch_traces.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    shard_dir = tmp_path / "shards" / "ww_test"
    resident_dir = shard_dir / "residents" / "mariko_tanaka"
    identity_dir = resident_dir / "identity"
    decisions_dir = resident_dir / "decisions"
    identity_dir.mkdir(parents=True, exist_ok=True)
    decisions_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "resident_id.txt").write_text("resident-mariko\n", encoding="utf-8")
    (decisions_dir / "decision_1.json").write_text(
        json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "guild_snapshot": {"rank": "apprentice", "branches": ["correspondence"]},
                "reflection_prompt": "What you've been doing:\n- I checked the post rack.",
                "subconscious_prompt": "Their journal entry:\n\nI kept thinking about Vera.",
                "reflection": "I kept thinking about Vera.",
                "subconscious": "She seems inclined to reach out.",
                "queued_intents": [{"intent_type": "mail_draft", "priority": 0.8}],
                "soul_note": "I do not want to leave people waiting.",
                "rest_started": False,
                "letter_to": "Vera Chen",
                "raw_reflection": "should not be exported",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    with Session.begin() as session:
        session.add(
            GuildMemberProfile(
                actor_id="resident-mariko",
                member_type="resident",
                rank="journeyman",
                branches=["correspondence"],
                mentor_actor_ids=["mentor-1"],
                quest_band="steady_practice",
                review_status={"state": "good_standing"},
                environment_guidance={"mentor_exposure": "high"},
            )
        )
        session.add(
            SocialFeedbackEvent(
                target_actor_id="resident-mariko",
                source_system="test",
                feedback_mode="explicit",
                channel="mentor",
                dimension_scores={"follow_through": 0.7, "mentorship_receptivity": 0.8},
                summary="Mariko followed through on a correspondence task.",
                evidence_refs=[{"kind": "mail", "id": "dm-1"}],
                branch_hint="correspondence",
            )
        )

    shard = export_module.ShardSpec(
        name="ww_test",
        shard_dir=shard_dir,
        env={"WW_DB_HOST": "", "WW_DB_NAME": ""},
    )

    original_compose = export_module._compose_postgres_url
    export_module._compose_postgres_url = lambda env, host_accessible=True: db_url
    try:
        traces = export_module.build_traces_for_shard(shard, max_per_actor=5)
    finally:
        export_module._compose_postgres_url = original_compose

    assert len(traces) == 1
    trace = traces[0]
    assert trace["branch"] == "correspondence"
    assert trace["rank"] == "journeyman"
    assert trace["selected_context"]["reflection_prompt"].startswith("What you've been doing")
    assert trace["outputs"]["reflection"] == "I kept thinking about Vera."
    assert "raw_reflection" not in trace["outputs"]
    assert trace["feedback_summaries"][0]["summary"].startswith("Mariko followed through")
