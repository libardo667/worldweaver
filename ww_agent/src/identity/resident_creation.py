# SPDX-License-Identifier: AGPL-3.0-or-later
"""Create a dormant resident home without model-written identity material."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unicodedata
import uuid

from src.identity.hearth_manifest import initialize_hearth_manifest
from src.identity.hearth_permissions import secure_hearth_permissions
from src.identity.resident_identity_custody import (
    initialize_resident_identity_custody,
)
from src.runtime.naming import slugify_resident_name


class ResidentCreationError(ValueError):
    """A new resident home cannot be created safely as requested."""


def validate_display_name(value: str) -> str:
    """Return one plain display name that is safe to place in identity Markdown."""

    name = str(value or "").strip()
    if not name or len(name) > 80:
        raise ResidentCreationError("display name must contain 1 to 80 characters")
    if any(unicodedata.category(character).startswith("C") for character in name):
        raise ResidentCreationError("display name cannot contain control characters")
    if not any(character.isalnum() for character in name):
        raise ResidentCreationError("display name must contain a letter or number")
    if any(not (character.isalnum() or character in " .'-") for character in name):
        raise ResidentCreationError(
            "display name may contain only letters, numbers, spaces, periods, apostrophes, and hyphens"
        )
    return name


def create_dormant_resident(
    residents_dir: Path,
    *,
    display_name: str,
    host_transport_private_key_path: Path,
    entry_location: str = "",
) -> dict[str, str]:
    """Atomically create a minimal, signed, dormant resident hearth.

    Creation writes no ledger event, biography, vocation, voice sample, or model
    output. City admission and hearth activation remain separate operator acts.
    """

    configured_parent = Path(residents_dir)
    if configured_parent.is_symlink():
        raise ResidentCreationError(
            f"residents directory cannot be a symbolic link: {configured_parent}"
        )
    parent = configured_parent.resolve()
    if not parent.is_dir():
        raise ResidentCreationError(f"residents directory is unavailable: {parent}")
    name = validate_display_name(display_name)
    slug = slugify_resident_name(name)
    target = parent / slug
    if target.exists() or target.is_symlink():
        raise ResidentCreationError(f"resident home already exists: {target}")

    location = str(entry_location or "").strip()
    if any(unicodedata.category(character).startswith("C") for character in location):
        raise ResidentCreationError("entry location cannot contain control characters")
    if len(location) > 200:
        raise ResidentCreationError(
            "entry location must contain at most 200 characters"
        )

    temporary = Path(tempfile.mkdtemp(dir=parent, prefix=f".{slug}.create."))
    try:
        identity_dir = temporary / "identity"
        identity_dir.mkdir()
        (temporary / "memory").mkdir()
        (temporary / "workshop").mkdir()

        actor_id = str(uuid.uuid4())
        canonical = f"Your name is {name}.\n"
        (identity_dir / "resident_id.txt").write_text(f"{actor_id}\n", encoding="utf-8")
        (identity_dir / "display_name.txt").write_text(f"{name}\n", encoding="utf-8")
        (identity_dir / "SOUL.canonical.md").write_text(canonical, encoding="utf-8")
        (identity_dir / "SOUL.md").write_text(canonical, encoding="utf-8")
        if location:
            (identity_dir / "entry_location.txt").write_text(
                f"{location}\n", encoding="utf-8"
            )
        (temporary / "hearth.json").write_text(
            json.dumps({"place": "the hearth"}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        manifest = initialize_hearth_manifest(temporary)
        descriptor = initialize_resident_identity_custody(
            temporary,
            host_transport_private_key_path=host_transport_private_key_path,
        )
        secure_hearth_permissions(temporary)
        temporary.replace(target)
        return {
            "resident": slug,
            "display_name": name,
            "actor_id": actor_id,
            "hearth_shard_id": manifest.hearth_shard_id,
            "identity_key_id": descriptor.identity_key_id,
            "home": str(target),
            "identity_card": str(target / "identity" / "resident_identity.json"),
            "state": "dormant",
            "entry_location": location,
        }
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
