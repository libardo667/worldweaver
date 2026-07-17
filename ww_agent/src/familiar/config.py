# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Optional capabilities attached to one resident's private hearth.

Every resident has a hearth. This file describes only the extra things a particular
hearth has been granted: a keeper relationship, local weather, read-only file roots,
and visual perception. Absence means a private home with none of those grants.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HearthConfig:
    """Concrete, optional grants for one resident's hearth."""

    place: str = "the hearth"
    keeper: str = ""
    read_roots: tuple[Path, ...] = ()
    weather: bool = False
    vision: bool = False
    source_path: Path | None = None

    @classmethod
    def load(cls, resident_dir: Path) -> "HearthConfig":
        """Load ``hearth.json``, with ``familiar.json`` as a temporary compatibility name."""
        home = Path(resident_dir).resolve()
        canonical = home / "hearth.json"
        legacy = home / "familiar.json"
        path = canonical if canonical.exists() else legacy if legacy.exists() else None
        if path is None:
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("could not read hearth config %s: %s", path, exc)
            return cls(source_path=path)
        if not isinstance(raw, dict):
            logger.warning("hearth config %s must contain a JSON object", path)
            return cls(source_path=path)
        return cls.from_mapping(raw, resident_dir=home, source_path=path)

    @classmethod
    def from_mapping(
        cls,
        raw: dict[str, Any],
        *,
        resident_dir: Path,
        source_path: Path | None = None,
    ) -> "HearthConfig":
        roots: list[Path] = []
        configured_roots = raw.get("read_roots") or []
        if isinstance(configured_roots, (str, os.PathLike)):
            configured_roots = [configured_roots]
        for configured in configured_roots if isinstance(configured_roots, list) else []:
            expanded = Path(os.path.expanduser(str(configured)))
            root = expanded if expanded.is_absolute() else Path(resident_dir) / expanded
            resolved = root.resolve()
            if resolved.exists() and resolved.is_dir() and resolved not in roots:
                roots.append(resolved)
        return cls(
            place=str(raw.get("place") or "the hearth").strip() or "the hearth",
            keeper=str(raw.get("keeper") or "").strip(),
            read_roots=tuple(roots),
            weather=bool(raw.get("weather", False)),
            vision=bool(raw.get("vision", False)),
            source_path=source_path,
        )
