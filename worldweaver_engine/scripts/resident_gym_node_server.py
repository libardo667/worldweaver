#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Serve one isolated federation-gym node with content-safe HTTP auditing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import threading

import uvicorn

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from main import app  # noqa: E402
from src.services.federation_node_auth import (  # noqa: E402
    NODE_ID_HEADER,
    NODE_SIGNATURE_HEADER,
)
from src.services.resident_protocol import (  # noqa: E402
    RESIDENT_CERTIFICATE_HEADER,
    RESIDENT_SIGNATURE_HEADER,
)


class AuditedApp:
    """Wrap the unmodified production app without retaining bodies or secrets."""

    def __init__(self, audit_path: Path) -> None:
        self._audit_path = audit_path
        self._lock = threading.Lock()

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await app(scope, receive, send)
            return
        status_code = 500
        headers = {
            bytes(key).decode("latin1").lower(): bytes(value).decode("latin1")
            for key, value in scope.get("headers") or []
        }

        async def observe_send(message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status") or 500)
            await send(message)

        try:
            await app(scope, receive, observe_send)
        finally:
            record = {
                "method": str(scope.get("method") or "").upper(),
                "path": str(scope.get("path") or ""),
                "status_code": status_code,
                "resident_proof": all(
                    str(headers.get(name.lower()) or "").strip()
                    for name in (
                        RESIDENT_CERTIFICATE_HEADER,
                        RESIDENT_SIGNATURE_HEADER,
                    )
                ),
                "node_proof": all(
                    str(headers.get(name.lower()) or "").strip()
                    for name in (NODE_ID_HEADER, NODE_SIGNATURE_HEADER)
                ),
            }
            with self._lock:
                with self._audit_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--audit", required=True, type=Path)
    args = parser.parse_args()
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    uvicorn.run(
        AuditedApp(args.audit),
        host=args.host,
        port=args.port,
        log_level="warning",
        access_log=False,
        lifespan="off",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
