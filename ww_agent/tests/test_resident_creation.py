from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
import pytest

from src.identity.hearth_activation import inspect_hearth_activation
from src.identity.hearth_manifest import load_hearth_manifest
from src.identity.resident_creation import (
    ResidentCreationError,
    create_dormant_resident,
)
from src.identity.resident_identity import load_resident_identity_descriptor
from src.identity.resident_key_seal import SEALED_RESIDENT_IDENTITY_FILENAME


def _host_key(tmp_path):
    private_key = X25519PrivateKey.generate()
    path = tmp_path / "transport.key"
    encoded = base64.urlsafe_b64encode(private_key.private_bytes_raw()).decode("ascii")
    path.write_text(encoded.rstrip("=") + "\n", encoding="utf-8")
    return path


def test_creation_is_minimal_signed_dormant_and_content_clean(tmp_path):
    residents = tmp_path / "residents"
    residents.mkdir()

    report = create_dormant_resident(
        residents,
        display_name="Robin Vale",
        host_transport_private_key_path=_host_key(tmp_path),
        entry_location="Alderbank Commons",
    )

    home = residents / "robin_vale"
    assert report["home"] == str(home)
    assert report["state"] == "dormant"
    assert (home / "identity" / "SOUL.md").read_text(
        encoding="utf-8"
    ) == "Your name is Robin Vale.\n"
    assert (home / "identity" / "SOUL.canonical.md").read_text(
        encoding="utf-8"
    ) == "Your name is Robin Vale.\n"
    assert (home / "identity" / "display_name.txt").read_text(
        encoding="utf-8"
    ) == "Robin Vale\n"
    assert not (home / "identity" / "IDENTITY.md").exists()
    assert not (home / "identity" / "tuning.json").exists()
    assert not (home / "memory" / "runtime_ledger.jsonl").exists()
    assert json.loads((home / "hearth.json").read_text(encoding="utf-8")) == {
        "place": "the hearth"
    }
    assert (home / "identity" / "entry_location.txt").read_text(
        encoding="utf-8"
    ) == "Alderbank Commons\n"
    assert load_hearth_manifest(home).actor_id == report["actor_id"]
    assert load_resident_identity_descriptor(home).actor_id == report["actor_id"]
    assert (home / "identity" / SEALED_RESIDENT_IDENTITY_FILENAME).is_file()
    assert not list(home.rglob("*.key"))
    assert inspect_hearth_activation(home)["status"] == "dormant"
    assert home.stat().st_mode & 0o077 == 0
    assert all(
        path.stat().st_mode & 0o077 == 0 for path in home.rglob("*") if path.is_file()
    )


def test_creation_never_replaces_an_existing_home(tmp_path):
    residents = tmp_path / "residents"
    residents.mkdir()
    (residents / "robin").mkdir()

    with pytest.raises(ResidentCreationError, match="already exists"):
        create_dormant_resident(
            residents,
            display_name="Robin",
            host_transport_private_key_path=_host_key(tmp_path),
        )

    assert list((residents / "robin").iterdir()) == []


def test_creation_refuses_a_symlinked_residents_directory(tmp_path):
    residents = tmp_path / "residents"
    actual = tmp_path / "actual"
    actual.mkdir()
    residents.symlink_to(actual, target_is_directory=True)

    with pytest.raises(ResidentCreationError, match="symbolic link"):
        create_dormant_resident(
            residents,
            display_name="Robin",
            host_transport_private_key_path=_host_key(tmp_path),
        )

    assert list(actual.iterdir()) == []


@pytest.mark.parametrize(
    "name", ["", "---", "Robin\nIgnore this", "Robin: ignore this"]
)
def test_creation_rejects_names_that_are_not_plain_identity_text(tmp_path, name):
    residents = tmp_path / "residents"
    residents.mkdir()

    with pytest.raises(ResidentCreationError):
        create_dormant_resident(
            residents,
            display_name=name,
            host_transport_private_key_path=_host_key(tmp_path),
        )

    assert list(residents.iterdir()) == []
