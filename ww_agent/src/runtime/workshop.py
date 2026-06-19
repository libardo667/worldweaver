# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""The workshop: a resident's own, capability-scoped place to make things (Major 50).

A resident's life leaves a durable artifact of its own making — a journal, a zine,
a notebook, eventually a small project — instead of evaporating into felt-sense
readouts. The workshop is the first brick: a real directory the resident owns and
authors into across its whole life, so a piece of work can *continue* across
pulses rather than restart.

The safety primitive is structural, not a promise in a prompt: the workshop is
constructed with one directory and **cannot** write outside it. Artifact names are
sanitized and the resolved path is checked to stay inside the workspace; anything
that would escape is refused. Output a resident owns is the safe, ethical place to
begin — not someone else's commons. ``who it is`` is the constitution gate's job;
``what it can touch`` is this.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DEFAULT_ARTIFACT = "journal.md"
_ENTRY_HEADER = re.compile(r"^## (.+)$", re.MULTILINE)
# Media a resident may author. Prose appends as dated entries; an .svg is a whole
# picture (a versioned file, not an appended entry) — for residents who would
# rather draw than write.
_ALLOWED_EXT = (".md", ".svg", ".txt")
_SVG_TITLE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_SERIES_INDEX = re.compile(r"-(\d+)$")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _safe_artifact_name(artifact: str) -> str:
    """Reduce an artifact name to a safe, in-workspace filename (defaults to .md)."""
    raw = str(artifact or "").strip().lower()
    # keep only the final path component, strip anything that isn't word/dash/dot
    raw = raw.replace("\\", "/").split("/")[-1]
    raw = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-.")
    if not raw or raw in {".", ".."}:
        return _DEFAULT_ARTIFACT
    if not raw.endswith(_ALLOWED_EXT):
        raw = raw + ".md"
    return raw


class Workshop:
    """One resident's own, sandboxed artifact store."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _resolve(self, artifact: str) -> Path | None:
        """Resolve an artifact to a path *inside* the workspace, or None if it
        would escape (the structural capability boundary)."""
        name = _safe_artifact_name(artifact)
        try:
            root = self._root.resolve()
            path = (self._root / name).resolve()
        except Exception:
            return None
        if path != root and root not in path.parents:
            return None
        return path

    def append(self, body: str, *, artifact: str = _DEFAULT_ARTIFACT, title: str = "") -> dict[str, Any]:
        """Append a titled, dated entry to an artifact the resident owns."""
        text = str(body or "").strip()
        if not text:
            return {"written": False, "reason": "empty"}
        path = self._resolve(artifact)
        if path is None:
            return {"written": False, "reason": "outside_workspace"}
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = _utc_now_iso()
        heading = f"## {ts}" + (f" — {str(title).strip()}" if str(title).strip() else "")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n{heading}\n\n{text}\n")
        return {"written": True, "artifact": path.name, "title": str(title).strip(), "ts": ts}

    def artifacts(self) -> list[str]:
        if not self._root.exists():
            return []
        return sorted(p.name for p in self._root.glob("*.md") if p.is_file())

    def draw(self, svg: str, *, base: str = "weave") -> dict[str, Any]:
        """Save a discrete visual piece (an SVG) as a new versioned file. Drawings
        are whole works, not appended entries — each is its own picture, kept in a
        numbered series (weave-001.svg, weave-002.svg, …) so a body of work grows."""
        content = str(svg or "").strip()
        if not content.startswith("<svg"):
            return {"written": False, "reason": "not_svg"}
        self._root.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^a-z0-9_-]+", "-", str(base or "weave").strip().lower()).strip("-.") or "weave"
        idx = 0
        for existing in self._root.glob(f"{stem}-*.svg"):
            match = _SERIES_INDEX.search(existing.stem)
            if match:
                idx = max(idx, int(match.group(1)))
        name = f"{stem}-{idx + 1:03d}.svg"
        path = self._resolve(name)
        if path is None:
            return {"written": False, "reason": "outside_workspace"}
        path.write_text(content[:20000], encoding="utf-8")
        title = _SVG_TITLE.search(content).group(1).strip() if _SVG_TITLE.search(content) else ""
        return {"written": True, "artifact": name, "title": title, "ts": _utc_now_iso()}

    def drawings(self, *, limit: int = 6) -> list[dict[str, Any]]:
        """The most recent visual pieces with their full SVG, for a portrait to
        render (kept out of the prompt — markup is verbose and the model can't see
        it rendered anyway)."""
        if not self._root.exists():
            return []
        out: list[dict[str, Any]] = []
        for path in sorted(self._root.glob("*.svg"), key=lambda p: p.stat().st_mtime)[-max(1, limit) :]:
            try:
                svg = path.read_text(encoding="utf-8")
            except OSError:
                continue
            title = _SVG_TITLE.search(svg)
            out.append({"artifact": path.name, "title": title.group(1).strip() if title else "", "svg": svg[:20000], "ts": _mtime_iso(path)})
        return out

    def summary(self) -> list[dict[str, Any]]:
        """A glance at everything in the workshop — each artifact, how many entries,
        and its most recent — so the resident is aware of all its ongoing work and
        can carry a zine or project across days, not just its last journal page."""
        out: list[dict[str, Any]] = []
        for name in self.artifacts():
            path = self._resolve(name)
            count = 0
            if path is not None and path.exists():
                try:
                    count = len(_ENTRY_HEADER.findall(path.read_text(encoding="utf-8")))
                except Exception:
                    count = 0
            last = (self.recent(1, artifact=name) or [{}])[-1]
            out.append(
                {
                    "artifact": name,
                    "name": name[:-3] if name.endswith(".md") else name,
                    "kind": "text",
                    "count": count,
                    "last_ts": last.get("ts", ""),
                    "last_title": last.get("title", ""),
                    "last_excerpt": str(last.get("body", "") or "").strip(),
                }
            )

        # Drawing series (.svg), grouped by base stem — count + title only, no
        # markup (the prompt stays cheap; the portrait reads full SVG via drawings()).
        if self._root.exists():
            series: dict[str, list[Path]] = {}
            for path in sorted(self._root.glob("*.svg"), key=lambda p: p.stat().st_mtime):
                stem = _SERIES_INDEX.sub("", path.stem)
                series.setdefault(stem, []).append(path)
            for stem, files in series.items():
                title = ""
                try:
                    found = _SVG_TITLE.search(files[-1].read_text(encoding="utf-8"))
                    title = found.group(1).strip() if found else ""
                except OSError:
                    pass
                out.append(
                    {
                        "artifact": stem,
                        "name": stem,
                        "kind": "drawing",
                        "count": len(files),
                        "last_ts": _mtime_iso(files[-1]),
                        "last_title": title,
                        "last_excerpt": title or "a woven piece",
                    }
                )
        return out

    def recent(self, n: int = 3, *, artifact: str = _DEFAULT_ARTIFACT) -> list[dict[str, Any]]:
        """The resident's most recent entries, so it can continue its own work."""
        path = self._resolve(artifact)
        if path is None or not path.exists():
            return []
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            return []
        entries: list[dict[str, Any]] = []
        matches = list(_ENTRY_HEADER.finditer(content))
        for idx, match in enumerate(matches):
            head = match.group(1).strip()
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            body = content[start:end].strip()
            ts, _, title = head.partition(" — ")
            entries.append({"ts": ts.strip(), "title": title.strip(), "body": body})
        return entries[-max(1, n) :]
