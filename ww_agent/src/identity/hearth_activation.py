# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Stopped-runtime activation and local split-brain protection for hearths."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from src.identity.hearth_manifest import (
    HearthManifest,
    HearthManifestError,
    advance_hearth_manifest_generation,
    load_hearth_manifest,
    manifest_path,
)

HEARTH_ACTIVATION_SCHEMA = "worldweaver.hearth-activation"
HEARTH_ACTIVATION_VERSION = 1
HEARTH_ACTIVATION_FILENAME = "hearth_activation.json"
HEARTH_RUNTIME_LOCK_FILENAME = "runtime.lock"
_ACTIVATION_FIELDS = {
    "schema",
    "schema_version",
    "actor_id",
    "hearth_shard_id",
    "runtime_generation",
    "state",
}

ActivationState = Literal["active", "retired"]


class HearthActivationError(RuntimeError):
    """A hearth is not entitled to start or cannot be safely transferred."""


@dataclass(frozen=True)
class HearthActivation:
    actor_id: str
    hearth_shard_id: str
    runtime_generation: int
    state: ActivationState
    schema: str = HEARTH_ACTIVATION_SCHEMA
    schema_version: int = HEARTH_ACTIVATION_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "schema_version": self.schema_version,
            "actor_id": self.actor_id,
            "hearth_shard_id": self.hearth_shard_id,
            "runtime_generation": self.runtime_generation,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "HearthActivation":
        if not isinstance(raw, dict):
            raise HearthActivationError("activation must be a JSON object")
        unknown = set(raw) - _ACTIVATION_FIELDS
        missing = _ACTIVATION_FIELDS - set(raw)
        if unknown:
            raise HearthActivationError(
                f"activation has unknown field(s): {', '.join(sorted(unknown))}"
            )
        if missing:
            raise HearthActivationError(
                f"activation is missing field(s): {', '.join(sorted(missing))}"
            )
        if raw["schema"] != HEARTH_ACTIVATION_SCHEMA:
            raise HearthActivationError(
                f"unsupported activation schema: {raw['schema']!r}"
            )
        version = raw["schema_version"]
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version != HEARTH_ACTIVATION_VERSION
        ):
            raise HearthActivationError(
                f"unsupported activation schema_version: {version!r}"
            )
        actor_id = str(raw["actor_id"] or "").strip()
        hearth_shard_id = str(raw["hearth_shard_id"] or "").strip()
        generation = raw["runtime_generation"]
        state = raw["state"]
        if not actor_id or not hearth_shard_id:
            raise HearthActivationError("activation identity is required")
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or generation < 1
        ):
            raise HearthActivationError(
                "activation runtime_generation must be greater than zero"
            )
        if state not in {"active", "retired"}:
            raise HearthActivationError("activation state must be active or retired")
        return cls(
            actor_id=actor_id,
            hearth_shard_id=hearth_shard_id,
            runtime_generation=generation,
            state=state,
        )


class HearthRuntimeLease:
    """One process-wide exclusive lock held for the resident's waking lifetime."""

    def __init__(self, resident_dir: Path):
        self.resident_dir = Path(resident_dir)
        self.path = self.resident_dir / HEARTH_RUNTIME_LOCK_FILENAME
        self._handle = None

    def acquire(self) -> "HearthRuntimeLease":
        if self._handle is not None:
            raise HearthActivationError("hearth runtime lock is already held")
        if not self.resident_dir.is_dir():
            raise HearthActivationError(
                f"resident home is not a directory: {self.resident_dir}"
            )
        handle = self.path.open("a+b")
        try:
            os.chmod(self.path, 0o600)
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            handle.close()
            raise HearthActivationError(
                "resident is already running or another transfer is in progress"
            ) from exc
        self._handle = handle
        return self

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "HearthRuntimeLease":
        return self.acquire()

    def __exit__(self, *_args: object) -> None:
        self.release()


def activation_path(resident_dir: Path) -> Path:
    return Path(resident_dir) / HEARTH_ACTIVATION_FILENAME


def _activation_for_manifest(
    manifest: HearthManifest, *, state: ActivationState
) -> HearthActivation:
    return HearthActivation(
        actor_id=manifest.actor_id,
        hearth_shard_id=manifest.hearth_shard_id,
        runtime_generation=manifest.runtime_generation,
        state=state,
    )


def _write_activation(resident_dir: Path, activation: HearthActivation) -> None:
    path = activation_path(resident_dir)
    encoded = json.dumps(activation.to_dict(), indent=2, sort_keys=True) + "\n"
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


def load_hearth_activation(resident_dir: Path) -> HearthActivation:
    path = activation_path(resident_dir)
    if not path.is_file() or path.is_symlink():
        raise HearthActivationError(f"{HEARTH_ACTIVATION_FILENAME} is missing")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HearthActivationError("activation is not valid UTF-8 JSON") from exc
    activation = HearthActivation.from_dict(raw)
    try:
        manifest = load_hearth_manifest(resident_dir)
    except (HearthManifestError, OSError) as exc:
        raise HearthActivationError(str(exc)) from exc
    if (
        activation.actor_id != manifest.actor_id
        or activation.hearth_shard_id != manifest.hearth_shard_id
        or activation.runtime_generation != manifest.runtime_generation
    ):
        raise HearthActivationError("activation does not match the hearth manifest")
    return activation


def inspect_hearth_activation(resident_dir: Path) -> dict[str, Any]:
    home = Path(resident_dir)
    if not manifest_path(home).exists():
        return {
            "resident": home.name,
            "status": "legacy",
            "note": "no hearth manifest; activation fencing is not enabled",
        }
    try:
        manifest = load_hearth_manifest(home)
    except (HearthManifestError, OSError) as exc:
        return {"resident": home.name, "status": "invalid", "error": str(exc)}
    if not activation_path(home).exists():
        return {
            "resident": home.name,
            "status": "dormant",
            "manifest": manifest.to_dict(),
            "error": f"{HEARTH_ACTIVATION_FILENAME} is missing",
        }
    try:
        activation = load_hearth_activation(home)
    except (HearthActivationError, OSError) as exc:
        return {"resident": home.name, "status": "invalid", "error": str(exc)}
    return {
        "resident": home.name,
        "status": activation.state,
        "manifest": manifest.to_dict(),
        "activation": activation.to_dict(),
    }


def initialize_hearth_activation(resident_dir: Path) -> HearthActivation:
    """Make a newly manifested, stopped home active for its first generation."""
    home = Path(resident_dir)
    with HearthRuntimeLease(home):
        path = activation_path(home)
        if path.exists() or path.is_symlink():
            raise HearthActivationError(
                f"refusing to replace existing {HEARTH_ACTIVATION_FILENAME}"
            )
        try:
            manifest = load_hearth_manifest(home)
        except (HearthManifestError, OSError) as exc:
            raise HearthActivationError(str(exc)) from exc
        activation = _activation_for_manifest(manifest, state="active")
        _write_activation(home, activation)
        return activation


def acquire_hearth_runtime(resident_dir: Path) -> HearthRuntimeLease:
    """Acquire one runtime slot and reject dormant or retired manifested homes."""
    home = Path(resident_dir)
    lease = HearthRuntimeLease(home).acquire()
    try:
        if not manifest_path(home).exists():
            return lease
        activation = load_hearth_activation(home)
        if activation.state != "active":
            raise HearthActivationError(
                f"hearth generation {activation.runtime_generation} is retired"
            )
        return lease
    except BaseException:
        lease.release()
        raise


def activate_imported_hearth(source_dir: Path, imported_dir: Path) -> HearthActivation:
    """Retire a stopped source and activate its imported copy at generation N+1.

    The operation is restartable after interruption: destination manifest advance,
    source retirement, and destination activation are deliberately ordered so there
    is never a normal path that starts both copies.
    """
    source = Path(source_dir)
    target = Path(imported_dir)
    if source.resolve() == target.resolve():
        raise HearthActivationError("source and imported hearth must be different")
    source_lease = HearthRuntimeLease(source).acquire()
    try:
        target_lease = HearthRuntimeLease(target).acquire()
    except BaseException:
        source_lease.release()
        raise
    try:
        try:
            source_manifest = load_hearth_manifest(source)
            target_manifest = load_hearth_manifest(target)
        except (HearthManifestError, OSError) as exc:
            raise HearthActivationError(str(exc)) from exc
        if (
            source_manifest.actor_id != target_manifest.actor_id
            or source_manifest.hearth_shard_id != target_manifest.hearth_shard_id
        ):
            raise HearthActivationError("source and imported hearth identities differ")
        if target_manifest.runtime_generation not in {
            source_manifest.runtime_generation,
            source_manifest.runtime_generation + 1,
        }:
            raise HearthActivationError(
                "imported hearth generation is not a resumable successor"
            )
        source_activation = load_hearth_activation(source)
        target_activation = (
            load_hearth_activation(target) if activation_path(target).exists() else None
        )
        if target_activation is not None and target_activation.state != "active":
            raise HearthActivationError("imported hearth activation is not active")
        if source_activation.state == "active" and target_activation is not None:
            raise HearthActivationError("both hearth copies claim to be active")
        if target_manifest.runtime_generation == source_manifest.runtime_generation:
            if source_activation.state != "active":
                raise HearthActivationError(
                    "retired source has no advanced imported successor"
                )
            try:
                target_manifest = advance_hearth_manifest_generation(
                    target,
                    expected_generation=source_manifest.runtime_generation,
                )
            except (HearthManifestError, OSError) as exc:
                raise HearthActivationError(str(exc)) from exc
        if source_activation.state == "active":
            _write_activation(
                source,
                _activation_for_manifest(source_manifest, state="retired"),
            )
        if target_activation is None:
            target_activation = _activation_for_manifest(
                target_manifest, state="active"
            )
            _write_activation(target, target_activation)
        return target_activation
    finally:
        target_lease.release()
        source_lease.release()
