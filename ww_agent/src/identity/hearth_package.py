# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Read-only classification of one resident home before portable packaging."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from src.identity.hearth_manifest import inspect_hearth_manifest

Disposition = Literal[
    "portable", "rebuildable", "host_specific", "city_local", "unknown"
]

_PORTABLE_ROOT_FILES = {"given.jsonl", "whispers.jsonl"}
_CITY_LOCAL_ROOT_FILES = {"session_id.txt", "world_id.txt"}
_HOST_SPECIFIC_ROOT_FILES = {"hearth.json", "familiar.json"}
_PORTABLE_IDENTITY_FILES = {
    "IDENTITY.md",
    "SOUL.canonical.md",
    "SOUL.md",
    "hearth_manifest.json",
    "resident_id.txt",
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
