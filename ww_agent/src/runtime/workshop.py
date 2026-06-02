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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_artifact_name(artifact: str) -> str:
    """Reduce an artifact name to a safe, in-workspace markdown filename."""
    raw = str(artifact or "").strip().lower()
    # keep only the final path component, strip anything that isn't word/dash/dot
    raw = raw.replace("\\", "/").split("/")[-1]
    raw = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-.")
    if not raw or raw in {".", ".."}:
        return _DEFAULT_ARTIFACT
    if not raw.endswith(".md"):
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
