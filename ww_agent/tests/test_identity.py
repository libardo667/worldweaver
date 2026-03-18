from pathlib import Path

from src.identity.loader import IdentityLoader


def _write_identity(resident_dir: Path) -> None:
    identity_dir = resident_dir / "identity"
    identity_dir.mkdir(parents=True, exist_ok=True)
    (identity_dir / "SOUL.md").write_text("A steady soul.\n", encoding="utf-8")
    (identity_dir / "IDENTITY.md").write_text("# Test Resident\n", encoding="utf-8")


def test_identity_loader_creates_resident_actor_id(tmp_path):
    resident_dir = tmp_path / "maya_chen"
    _write_identity(resident_dir)

    identity = IdentityLoader.load(resident_dir)

    id_path = resident_dir / "identity" / "resident_id.txt"
    assert id_path.exists()
    assert identity.actor_id == id_path.read_text(encoding="utf-8").strip()


def test_identity_loader_preserves_existing_resident_actor_id(tmp_path):
    resident_dir = tmp_path / "maya_chen"
    _write_identity(resident_dir)
    id_path = resident_dir / "identity" / "resident_id.txt"
    id_path.write_text("resident-maya-chen\n", encoding="utf-8")

    identity = IdentityLoader.load(resident_dir)

    assert identity.actor_id == "resident-maya-chen"
    assert id_path.read_text(encoding="utf-8").strip() == "resident-maya-chen"
