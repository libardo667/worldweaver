"""Tests for the substrate port-assistant (scripts/sync_substrate.py).

Hermetic: the routing is a pure function; the 3-way merge and the end-to-end run
use throwaway git repos in tmp_path. See prune/majors/76-*.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "sync_substrate", Path(__file__).resolve().parents[1] / "scripts" / "sync_substrate.py"
)
sync = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sync)


# --- the pure router -------------------------------------------------------

def test_fork_files_are_never_touched():
    for cat in (sync.FORK_WW, sync.FORK_STABLE):
        bucket, content, _ = sync.decide(cat, "ww", "base", "stable", sha="x")
        assert bucket == "skipped-fork"
        assert content is None  # nothing staged


def test_canonical_in_sync_stages_nothing():
    bucket, content, _ = sync.decide(sync.CANONICAL, "same", "old", "same", sha="x")
    assert bucket == "in-sync" and content is None


def test_canonical_applies_when_worldweaver_at_baseline():
    # worldweaver still holds the baseline version → safe fast-forward to the-stable now.
    bucket, content, _ = sync.decide(sync.CANONICAL, "base_ver", "base_ver", "new_ver", sha="x")
    assert bucket == "applied" and content == "new_ver"


def test_canonical_applies_when_absent_on_worldweaver():
    bucket, content, _ = sync.decide(sync.CANONICAL, None, "base", "new_ver", sha="x")
    assert bucket == "applied" and content == "new_ver"


def test_canonical_divergence_is_flagged_not_clobbered():
    # worldweaver changed a canonical file too → flag, 3-way, never blind-overwrite.
    base = "a\nb\nc\n"
    ours = "a\nWW\nc\n"
    theirs = "a\nb\nSTABLE\n"
    bucket, content, detail = sync.decide(sync.CANONICAL, ours, base, theirs, sha="deadbeef")
    assert bucket == "DIVERGED"
    assert "WW" in content and "STABLE" in content  # worldweaver's line preserved
    assert "review" in detail


def test_bidirectional_no_upstream_change():
    bucket, content, _ = sync.decide(sync.BIDIRECTIONAL, "ww", "same", "same", sha="x")
    assert bucket == "no-upstream-change" and content is None


def test_bidirectional_clean_three_way_merge():
    # the-stable changed line b; worldweaver appended its own line → clean merge of both.
    base = "a\nb\nc\n"
    ours = "a\nb\nc\nWW_EXTRA\n"
    theirs = "a\nNEW_B\nc\n"
    bucket, content, _ = sync.decide(sync.BIDIRECTIONAL, ours, base, theirs, sha="x")
    assert bucket == "merged-clean"
    assert "NEW_B" in content and "WW_EXTRA" in content
    assert "<<<<<<<" not in content


def test_bidirectional_conflict_is_marked_and_staged():
    base = "a\nb\nc\n"
    ours = "a\nWW_LINE\nc\n"
    theirs = "a\nSTABLE_LINE\nc\n"  # both edited the same line
    bucket, content, detail = sync.decide(sync.BIDIRECTIONAL, ours, base, theirs, sha="x")
    assert bucket == "CONFLICT"
    assert "<<<<<<<" in content and ">>>>>>>" in content
    assert "conflict" in detail.lower()


# --- the 3.10 fallback parser (must match the real manifest) ----------------

def test_fallback_parser_reads_the_real_manifest():
    text = sync.MANIFEST_PATH.read_text(encoding="utf-8")
    files = sync._parse_files_table(text)
    assert files["src/runtime/salience.py"] == sync.BIDIRECTIONAL
    assert files["src/runtime/ledger.py"] == sync.CANONICAL
    assert files["src/runtime/incubation.py"] == sync.FORK_WW
    assert files["src/runtime/growth.py"] == sync.FORK_STABLE
    assert files["src/runtime/guild.py"] == sync.FORK_STABLE
    assert files["src/runtime/retrieval.py"] == sync.FORK_STABLE
    assert files["src/runtime/source_gate.py"] == sync.CANONICAL
    # inline drift comments must not leak into values
    assert all("#" not in v for v in files.values())


def test_real_manifest_has_only_known_categories():
    files = sync.load_manifest()  # raises/exits on an unknown category
    assert set(files.values()) <= sync.KNOWN_CATEGORIES
    assert len(files) >= 20


def test_manifest_classifies_every_stable_runtime_file_if_present():
    """If the-stable is checked out beside worldweaver, the manifest must cover all
    of its src/runtime/*.py (the UNMANIFESTED guard). Skips when it isn't present."""
    stable = (sync.WORLDWEAVER_ROOT.parent / "the-stable")
    runtime = stable / "src" / "runtime"
    if not runtime.exists():
        pytest.skip("the-stable not checked out beside worldweaver")
    manifest = sync.load_manifest()
    for p in runtime.glob("*.py"):
        rel = p.relative_to(stable).as_posix()
        assert rel in manifest, f"{rel} is unmanifested — classify it"


# --- end-to-end against a throwaway git repo --------------------------------

def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def test_end_to_end_stages_a_merge_without_committing(tmp_path, monkeypatch):
    # build a tiny "the-stable" git repo: base commit, then a runtime change.
    stable = tmp_path / "the-stable"
    (stable / "src" / "runtime").mkdir(parents=True)
    foo = stable / "src" / "runtime" / "foo.py"
    foo.write_text("a\nb\nc\n", encoding="utf-8")
    _git(stable, "init", "-q")
    _git(stable, "config", "user.email", "t@t")
    _git(stable, "config", "user.name", "t")
    _git(stable, "add", "-A")
    _git(stable, "commit", "-qm", "base")
    base_sha = subprocess.run(["git", "-C", str(stable), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    foo.write_text("a\nNEW_B\nc\n", encoding="utf-8")  # the-stable's new change
    _git(stable, "commit", "-qam", "head")

    # a worldweaver tree that diverged elsewhere in the file (clean merge expected).
    ww = tmp_path / "ww_agent"
    (ww / "src" / "runtime").mkdir(parents=True)
    (ww / "src" / "runtime" / "foo.py").write_text("a\nb\nc\nWW_EXTRA\n", encoding="utf-8")

    manifest = tmp_path / "manifest.toml"
    manifest.write_text('[files]\n"src/runtime/foo.py" = "bidirectional"\n', encoding="utf-8")
    baseline = tmp_path / ".baseline"
    baseline.write_text(f'{{"stable_repo": "{stable}", "baseline_sha": "{base_sha}"}}\n', encoding="utf-8")

    monkeypatch.setattr(sync, "WW_AGENT", ww)
    monkeypatch.setattr(sync, "MANIFEST_PATH", manifest)
    monkeypatch.setattr(sync, "BASELINE_PATH", baseline)

    # dry-run writes nothing
    monkeypatch.setattr(sys, "argv", ["sync_substrate.py", "--dry-run"])
    assert sync.main() == 0
    assert "WW_EXTRA" in (ww / "src" / "runtime" / "foo.py").read_text()
    assert "NEW_B" not in (ww / "src" / "runtime" / "foo.py").read_text()

    # real run stages the merged file (both edits present), still no commit/baseline bump
    monkeypatch.setattr(sys, "argv", ["sync_substrate.py"])
    assert sync.main() == 0
    merged = (ww / "src" / "runtime" / "foo.py").read_text()
    assert "NEW_B" in merged and "WW_EXTRA" in merged
    assert '"baseline_sha": "%s"' % base_sha in baseline.read_text()  # unchanged without --accept
