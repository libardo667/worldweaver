# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""FileScope: a read-only, capability-scoped view of the filesystem (Major 50).

The workshop is the resident's write capability — structurally one directory it
cannot escape. This is the read capability, the same idea inverted: an agent may
*read* files, but only inside declared roots, and never anything an ignore rule
hides. Two structural guards, both enforced in code, not asked of the prompt:

1. **Roots.** Every path is resolved and checked to live inside an allowed root;
   anything that would escape (``..`` traversal, an absolute path elsewhere) is
   refused. Like the workshop's boundary, in reverse.
2. **Ignore.** What the agent can see — and therefore what reaches the LLM that
   runs its mind — is filtered by gitignore semantics (pathspec): the roots' own
   ``.gitignore`` and an optional ``.familiarignore``, *plus* a hard default-deny
   for secrets (``.env``, keys, ``.ssh``…) that applies no matter what. Refusing
   to *read* an ignored file is the enforcement; its bytes never enter a prompt.

There are no write methods here, by construction. Writing remains the workshop's
job alone.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pathspec

# A hard floor under whatever .gitignore says — secrets are never readable even if
# a project forgot to ignore them. Over-broad on purpose (hiding a doc about
# passwords is fine; leaking a key is not).
_DEFAULT_DENY = [
    ".env",
    "*.env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.pfx",
    "*.p12",
    "*.keystore",
    "*.jks",
    "*.ppk",
    "id_rsa*",
    "id_dsa*",
    "id_ecdsa*",
    "id_ed25519*",
    ".netrc",
    ".npmrc",
    ".pypirc",
    ".pgpass",
    "*.secret",
    "*secret*",
    "*credential*",
    "*password*",
    "*.token",
    ".ssh/",
    ".aws/",
    ".gnupg/",
    ".git/",
    "node_modules/",
    "__pycache__/",
    ".venv/",
    "venv/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
]

_IGNORE_FILES = (".gitignore", ".familiarignore")
_MAX_READ_BYTES = 40_000
_MAX_MEDIA_BYTES = 20_000_000
_BINARY_SNIFF = 2048


class FileScope:
    """A read-only window onto the filesystem, scoped to roots and filtered by
    gitignore-style ignore rules (plus a hard secret default-deny)."""

    def __init__(self, *, read_roots: list[Any], extra_ignore: list[str] = ()) -> None:
        self.roots: list[Path] = []
        self._specs: dict[Path, pathspec.PathSpec] = {}
        for raw in read_roots:
            root = Path(os.path.expanduser(str(raw))).resolve()
            if not (root.exists() and root.is_dir()):
                continue
            self.roots.append(root)
            lines = list(_DEFAULT_DENY) + list(extra_ignore)
            for name in _IGNORE_FILES:
                f = root / name
                if f.exists():
                    try:
                        lines += f.read_text(
                            encoding="utf-8", errors="ignore"
                        ).splitlines()
                    except OSError:
                        pass
            self._specs[root] = pathspec.PathSpec.from_lines("gitignore", lines)

    # --- the two structural guards --------------------------------------

    def _root_of(self, resolved: Path) -> Path | None:
        for root in self.roots:
            if resolved == root or root in resolved.parents:
                return root
        return None

    def _resolve(self, path: Any) -> tuple[Path | None, Path | None]:
        """Resolve a path to a real location inside a root, or (None, None).

        A bare name may match in more than one root; prefer a candidate that
        actually exists (so a file in the drop-folder isn't shadowed by a
        non-existent path in the first root), falling back to the first in-root
        candidate so a genuinely missing file still reports not_found, not escape.
        """
        raw = str(path or "").strip()
        candidates: list[Path] = []
        if os.path.isabs(raw):
            candidates.append(Path(raw))
        # Root-qualified ("<root-name>/rest"): when several roots are open, the first
        # segment may name the root and the remainder is relative to it. Tried first so
        # a qualified path is unambiguous; a bare path still falls through to the scan.
        head, _, tail = raw.partition("/")
        if head and not os.path.isabs(raw):
            for root in self.roots:
                if root.name == head:
                    candidates.append(root / tail if tail else root)
        for root in self.roots:
            candidates.append(root / raw)
        fallback: tuple[Path, Path] | None = None
        for cand in candidates:
            try:
                resolved = cand.resolve()
            except (OSError, RuntimeError):
                continue
            root = self._root_of(resolved)
            if root is None:
                continue
            if resolved.exists():
                return resolved, root
            if fallback is None:
                fallback = (resolved, root)
        return fallback if fallback is not None else (None, None)

    def _ignored(self, resolved: Path, root: Path) -> bool:
        rel = resolved.relative_to(root).as_posix()
        if not rel or rel == ".":
            return False
        spec = self._specs.get(root)
        if spec is None:
            return False
        # match the path itself (also with a trailing slash so directory-only
        # patterns like "node_modules/" hide the directory, not just its contents)
        if spec.match_file(rel) or spec.match_file(rel + "/"):
            return True
        # a path is hidden if any ancestor directory is ignored
        parts = rel.split("/")
        return any(
            spec.match_file("/".join(parts[:i]) + "/") for i in range(1, len(parts))
        )

    def _display(self, resolved: Path, root: Path) -> str:
        """How a path is shown and typed. With one root it's relative to that root;
        with several it is root-qualified ("skein/workshop/journal.md") so the name
        is unambiguous and round-trips back through ``_resolve``."""
        rel = resolved.relative_to(root).as_posix()
        if len(self.roots) > 1:
            return f"{root.name}/{rel}" if rel and rel != "." else root.name
        return rel

    # --- read-only surface ----------------------------------------------

    def read(
        self,
        path: Any,
        *,
        offset: int = 0,
        max_bytes: int = _MAX_READ_BYTES,
    ) -> dict[str, Any]:
        """Read one bounded byte window from an allowed text file."""
        resolved, root = self._resolve(path)
        if resolved is None or root is None:
            return {"ok": False, "reason": "outside_scope"}
        if not resolved.exists():
            return {"ok": False, "reason": "not_found"}
        if not resolved.is_file():
            return {"ok": False, "reason": "not_a_file"}
        if self._ignored(resolved, root):
            return {"ok": False, "reason": "ignored"}
        try:
            data = resolved.read_bytes()
        except OSError:
            return {"ok": False, "reason": "unreadable"}
        if b"\x00" in data[:_BINARY_SNIFF]:
            return {"ok": False, "reason": "binary"}
        offset = max(0, min(int(offset), len(data)))
        window = data[offset : offset + max_bytes]
        text = window.decode("utf-8", errors="replace")
        return {
            "ok": True,
            "path": self._display(resolved, root),
            "root": root.name,
            "content": text,
            "offset": offset,
            "bytes_total": len(data),
            "truncated": offset + len(window) < len(data),
        }

    def read_media(self, path: Any) -> dict[str, Any]:
        """Read bounded image/PDF bytes after applying the normal scope guards."""
        from . import visual

        resolved, root = self._resolve(path)
        if resolved is None or root is None:
            return {"ok": False, "reason": "outside_scope"}
        if not resolved.exists():
            return {"ok": False, "reason": "not_found"}
        if not resolved.is_file():
            return {"ok": False, "reason": "not_a_file"}
        if self._ignored(resolved, root):
            return {"ok": False, "reason": "ignored"}
        try:
            size = resolved.stat().st_size
        except OSError:
            return {"ok": False, "reason": "unreadable"}
        if size > _MAX_MEDIA_BYTES:
            return {"ok": False, "reason": "too_large", "bytes_total": size}
        try:
            data = resolved.read_bytes()
        except OSError:
            return {"ok": False, "reason": "unreadable"}
        kind = visual.kind_of(resolved.name, data)
        if kind is None:
            return {"ok": False, "reason": "not_visual"}
        return {
            "ok": True,
            "path": self._display(resolved, root),
            "root": root.name,
            "kind": kind,
            "data": data,
            "bytes_total": len(data),
        }

    def listdir(self, subpath: Any = "") -> dict[str, Any]:
        """List the (non-ignored) entries of a directory inside a root."""
        resolved, root = self._resolve(subpath or (self.roots[0] if self.roots else ""))
        if resolved is None or root is None or not resolved.is_dir():
            return {
                "ok": False,
                "reason": "outside_scope" if resolved is None else "not_a_dir",
            }
        entries: list[dict[str, Any]] = []
        try:
            children = sorted(
                resolved.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except OSError:
            return {"ok": False, "reason": "unreadable"}
        for child in children:
            if self._ignored(child, root):
                continue
            try:
                size = child.stat().st_size if child.is_file() else None
            except OSError:
                size = None
            entries.append({"name": child.name, "is_dir": child.is_dir(), "size": size})
        return {
            "ok": True,
            "path": self._display(resolved, root) or ".",
            "root": root.name,
            "entries": entries,
        }

    def find_by_name(
        self,
        name: Any,
        *,
        limit: int = 4,
        max_scan: int = 3000,
    ) -> list[str]:
        """Find a few allowed files with the requested basename, without leaving the roots."""
        wanted = os.path.basename(str(name or "").strip().rstrip("/")).lower()
        if not wanted:
            return []
        matches: list[str] = []
        scanned = 0
        for root in self.roots:
            stack = [root]
            while stack and len(matches) < limit and scanned < max_scan:
                directory = stack.pop()
                try:
                    children = list(directory.iterdir())
                except OSError:
                    continue
                for child in children:
                    scanned += 1
                    if self._ignored(child, root):
                        continue
                    if child.is_dir():
                        stack.append(child)
                    elif child.name.lower() == wanted:
                        matches.append(self._display(child, root))
                        if len(matches) >= limit:
                            break
        return matches

    def tree(
        self, subpath: Any = "", *, max_depth: int = 2, max_entries: int = 120
    ) -> list[str]:
        """A flat, scoped listing of relative paths (dirs marked with a trailing
        slash), for the agent to get its bearings. Ignored paths never appear."""
        out: list[str] = []
        roots = [self._resolve(subpath)[0]] if subpath else list(self.roots)
        # When showing several roots at once, qualify every entry with its root name
        # so the listing is legible and each path round-trips through read(). A scoped
        # call (subpath given) stays relative — the caller already knows the root.
        qualify = len(self.roots) > 1 and not subpath
        for start in roots:
            if start is None:
                continue
            base = self._root_of(start)
            if base is None:
                continue
            stack = [(start, 0)]
            while stack and len(out) < max_entries:
                d, depth = stack.pop()
                try:
                    children = sorted(
                        d.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
                    )
                except OSError:
                    continue
                for child in children:
                    if len(out) >= max_entries or self._ignored(child, base):
                        continue
                    rel = child.relative_to(base).as_posix()
                    if qualify:
                        rel = f"{base.name}/{rel}"
                    out.append(rel + "/" if child.is_dir() else rel)
                    if child.is_dir() and depth + 1 < max_depth:
                        stack.append((child, depth + 1))
        return sorted(out)
