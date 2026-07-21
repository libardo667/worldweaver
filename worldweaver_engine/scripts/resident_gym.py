#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Run a deterministic resident-gym episode without a live shard or model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ENGINE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ENGINE_ROOT.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.api.game import _state_managers  # noqa: E402
from src.database import Base  # noqa: E402
from src.services.gym_presentation import render_html, render_terminal  # noqa: E402
from src.services.resident_gym import (  # noqa: E402
    run_first_conversation,
    run_waiting_letter,
)
from src.services.session_service import _session_locks  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a deterministic production-rule resident gym episode."
    )
    parser.add_argument(
        "--episode",
        choices=("footbridge", "waiting-letter"),
        default="footbridge",
        help="episode to run (default: footbridge)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="self-contained HTML result (default: .runs/gym/<episode>.html)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the structural episode JSON instead of the terminal view",
    )
    args = parser.parse_args()

    _state_managers.clear()
    _session_locks.clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    try:
        with session_factory() as db:
            result = (
                run_waiting_letter(db)
                if args.episode == "waiting-letter"
                else run_first_conversation(db)
            )
        default_name = (
            "waiting-letter.html"
            if args.episode == "waiting-letter"
            else "footbridge-hello.html"
        )
        output = (
            (args.output or WORKSPACE_ROOT / ".runs" / "gym" / default_name)
            .expanduser()
            .resolve()
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_html(result), encoding="utf-8")
        if args.json:
            print(json.dumps(result.as_payload(), indent=2, ensure_ascii=False))
        else:
            print(render_terminal(result))
        print(f"Visual episode: {output}")
    finally:
        engine.dispose()
        _state_managers.clear()
        _session_locks.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
