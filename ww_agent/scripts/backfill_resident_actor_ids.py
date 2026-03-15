"""Assign durable resident actor IDs to existing resident workspaces.

Writes identity/resident_id.txt for any resident that does not already have one.
This keeps agent identity stable across shard federation and pulse restarts.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path
from typing import Dict, Iterable, Optional


def iter_resident_dirs(root: Path) -> Iterable[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith((".", "_"))
    )


def read_resident_id(id_file: Path) -> Optional[str]:
    if not id_file.exists():
        return None
    value = id_file.read_text(encoding="utf-8").strip()
    return value or None


def ensure_resident_id(
    resident_dir: Path,
    known_ids: Dict[str, str],
    dry_run: bool = False,
) -> tuple[str, str]:
    identity_dir = resident_dir / "identity"
    id_file = identity_dir / "resident_id.txt"
    if not identity_dir.exists():
        return ("skipped", f"{resident_dir.name}: missing identity/")
    existing = read_resident_id(id_file)
    canonical = known_ids.get(resident_dir.name)
    if existing:
        if canonical and canonical != existing:
            if not dry_run:
                id_file.write_text(f"{canonical}\n", encoding="utf-8")
            return ("rewritten", f"{resident_dir.name}: {existing} -> {canonical}")
        known_ids.setdefault(resident_dir.name, existing)
        return ("exists", f"{resident_dir.name}: {existing}")

    new_id = canonical or str(uuid.uuid4())
    if not dry_run:
        id_file.write_text(f"{new_id}\n", encoding="utf-8")
    known_ids.setdefault(resident_dir.name, new_id)
    return ("created", f"{resident_dir.name}: {new_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "roots",
        nargs="*",
        help="Resident roots to backfill. Defaults to ww_agent/residents.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be written without changing files.",
    )
    args = parser.parse_args(argv)

    script_dir = Path(__file__).resolve().parent
    default_root = script_dir.parent / "residents"
    roots = [Path(root).resolve() for root in args.roots] if args.roots else [default_root]

    created = 0
    exists = 0
    rewritten = 0
    skipped = 0
    known_ids: Dict[str, str] = {}
    for root in roots:
        print(f"[root] {root}")
        for resident_dir in iter_resident_dirs(root):
            status, message = ensure_resident_id(resident_dir, known_ids, dry_run=args.dry_run)
            print(f"  [{status}] {message}")
            if status == "created":
                created += 1
            elif status == "exists":
                exists += 1
            elif status == "rewritten":
                rewritten += 1
            else:
                skipped += 1

    print(f"\nSummary: created={created} exists={exists} rewritten={rewritten} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
