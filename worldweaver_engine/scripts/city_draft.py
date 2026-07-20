#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Create and inspect local city drafts without touching a published pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.services.city_draft_store import (  # noqa: E402
    DEFAULT_CITY_DRAFTS_DIR,
    CityDraft,
    CityDraftStore,
)


def _store(args: argparse.Namespace) -> CityDraftStore:
    return CityDraftStore(Path(args.root))


def _summary(draft: CityDraft) -> dict:
    generated = draft.preview.files.get("generated_map.json") or {}
    sections = generated.get("sections") or []
    return {
        **draft.metadata,
        "section_count": len(sections),
        "locked_section_count": sum(
            section.get("locked") is True for section in sections
        ),
        "preview_dir": str((_store_path(draft.draft_id) / "preview").resolve()),
    }


def _store_path(draft_id: str) -> Path:
    return _ACTIVE_STORE.root / draft_id


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _create(args: argparse.Namespace) -> int:
    config_path = (
        Path(args.config)
        if args.config
        else ENGINE_ROOT / "scripts" / "city_configs" / f"{args.city}.json"
    )
    if not config_path.is_file():
        raise FileNotFoundError(f"city configuration not found: {config_path}")
    source = json.loads(config_path.read_text(encoding="utf-8"))
    draft = _ACTIVE_STORE.create(source, draft_id=args.draft_id or None)
    _print(_summary(draft))
    return 0


def _list(_: argparse.Namespace) -> int:
    _print(_ACTIVE_STORE.list())
    return 0


def _inspect(args: argparse.Namespace) -> int:
    _print(_summary(_ACTIVE_STORE.get(args.draft_id)))
    return 0


def _section(args: argparse.Namespace) -> int:
    draft = _ACTIVE_STORE.edit_section(
        args.draft_id,
        section_id=args.section_id,
        action=args.action,
        expected_revision=args.expected_revision,
    )
    summary = _summary(draft)
    summary["section_preview"] = str(
        (
            _store_path(args.draft_id)
            / "preview"
            / "sections"
            / f"{args.section_id}.svg"
        ).resolve()
    )
    _print(summary)
    return 0


def _preview(args: argparse.Namespace) -> int:
    draft = _ACTIVE_STORE.get(args.draft_id)
    path = _store_path(args.draft_id) / "preview" / "generated_map.svg"
    if args.section_id:
        known_sections = {
            section["id"]
            for section in draft.preview.files["generated_map.json"]["sections"]
        }
        if args.section_id not in known_sections:
            raise ValueError(f"unknown map section: {args.section_id}")
        path = path.parent / "sections" / f"{args.section_id}.svg"
    _print({"draft_id": args.draft_id, "preview": str(path.resolve())})
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Work on a local city draft without touching data/cities"
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_CITY_DRAFTS_DIR),
        help="draft storage directory (default: worldweaver_engine/data/city_drafts)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser(
        "create", help="create a draft from one city configuration"
    )
    source = create.add_mutually_exclusive_group(required=True)
    source.add_argument("--city", help="configuration name from scripts/city_configs")
    source.add_argument("--config", help="path to a city configuration JSON file")
    create.add_argument("--draft-id", default="")
    create.set_defaults(handler=_create)

    list_command = commands.add_parser("list", help="list local drafts")
    list_command.set_defaults(handler=_list)

    inspect = commands.add_parser("inspect", help="validate and describe one draft")
    inspect.add_argument("draft_id")
    inspect.set_defaults(handler=_inspect)

    section = commands.add_parser(
        "section", help="lock, unlock, or reroll one draft map section"
    )
    section.add_argument("draft_id")
    section.add_argument("section_id")
    section.add_argument("action", choices=("lock", "unlock", "reroll"))
    section.add_argument("--expected-revision", type=int)
    section.set_defaults(handler=_section)

    preview = commands.add_parser("preview", help="print a generated SVG preview path")
    preview.add_argument("draft_id")
    preview.add_argument("--section", dest="section_id", default="")
    preview.set_defaults(handler=_preview)
    return parser


_ACTIVE_STORE = CityDraftStore(DEFAULT_CITY_DRAFTS_DIR)


def main() -> None:
    global _ACTIVE_STORE
    parser = _parser()
    args = parser.parse_args()
    _ACTIVE_STORE = _store(args)
    try:
        raise SystemExit(args.handler(args))
    except (FileExistsError, FileNotFoundError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
