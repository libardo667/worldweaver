#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks
"""add_spdx_headers.py — idempotently stamp SPDX AGPL headers on first-party source.

The repo relicensed MIT -> AGPL-3.0-or-later (2026-06-16). Per-file SPDX headers make each
file's license unambiguous when it travels apart from the repo root, and keep the
non-enclosure commitment (the commons thesis) cold-verifiable file by file.

Scope (first-party source only): worldweaver_engine/src, ww_agent/src,
worldweaver_engine/client/src, and scripts/. Third-party / vendored / generated trees
(node_modules, dist, build, .venv, __pycache__, ...) are never touched. The insert is
shebang- and encoding-cookie-aware, BOM-safe, and idempotent (re-running adds nothing).

    python3 scripts/add_spdx_headers.py            # stamp (idempotent)
    python3 scripts/add_spdx_headers.py --check     # report unstamped, exit 1 if any
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SPDX = "SPDX-License-Identifier: AGPL-3.0-or-later"
COPYRIGHT = "Copyright (C) 2026 Levi Banks"

ROOT = Path(__file__).resolve().parent.parent  # worldweaver/

# (dir relative to ROOT, source suffixes, comment prefix)
SCOPE = [
    ("worldweaver_engine/src", (".py",), "#"),
    ("ww_agent/src", (".py",), "#"),
    ("scripts", (".py",), "#"),
    ("worldweaver_engine/client/src", (".ts", ".tsx"), "//"),
]
# Any path containing one of these parts is third-party / generated and never touched.
EXCLUDE_PARTS = {"node_modules", "dist", "build", ".venv", "venv", "__pycache__", ".next", "coverage", ".git"}

ENCODING_COOKIE = re.compile(r"^#.*coding[:=]")


def iter_files():
    for rel, suffixes, prefix in SCOPE:
        base = ROOT / rel
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix not in suffixes:
                continue
            if EXCLUDE_PARTS & set(p.parts):
                continue
            yield p, prefix


def has_header(text: str) -> bool:
    # Only the first few lines count, so a stray SPDX deeper in a file is not mistaken for the header.
    head = "".join(text.splitlines(keepends=True)[:8])
    return SPDX in head


def stamp(text: str, prefix: str, is_py: bool) -> str:
    """Return text with the SPDX header inserted after any shebang / encoding cookie."""
    bom = ""
    if text.startswith("﻿"):
        bom, text = "﻿", text[1:]

    lines = text.splitlines(keepends=True)
    i = 0
    if i < len(lines) and lines[i].startswith("#!"):
        i += 1
    if is_py and i < len(lines) and ENCODING_COOKIE.match(lines[i]):
        i += 1

    block = f"{prefix} {SPDX}\n{prefix} {COPYRIGHT}\n"
    rest = lines[i:]
    # one blank line between the header and following content, unless content is empty/already blank
    if rest and rest[0].strip() != "":
        block += "\n"
    return bom + "".join(lines[:i]) + block + "".join(rest)


def main() -> int:
    ap = argparse.ArgumentParser(description="Idempotently stamp SPDX AGPL headers on first-party source.")
    ap.add_argument("--check", action="store_true", help="report unstamped files and exit 1 if any; change nothing")
    args = ap.parse_args()

    missing, stamped, already = [], [], 0
    for path, prefix in iter_files():
        text = path.read_text(encoding="utf-8")
        if has_header(text):
            already += 1
            continue
        if args.check:
            missing.append(path)
            continue
        path.write_text(stamp(text, prefix, path.suffix == ".py"), encoding="utf-8")
        stamped.append(path)

    if args.check:
        if missing:
            print(f"✗ {len(missing)} file(s) missing the SPDX header ({already} already stamped):")
            for p in missing:
                print(f"   {p.relative_to(ROOT)}")
            return 1
        print(f"✓ all {already} first-party source files carry the SPDX header.")
        return 0

    print(f"stamped {len(stamped)} file(s); {already} already had the header.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
