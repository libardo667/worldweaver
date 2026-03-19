import importlib.util
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _load_canon_reset_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "canon_reset.py"
    spec = importlib.util.spec_from_file_location("canon_reset", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clear_federation_residue_removes_shard_scoped_agent_state(tmp_path):
    canon_reset = _load_canon_reset_module()

    from src.database import Base
    from src.models import FederationMessage, FederationResident, FederationTraveler

    db_path = tmp_path / "world.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session.begin() as session:
        session.add_all(
            [
                FederationResident(
                    resident_id="resident-sfo-1",
                    name="Sun Li",
                    home_shard="san_francisco",
                    current_shard="san_francisco",
                    resident_type="agent",
                    status="active",
                ),
                FederationResident(
                    resident_id="resident-pdx-1",
                    name="Mateo Flores",
                    home_shard="portland",
                    current_shard="portland",
                    resident_type="agent",
                    status="active",
                ),
                FederationResident(
                    resident_id="player-sfo-1",
                    name="Levi",
                    home_shard="san_francisco",
                    current_shard="san_francisco",
                    resident_type="player",
                    status="active",
                ),
                FederationTraveler(
                    resident_id="resident-sfo-1",
                    name="Sun Li",
                    from_shard="san_francisco",
                    to_shard="portland",
                ),
                FederationTraveler(
                    resident_id="resident-pdx-1",
                    name="Mateo Flores",
                    from_shard="portland",
                    to_shard="san_francisco",
                ),
                FederationMessage(
                    from_resident_id="resident-sfo-1",
                    from_shard="san_francisco",
                    to_resident_id="resident-pdx-1",
                    to_shard="portland",
                    body="Meet me in Chinatown.",
                ),
                FederationMessage(
                    from_resident_id="resident-pdx-1",
                    from_shard="portland",
                    to_resident_id="resident-sfo-1",
                    to_shard="san_francisco",
                    body="On my way.",
                ),
            ]
        )

    result = canon_reset._clear_federation_residue(
        db_url,
        shard_id="san_francisco",
        resident_actor_ids=["resident-sfo-1"],
        dry_run=False,
    )

    assert result == {
        "federation_messages_deleted": 2,
        "federation_travelers_deleted": 2,
        "federation_residents_deleted": 1,
    }

    with Session() as session:
        residents = session.query(FederationResident).order_by(FederationResident.resident_id).all()
        assert [resident.resident_id for resident in residents] == ["player-sfo-1", "resident-pdx-1"]
        assert session.query(FederationTraveler).count() == 0
        assert session.query(FederationMessage).count() == 0


def test_clear_resident_identity_growth_removes_actor_scoped_rows(tmp_path):
    canon_reset = _load_canon_reset_module()

    from src.database import Base
    from src.models import ResidentIdentityGrowth

    db_path = tmp_path / "world.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session.begin() as session:
        session.add_all(
            [
                ResidentIdentityGrowth(
                    actor_id="resident-sfo-1",
                    growth_text="Steadier under pressure.",
                    growth_metadata={"promoted_at": "2026-03-18T12:00:00+00:00"},
                    note_records=[{"note": "I kept my footing."}],
                ),
                ResidentIdentityGrowth(
                    actor_id="resident-pdx-1",
                    growth_text="Still here.",
                    growth_metadata={},
                    note_records=[],
                ),
            ]
        )

    result = canon_reset._clear_resident_identity_growth(
        db_url,
        resident_actor_ids=["resident-sfo-1"],
        dry_run=False,
    )

    assert result == {"identity_growth_deleted": 1}

    with Session() as session:
        rows = session.query(ResidentIdentityGrowth).order_by(ResidentIdentityGrowth.actor_id).all()
        assert [row.actor_id for row in rows] == ["resident-pdx-1"]


def test_clear_resident_identity_growth_clear_all_removes_all_rows(tmp_path):
    canon_reset = _load_canon_reset_module()

    from src.database import Base
    from src.models import ResidentIdentityGrowth

    db_path = tmp_path / "world.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session.begin() as session:
        session.add_all(
            [
                ResidentIdentityGrowth(actor_id="resident-a", growth_text="A", growth_metadata={}, note_records=[]),
                ResidentIdentityGrowth(actor_id="resident-b", growth_text="B", growth_metadata={}, note_records=[]),
            ]
        )

    result = canon_reset._clear_resident_identity_growth(
        db_url,
        resident_actor_ids=[],
        clear_all=True,
        dry_run=False,
    )

    assert result == {"identity_growth_deleted": 2}

    with Session() as session:
        assert session.query(ResidentIdentityGrowth).count() == 0


def test_clear_resident_sessions_uses_actor_ids_when_slug_matching_misses(tmp_path):
    canon_reset = _load_canon_reset_module()

    from src.database import Base
    from src.models import SessionVars

    db_path = tmp_path / "world.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session.begin() as session:
        session.add_all(
            [
                SessionVars(session_id="anita_cortez-20260318-214752", actor_id="resident-anita", vars={"location": "Hayes Valley"}),
                SessionVars(session_id="world-20260318-000000", actor_id=None, vars={"location": "The Mission"}),
            ]
        )

    result = canon_reset._clear_resident_sessions(
        db_url,
        resident_slugs=["anita cortez"],
        resident_actor_ids=["resident-anita"],
        dry_run=False,
    )

    assert result == {"sessions_deleted": 1}

    with Session() as session:
        rows = session.query(SessionVars).order_by(SessionVars.session_id).all()
        assert [row.session_id for row in rows] == ["world-20260318-000000"]


def test_clear_resident_sessions_clear_all_preserves_world_session_only(tmp_path):
    canon_reset = _load_canon_reset_module()

    from src.database import Base
    from src.models import SessionVars

    db_path = tmp_path / "world.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    with Session.begin() as session:
        session.add_all(
            [
                SessionVars(session_id="elaine_cho-20260319-031626", actor_id="resident-elaine", vars={"location": "Kerns"}),
                SessionVars(session_id="ww-mmwkfnz2-8v4k6h1f", actor_id="player-actor", vars={"location": "Pleasant Valley"}),
                SessionVars(session_id="world-20260318-000000", actor_id=None, vars={"location": "The Mission"}),
            ]
        )

    result = canon_reset._clear_resident_sessions(
        db_url,
        resident_slugs=[],
        resident_actor_ids=[],
        clear_all=True,
        dry_run=False,
    )

    assert result == {"sessions_deleted": 2}

    with Session() as session:
        rows = session.query(SessionVars).order_by(SessionVars.session_id).all()
        assert [row.session_id for row in rows] == ["world-20260318-000000"]


def test_reset_resident_restores_canonical_soul_and_clears_growth(tmp_path):
    canon_reset = _load_canon_reset_module()

    resident_dir = tmp_path / "residents" / "sun_li"
    identity_dir = resident_dir / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "SOUL.canonical.md").write_text("Canonical Sun Li.\n", encoding="utf-8")
    (identity_dir / "SOUL.md").write_text(
        "Corrupted drift.\n\n---\n\nWhat has deepened through lived experience:\n\nSomething uncanny.\n",
        encoding="utf-8",
    )
    (identity_dir / "soul_growth.md").write_text("Something uncanny.\n", encoding="utf-8")
    (identity_dir / "soul_growth.json").write_text('{"promoted_at":"2026-03-18T10:00:00+00:00"}\n', encoding="utf-8")
    (identity_dir / "soul_notes.md").write_text("\n---\nA strange note\n", encoding="utf-8")
    (identity_dir / "soul_notes.jsonl").write_text('{"ts":"2026-03-18T10:00:00+00:00","note":"A strange note"}\n', encoding="utf-8")

    canon_reset._reset_resident(resident_dir, dry_run=False)

    assert (identity_dir / "SOUL.md").read_text(encoding="utf-8") == "Canonical Sun Li.\n"
    assert not (identity_dir / "soul_growth.md").exists()
    assert not (identity_dir / "soul_growth.json").exists()
    assert not (identity_dir / "soul_notes.md").exists()
    assert not (identity_dir / "soul_notes.jsonl").exists()
