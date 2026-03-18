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
