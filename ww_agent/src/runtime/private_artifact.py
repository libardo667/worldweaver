# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Verify and restore one participant-private checkpoint artifact.

The engine receives only the descriptor returned here. The archive itself stays
under participant custody and uses the existing portable hearth-package format.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.identity.hearth_package import HearthPackageError, import_hearth_package
from src.runtime.ledger import (
    LedgerCorruptionError,
    load_open_private_activity,
    load_resident_process_envelope,
    rebuild_runtime_artifacts,
)
from src.runtime.process_state import ResidentProcessBinding

PRIVATE_ARTIFACT_FORMAT = "worldweaver.hearth-package"
PRIVATE_ARTIFACT_FORMAT_VERSION = 1
PRIVATE_ARTIFACT_SCHEMA = "worldweaver.participant-private-artifact"
PRIVATE_ARTIFACT_SCHEMA_VERSION = 1
_DESCRIPTOR_FIELDS = {
    "custody",
    "format",
    "format_version",
    "artifact_id",
    "sha256",
    "byte_length",
}


class PrivateArtifactError(ValueError):
    """A private artifact is damaged, mismatched, or unsafe to restore."""


def _file_digest(path: Path) -> tuple[int, str]:
    size = 0
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


@dataclass(frozen=True, slots=True)
class PrivateArtifactDescriptor:
    """Content binding shared with the engine; no private prose or file path."""

    artifact_id: str
    sha256: str
    byte_length: int
    format: str = PRIVATE_ARTIFACT_FORMAT
    format_version: int = PRIVATE_ARTIFACT_FORMAT_VERSION
    custody: str = "participant_private"

    def as_dict(self) -> dict[str, Any]:
        return {
            "custody": self.custody,
            "format": self.format,
            "format_version": self.format_version,
            "artifact_id": self.artifact_id,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PrivateArtifactDescriptor":
        if not isinstance(raw, dict) or set(raw) != _DESCRIPTOR_FIELDS:
            raise PrivateArtifactError("private artifact descriptor fields are invalid")
        if raw.get("custody") != "participant_private":
            raise PrivateArtifactError("private artifact custody is invalid")
        if raw.get("format") != PRIVATE_ARTIFACT_FORMAT:
            raise PrivateArtifactError("private artifact format is unsupported")
        if raw.get("format_version") != PRIVATE_ARTIFACT_FORMAT_VERSION:
            raise PrivateArtifactError("private artifact version is unsupported")
        digest = str(raw.get("sha256") or "")
        length = raw.get("byte_length")
        if (
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or isinstance(length, bool)
            or not isinstance(length, int)
            or length <= 0
        ):
            raise PrivateArtifactError("private artifact digest or size is invalid")
        expected_id = f"hearth-package-v1-{digest[:24]}"
        if str(raw.get("artifact_id") or "") != expected_id:
            raise PrivateArtifactError("private artifact ID does not match its digest")
        return cls(
            artifact_id=expected_id,
            sha256=digest,
            byte_length=length,
        )


def describe_private_artifact(package_path: Path) -> PrivateArtifactDescriptor:
    """Describe existing package bytes without exposing their path or contents."""

    package = Path(package_path)
    if not package.is_file() or package.is_symlink():
        raise PrivateArtifactError("private artifact must be a regular file")
    try:
        byte_length, digest = _file_digest(package)
    except OSError as exc:
        raise PrivateArtifactError("private artifact could not be read") from exc
    if byte_length <= 0:
        raise PrivateArtifactError("private artifact is empty")
    return PrivateArtifactDescriptor(
        artifact_id=f"hearth-package-v1-{digest[:24]}",
        sha256=digest,
        byte_length=byte_length,
    )


def verify_private_artifact(
    package_path: Path,
    descriptor: PrivateArtifactDescriptor | dict[str, Any],
) -> PrivateArtifactDescriptor:
    """Verify exact bytes against one descriptor before archive extraction."""

    expected = (
        descriptor
        if isinstance(descriptor, PrivateArtifactDescriptor)
        else PrivateArtifactDescriptor.from_dict(descriptor)
    )
    actual = describe_private_artifact(package_path)
    if actual.byte_length != expected.byte_length or not hmac.compare_digest(
        actual.sha256, expected.sha256
    ):
        raise PrivateArtifactError("private artifact bytes failed integrity validation")
    return expected


def _content_safe_restore_report(
    descriptor: PrivateArtifactDescriptor,
    binding: ResidentProcessBinding,
    activity: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema": PRIVATE_ARTIFACT_SCHEMA,
        "schema_version": PRIVATE_ARTIFACT_SCHEMA_VERSION,
        "artifact_id": descriptor.artifact_id,
        "actor_id": binding.actor_id,
        "hearth": {
            "shard_id": binding.hearth_shard_id,
            "runtime_generation": binding.runtime_generation,
        },
        "attachment": {
            "kind": binding.attachment_kind,
            "world_id": binding.world_id,
            "city_id": binding.city_id,
            "session_id": binding.session_id,
            "travel_id": binding.travel_id,
        },
        "adapter": {
            "id": binding.adapter_id,
            "version": binding.adapter_version,
        },
        "model": {"id": binding.model_id},
        "private_activity": {
            "open": activity is not None,
            "activity_id": str((activity or {}).get("activity_id") or ""),
            "return_at": str((activity or {}).get("return_at") or ""),
            "wake_on": list((activity or {}).get("wake_on") or []),
        },
    }


def restore_private_artifact(
    package_path: Path,
    resident_dir: Path,
    *,
    descriptor: PrivateArtifactDescriptor | dict[str, Any],
    expected_process: ResidentProcessBinding,
) -> dict[str, Any]:
    """Restore through staging and install only after exact process validation."""

    verified = verify_private_artifact(package_path, descriptor)
    target = Path(resident_dir)
    if target.exists() or target.is_symlink():
        raise PrivateArtifactError("private artifact restore target already exists")
    target.parent.mkdir(parents=True, exist_ok=True)

    temporary_root = Path(
        tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}.private-artifact.")
    )
    staged = temporary_root / "resident"
    try:
        import_hearth_package(
            package_path,
            staged,
            expected_actor_id=expected_process.actor_id,
            expected_hearth_shard_id=expected_process.hearth_shard_id,
            expected_runtime_generation=expected_process.runtime_generation,
        )
        memory_dir = staged / "memory"
        rebuild_runtime_artifacts(memory_dir)
        raw_process = load_resident_process_envelope(memory_dir)
        if raw_process is None:
            raise PrivateArtifactError(
                "private artifact has no resident process checkpoint"
            )
        restored_process = ResidentProcessBinding.from_dict(raw_process)
        if restored_process != expected_process:
            raise PrivateArtifactError(
                "private artifact resident process binding does not match"
            )
        activity = load_open_private_activity(memory_dir)
        report = _content_safe_restore_report(
            verified,
            restored_process,
            activity,
        )
        if target.exists() or target.is_symlink():
            raise PrivateArtifactError("private artifact restore target already exists")
        os.replace(staged, target)
        return report
    except (HearthPackageError, LedgerCorruptionError, OSError, ValueError) as exc:
        if isinstance(exc, PrivateArtifactError):
            raise
        raise PrivateArtifactError(str(exc)) from exc
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)
