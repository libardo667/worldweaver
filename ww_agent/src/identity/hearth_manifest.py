# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Stable, host-independent identity for one resident's hearth shard.

The manifest deliberately excludes current world attachment, city session IDs, physical
host identity, provider credentials, and host grants. It is the first portable-hearth
contract, not yet a runtime lease or an export format.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HEARTH_MANIFEST_SCHEMA = "worldweaver.hearth"
HEARTH_MANIFEST_VERSION = 1
HEARTH_MANIFEST_FILENAME = "hearth_manifest.json"
_MANIFEST_FIELDS = {
    "schema",
    "schema_version",
    "actor_id",
    "hearth_shard_id",
    "runtime_generation",
}


class HearthManifestError(ValueError):
    """A resident home cannot provide one valid hearth identity manifest."""


def hearth_shard_id_for_actor(actor_id: str) -> str:
    """Return the stable first-generation hearth ID for one actor."""
    normalized = str(actor_id or "").strip()
    if not normalized:
        raise HearthManifestError("actor_id is required")
    return f"hearth:{normalized}"


@dataclass(frozen=True)
class HearthManifest:
    """Host-independent identity and activation generation for one hearth shard."""

    actor_id: str
    hearth_shard_id: str
    runtime_generation: int = 1
    schema: str = HEARTH_MANIFEST_SCHEMA
    schema_version: int = HEARTH_MANIFEST_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "actor_id": self.actor_id,
            "hearth_shard_id": self.hearth_shard_id,
            "runtime_generation": self.runtime_generation,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "HearthManifest":
        if not isinstance(raw, dict):
            raise HearthManifestError("manifest must be a JSON object")
        unknown = set(raw) - _MANIFEST_FIELDS
        missing = _MANIFEST_FIELDS - set(raw)
        if unknown:
            raise HearthManifestError(
                f"manifest has unknown field(s): {', '.join(sorted(unknown))}"
            )
        if missing:
            raise HearthManifestError(
                f"manifest is missing field(s): {', '.join(sorted(missing))}"
            )
        if raw.get("schema") != HEARTH_MANIFEST_SCHEMA:
            raise HearthManifestError(
                f"unsupported manifest schema: {raw.get('schema')!r}"
            )
        version = raw.get("schema_version")
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version != HEARTH_MANIFEST_VERSION
        ):
            raise HearthManifestError(
                f"unsupported manifest schema_version: {version!r}"
            )
        actor_id = str(raw.get("actor_id") or "").strip()
        if not actor_id:
            raise HearthManifestError("manifest actor_id is required")
        expected_hearth_id = hearth_shard_id_for_actor(actor_id)
        hearth_shard_id = str(raw.get("hearth_shard_id") or "").strip()
        if hearth_shard_id != expected_hearth_id:
            raise HearthManifestError(
                f"hearth_shard_id must be {expected_hearth_id!r} for this manifest version"
            )
        generation = raw.get("runtime_generation")
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
        ):
            raise HearthManifestError(
                "runtime_generation must be an integer greater than zero"
            )
        return cls(
            actor_id=actor_id,
            hearth_shard_id=hearth_shard_id,
            runtime_generation=generation,
        )


def manifest_path(resident_dir: Path) -> Path:
    return Path(resident_dir) / "identity" / HEARTH_MANIFEST_FILENAME


def _read_actor_id(resident_dir: Path) -> str:
    id_path = Path(resident_dir) / "identity" / "resident_id.txt"
    if not id_path.is_file():
        raise HearthManifestError("identity/resident_id.txt is missing")
    actor_id = id_path.read_text(encoding="utf-8").strip()
    if not actor_id:
        raise HearthManifestError("identity/resident_id.txt is empty")
    return actor_id


def proposed_hearth_manifest(resident_dir: Path) -> HearthManifest:
    """Derive the initial manifest without writing anything."""
    actor_id = _read_actor_id(resident_dir)
    return HearthManifest(
        actor_id=actor_id,
        hearth_shard_id=hearth_shard_id_for_actor(actor_id),
    )


def load_hearth_manifest(resident_dir: Path) -> HearthManifest:
    """Read and validate a manifest against the resident's durable actor ID."""
    path = manifest_path(resident_dir)
    if not path.is_file():
        raise HearthManifestError(f"identity/{HEARTH_MANIFEST_FILENAME} is missing")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HearthManifestError(f"manifest is not valid JSON: {exc.msg}") from exc
    manifest = HearthManifest.from_dict(raw)
    actor_id = _read_actor_id(resident_dir)
    if manifest.actor_id != actor_id:
        raise HearthManifestError(
            "manifest actor_id does not match identity/resident_id.txt"
        )
    return manifest


def initialize_hearth_manifest(resident_dir: Path) -> HearthManifest:
    """Write the initial manifest once; never replace an existing file."""
    path = manifest_path(resident_dir)
    if path.exists() or path.is_symlink():
        raise HearthManifestError(
            f"refusing to replace existing identity/{HEARTH_MANIFEST_FILENAME}"
        )
    manifest = proposed_hearth_manifest(resident_dir)
    encoded = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return manifest


def inspect_hearth_manifest(resident_dir: Path) -> dict[str, Any]:
    """Return a safe, read-only status report for operators and migration tooling."""
    home = Path(resident_dir)
    path = manifest_path(home)
    if not path.exists():
        try:
            proposed = proposed_hearth_manifest(home)
        except (HearthManifestError, OSError) as exc:
            return {
                "resident": home.name,
                "status": "invalid",
                "error": str(exc),
            }
        return {
            "resident": home.name,
            "status": "missing",
            "error": f"identity/{HEARTH_MANIFEST_FILENAME} is missing",
            "proposed_manifest": proposed.to_dict(),
        }
    try:
        manifest = load_hearth_manifest(home)
    except (HearthManifestError, OSError) as exc:
        return {
            "resident": home.name,
            "status": "invalid",
            "error": str(exc),
        }
    return {
        "resident": home.name,
        "status": "valid",
        "manifest": manifest.to_dict(),
    }
