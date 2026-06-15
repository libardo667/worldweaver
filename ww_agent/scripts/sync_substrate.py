#!/usr/bin/env python3
"""sync_substrate.py — a baseline-pinned port-assistant: the-stable → ww_agent.

The agent substrate is forked across two live trees (see prune/majors/76-*):
``the-stable/src/runtime/`` (where small changes + per-resident observation happen
first) and ``ww_agent/src/runtime/`` (the city runtime, scaled testing). Matured
cognitive pieces flow the-stable → here. The drift is *bidirectional* (the-stable
leads on cognition; worldweaver leads on world-integration + scale), so a blind
copy would clobber worldweaver-only work.

This tool is one-way and **never commits**. It pins the the-stable SHA of the last
sync (``.substrate_sync_baseline``), so each run isolates *only the-stable's new
changes since then* and routes each file by the manifest:

  canonical-stable : the-stable is source of truth — apply its current version
                     (and loudly flag if worldweaver has diverged on it anyway).
  bidirectional    : both forks evolve it — 3-way merge (base = the-stable@baseline,
                     ours = ww_agent now, theirs = the-stable@HEAD) via git merge-file.
  fork-worldweaver : worldweaver-only — never touched.
  fork-stable      : the-stable-only — not ported.

Changes are *staged into the working tree* (or just reported with --dry-run) for
human review + quality-strict. The baseline advances only with --accept, and only
when nothing is left in conflict.

Usage:
  python scripts/sync_substrate.py --dry-run          # report only (default-safe)
  python scripts/sync_substrate.py                    # stage clean changes for review
  python scripts/sync_substrate.py --only src/runtime/salience.py
  python scripts/sync_substrate.py --accept           # stage, then advance the baseline
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - exercised only on 3.10
    tomllib = None

HERE = Path(__file__).resolve().parent          # ww_agent/scripts
WW_AGENT = HERE.parent                           # ww_agent/
WORLDWEAVER_ROOT = WW_AGENT.parent               # worldweaver/
MANIFEST_PATH = HERE / "substrate_sync_manifest.toml"
BASELINE_PATH = HERE / ".substrate_sync_baseline"

CANONICAL = "canonical-stable"
BIDIRECTIONAL = "bidirectional"
FORK_WW = "fork-worldweaver"
FORK_STABLE = "fork-stable"
KNOWN_CATEGORIES = {CANONICAL, BIDIRECTIONAL, FORK_WW, FORK_STABLE}

# The one tree scanned for unmanifested files (the manifest must cover all of it).
SCAN_DIR = "src/runtime"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _show(repo: Path, sha: str, relpath: str) -> str | None:
    """File content at a revision, or None if it didn't exist there."""
    r = _git(repo, "show", f"{sha}:{relpath}")
    return r.stdout if r.returncode == 0 else None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError):
        return None


def _parse_files_table(text: str) -> dict[str, str]:
    """Minimal parser for THIS manifest's ``[files]`` table (``"path" = "value"``).

    Used only when tomllib is unavailable (Python < 3.11). The format is fully
    controlled here and kept deliberately trivial; the test-suite loads the real
    manifest through this path, so any drift in format is caught.
    """
    files: dict[str, str] = {}
    in_files = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_files = line == "[files]"
            continue
        if not in_files:
            continue
        line = line.split("#", 1)[0].strip()  # our keys/values never contain '#'
        m = re.match(r'^"([^"]+)"\s*=\s*"([^"]+)"\s*$', line)
        if m:
            files[m.group(1)] = m.group(2)
    return files


def load_manifest() -> dict[str, str]:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    files = tomllib.loads(text).get("files", {}) if tomllib is not None else _parse_files_table(text)
    bad = {k: v for k, v in files.items() if v not in KNOWN_CATEGORIES}
    if bad:
        sys.exit(f"manifest has unknown categories: {bad}\nknown: {sorted(KNOWN_CATEGORIES)}")
    return files


def load_baseline() -> dict:
    if BASELINE_PATH.exists():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {}


def save_baseline(data: dict) -> None:
    BASELINE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def merge_file(ours: str, base: str, theirs: str, *, sha: str) -> tuple[str, int]:
    """3-way merge via ``git merge-file``. Returns (content, conflict_count).

    conflict_count: 0 = clean, >0 = number of conflict hunks (markers in content).
    """
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        f_ours, f_base, f_theirs = td_path / "ours", td_path / "base", td_path / "theirs"
        f_ours.write_text(ours, encoding="utf-8")
        f_base.write_text(base, encoding="utf-8")
        f_theirs.write_text(theirs, encoding="utf-8")
        r = subprocess.run(
            [
                "git", "merge-file", "-p",
                "-L", "ww_agent (ours)", "-L", f"the-stable @ baseline {sha[:9]}", "-L", "the-stable (incoming)",
                str(f_ours), str(f_base), str(f_theirs),
            ],
            capture_output=True, text=True,
        )
        # merge-file returns the conflict count (>=0) or a negative value on error.
        if r.returncode < 0 or r.returncode > 127:
            raise RuntimeError(f"git merge-file failed: {r.stderr.strip()}")
        return r.stdout, r.returncode


def decide(category: str, ww_now: str | None, stable_base: str | None, stable_now: str | None, *, sha: str) -> tuple[str, str | None, str]:
    """Pure routing for one file. Returns (bucket, content_to_stage_or_None, detail).

    ``content_to_stage_or_None`` is what the caller should write into the worldweaver
    tree; None means "leave worldweaver untouched."
    """
    if category in (FORK_WW, FORK_STABLE):
        return ("skipped-fork", None, f"[{category}]")
    if stable_now is None:
        return ("missing", None, "(absent in the-stable)")

    if category == CANONICAL:
        if ww_now == stable_now:
            return ("in-sync", None, "")
        if ww_now is None or ww_now == stable_base:
            # worldweaver has not diverged from the pinned baseline → safe to apply.
            return ("applied", stable_now, "")
        # manifest says canonical, but worldweaver changed it too → 3-way, don't clobber, flag.
        merged, conflicts = merge_file(ww_now, stable_base or "", stable_now, sha=sha)
        return ("DIVERGED", merged, f"(canonical, but worldweaver diverged — {conflicts} conflict(s); review + fix manifest)")

    # bidirectional
    if stable_base == stable_now:
        return ("no-upstream-change", None, "")
    if ww_now == stable_now:
        return ("in-sync", None, "")
    if ww_now is None:
        return ("applied", stable_now, "(new on the worldweaver side)")
    merged, conflicts = merge_file(ww_now, stable_base or "", stable_now, sha=sha)
    if conflicts:
        return ("CONFLICT", merged, f"({conflicts} conflict hunk(s) — markers staged for review)")
    return ("merged-clean", merged, "")


def resolve_stable(baseline: dict, cli_path: str | None) -> Path:
    raw = cli_path or baseline.get("stable_repo") or "../the-stable"
    p = Path(raw)
    if not p.is_absolute():
        p = (WORLDWEAVER_ROOT / p).resolve()
    if not (p / ".git").exists():
        sys.exit(f"the-stable repo not found / not a git repo at: {p}")
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description="Port-assistant: the-stable → ww_agent substrate.")
    ap.add_argument("--stable", help="path to the-stable repo (default: ../the-stable or baseline)")
    ap.add_argument("--dry-run", action="store_true", help="report only; stage nothing")
    ap.add_argument("--accept", action="store_true", help="after staging, advance the baseline to the-stable HEAD")
    ap.add_argument("--only", action="append", default=[], help="limit to these relpaths (repeatable)")
    ap.add_argument("--allow-dirty", action="store_true", help="proceed even if the-stable scope is dirty (unsafe)")
    args = ap.parse_args()

    manifest = load_manifest()
    baseline = load_baseline()
    stable = resolve_stable(baseline, args.stable)
    base_sha = baseline.get("baseline_sha")
    if not base_sha:
        sys.exit(
            "no baseline pinned. Set one in .substrate_sync_baseline, e.g.:\n"
            '  {"stable_repo": "../the-stable", "baseline_sha": "<sha>"}'
        )
    if _git(stable, "cat-file", "-e", base_sha).returncode != 0:
        sys.exit(f"baseline_sha {base_sha} not found in {stable}")

    head_sha = _git(stable, "rev-parse", "HEAD").stdout.strip()

    scoped = [r for r in manifest if r in args.only] if args.only else list(manifest)

    # Baseline integrity: refuse on a dirty the-stable scope (working ≠ HEAD would
    # make "the-stable now" ambiguous against the pinned baseline).
    dirty = _git(stable, "status", "--porcelain", "--", *[r for r in scoped]).stdout.strip()
    if dirty and not args.allow_dirty:
        print("the-stable has uncommitted changes in scope — refusing (use --allow-dirty to override):")
        print(dirty)
        return 2

    buckets: dict[str, list[str]] = {k: [] for k in (
        "in-sync", "applied", "merged-clean", "CONFLICT", "DIVERGED", "no-upstream-change",
        "skipped-fork", "missing", "UNMANIFESTED",
    )}
    staged: list[tuple[str, str]] = []  # (relpath, content)

    for rel in scoped:
        ww_now = _read(WW_AGENT / rel)
        stable_now = _read(stable / rel)  # working == HEAD (clean tree guaranteed above)
        stable_base = _show(stable, base_sha, rel)
        bucket, content, detail = decide(manifest[rel], ww_now, stable_base, stable_now, sha=base_sha)
        buckets[bucket].append(f"{rel}  {detail}".rstrip())
        if content is not None:
            staged.append((rel, content))

    # Unmanifested scan: every .py under the-stable's SCAN_DIR must be classified.
    if not args.only:
        for p in sorted((stable / SCAN_DIR).glob("*.py")):
            rel = p.relative_to(stable).as_posix()
            if rel not in manifest:
                buckets["UNMANIFESTED"].append(f"{rel}  (new in the-stable — classify it in the manifest)")

    # ---- write staged changes (unless dry-run) ----
    wrote = 0
    if not args.dry_run:
        for rel, content in staged:
            dest = WW_AGENT / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            wrote += 1

    # ---- report ----
    print(f"\n  the-stable: {stable}")
    print(f"  baseline:   {base_sha[:9]}   →   HEAD: {head_sha[:9]}")
    print(f"  mode:       {'DRY-RUN (nothing written)' if args.dry_run else f'staged {wrote} file(s) into the working tree'}\n")
    order = ["applied", "merged-clean", "in-sync", "no-upstream-change", "skipped-fork",
             "CONFLICT", "DIVERGED", "UNMANIFESTED", "missing"]
    for key in order:
        items = buckets[key]
        if not items:
            continue
        print(f"  {key}  ({len(items)})")
        for it in items:
            print(f"      • {it}")
        print()

    unresolved = buckets["CONFLICT"] + buckets["DIVERGED"] + buckets["UNMANIFESTED"]
    if unresolved:
        print("  ⚠ review the items above. Conflicts carry <<<<<<< markers; nothing was committed.")
    else:
        print("  ✓ no conflicts. Review the staged diff with `git diff`, then run quality-strict.")

    if args.accept:
        if args.dry_run:
            print("\n  --accept ignored under --dry-run.")
        elif unresolved:
            print("\n  --accept refused: resolve conflicts / unmanifested files first, then re-run with --accept.")
        else:
            from datetime import date
            baseline.update({"stable_repo": baseline.get("stable_repo", "../the-stable"),
                             "baseline_sha": head_sha, "last_synced": date.today().isoformat()})
            save_baseline(baseline)
            print(f"\n  baseline advanced → {head_sha[:9]}  (commit the staged changes + the baseline together)")

    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
