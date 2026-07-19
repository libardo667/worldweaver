#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Run the private City Studio on this computer only."""

from __future__ import annotations

import argparse
import secrets
import sys
import threading
import webbrowser
from pathlib import Path

import uvicorn

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.city_studio_app import create_city_studio_app  # noqa: E402
from src.services.city_draft_store import (  # noqa: E402
    DEFAULT_CITY_DRAFTS_DIR,
    CityDraftStore,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the private WorldWeaver City Studio on loopback")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--root", default=str(DEFAULT_CITY_DRAFTS_DIR))
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")

    token = secrets.token_urlsafe(32)
    url = f"http://127.0.0.1:{args.port}/"
    app = create_city_studio_app(
        store=CityDraftStore(Path(args.root)),
        configurations_dir=(ENGINE_ROOT / "scripts" / "city_configs").resolve(),
        access_token=token,
        html_path=ENGINE_ROOT / "scripts" / "city_studio.html",
    )
    print(f"City Studio: {url}")
    print("It is bound to this computer only. Ctrl+C stops it.")
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
