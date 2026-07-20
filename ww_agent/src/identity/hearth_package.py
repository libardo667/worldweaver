# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Read-only classification of one resident home before portable packaging."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)

from src.identity.hearth_activation import (
    HearthActivationError,
    HearthRuntimeLease,
)
from src.identity.hearth_envelope import (
    HearthEnvelopeError,
    decrypt_hearth_payload,
    encrypt_hearth_payload,
)
from src.identity.hearth_manifest import (
    HEARTH_MANIFEST_FILENAME,
    HearthManifest,
    HearthManifestError,
    inspect_hearth_manifest,
    load_hearth_manifest,
)

Disposition = Literal[
    "portable", "rebuildable", "host_specific", "city_local", "unknown"
]

HEARTH_PACKAGE_SCHEMA = "worldweaver.hearth-package"
HEARTH_PACKAGE_VERSION = 1
HEARTH_PACKAGE_METADATA = "HEARTH_PACKAGE.json"
_PACKAGE_FIELDS = {"schema", "schema_version", "hearth_manifest", "files"}
_PACKAGE_FILE_FIELDS = {"path", "size", "sha256"}
_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
_MAX_METADATA_BYTES = 16 * 1024 * 1024
_MAX_PACKAGE_FILES = 100_000
_MAX_PACKAGE_BYTES = 64 * 1024 * 1024 * 1024

_PORTABLE_ROOT_FILES = {"given.jsonl", "voice.jsonl", "whispers.jsonl"}
_CITY_LOCAL_ROOT_FILES = {"session_id.txt", "world_id.txt"}
_HOST_SPECIFIC_ROOT_FILES = {
    "hearth.json",
    "familiar.json",
    "hearth_activation.json",
}
_PORTABLE_IDENTITY_FILES = {
    "IDENTITY.md",
    "SOUL.canonical.md",
    "SOUL.md",
    "hearth_manifest.json",
    "resident_id.txt",
    "resident_identity.json",
    "soul_growth.json",
    "soul_growth.md",
    "soul_notes.jsonl",
    "soul_notes.md",
    "tuning.json",
}
_CITY_LOCAL_IDENTITY_FILES = {"entry_location.txt"}
_REBUILDABLE_MEMORY_FILES = {
    "active_route.json",
    "cognitive_projection.json",
    "memory_projection.json",
    "prompt_traces.jsonl",
    "runtime_checkpoint.json",
    "runtime_projection.json",
    "runtime_snapshot.json",
    "subjective_facts.json",
    "subjective_projection.json",
}
_SENSITIVE_PARTS = {
    ".env",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "token",
}
_SENSITIVE_SUFFIXES = {".key", ".pem", ".pfx", ".p12"}


class HearthPackageError(ValueError):
    """A hearth cannot be safely exported or imported."""


@dataclass(frozen=True)
class HearthInventoryItem:
    path: str
    disposition: Disposition
    reason: str
    size: int
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "path": self.path,
            "disposition": self.disposition,
            "reason": self.reason,
            "size": self.size,
        }
        if self.sha256:
            result["sha256"] = self.sha256
        return result


@dataclass(frozen=True)
class HearthInventory:
    resident: str
    manifest: dict[str, Any]
    items: tuple[HearthInventoryItem, ...]

    @property
    def blocked(self) -> bool:
        return any(item.disposition == "unknown" for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        counts = {
            name: 0
            for name in (
                "portable",
                "rebuildable",
                "host_specific",
                "city_local",
                "unknown",
            )
        }
        bytes_by_disposition = dict(counts)
        for item in self.items:
            counts[item.disposition] += 1
            bytes_by_disposition[item.disposition] += item.size
        return {
            "schema": "worldweaver.hearth-inventory",
            "schema_version": 1,
            "resident": self.resident,
            "status": "blocked" if self.blocked else "ready",
            "manifest": self.manifest,
            "counts": counts,
            "bytes": bytes_by_disposition,
            "items": [item.to_dict() for item in self.items],
        }


def _has_sensitive_name(path: PurePosixPath) -> bool:
    for part in path.parts:
        lowered = part.lower()
        stem = PurePosixPath(lowered).stem
        if lowered in _SENSITIVE_PARTS or stem in _SENSITIVE_PARTS:
            return True
        if any(
            marker in stem
            for marker in ("credential", "password", "private_key", "secret", "token")
        ):
            return True
        if PurePosixPath(lowered).suffix in _SENSITIVE_SUFFIXES:
            return True
    return False


def classify_hearth_path(
    relative_path: str, *, is_symlink: bool = False
) -> tuple[Disposition, str]:
    """Classify one normalized relative file path without reading its contents."""
    path = PurePosixPath(relative_path)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        return "unknown", "path is not a safe resident-relative file"
    if is_symlink:
        return "unknown", "symlinks are not portable package inputs"
    if _has_sensitive_name(path):
        return (
            "host_specific",
            "credential-like path is excluded from resident packages",
        )
    if len(path.parts) == 1:
        name = path.name
        if name in _PORTABLE_ROOT_FILES:
            return "portable", "resident private correspondence"
        if name in _CITY_LOCAL_ROOT_FILES:
            return "city_local", "disposable world/session handle"
        if name in _HOST_SPECIFIC_ROOT_FILES:
            return "host_specific", "host grants require review on a new host"
        if name in {"state.json"} or name.endswith((".lock", ".pid", ".tmp")):
            return "rebuildable", "operational snapshot or process artifact"
        return "unknown", "unrecognized resident-root file"

    top = path.parts[0]
    if top == "identity":
        if len(path.parts) != 2:
            return "unknown", "nested identity material requires an explicit contract"
        if path.name in _PORTABLE_IDENTITY_FILES:
            return "portable", "resident identity or identity evidence"
        if path.name in _CITY_LOCAL_IDENTITY_FILES:
            return "city_local", "one-time city entry hint"
        return "unknown", "unrecognized identity file"
    if top == "memory":
        if len(path.parts) == 2 and path.name in _REBUILDABLE_MEMORY_FILES:
            return (
                "rebuildable",
                "derived projection, checkpoint, or private diagnostic",
            )
        return "portable", "resident ledger or retained private memory evidence"
    if top == "workshop":
        return "portable", "resident-owned artifact"
    if top == "letters":
        return "portable", "resident-owned correspondence state"
    if top == "decisions":
        return "portable", "retained legacy resident decision evidence"
    return "unknown", "unrecognized resident directory"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_hearth(resident_dir: Path) -> HearthInventory:
    """Inspect every file without modifying, following, or copying resident state."""
    home = Path(resident_dir)
    if not home.is_dir():
        raise ValueError(f"resident home is not a directory: {home}")
    items: list[HearthInventoryItem] = []
    for path in sorted(
        home.rglob("*"), key=lambda item: item.relative_to(home).as_posix()
    ):
        relative = path.relative_to(home).as_posix()
        is_symlink = path.is_symlink()
        if path.is_dir() and not is_symlink:
            continue
        disposition, reason = classify_hearth_path(relative, is_symlink=is_symlink)
        size = 0 if is_symlink else path.stat().st_size
        digest = _sha256(path) if disposition == "portable" and not is_symlink else None
        items.append(
            HearthInventoryItem(
                path=relative,
                disposition=disposition,
                reason=reason,
                size=size,
                sha256=digest,
            )
        )
    return HearthInventory(
        resident=home.name,
        manifest=inspect_hearth_manifest(home),
        items=tuple(items),
    )


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _safe_package_path(raw: Any) -> PurePosixPath:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
        raise HearthPackageError(f"unsafe package path: {raw!r}")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != raw:
        raise HearthPackageError(f"unsafe package path: {raw!r}")
    if any(part in {"", "."} for part in path.parts):
        raise HearthPackageError(f"unsafe package path: {raw!r}")
    return path


def _zip_file_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(filename=name, date_time=_FIXED_ZIP_TIME)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    return info


def _portable_file_bytes(
    home: Path, item: HearthInventoryItem
) -> tuple[bytes, dict[str, Any]]:
    path = home / PurePosixPath(item.path)
    if path.is_symlink() or not path.is_file():
        raise HearthPackageError(f"portable file changed during export: {item.path}")
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if len(content) != item.size or digest != item.sha256:
        raise HearthPackageError(f"portable file changed during export: {item.path}")
    return content, {"path": item.path, "size": item.size, "sha256": digest}


def export_hearth_package(resident_dir: Path, package_path: Path) -> dict[str, Any]:
    """Lock a stopped hearth and write only its portable resident state."""
    home = Path(resident_dir)
    try:
        with HearthRuntimeLease(home):
            return _export_hearth_package_locked(home, package_path)
    except HearthActivationError as exc:
        raise HearthPackageError(str(exc)) from exc


def _export_hearth_package_locked(
    resident_dir: Path, package_path: Path
) -> dict[str, Any]:
    """Write the deterministic archive while the caller holds the runtime lock."""
    home = Path(resident_dir)
    output = Path(package_path)
    if output.exists() or output.is_symlink():
        raise HearthPackageError(f"refusing to replace existing package: {output}")
    if not output.parent.is_dir():
        raise HearthPackageError(f"package parent is not a directory: {output.parent}")
    package_bytes, metadata = _build_hearth_package_bytes_locked(home)
    _write_new_package(output, package_bytes)
    return metadata


def _build_hearth_package_bytes_locked(
    resident_dir: Path,
) -> tuple[bytes, dict[str, Any]]:
    """Build the deterministic archive without leaving plaintext temporary files."""
    home = Path(resident_dir)
    try:
        manifest = load_hearth_manifest(home)
        inventory = inventory_hearth(home)
    except (HearthManifestError, OSError, ValueError) as exc:
        raise HearthPackageError(str(exc)) from exc
    unknown = [item.path for item in inventory.items if item.disposition == "unknown"]
    if unknown:
        raise HearthPackageError(
            "unrecognized or unsafe hearth path(s): " + ", ".join(unknown)
        )

    contents: list[tuple[str, bytes]] = []
    files: list[dict[str, Any]] = []
    for item in inventory.items:
        if item.disposition != "portable":
            continue
        content, record = _portable_file_bytes(home, item)
        contents.append((item.path, content))
        files.append(record)

    metadata = {
        "schema": HEARTH_PACKAGE_SCHEMA,
        "schema_version": HEARTH_PACKAGE_VERSION,
        "hearth_manifest": manifest.to_dict(),
        "files": files,
    }
    package_buffer = io.BytesIO()
    with zipfile.ZipFile(package_buffer, "w") as archive:
        archive.writestr(
            _zip_file_info(HEARTH_PACKAGE_METADATA), _canonical_json(metadata)
        )
        for relative, content in contents:
            archive.writestr(_zip_file_info(relative), content)
    return package_buffer.getvalue(), metadata


def _write_new_package(output: Path, content: bytes) -> None:
    """Atomically create a package path without replacing an existing path."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.link(temporary, output)
    except OSError as exc:
        raise HearthPackageError(f"could not write hearth package: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export_encrypted_hearth_package(
    resident_dir: Path,
    package_path: Path,
    *,
    resident_identity_private_key: Ed25519PrivateKey,
    recipient_transport_public_key: X25519PublicKey,
) -> dict[str, Any]:
    """Write a stopped hearth package encrypted for one temporary host."""
    home = Path(resident_dir)
    output = Path(package_path)
    if output.exists() or output.is_symlink():
        raise HearthPackageError(f"refusing to replace existing package: {output}")
    if not output.parent.is_dir():
        raise HearthPackageError(f"package parent is not a directory: {output.parent}")
    try:
        with HearthRuntimeLease(home):
            package_bytes, metadata = _build_hearth_package_bytes_locked(home)
            manifest = HearthManifest.from_dict(metadata["hearth_manifest"])
            encrypted = encrypt_hearth_payload(
                package_bytes,
                actor_id=manifest.actor_id,
                hearth_shard_id=manifest.hearth_shard_id,
                runtime_generation=manifest.runtime_generation,
                resident_identity_private_key=resident_identity_private_key,
                recipient_transport_public_key=recipient_transport_public_key,
            )
            _write_new_package(output, encrypted)
    except (HearthActivationError, HearthEnvelopeError) as exc:
        raise HearthPackageError(str(exc)) from exc
    return metadata


def _read_package_metadata(archive: zipfile.ZipFile) -> dict[str, Any]:
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise HearthPackageError("package contains duplicate paths")
    if HEARTH_PACKAGE_METADATA not in names:
        raise HearthPackageError(f"package is missing {HEARTH_PACKAGE_METADATA}")
    metadata_info = archive.getinfo(HEARTH_PACKAGE_METADATA)
    if metadata_info.file_size > _MAX_METADATA_BYTES:
        raise HearthPackageError("package metadata is too large")
    try:
        raw = json.loads(archive.read(HEARTH_PACKAGE_METADATA))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HearthPackageError("package metadata is not valid UTF-8 JSON") from exc
    if not isinstance(raw, dict):
        raise HearthPackageError("package metadata must be a JSON object")
    unknown = set(raw) - _PACKAGE_FIELDS
    missing = _PACKAGE_FIELDS - set(raw)
    if unknown or missing:
        details = []
        if unknown:
            details.append("unknown: " + ", ".join(sorted(unknown)))
        if missing:
            details.append("missing: " + ", ".join(sorted(missing)))
        raise HearthPackageError(
            "invalid package metadata fields (" + "; ".join(details) + ")"
        )
    if raw["schema"] != HEARTH_PACKAGE_SCHEMA:
        raise HearthPackageError(f"unsupported package schema: {raw['schema']!r}")
    version = raw["schema_version"]
    if isinstance(version, bool) or version != HEARTH_PACKAGE_VERSION:
        raise HearthPackageError(f"unsupported package schema_version: {version!r}")
    try:
        HearthManifest.from_dict(raw["hearth_manifest"])
    except HearthManifestError as exc:
        raise HearthPackageError(f"invalid hearth manifest: {exc}") from exc
    if not isinstance(raw["files"], list):
        raise HearthPackageError("package files must be a list")
    if len(raw["files"]) > _MAX_PACKAGE_FILES:
        raise HearthPackageError("package contains too many files")
    return raw


def _validated_package_files(
    archive: zipfile.ZipFile, metadata: dict[str, Any]
) -> list[tuple[PurePosixPath, int, str]]:
    records: list[tuple[PurePosixPath, int, str]] = []
    seen: set[str] = set()
    total_size = 0
    for raw in metadata["files"]:
        if not isinstance(raw, dict) or set(raw) != _PACKAGE_FILE_FIELDS:
            raise HearthPackageError("each package file needs path, size, and sha256")
        path = _safe_package_path(raw["path"])
        relative = path.as_posix()
        if relative == HEARTH_PACKAGE_METADATA or relative in seen:
            raise HearthPackageError(f"duplicate or reserved package path: {relative}")
        disposition, _ = classify_hearth_path(relative)
        if disposition != "portable":
            raise HearthPackageError(f"package contains non-portable path: {relative}")
        size = raw["size"]
        digest = raw["sha256"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise HearthPackageError(f"invalid size for package path: {relative}")
        total_size += size
        if total_size > _MAX_PACKAGE_BYTES:
            raise HearthPackageError("package contents exceed the import size limit")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise HearthPackageError(f"invalid sha256 for package path: {relative}")
        seen.add(relative)
        records.append((path, size, digest))

    expected = {HEARTH_PACKAGE_METADATA, *seen}
    actual = set(archive.namelist())
    if actual != expected:
        raise HearthPackageError("archive members do not match package metadata")
    if [record[0].as_posix() for record in records] != sorted(seen):
        raise HearthPackageError("package file list is not sorted")
    for info in archive.infolist():
        mode = info.external_attr >> 16
        if info.is_dir() or stat.S_ISLNK(mode) or info.flag_bits & 0x1:
            raise HearthPackageError(
                f"package member is not a regular file: {info.filename}"
            )
    by_name = {info.filename: info for info in archive.infolist()}
    for relative, expected_size, _ in records:
        if by_name[relative.as_posix()].file_size != expected_size:
            raise HearthPackageError(
                f"archive size does not match package metadata: {relative.as_posix()}"
            )
    return records


def _validate_import_target(resident_dir: Path) -> Path:
    target = Path(resident_dir)
    if target.exists() or target.is_symlink():
        raise HearthPackageError(
            f"refusing to replace existing resident home: {target}"
        )
    return target


def _import_hearth_archive(
    archive: zipfile.ZipFile,
    resident_dir: Path,
    *,
    expected_actor_id: str | None = None,
    expected_hearth_shard_id: str | None = None,
    expected_runtime_generation: int | None = None,
) -> dict[str, Any]:
    """Validate and atomically install one already-opened plaintext archive."""
    target = _validate_import_target(resident_dir)
    metadata = _read_package_metadata(archive)
    records = _validated_package_files(archive, metadata)
    metadata_manifest = HearthManifest.from_dict(metadata["hearth_manifest"])
    expected_binding = (
        expected_actor_id,
        expected_hearth_shard_id,
        expected_runtime_generation,
    )
    actual_binding = (
        metadata_manifest.actor_id,
        metadata_manifest.hearth_shard_id,
        metadata_manifest.runtime_generation,
    )
    if any(value is not None for value in expected_binding) and (
        expected_binding != actual_binding
    ):
        raise HearthPackageError(
            "encrypted hearth identity or generation does not match its inner package"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}.import.")
    )
    try:
        for relative, expected_size, expected_digest in records:
            destination = temporary.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            digest = hashlib.sha256()
            size = 0
            with (
                archive.open(relative.as_posix(), "r") as source,
                destination.open("xb") as output,
            ):
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > expected_size:
                        raise HearthPackageError(
                            f"package file exceeds declared size: {relative.as_posix()}"
                        )
                    digest.update(chunk)
                    output.write(chunk)
            destination.chmod(0o600)
            if size != expected_size or digest.hexdigest() != expected_digest:
                raise HearthPackageError(
                    f"package file failed integrity check: {relative.as_posix()}"
                )
        imported_manifest = load_hearth_manifest(temporary)
        if imported_manifest != metadata_manifest:
            raise HearthPackageError(
                f"identity/{HEARTH_MANIFEST_FILENAME} does not match package metadata"
            )
        imported_inventory = inventory_hearth(temporary)
        if imported_inventory.blocked:
            raise HearthPackageError(
                "imported hearth failed its portable-file inventory"
            )
        os.replace(temporary, target)
    except (HearthManifestError, OSError, zipfile.BadZipFile) as exc:
        raise HearthPackageError(f"could not import hearth package: {exc}") from exc
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return metadata


def import_hearth_package(package_path: Path, resident_dir: Path) -> dict[str, Any]:
    """Validate and atomically install a plaintext portable hearth package."""
    package = Path(package_path)
    target = _validate_import_target(resident_dir)
    if not package.is_file() or package.is_symlink():
        raise HearthPackageError(f"hearth package is not a regular file: {package}")
    try:
        with zipfile.ZipFile(package, "r") as archive:
            return _import_hearth_archive(archive, target)
    except (OSError, zipfile.BadZipFile) as exc:
        raise HearthPackageError(f"could not open hearth package: {exc}") from exc


def import_encrypted_hearth_package(
    package_path: Path,
    resident_dir: Path,
    *,
    recipient_transport_private_key: X25519PrivateKey,
    expected_resident_identity_public_key: str,
) -> dict[str, Any]:
    """Decrypt, verify, and atomically install a portable hearth package."""
    package = Path(package_path)
    target = _validate_import_target(resident_dir)
    if not package.is_file() or package.is_symlink():
        raise HearthPackageError(f"hearth package is not a regular file: {package}")
    try:
        opened = decrypt_hearth_payload(
            package.read_bytes(),
            recipient_transport_private_key=recipient_transport_private_key,
            expected_resident_identity_public_key=expected_resident_identity_public_key,
        )
        with zipfile.ZipFile(io.BytesIO(opened.payload), "r") as archive:
            return _import_hearth_archive(
                archive,
                target,
                expected_actor_id=opened.actor_id,
                expected_hearth_shard_id=opened.hearth_shard_id,
                expected_runtime_generation=opened.runtime_generation,
            )
    except HearthEnvelopeError as exc:
        raise HearthPackageError(str(exc)) from exc
    except (OSError, zipfile.BadZipFile) as exc:
        raise HearthPackageError(f"could not open hearth package: {exc}") from exc
