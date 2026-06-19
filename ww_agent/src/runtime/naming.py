# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_MULTI_UNDERSCORE_RE = re.compile(r"_+")
_SEP_RE = re.compile(r"[\s_\-]+")


def slugify_resident_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = _NON_ALNUM_RE.sub("_", normalized.strip().lower())
    slug = _MULTI_UNDERSCORE_RE.sub("_", slug).strip("_")
    if not slug:
        return "resident"
    if not slug[0].isalpha():
        return f"resident_{slug}"
    return slug


def normalize_reference(name: str) -> str:
    """Fold a pen-written reference / display name to a comparable form.

    Lowercase, strip accents, and collapse any run of whitespace / ``_`` / ``-`` to a single
    space. This is what makes the pen's ``"Ji Hoon Park"`` (space) match the roster's
    ``"Ji-Hoon Park"`` (hyphen) without merging the homophone cluster — ``"ji hoon park"``,
    ``"jihoon cho"``, and ``"jiahao chen"`` stay three distinct strings. Used by the runtime
    co-presence / reply-edge match (so directed speech to a co-present peer lands in the room
    instead of mis-routing to the mail path) and by the offline addressing scorer.
    """
    folded = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    return _SEP_RE.sub(" ", folded.strip().lower()).strip()


@dataclass(frozen=True)
class RefResolution:
    """Result of resolving a raw pen reference against a cohort roster.

    ``status`` is the discriminant the verdict scorer keys on — only ``"resolved"`` is safe to
    score; everything else is FLAGGED, not guessed (the standing-brief rule: a name->identity
    resolver must flag ambiguity rather than silently pick, or it corrupts the primary axis).
    """

    status: str  # "resolved" | "weak" | "ambiguous" | "unresolved"
    slug: str | None = None
    candidates: list[str] = field(default_factory=list)


def resolve_reference(raw: str, roster: dict[str, str]) -> RefResolution:
    """Resolve a raw pen reference to a roster identity, FLAGGING ambiguity instead of guessing.

    ``roster`` maps slug -> display name. Resolution order:
      1. unique normalized FULL-name match -> ``resolved`` (covers ~all real data, incl. the
         hyphen/space variant);
      2. unique normalized FIRST-name match -> ``weak`` (a fallback; homophones can still alias,
         so the scorer should exclude/flag, not score it);
      3. multiple candidates by either route -> ``ambiguous`` (e.g. bare "Ari" over three Aris);
      4. nothing -> ``unresolved``.
    """
    q = normalize_reference(raw)
    if not q:
        return RefResolution("unresolved")
    norm = {slug: normalize_reference(disp) for slug, disp in roster.items()}
    full = [slug for slug, n in norm.items() if n == q]
    if len(full) == 1:
        return RefResolution("resolved", full[0])
    if len(full) > 1:
        return RefResolution("ambiguous", candidates=sorted(full))
    first = [slug for slug, n in norm.items() if n.split(" ", 1)[0] == q]
    if len(first) == 1:
        return RefResolution("weak", first[0], candidates=first)
    if len(first) > 1:
        return RefResolution("ambiguous", candidates=sorted(first))
    return RefResolution("unresolved")
