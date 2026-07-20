# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Private elective information access for a resident pulse.

This boundary is deliberately separate from ``WorldEffector``: reaching toward
a source changes what the resident knows inside the current ignition, but does
not perform a physical action, speak, move, write, or call the world's action
narrator. The source result returns only to the bounded continuation prompt.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import logging
import math
import operator
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.runtime.ledger import append_runtime_event
from src.runtime.pulse import Reach
from src.runtime.world import WorldWeaverClient

logger = logging.getLogger(__name__)


PROVENANCE_LOCAL_KNOWLEDGE = "local-knowledge"
PROVENANCE_SELF_MEMORY = "self-memory"
PROVENANCE_LOCAL_PERCEPTION = "local-perception"
PROVENANCE_LOCAL_COMPUTATION = "local-computation"
PROVENANCE_SCOPED_READING = "scoped-reading"
PROVENANCE_WORLD_EGRESS = "world-egress"


def provenance_guidance(provenance: str) -> str:
    """Phenomenological instruction for one result's actual source class."""
    return {
        PROVENANCE_LOCAL_KNOWLEDGE: (
            "What you received is knowledge you already carry; speak it as your own knowing, not as a lookup."
        ),
        PROVENANCE_SELF_MEMORY: (
            "What you received came from your own remembered life; hold it as recall, not as a new outside fact."
        ),
        PROVENANCE_LOCAL_PERCEPTION: (
            "What you received is first-hand perception of your present surroundings; keep that situated origin clear."
        ),
        PROVENANCE_LOCAL_COMPUTATION: (
            "What you received is a result you calculated locally; keep clear that it was measured or calculated rather than remembered or looked up."
        ),
        PROVENANCE_SCOPED_READING: (
            "What you received came from an authorized artifact you deliberately read; if you use it, keep clear that you read or consulted it rather than already knowing it."
        ),
        PROVENANCE_WORLD_EGRESS: (
            "What you received came from reaching outside the world; name that lookup plainly if you use it."
        ),
    }.get(
        str(provenance or "").strip(),
        "Keep the stated source of what you received explicit if you use it.",
    )


def information_record_id(source: str, *parts: Any) -> str:
    """Stable content-derived identity for a provider record."""
    material = "\x1f".join(str(part or "").strip() for part in parts)
    digest = hashlib.sha1(material.encode("utf-8")).hexdigest()[:12]
    return f"{source}:{digest}"


_MEASURE_BINARY_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_MEASURE_UNARY_OPS: dict[type[ast.unaryop], Callable[[Any], Any]] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_MEASURE_MAX_CHARS = 200
_MEASURE_MAX_NODES = 64
_MEASURE_MAX_ABS = 10**18
_MEASURE_MAX_EXPONENT = 12


def _bounded_number(value: Any) -> int | float:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        raise ValueError("result must be a finite number")
    if abs(value) > _MEASURE_MAX_ABS:
        raise ValueError("result is outside the measure's range")
    return value


def _safe_measure(expression: str) -> int | float:
    """Evaluate bounded arithmetic only: no names, calls, attributes, or containers."""
    text = str(expression or "").strip()
    if not text:
        raise ValueError("query_required")
    if len(text) > _MEASURE_MAX_CHARS:
        raise ValueError("expression_too_long")
    tree = ast.parse(text, mode="eval")
    if sum(1 for _node in ast.walk(tree)) > _MEASURE_MAX_NODES:
        raise ValueError("expression_too_complex")

    def evaluate(node: ast.AST) -> int | float:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return _bounded_number(node.value)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _MEASURE_UNARY_OPS:
            return _bounded_number(
                _MEASURE_UNARY_OPS[type(node.op)](evaluate(node.operand))
            )
        if isinstance(node, ast.BinOp) and type(node.op) in _MEASURE_BINARY_OPS:
            left = evaluate(node.left)
            right = evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > _MEASURE_MAX_EXPONENT:
                raise ValueError("exponent_too_large")
            return _bounded_number(_MEASURE_BINARY_OPS[type(node.op)](left, right))
        raise ValueError("only numbers and + - * / // % ** are allowed")

    return evaluate(tree.body)


def _measure_records(query: str) -> dict[str, Any]:
    expression = str(query or "").strip()
    try:
        result = _safe_measure(expression)
    except (
        SyntaxError,
        TypeError,
        ValueError,
        ZeroDivisionError,
        OverflowError,
    ) as exc:
        reason = (
            str(exc)
            if str(exc)
            in {
                "query_required",
                "expression_too_long",
                "expression_too_complex",
                "exponent_too_large",
            }
            else "invalid_expression"
        )
        return {"ok": False, "reason": reason, "records": []}
    rendered = str(result)
    return {
        "records": [
            {
                "record_id": information_record_id("measure", expression, rendered),
                "title": expression,
                "content": rendered,
                "selection_mode": "expression",
            }
        ]
    }


@dataclass(frozen=True)
class InformationSource:
    """One elective information provider, independent of the current world.

    Worlds and the resident host contribute these records to the same registry.
    ``run`` may be synchronous or asynchronous and returns structured records (or
    a legacy scalar/list normalized by :class:`InformationSourceRegistry`).
    """

    name: str
    description: str
    run: Callable[[str], Any]
    egress: bool = False
    provenance: str = PROVENANCE_LOCAL_KNOWLEDGE
    freshness: str = "live"
    locality: str = "unknown"
    visibility: str = "private"
    selection_mode: str = "query"


class InformationSourceRegistry:
    """Named private information providers shared by every resident embodiment."""

    def __init__(self, sources: list[InformationSource] | None = None) -> None:
        self._sources: dict[str, InformationSource] = {
            str(source.name or "").strip().lower(): source
            for source in list(sources or [])
            if str(source.name or "").strip()
        }

    def list(self) -> list[InformationSource]:
        return list(self._sources.values())

    @property
    def names(self) -> list[str]:
        return list(self._sources)

    def __bool__(self) -> bool:
        return bool(self._sources)

    async def read(self, name: str, arg: str) -> dict[str, Any]:
        source = self._sources.get(str(name or "").strip().lower())
        if source is None:
            return {"ok": False, "reason": "unknown_source", "records": []}
        try:
            result = source.run(str(arg or "").strip())
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, dict):
                payload = dict(result)
            elif isinstance(result, list):
                payload = {"records": result}
            else:
                payload = {
                    "records": [
                        {
                            "record_id": f"{source.name}:legacy",
                            "title": source.name,
                            "content": str(result),
                        }
                    ]
                }
            records = []
            for raw in list(payload.get("records") or []):
                if not isinstance(raw, dict):
                    continue
                records.append(
                    {
                        **raw,
                        "source": str(raw.get("source") or source.name),
                        "provenance": str(raw.get("provenance") or source.provenance),
                        "freshness": str(raw.get("freshness") or source.freshness),
                        "locality": str(raw.get("locality") or source.locality),
                        "visibility": str(raw.get("visibility") or source.visibility),
                        "selection_mode": str(
                            raw.get("selection_mode")
                            or payload.get("selection_mode")
                            or source.selection_mode
                        ),
                    }
                )
            ok = bool(payload.get("ok", True))
            images = [
                str(image)
                for image in list(payload.get("images") or [])
                if str(image or "").strip()
            ]
            return {
                "ok": ok,
                "records": records,
                **({"images": images} if images else {}),
                "egress": source.egress,
                "provenance": source.provenance,
                "freshness": source.freshness,
                "locality": source.locality,
                "visibility": source.visibility,
                "selection_mode": str(
                    payload.get("selection_mode") or source.selection_mode
                ),
                **(
                    {"reason": str(payload.get("reason") or "unavailable")}
                    if not ok
                    else {}
                ),
            }
        except Exception:
            logger.exception("information source %s failed", source.name)
            return {"ok": False, "reason": "source_exception", "records": []}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    except OSError:
        pass
    return out


def _recall_records(memory_dir: Path, query: str) -> dict[str, Any]:
    """Read one resident's own selected memories and felt history."""
    kept = [
        str(item.get("note") or "").strip()
        for item in _read_jsonl(memory_dir / "kept_memory.jsonl")
    ]
    kept = [item for item in kept if item]
    feelings = [
        str((event.get("payload") or {}).get("felt_sense") or "").strip()
        for event in _read_jsonl(memory_dir / "runtime_ledger.jsonl")
        if str(event.get("event_type") or "") == "felt_sense_logged"
    ]
    feelings = [item for item in feelings if item]
    query_text = str(query or "").strip()
    if query_text:
        needle = query_text.lower()
        selected = [("kept memory", item) for item in kept if needle in item.lower()]
        selected += [
            ("felt sense", item) for item in feelings if needle in item.lower()
        ]
        selection_mode = "text_match"
    else:
        selected = [("kept memory", item) for item in kept[-3:]]
        selected += [("felt sense", item) for item in feelings[-1:]]
        selection_mode = "recent"
    return {
        "selection_mode": selection_mode,
        "records": [
            {
                "record_id": information_record_id("recall", kind, content),
                "title": kind,
                "content": content,
                "freshness": "remembered",
                "locality": "self",
                "visibility": "private",
                "selection_mode": selection_mode,
            }
            for kind, content in selected[-4:]
        ],
    }


def resident_information_sources(
    memory_dir: Path | None = None,
) -> list[InformationSource]:
    """Faculties owned by the resident and available in every embodiment."""
    sources: list[InformationSource] = []
    if memory_dir is not None:
        sources.append(
            InformationSource(
                name="recall",
                description="look back over your own kept memories and how you have felt (query: a word or theme, or blank)",
                run=lambda arg: _recall_records(memory_dir, arg),
                provenance=PROVENANCE_SELF_MEMORY,
                freshness="remembered",
                locality="self",
                visibility="private",
                selection_mode="text_match",
            )
        )
    sources.append(
        InformationSource(
            name="measure",
            description="calculate bounded arithmetic exactly (query: numbers with + - * / // % or **)",
            run=_measure_records,
            provenance=PROVENANCE_LOCAL_COMPUTATION,
            freshness="immediate",
            locality="self",
            visibility="private",
            selection_mode="expression",
        )
    )
    return sources


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
    def from_dict(
        cls, raw: dict[str, Any], *, source: str, defaults: dict[str, str] | None = None
    ) -> "InformationRecord":
        defaults = dict(defaults or {})
        return cls(
            record_id=str(raw.get("record_id") or raw.get("id") or f"{source}:record"),
            source=str(raw.get("source") or source),
            title=str(raw.get("title") or "").strip(),
            content=str(raw.get("content") or raw.get("text") or "").strip(),
            provenance=str(
                raw.get("provenance") or defaults.get("provenance") or "unknown"
            ),
            freshness=str(
                raw.get("freshness") or defaults.get("freshness") or "unknown"
            ),
            locality=str(raw.get("locality") or defaults.get("locality") or "unknown"),
            visibility=str(
                raw.get("visibility") or defaults.get("visibility") or "private"
            ),
            selection_mode=str(
                raw.get("selection_mode")
                or defaults.get("selection_mode")
                or "provider"
            ),
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

    def __init__(
        self,
        *,
        ww_client: WorldWeaverClient,
        memory_dir: Path,
        freshness_seconds: float = 30.0,
    ) -> None:
        self._ww = ww_client
        self._memory_dir = memory_dir
        self._freshness_seconds = max(0.0, min(float(freshness_seconds), 300.0))
        self._recent: dict[tuple[str, str, str], tuple[float, dict[str, Any]]] = {}

    @staticmethod
    def _cache_key(request: Reach) -> tuple[str, str, str]:
        """Treat harmless casing and whitespace changes as the same private read."""
        return (
            str(request.kind or "").strip().casefold(),
            str(request.source or "").strip().casefold(),
            " ".join(str(request.query or "").split()).casefold(),
        )

    async def __call__(self, request: Reach, *, now: Any = None) -> dict[str, Any]:
        key = self._cache_key(request)
        monotonic_now = time.monotonic()
        expired = [
            cached_key
            for cached_key, (cached_at, _result) in self._recent.items()
            if monotonic_now - cached_at > self._freshness_seconds
        ]
        for cached_key in expired:
            self._recent.pop(cached_key, None)
        cached = self._recent.get(key)
        if cached is not None and monotonic_now - cached[0] <= self._freshness_seconds:
            result = copy.deepcopy(cached[1])
            result["deduplicated"] = True
            result["cache_age_seconds"] = round(monotonic_now - cached[0], 3)
            append_runtime_event(
                self._memory_dir,
                event_type="information_access_deduplicated",
                payload={
                    "accessed": bool(result.get("accessed")),
                    "cache_age_seconds": result["cache_age_seconds"],
                },
            )
            return result
        if cached is not None:
            self._recent.pop(key, None)

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
                raw = await access(
                    kind=request.kind, source=request.source, query=request.query
                )
                payload = (
                    dict(raw or {})
                    if isinstance(raw, dict)
                    else {"result": str(raw or "")}
                )
                defaults = {
                    "provenance": str(payload.get("provenance") or ""),
                    "freshness": str(payload.get("freshness") or ""),
                    "locality": str(payload.get("locality") or ""),
                    "visibility": str(payload.get("visibility") or ""),
                    "selection_mode": str(payload.get("selection_mode") or ""),
                }
                records = [
                    InformationRecord.from_dict(
                        item, source=request.source, defaults=defaults
                    )
                    for item in list(payload.get("records") or [])
                    if isinstance(item, dict)
                ]
                legacy_detail = str(
                    payload.get("result") or payload.get("detail") or ""
                )
                if not records and legacy_detail:
                    records = [
                        InformationRecord.from_dict(
                            {
                                "record_id": f"{request.source}:legacy",
                                "content": legacy_detail,
                            },
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
                    **(
                        {
                            "images": [
                                str(image)
                                for image in list(payload.get("images") or [])
                                if str(image or "").strip()
                            ]
                        }
                        if payload.get("images")
                        else {}
                    ),
                    "detail": detail,
                    **(
                        {"reason": str(payload.get("reason") or "unavailable")}
                        if not bool(payload.get("ok", True))
                        else {}
                    ),
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

        if bool(result.get("accessed")) and self._freshness_seconds > 0:
            self._recent[key] = (time.monotonic(), copy.deepcopy(result))

        records = [
            record
            for record in list(result.get("records") or [])
            if isinstance(record, dict)
        ]
        receipt = {
            "reach_kind": request.kind,
            "source": request.source,
            "query_present": bool(str(request.query or "").strip()),
            "accessed": bool(result.get("accessed")),
            "provenance": str(result.get("provenance") or ""),
            "record_count": len(records),
            "reason": str(result.get("reason") or ""),
        }
        # Growth adoption is deliberately two-step: the ledger must prove that the
        # exact proposal record was returned before it may be adopted. Other source
        # IDs can reveal file paths, gift names, people, or places and have no durable
        # reader, so they do not enter resident history.
        if request.source.strip().lower() == "growth":
            receipt["record_refs"] = [
                {"record_id": str(record.get("record_id") or "")}
                for record in records
                if str(record.get("record_id") or "").strip()
            ]
        append_runtime_event(
            self._memory_dir,
            event_type="information_accessed",
            payload=receipt,
        )
        return result
