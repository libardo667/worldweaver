# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Content-safe structural aggregation for independent resident gym episodes."""

from __future__ import annotations

from collections import Counter
import html
import json
from typing import Any, Iterable


class GymBatchError(ValueError):
    """Raised when an episode cannot be summarized safely."""


def summarize_episode(
    payload: Any,
    *,
    run_id: str,
    duration_ms: int,
    report_name: str,
) -> dict[str, Any]:
    """Extract the bounded structural fields permitted in a batch report."""

    if not isinstance(payload, dict) or payload.get("schema") != (
        "worldweaver.resident-gym.episode"
    ):
        raise GymBatchError("batch member is not a resident gym episode")
    records = payload.get("records")
    fidelity = payload.get("fidelity")
    final_locations = payload.get("final_locations")
    if (
        not isinstance(records, list)
        or not isinstance(fidelity, dict)
        or not isinstance(final_locations, dict)
    ):
        raise GymBatchError("batch member structure is incomplete")

    structural_records = [record for record in records if isinstance(record, dict)]
    inference_finished = [
        record
        for record in structural_records
        if record.get("kind") == "resident_inference_finished"
        and isinstance(record.get("detail"), dict)
    ]
    inference_started = [
        record
        for record in structural_records
        if record.get("kind") == "resident_inference_started"
        and isinstance(record.get("detail"), dict)
    ]
    inference_failed = [
        record
        for record in structural_records
        if record.get("kind") == "resident_inference_failed"
        and isinstance(record.get("detail"), dict)
    ]
    activation = next(
        (
            record
            for record in reversed(structural_records)
            if record.get("kind") == "resident_activation_finished"
            and isinstance(record.get("detail"), dict)
        ),
        None,
    )
    attachment = next(
        (
            record
            for record in reversed(structural_records)
            if record.get("kind") == "resident_attachment_verified"
            and isinstance(record.get("detail"), dict)
        ),
        None,
    )
    activation_detail = activation.get("detail", {}) if activation else {}
    attachment_detail = attachment.get("detail", {}) if attachment else {}
    model_ids = {
        str(record.get("detail", {}).get("model_id") or "").strip()
        for record in inference_started + inference_finished + inference_failed
    }
    model_ids.discard("")
    if len(model_ids) > 1:
        raise GymBatchError("batch member reported multiple model IDs")

    active_attempt: tuple[int, str] | None = None
    previous_prompt_tokens = 0
    previous_completion_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    for record in structural_records:
        kind = record.get("kind")
        if kind not in {
            "resident_inference_started",
            "resident_inference_finished",
            "resident_inference_failed",
        }:
            continue
        detail = record.get("detail")
        if not isinstance(detail, dict):
            raise GymBatchError("inference boundary detail is invalid")
        call_index = int(detail.get("call_index") or 0)
        model_id = str(detail.get("model_id") or "").strip()
        if call_index < 1 or not model_id:
            raise GymBatchError("inference boundary identity is invalid")
        if kind == "resident_inference_started":
            if active_attempt is not None:
                raise GymBatchError("inference attempt has no terminal boundary")
            if call_index == 1:
                previous_prompt_tokens = 0
                previous_completion_tokens = 0
            active_attempt = (call_index, model_id)
            continue
        if active_attempt != (call_index, model_id):
            raise GymBatchError("inference terminal boundary does not match its start")
        cumulative_prompt = int(detail.get("prompt_tokens") or 0)
        cumulative_completion = int(detail.get("completion_tokens") or 0)
        if (
            cumulative_prompt < previous_prompt_tokens
            or cumulative_completion < previous_completion_tokens
        ):
            raise GymBatchError("inference usage moved backward")
        prompt_tokens += cumulative_prompt - previous_prompt_tokens
        completion_tokens += cumulative_completion - previous_completion_tokens
        previous_prompt_tokens = cumulative_prompt
        previous_completion_tokens = cumulative_completion
        active_attempt = None
    if active_attempt is not None:
        raise GymBatchError("inference attempt has no terminal boundary")

    http_records = [
        record
        for record in structural_records
        if record.get("kind") == "participant_http"
        and isinstance(record.get("detail"), dict)
    ]
    http_statuses = [
        int(record.get("detail", {}).get("status_code") or 500)
        for record in http_records
    ]
    chronology = next(
        (
            record
            for record in reversed(structural_records)
            if record.get("kind") == "world_chronology_audited"
            and isinstance(record.get("detail"), dict)
        ),
        None,
    )
    chronology_detail = chronology.get("detail", {}) if chronology else {}
    return {
        "run_id": str(run_id),
        "episode": str(payload.get("episode") or ""),
        "model_id": next(iter(model_ids), ""),
        "duration_ms": max(0, int(duration_ms)),
        "model_calls": len(inference_started),
        "inference_failures": len(inference_failed),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "choice": str(activation_detail.get("choice") or "none"),
        "activation_status": str(
            activation_detail.get("activation_status") or "unknown"
        ),
        "attachment": str(attachment_detail.get("attachment") or "city"),
        "final_location": str(final_locations.get("Mara") or "unknown"),
        "retirement_receipts": sum(
            record.get("kind") == "resident_departure_receipt"
            for record in structural_records
        ),
        "host_starts": sum(
            record.get("kind") == "resident_host_started"
            for record in structural_records
        ),
        "http_requests": len(http_records),
        "http_errors": sum(status >= 400 for status in http_statuses),
        "http_refusals": sum(400 <= status < 500 for status in http_statuses),
        "http_server_errors": sum(status >= 500 for status in http_statuses),
        "off_clock_rows": max(0, int(chronology_detail.get("off_clock_count") or 0)),
        "infrastructure": str(fidelity.get("infrastructure") or "unknown"),
        "participant_transport": str(
            fidelity.get("participant_transport") or "unknown"
        ),
        "report": str(report_name),
    }


def aggregate_batch(
    summaries: Iterable[dict[str, Any]],
    failures: Iterable[dict[str, Any]],
    *,
    requested_runs: int,
    models: Iterable[str],
    concurrency: int,
    transport: str,
    infrastructure: str,
    episode: str = "resident-model",
) -> dict[str, Any]:
    """Build one versioned aggregate containing structural counts only."""

    completed = sorted(
        (dict(item) for item in summaries), key=lambda item: item["run_id"]
    )
    failed = sorted((dict(item) for item in failures), key=lambda item: item["run_id"])

    def distribution(field: str) -> dict[str, int]:
        return dict(sorted(Counter(str(item[field]) for item in completed).items()))

    return {
        "schema": "worldweaver.resident-gym.batch",
        "schema_version": 4,
        "configuration": {
            "requested_runs": int(requested_runs),
            "models": list(models),
            "concurrency": int(concurrency),
            "transport": str(transport),
            "infrastructure": str(infrastructure),
            "episode": str(episode),
        },
        "totals": {
            "completed_runs": len(completed),
            "failed_runs": len(failed),
            "model_calls": sum(int(item["model_calls"]) for item in completed),
            "inference_failures": sum(
                int(item["inference_failures"]) for item in completed
            ),
            "prompt_tokens": sum(int(item["prompt_tokens"]) for item in completed),
            "completion_tokens": sum(
                int(item["completion_tokens"]) for item in completed
            ),
            "retirement_receipts": sum(
                int(item["retirement_receipts"]) for item in completed
            ),
            "http_requests": sum(int(item["http_requests"]) for item in completed),
            "http_errors": sum(int(item["http_errors"]) for item in completed),
            "http_refusals": sum(int(item["http_refusals"]) for item in completed),
            "http_server_errors": sum(
                int(item["http_server_errors"]) for item in completed
            ),
            "off_clock_rows": sum(int(item["off_clock_rows"]) for item in completed),
        },
        "distributions": {
            "models": distribution("model_id"),
            "choices": distribution("choice"),
            "attachments": distribution("attachment"),
            "final_locations": distribution("final_location"),
            "failure_classes": dict(
                sorted(
                    Counter(
                        str(item.get("failure_class") or "unclassified")
                        for item in failed
                    ).items()
                )
            ),
        },
        "runs": completed,
        "failures": failed,
    }


def render_batch_html(payload: dict[str, Any]) -> str:
    """Render a self-contained, prose-free structural batch report."""

    totals = payload["totals"]
    rows = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(run[field]))}</td>"
            for field in (
                "run_id",
                "model_id",
                "choice",
                "attachment",
                "final_location",
                "model_calls",
                "inference_failures",
                "prompt_tokens",
                "completion_tokens",
                "duration_ms",
            )
        )
        + f'<td><a href="{html.escape(str(run["report"]), quote=True)}">episode</a></td>'
        + "</tr>"
        for run in payload["runs"]
    )
    embedded = html.escape(json.dumps(payload, sort_keys=True), quote=False)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>WorldWeaver resident gym batch</title>
<style>
body{{font:15px system-ui,sans-serif;margin:2rem;background:#f6f2e8;color:#20352d}}
main{{max-width:1200px;margin:auto}} .cards{{display:flex;gap:1rem;flex-wrap:wrap}}
.card{{background:white;border:1px solid #cbd8ce;border-radius:12px;padding:1rem;min-width:140px}}
.number{{font-size:1.8rem;font-weight:700}} table{{width:100%;border-collapse:collapse;background:white}}
th,td{{padding:.55rem;border:1px solid #d7dfd8;text-align:left}} th{{background:#e6eee7}}
code,pre{{background:#edf2ed}} pre{{padding:1rem;overflow:auto}}
</style></head><body><main><h1>Resident gym batch</h1>
<div class="cards">
<div class="card"><div class="number">{totals["completed_runs"]}</div>completed</div>
<div class="card"><div class="number">{totals["failed_runs"]}</div>failed</div>
<div class="card"><div class="number">{totals["model_calls"]}</div>model calls</div>
<div class="card"><div class="number">{totals["inference_failures"]}</div>inference failures</div>
<div class="card"><div class="number">{totals["prompt_tokens"] + totals["completion_tokens"]}</div>tokens</div>
</div>
<h2>Structural outcomes</h2><table><thead><tr><th>Run</th><th>Model</th><th>Choice</th>
<th>Attachment</th><th>Final location</th><th>Calls</th><th>Inference failures</th><th>Prompt tokens</th>
<th>Completion tokens</th><th>Duration ms</th><th>Report</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Machine-readable aggregate</h2><pre>{embedded}</pre>
</main></body></html>"""
