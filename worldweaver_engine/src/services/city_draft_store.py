# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Node-local city drafts kept apart from published city packs."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .city_pack_builder import BuiltCityPack, assemble_city_pack
from .map_generation import edit_section, section_preview_svg

_DRAFT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
DEFAULT_CITY_DRAFTS_DIR = Path(__file__).resolve().parents[2] / "data" / "city_drafts"


@dataclass(frozen=True)
class CityDraft:
    draft_id: str
    metadata: dict[str, Any]
    source: dict[str, Any]
    preview: BuiltCityPack


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class CityDraftStore:
    """Save validated city drafts without reading or writing published packs."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def _draft_path(self, draft_id: str) -> Path:
        if not _DRAFT_ID.fullmatch(draft_id):
            raise ValueError("draft ID must use lowercase letters, numbers, hyphens, or underscores")
        return self.root / draft_id

    def list(self) -> tuple[dict[str, Any], ...]:
        if not self.root.exists():
            return ()
        result: list[dict[str, Any]] = []
        for path in sorted(self.root.iterdir()):
            if path.is_symlink() or not path.is_dir() or not _DRAFT_ID.fullmatch(path.name):
                continue
            metadata_path = path / "draft.json"
            if metadata_path.exists():
                result.append(self._read_json(metadata_path))
        return tuple(result)

    def create(
        self,
        source: Mapping[str, Any],
        *,
        draft_id: str | None = None,
        now: str | None = None,
    ) -> CityDraft:
        copied_source = copy.deepcopy(dict(source))
        city_id = str(copied_source.get("city_id") or "").strip()
        chosen_id = draft_id or city_id
        target = self._draft_path(chosen_id)
        if target.exists():
            raise FileExistsError(f"city draft already exists: {chosen_id}")
        timestamp = now or _utc_now()
        metadata = {
            "schema": "worldweaver.city-draft",
            "schema_version": 1,
            "draft_id": chosen_id,
            "city_id": city_id,
            "draft_revision": 0,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        return self._save(target, metadata=metadata, source=copied_source)

    def get(self, draft_id: str) -> CityDraft:
        target = self._draft_path(draft_id)
        if target.is_symlink():
            raise ValueError(f"city draft cannot be a symbolic link: {draft_id}")
        if not target.is_dir():
            raise FileNotFoundError(f"city draft not found: {draft_id}")
        metadata = self._read_json(target / "draft.json")
        source = self._read_json(target / "source.json")
        if (
            metadata.get("schema") != "worldweaver.city-draft"
            or metadata.get("schema_version") != 1
            or metadata.get("draft_id") != draft_id
            or metadata.get("city_id") != source.get("city_id")
            or not isinstance(metadata.get("draft_revision"), int)
            or isinstance(metadata.get("draft_revision"), bool)
            or int(metadata["draft_revision"]) < 0
            or not str(metadata.get("updated_at") or "").strip()
        ):
            raise ValueError(f"city draft metadata is invalid: {draft_id}")
        preview = assemble_city_pack(source, built_at=str(metadata["updated_at"]))
        self._assert_preview_matches(target, preview)
        expected_artifact_hash = str((preview.files.get("generated_map.json") or {}).get("artifact_sha256", ""))
        if metadata.get("valid") is not preview.validation.valid or metadata.get("pack_version") != preview.files["manifest.json"]["version"] or metadata.get("artifact_sha256") != expected_artifact_hash:
            raise ValueError(f"city draft metadata is stale: {draft_id}")
        return CityDraft(
            draft_id=draft_id,
            metadata=metadata,
            source=source,
            preview=preview,
        )

    def edit_section(
        self,
        draft_id: str,
        *,
        section_id: str,
        action: str,
        expected_revision: int | None = None,
        now: str | None = None,
    ) -> CityDraft:
        current = self.get(draft_id)
        current_revision = int(current.metadata["draft_revision"])
        if expected_revision is not None and expected_revision != current_revision:
            raise ValueError(f"city draft changed: expected revision {expected_revision}, " f"found {current_revision}")
        source = edit_section(current.source, section_id=section_id, action=action)
        metadata = {
            **current.metadata,
            "draft_revision": current_revision + 1,
            "updated_at": now or _utc_now(),
        }
        return self._save(self._draft_path(draft_id), metadata=metadata, source=source)

    def _save(
        self,
        target: Path,
        *,
        metadata: dict[str, Any],
        source: dict[str, Any],
    ) -> CityDraft:
        preview = assemble_city_pack(source, built_at=str(metadata["updated_at"]))
        metadata = {
            **metadata,
            "valid": preview.validation.valid,
            "pack_version": str(preview.files["manifest.json"]["version"]),
            "artifact_sha256": str((preview.files.get("generated_map.json") or {}).get("artifact_sha256", "")),
        }
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=self.root))
        backup: Path | None = None
        try:
            self._write_json(temporary / "draft.json", metadata)
            self._write_json(temporary / "source.json", source)
            preview_dir = temporary / "preview"
            preview_dir.mkdir(mode=0o700)
            for filename, data in preview.files.items():
                self._write_json(preview_dir / filename, data)
            self._write_json(preview_dir / "validation.json", preview.validation.to_dict())
            if preview.generated_map_svg is not None:
                svg_path = preview_dir / "generated_map.svg"
                svg_path.write_text(preview.generated_map_svg, encoding="utf-8")
                svg_path.chmod(0o600)
                sections_dir = preview_dir / "sections"
                sections_dir.mkdir(mode=0o700)
                for section in preview.files["generated_map.json"]["sections"]:
                    section_path = sections_dir / f"{section['id']}.svg"
                    section_path.write_text(
                        section_preview_svg(preview.generated_map_svg, section),
                        encoding="utf-8",
                    )
                    section_path.chmod(0o600)

            if target.exists():
                backup = self.root / f".{target.name}.previous-{uuid.uuid4().hex}"
                os.replace(target, backup)
            try:
                os.replace(temporary, target)
            except Exception:
                if backup is not None and backup.exists():
                    os.replace(backup, target)
                raise
            if backup is not None and backup.exists():
                shutil.rmtree(backup)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        return CityDraft(
            draft_id=str(metadata["draft_id"]),
            metadata=metadata,
            source=copy.deepcopy(source),
            preview=preview,
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"expected a JSON object in {path.name}")
        return value

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
        path.chmod(0o600)

    @staticmethod
    def _assert_preview_matches(target: Path, preview: BuiltCityPack) -> None:
        preview_dir = target / "preview"
        for filename, expected in preview.files.items():
            saved_path = preview_dir / filename
            if not saved_path.exists():
                raise ValueError(f"city draft preview is missing {filename}")
            saved = json.loads(saved_path.read_text(encoding="utf-8"))
            if saved != expected:
                raise ValueError(f"city draft preview {filename} no longer matches its source")
        if preview.generated_map_svg is not None:
            svg_path = preview_dir / "generated_map.svg"
            if not svg_path.exists() or svg_path.read_text(encoding="utf-8") != preview.generated_map_svg:
                raise ValueError("city draft preview generated_map.svg no longer matches its source")


def default_city_draft_store() -> CityDraftStore:
    return CityDraftStore(DEFAULT_CITY_DRAFTS_DIR)


__all__ = [
    "DEFAULT_CITY_DRAFTS_DIR",
    "CityDraft",
    "CityDraftStore",
    "default_city_draft_store",
]
