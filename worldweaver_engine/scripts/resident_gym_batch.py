#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Run independent model-backed gym episodes and aggregate structural outcomes."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ENGINE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ENGINE_ROOT.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.services.gym_batch import (  # noqa: E402
    GymBatchError,
    aggregate_batch,
    render_batch_html,
    summarize_episode,
)


def _episode_payload(stdout: str) -> dict:
    start = stdout.find('{\n  "schema"')
    end = stdout.find("\nVisual episode:", start)
    if start < 0 or end <= start:
        raise GymBatchError("batch member did not emit structural JSON")
    payload = json.loads(stdout[start:end])
    if not isinstance(payload, dict):
        raise GymBatchError("batch member JSON is not an object")
    return payload


def _safe_model_slug(model_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")[:48] or "model"


def _run_member(
    *,
    ordinal: int,
    model_id: str,
    model_mode: str,
    transport: str,
    output_dir: Path,
) -> tuple[dict | None, dict | None]:
    run_id = f"run-{ordinal:04d}"
    report_name = f"{run_id}-{_safe_model_slug(model_id)}.html"
    report = output_dir / report_name
    command = [
        sys.executable,
        "scripts/resident_gym.py",
        "--episode",
        "resident-model",
        "--model",
        model_id,
        "--model-mode",
        model_mode,
        "--transport-mode",
        transport,
        "--json",
        "--output",
        str(report),
    ]
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=ENGINE_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    duration_ms = round((time.monotonic() - started) * 1000)
    if completed.returncode != 0:
        return None, {
            "run_id": run_id,
            "model_id": model_id,
            "duration_ms": duration_ms,
            "return_code": completed.returncode,
        }
    try:
        summary = summarize_episode(
            _episode_payload(completed.stdout),
            run_id=run_id,
            duration_ms=duration_ms,
            report_name=report_name,
        )
    except (GymBatchError, json.JSONDecodeError, TypeError, ValueError):
        return None, {
            "run_id": run_id,
            "model_id": model_id,
            "duration_ms": duration_ms,
            "return_code": 0,
        }
    return summary, None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run independent model-backed gym episodes and aggregate structural outcomes."
    )
    parser.add_argument(
        "--runs-per-model", type=int, default=1, help="independent episodes per model"
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="model ID; repeat for a model family (default: WW_INFERENCE_MODEL)",
    )
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--transport-mode", choices=("stdio", "loopback"), default="loopback"
    )
    parser.add_argument(
        "--model-mode",
        choices=("live", "scripted-read-home", "scripted-read-move"),
        default="live",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    models = [str(model).strip() for model in args.model if str(model).strip()]
    if not models:
        configured = str(os.environ.get("WW_INFERENCE_MODEL") or "").strip()
        if configured:
            models = [configured]
    if not models:
        parser.error("--model or WW_INFERENCE_MODEL is required")
    if not 1 <= args.runs_per_model <= 100:
        parser.error("--runs-per-model must be between 1 and 100")
    if not 1 <= args.concurrency <= 16:
        parser.error("--concurrency must be between 1 and 16")

    output_dir = (
        (args.output_dir or WORKSPACE_ROOT / ".runs" / "gym" / "batch")
        .expanduser()
        .resolve()
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    specifications = [
        (ordinal, model_id)
        for ordinal, model_id in enumerate(
            (model_id for model_id in models for _ in range(args.runs_per_model)),
            start=1,
        )
    ]
    summaries: list[dict] = []
    failures: list[dict] = []
    with ThreadPoolExecutor(
        max_workers=min(args.concurrency, len(specifications))
    ) as pool:
        futures = {
            pool.submit(
                _run_member,
                ordinal=ordinal,
                model_id=model_id,
                model_mode=args.model_mode,
                transport=args.transport_mode,
                output_dir=output_dir,
            ): ordinal
            for ordinal, model_id in specifications
        }
        for future in as_completed(futures):
            summary, failure = future.result()
            if summary is not None:
                summaries.append(summary)
            if failure is not None:
                failures.append(failure)

    infrastructure = (
        "disposable_container"
        if os.environ.get("WW_GYM_INFRASTRUCTURE") == "disposable_container"
        else "host_process"
    )
    aggregate = aggregate_batch(
        summaries,
        failures,
        requested_runs=len(specifications),
        models=models,
        concurrency=min(args.concurrency, len(specifications)),
        transport=args.transport_mode,
        infrastructure=infrastructure,
    )
    json_path = output_dir / "aggregate.json"
    html_path = output_dir / "aggregate.html"
    json_path.write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    html_path.write_text(render_batch_html(aggregate), encoding="utf-8")
    totals = aggregate["totals"]
    print(
        f"Resident gym batch: {totals['completed_runs']} completed, "
        f"{totals['failed_runs']} failed, {totals['model_calls']} model calls."
    )
    print(f"Structural aggregate: {html_path}")
    print(f"Aggregate JSON: {json_path}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
