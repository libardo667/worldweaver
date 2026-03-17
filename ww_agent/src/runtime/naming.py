from __future__ import annotations

import re
import unicodedata

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_MULTI_UNDERSCORE_RE = re.compile(r"_+")


def slugify_resident_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = _NON_ALNUM_RE.sub("_", normalized.strip().lower())
    slug = _MULTI_UNDERSCORE_RE.sub("_", slug).strip("_")
    if not slug:
        return "resident"
    if not slug[0].isalpha():
        return f"resident_{slug}"
    return slug
