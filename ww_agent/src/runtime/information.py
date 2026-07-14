# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Private elective information access for a resident pulse.

This boundary is deliberately separate from ``WorldEffector``: reaching toward
a source changes what the resident knows inside the current ignition, but does
not perform a physical action, speak, move, write, or call the world's action
narrator. The source result returns only to the bounded continuation prompt.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.runtime.ledger import append_runtime_event
from src.runtime.pulse import Reach
from src.runtime.world import WorldWeaverClient

logger = logging.getLogger(__name__)


class InformationAccess:
    """Dispatch a typed reach to the current world's named source registry."""

    def __init__(self, *, ww_client: WorldWeaverClient, memory_dir: Path) -> None:
        self._ww = ww_client
        self._memory_dir = memory_dir

    async def __call__(self, request: Reach, *, now: Any = None) -> dict[str, Any]:
        access = getattr(self._ww, "access_information", None)
        if not callable(access):
            result = {
                "accessed": False,
                "kind": "reach",
                "source": request.source,
                "reason": "information_access_unavailable",
                "detail": "That information source is not available in this world.",
            }
        else:
            try:
                raw = await access(kind=request.kind, source=request.source, query=request.query)
                payload = dict(raw or {}) if isinstance(raw, dict) else {"result": str(raw or "")}
                detail = str(payload.get("result") or payload.get("detail") or "")
                result = {
                    "accessed": bool(payload.get("ok", True)),
                    "kind": "reach",
                    "reach_kind": request.kind,
                    "source": request.source,
                    "query": request.query,
                    "provenance": str(payload.get("provenance") or ""),
                    "detail": detail,
                    **({"reason": str(payload.get("reason") or "unavailable")} if not bool(payload.get("ok", True)) else {}),
                }
            except Exception as exc:
                logger.warning("information reach %s failed: %s", request.source, exc)
                result = {
                    "accessed": False,
                    "kind": "reach",
                    "reach_kind": request.kind,
                    "source": request.source,
                    "query": request.query,
                    "reason": "exception",
                    "detail": "The source did not answer.",
                }

        append_runtime_event(
            self._memory_dir,
            event_type="information_accessed",
            payload={
                "reach_kind": request.kind,
                "source": request.source,
                "query": request.query,
                "accessed": bool(result.get("accessed")),
                "provenance": str(result.get("provenance") or ""),
                "result_excerpt": str(result.get("detail") or "")[:500],
                "reason": str(result.get("reason") or ""),
            },
        )
        return result
