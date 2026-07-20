# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Private, append-only evidence of the resident inference boundary.

Prompt traces are diagnostics, not cognitive state. They deliberately live beside the
ledger instead of inside it: reducers must never change because somebody observed the
prompt they were about to produce. The trace preserves the otherwise-transient perception
brief and the exact messages sent to inference so a historical pulse can be audited rather
than reconstructed approximately from later projections.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROMPT_TRACE_FILENAME = "prompt_traces.jsonl"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _enabled() -> bool:
    """Capture exact prompts only during an explicit diagnostic run."""
    return str(os.environ.get("WW_PROMPT_TRACE", "0") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


class PromptTraceRecorder:
    """Write exact inference requests and outcomes without entering substrate reducers."""

    def __init__(self, memory_dir: Path, *, resident_name: str) -> None:
        self._path = memory_dir / PROMPT_TRACE_FILENAME
        self._resident_name = str(resident_name or "").strip()

    @property
    def path(self) -> Path:
        return self._path

    def record_prompt(
        self,
        *,
        phase: str,
        system_prompt: str,
        user_prompt: str,
        model: str | None,
        temperature: float | None,
        max_tokens: int,
        source_context: dict[str, Any],
        images: list[str] | None = None,
    ) -> str | None:
        if not _enabled():
            return None
        trace_id = f"prm-{uuid.uuid4().hex[:16]}"
        image_items = [
            {
                "index": index,
                "sha256": _sha256_text(item),
                "bytes": len(str(item or "").encode("utf-8")),
            }
            for index, item in enumerate(images or [])
        ]
        inference = {
            "model": model,
            "max_tokens": int(max_tokens),
            "response_format": {"type": "json_object"},
        }
        if temperature is not None:
            inference["temperature"] = float(temperature)
        self._append(
            {
                "record_type": "prompt_assembled",
                "prompt_trace_id": trace_id,
                "ts": _utc_now_iso(),
                "resident": self._resident_name,
                "phase": str(phase or "pulse"),
                "inference": inference,
                "messages": [
                    {"role": "system", "content": str(system_prompt or "")},
                    {"role": "user", "content": str(user_prompt or "")},
                ],
                # Image bodies can be multi-megabyte data URLs. Their ordered digests prove
                # exactly which visual inputs rode with the text without duplicating them.
                "images": image_items,
                "source_context": dict(source_context or {}),
            }
        )
        return trace_id

    def record_completion(self, prompt_trace_id: str | None, raw_response: Any) -> None:
        if not prompt_trace_id:
            return
        self._append(
            {
                "record_type": "completion_received",
                "prompt_trace_id": prompt_trace_id,
                "ts": _utc_now_iso(),
                "resident": self._resident_name,
                "raw_response": raw_response,
            }
        )

    def record_failure(self, prompt_trace_id: str | None, exc: Exception) -> None:
        if not prompt_trace_id:
            return
        private_diagnostic = getattr(exc, "private_diagnostic", None)
        self._append(
            {
                "record_type": "completion_failed",
                "prompt_trace_id": prompt_trace_id,
                "ts": _utc_now_iso(),
                "resident": self._resident_name,
                "error_type": exc.__class__.__name__,
                "error": str(exc),
                **(
                    {"private_diagnostic": private_diagnostic}
                    if private_diagnostic is not None
                    else {}
                ),
            }
        )

    def record_validation_failure(
        self, prompt_trace_id: str | None, exc: Exception
    ) -> None:
        if not prompt_trace_id:
            return
        self._append(
            {
                "record_type": "completion_rejected",
                "prompt_trace_id": prompt_trace_id,
                "ts": _utc_now_iso(),
                "resident": self._resident_name,
                "error_type": exc.__class__.__name__,
                "error": str(exc),
            }
        )

    def _append(self, record: dict[str, Any]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            created = not self._path.exists()
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        record, ensure_ascii=False, default=str, separators=(",", ":")
                    )
                    + "\n"
                )
            if created:
                try:
                    self._path.chmod(0o600)
                except OSError:
                    pass
        except Exception as exc:
            # Observability must never stall or alter the resident's rhythm.
            logger.warning(
                "[%s:prompt-trace] capture failed: %s", self._resident_name, exc
            )
