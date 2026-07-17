#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Leave a file in a resident's explicitly enabled private gift source."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = REPO_ROOT / "ww_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.familiar.config import HearthConfig  # noqa: E402


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Leave a file in a resident's private gift source.")
    parser.add_argument("home", help="resident home directory")
    parser.add_argument("file", help="file to give")
    parser.add_argument("--as", dest="rename", default="", help="name used inside workshop/given")
    parser.add_argument("--note", default="", help="private note stored with the gift")
    parser.add_argument("--say", default="", help="optional keeper whisper, which also rouses the resident")
    args = parser.parse_args()

    home = Path(args.home).expanduser().resolve()
    if not home.is_dir() or not (home / "identity").is_dir():
        print(f"error: {home} is not a resident home (missing identity/)", file=sys.stderr)
        return 2
    config = HearthConfig.load(home)
    if not config.gifts:
        print(f'error: gifts are not enabled for {home}; add "gifts": true to hearth.json', file=sys.stderr)
        return 2
    if str(args.say or "").strip() and not config.keeper:
        print("error: --say requires a configured keeper", file=sys.stderr)
        return 2

    source = Path(args.file).expanduser().resolve()
    if not source.is_file():
        print(f"error: no such file: {source}", file=sys.stderr)
        return 2
    name = Path(str(args.rename or source.name).strip()).name
    if not name or name in {".", ".."}:
        print("error: the gift needs a safe filename", file=sys.stderr)
        return 2

    given_dir = home / "workshop" / "given"
    given_dir.mkdir(parents=True, exist_ok=True)
    destination = given_dir / name
    if destination.is_symlink():
        print(f"error: refusing to replace symlink: {destination}", file=sys.stderr)
        return 2
    try:
        shutil.copy2(source, destination)
    except (OSError, shutil.SameFileError) as exc:
        print(f"error: could not store gift: {exc}", file=sys.stderr)
        return 2

    timestamp = datetime.now().astimezone().isoformat()
    _append_jsonl(
        home / "given.jsonl",
        {
            "ts": timestamp,
            "file": name,
            "note": str(args.note or "").strip(),
        },
    )
    if str(args.say or "").strip():
        _append_jsonl(
            home / "whispers.jsonl",
            {"ts": timestamp, "text": str(args.say).strip()},
        )

    print(f"gave {home.name} workshop/given/{name} ({destination.stat().st_size} bytes)")
    print("the resident can inspect it through the private gifts source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
