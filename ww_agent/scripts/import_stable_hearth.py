#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Import one legacy the-stable familiar as a dormant WorldWeaver hearth."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.identity.hearth_manifest import initialize_hearth_manifest  # noqa: E402
from src.identity.hearth_package import inventory_hearth  # noqa: E402
from src.identity.loader import IdentityLoader  # noqa: E402
from src.runtime.ledger import append_runtime_event  # noqa: E402

_ROOT_FILES = ("given.jsonl", "voice.jsonl", "whispers.jsonl")
_IDENTITY_FILES = (
    "IDENTITY.md",
    "SOUL.canonical.md",
    "resident_id.txt",
    "soul_growth.json",
    "soul_growth.md",
    "soul_notes.jsonl",
    "soul_notes.md",
)
_MEMORY_FILES = ("kept_memory.jsonl", "runtime_ledger.jsonl")


class StableHearthImportError(ValueError):
    """The legacy home cannot be safely imported."""


def _source_plan(source: Path) -> list[tuple[Path, Path]]:
    required = (
        source / "identity" / "SOUL.canonical.md",
        source / "identity" / "resident_id.txt",
        source / "memory" / "runtime_ledger.jsonl",
    )
    missing = [
        path.relative_to(source).as_posix() for path in required if not path.is_file()
    ]
    if missing:
        raise StableHearthImportError(
            "legacy home is missing required file(s): " + ", ".join(missing)
        )
    planned: list[tuple[Path, Path]] = []
    for name in _ROOT_FILES:
        path = source / name
        if path.is_file():
            planned.append((path, Path(name)))
    for name in _IDENTITY_FILES:
        path = source / "identity" / name
        if path.is_file():
            planned.append((path, Path("identity") / name))
    for name in _MEMORY_FILES:
        path = source / "memory" / name
        if path.is_file():
            planned.append((path, Path("memory") / name))
    workshop = source / "workshop"
    if workshop.is_dir():
        for path in sorted(workshop.rglob("*")):
            if path.is_symlink():
                raise StableHearthImportError(
                    f"legacy workshop contains a symlink: {path.relative_to(source)}"
                )
            if path.is_file():
                planned.append((path, Path("workshop") / path.relative_to(workshop)))
    return planned


def _read_legacy_config(source: Path) -> dict[str, Any]:
    path = source / "familiar.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StableHearthImportError(
            f"legacy familiar.json is invalid: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise StableHearthImportError("legacy familiar.json must be a JSON object")
    return raw


def inspect_stable_hearth(source_dir: Path) -> dict[str, Any]:
    source = Path(source_dir).resolve()
    if not source.is_dir():
        raise StableHearthImportError(f"legacy home is not a directory: {source}")
    planned = _source_plan(source)
    config = _read_legacy_config(source)
    return {
        "status": "ready",
        "resident": source.name,
        "portable_file_count": len(planned),
        "portable_bytes": sum(path.stat().st_size for path, _ in planned),
        "legacy_model": str(config.get("model") or "").strip() or None,
        "anchor_gating": bool(config.get("anchor_gating", False)),
        "excluded": {
            "host_grants": "legacy familiar.json paths, tools, and city URLs",
            "runtime_output": "daemon.log, state.json, and derived projections",
        },
    }


def import_stable_hearth(
    source_dir: Path,
    target_dir: Path,
    *,
    place: str = "the hearth",
    read_roots: tuple[Path, ...] = (),
) -> dict[str, Any]:
    """Copy allowlisted resident state into a new, dormant home atomically."""
    source = Path(source_dir).resolve()
    target = Path(target_dir).resolve()
    report = inspect_stable_hearth(source)
    if target.exists() or target.is_symlink():
        raise StableHearthImportError(f"refusing to replace existing target: {target}")
    if not target.parent.is_dir():
        raise StableHearthImportError(
            f"target parent is not a directory: {target.parent}"
        )
    planned = _source_plan(source)
    config = _read_legacy_config(source)
    temporary = Path(
        tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}.import.")
    )
    try:
        for source_path, relative in planned:
            destination = temporary / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, destination)

        canonical, growth = IdentityLoader.load_canonical_and_growth(temporary)
        IdentityLoader.write_composed_soul(temporary, canonical, growth)
        model = str(config.get("model") or "").strip()
        tuning: dict[str, Any] = {
            "anchor_gating": bool(config.get("anchor_gating", False))
        }
        if model:
            tuning["fast"] = {"model": model}
            tuning["slow"] = {"model": model}
        (temporary / "identity" / "tuning.json").write_text(
            json.dumps(tuning, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        hearth = {
            "place": str(place or "the hearth").strip() or "the hearth",
            "read_roots": [str(Path(root).resolve()) for root in read_roots],
        }
        (temporary / "hearth.json").write_text(
            json.dumps(hearth, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        append_runtime_event(
            temporary / "memory",
            event_type="legacy_hearth_imported",
            payload={
                "source_lineage": "the-stable familiar",
                "portable_file_count": len(planned),
                "host_grants_carried": False,
                "runtime_generation": 1,
            },
        )
        manifest = initialize_hearth_manifest(temporary)
        inventory = inventory_hearth(temporary)
        if inventory.blocked:
            unknown = [
                item.path for item in inventory.items if item.disposition == "unknown"
            ]
            raise StableHearthImportError(
                "imported home has unclassified path(s): " + ", ".join(unknown)
            )
        os.replace(temporary, target)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return {
        **report,
        "status": "imported_dormant",
        "target": str(target),
        "hearth_manifest": manifest.to_dict(),
        "new_host_read_root_count": len(read_roots),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="legacy the-stable familiar home")
    parser.add_argument("target", help="new WorldWeaver resident home")
    parser.add_argument("--place", default="the hearth", help="new hearth description")
    parser.add_argument(
        "--read-root",
        action="append",
        default=[],
        help="explicit host read grant; old Stable grants are never copied",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the atomic import; omitted means read-only inspection",
    )
    args = parser.parse_args(argv)
    source = Path(args.source).expanduser()
    target = Path(args.target).expanduser()
    try:
        if args.apply:
            report = import_stable_hearth(
                source,
                target,
                place=args.place,
                read_roots=tuple(Path(root).expanduser() for root in args.read_root),
            )
        else:
            report = {
                **inspect_stable_hearth(source),
                "mode": "dry_run",
                "target": str(target.resolve()),
                "new_host_read_root_count": len(args.read_root),
            }
    except (OSError, StableHearthImportError, ValueError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
