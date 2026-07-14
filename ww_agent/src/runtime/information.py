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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.runtime.ledger import append_runtime_event
from src.runtime.pulse import Reach
from src.runtime.world import WorldWeaverClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InformationRecord:
    """One provider result with source semantics intact through prompt tracing."""

    record_id: str
    source: str
    title: str
    content: str
    provenance: str
    freshness: str
    locality: str
    visibility: str
    selection_mode: str
    observed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, source: str, defaults: dict[str, str] | None = None) -> "InformationRecord":
        defaults = dict(defaults or {})
        return cls(
            record_id=str(raw.get("record_id") or raw.get("id") or f"{source}:record"),
            source=str(raw.get("source") or source),
            title=str(raw.get("title") or "").strip(),
            content=str(raw.get("content") or raw.get("text") or "").strip(),
            provenance=str(raw.get("provenance") or defaults.get("provenance") or "unknown"),
            freshness=str(raw.get("freshness") or defaults.get("freshness") or "unknown"),
            locality=str(raw.get("locality") or defaults.get("locality") or "unknown"),
            visibility=str(raw.get("visibility") or defaults.get("visibility") or "private"),
            selection_mode=str(raw.get("selection_mode") or defaults.get("selection_mode") or "provider"),
            observed_at=str(raw.get("observed_at") or raw.get("ts") or ""),
            metadata=dict(raw.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def render_information_records(records: list[InformationRecord]) -> str:
    """Render provider-neutral records only at the inference boundary."""
    blocks: list[str] = []
    for record in records:
        heading = f"[{record.source} | {record.selection_mode} | {record.freshness}]"
        if record.title:
            heading += f" {record.title}"
        blocks.append(f"{heading}\n{record.content}".rstrip())
    return "\n\n".join(blocks)


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
                defaults = {
                    "provenance": str(payload.get("provenance") or ""),
                    "freshness": str(payload.get("freshness") or ""),
                    "locality": str(payload.get("locality") or ""),
                    "visibility": str(payload.get("visibility") or ""),
                    "selection_mode": str(payload.get("selection_mode") or ""),
                }
                records = [
                    InformationRecord.from_dict(item, source=request.source, defaults=defaults)
                    for item in list(payload.get("records") or [])
                    if isinstance(item, dict)
                ]
                legacy_detail = str(payload.get("result") or payload.get("detail") or "")
                if not records and legacy_detail:
                    records = [
                        InformationRecord.from_dict(
                            {"record_id": f"{request.source}:legacy", "content": legacy_detail},
                            source=request.source,
                            defaults=defaults,
                        )
                    ]
                detail = render_information_records(records)
                if not detail:
                    detail = (
                        f"The source returned no records ({str(payload.get('reason') or 'no_match')})."
                        if not bool(payload.get("ok", True))
                        else "The source returned no matching records."
                    )
                result = {
                    "accessed": bool(payload.get("ok", True)),
                    "kind": "reach",
                    "reach_kind": request.kind,
                    "source": request.source,
                    "query": request.query,
                    "provenance": str(payload.get("provenance") or ""),
                    "records": [record.to_dict() for record in records],
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
                "record_refs": [
                    {
                        "record_id": str(record.get("record_id") or ""),
                        "source": str(record.get("source") or ""),
                        "provenance": str(record.get("provenance") or ""),
                        "freshness": str(record.get("freshness") or ""),
                        "locality": str(record.get("locality") or ""),
                        "visibility": str(record.get("visibility") or ""),
                        "selection_mode": str(record.get("selection_mode") or ""),
                    }
                    for record in list(result.get("records") or [])
                    if isinstance(record, dict)
                ],
                "reason": str(result.get("reason") or ""),
            },
        )
        return result
