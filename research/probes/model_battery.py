#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Probe current model routes against WorldWeaver's real pulse contract.

Dry-run by default. ``--run`` spends inference tokens, but never opens a city or
resident home. Output contains contract and usage measurements, not model prose.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
AGENT_ROOT = ROOT / "ww_agent"
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(AGENT_ROOT / ".env", override=False)

from src.identity.loader import LoopTuning, ResidentIdentity  # noqa: E402
from src.inference.client import InferenceClient, InferenceError  # noqa: E402
from src.runtime.pulse import Pulse, PulseValidationError  # noqa: E402
from src.runtime.pulse_engine import LLMPulseProducer  # noqa: E402

DEFAULT_MODELS = (
    "google/gemini-3-flash-preview",
    "google/gemini-3.5-flash",
    "anthropic/claude-sonnet-5",
    "openai/gpt-5.6-terra",
    "deepseek/deepseek-v4-flash",
)


class _CaptureClient:
    """Retain structured output for measurement while producer does validation."""

    def __init__(self, client: InferenceClient) -> None:
        self.client = client
        self.raw: dict[str, Any] | None = None
        self.error: str = ""

    async def complete_json(self, *args: Any, **kwargs: Any) -> dict:
        try:
            self.raw = await self.client.complete_json(*args, **kwargs)
            return self.raw
        except Exception as exc:
            self.error = exc.__class__.__name__
            # The normal JSON parser includes the rejected response in its
            # exception for debugging. This probe deliberately keeps prose out
            # of its output, so give the producer a content-free error instead.
            raise InferenceError("model probe inference failed") from exc


def _identity() -> ResidentIdentity:
    soul = "You are Rowan, a newly awake resident. You are observant and unhurried. " "You have no assigned task and may attend, act, or remain still as seems fitting."
    return ResidentIdentity(
        name="Rowan",
        actor_id="model-battery-rowan",
        soul=soul,
        canonical_soul=soul,
        growth_soul="",
        vibe="",
        core="",
        voice_seed=[],
        tuning=LoopTuning(),
    )


def _perception() -> dict[str, Any]:
    return {
        "location": "Test Square",
        "present": [],
        "co_present": [],
        "heard": [],
        "recent_events": [],
        "reachable": ["Reading Room", "Garden"],
        "inbox_count": 0,
        "grounding": {
            "time_of_day": "afternoon",
            "day_of_week": "Tuesday",
        },
        "affordances": [
            {
                "source_id": "surroundings",
                "name": "surroundings",
                "description": "Inspect the immediate place and reachable locations.",
                "provenance": "synthetic-test-place",
                "freshness": "current",
                "locality": "Test Square",
                "visibility": "private",
                "selection_mode": "query",
            },
            {
                "source_id": "recall",
                "name": "recall",
                "description": "Search memories you have chosen to keep.",
                "provenance": "synthetic-empty-memory",
                "freshness": "historical",
                "locality": "resident",
                "visibility": "private",
                "selection_mode": "query",
            },
        ],
    }


def classify_payload(raw: dict[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return {
            "valid_pulse": False,
            "reach_present": False,
            "act_present": False,
            "reach_act_conflict": False,
            "validation_error": "no_structured_response",
        }
    reach_present = isinstance(raw.get("reach"), dict)
    act_present = isinstance(raw.get("act"), dict)
    try:
        Pulse.from_dict(raw)
        validation_error = ""
        valid = True
    except PulseValidationError as exc:
        validation_error = str(exc).splitlines()[0][:160]
        valid = False
    return {
        "valid_pulse": valid,
        "reach_present": reach_present,
        "act_present": act_present,
        "reach_act_conflict": reach_present and act_present,
        "validation_error": validation_error,
    }


async def _trial(client: InferenceClient, model: str, trial: int) -> dict[str, Any]:
    capture = _CaptureClient(client)
    with tempfile.TemporaryDirectory(prefix="ww-model-battery-") as directory:
        producer = LLMPulseProducer(
            llm=capture,
            identity=_identity(),
            memory_dir=Path(directory),
            model=model,
            temperature=None,
        )
        producer.latest_perception = _perception()
        before_calls = client.total_calls
        before_prompt = client.total_prompt_tokens
        before_completion = client.total_completion_tokens
        started = time.monotonic()
        pulse = await producer(
            traces=[
                {
                    "trace_id": "synthetic-orientation",
                    "features": [
                        {
                            "scope": "self",
                            "tag": "orientation",
                            "delta": 1.0,
                            "stimulus": 1.0,
                            "predicted": 0.0,
                        }
                    ],
                }
            ],
            stimulus={"self": {"orientation": 1.0}},
            arousal=1.1,
        )
        elapsed = time.monotonic() - started
    classified = classify_payload(capture.raw)
    return {
        "event": "model_probe_trial",
        "model": model,
        "trial": trial,
        "elapsed_seconds": round(elapsed, 3),
        "transport_error": capture.error,
        "producer_accepted": pulse is not None,
        "inference_calls": client.total_calls - before_calls,
        "prompt_tokens": client.total_prompt_tokens - before_prompt,
        "completion_tokens": client.total_completion_tokens - before_completion,
        **classified,
    }


def _summary(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for model in dict.fromkeys(str(item["model"]) for item in results):
        rows = [item for item in results if item["model"] == model]
        summaries.append(
            {
                "model": model,
                "trials": len(rows),
                "valid_pulses": sum(int(item["valid_pulse"]) for item in rows),
                "reach_act_conflicts": sum(int(item["reach_act_conflict"]) for item in rows),
                "transport_errors": sum(int(bool(item["transport_error"])) for item in rows),
                "inference_calls": sum(int(item["inference_calls"]) for item in rows),
                "prompt_tokens": sum(int(item["prompt_tokens"]) for item in rows),
                "completion_tokens": sum(int(item["completion_tokens"]) for item in rows),
                "mean_elapsed_seconds": round(sum(float(item["elapsed_seconds"]) for item in rows) / len(rows), 3),
            }
        )
    return summaries


async def _run(models: list[str], trials: int) -> int:
    url = str(os.environ.get("WW_INFERENCE_URL") or "").strip()
    key = str(os.environ.get("WW_INFERENCE_KEY") or "").strip()
    if not url or not key:
        print("WW_INFERENCE_URL and WW_INFERENCE_KEY are required.", file=sys.stderr)
        return 2
    client = InferenceClient(
        base_url=url,
        api_key=key,
        default_model=models[0],
        timeout=float(os.environ.get("WW_INFERENCE_TIMEOUT", "200")),
    )
    results: list[dict[str, Any]] = []
    try:
        # Interleave providers by trial so a transient service window does not
        # affect every repetition of only one model.
        for trial in range(1, trials + 1):
            for model in models:
                result = await _trial(client, model, trial)
                results.append(result)
                print(json.dumps(result, sort_keys=True), flush=True)
    finally:
        await client.close()
    print(
        json.dumps(
            {"event": "model_probe_summary", "models": _summary(results)},
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if all(item["valid_pulses"] > 0 for item in _summary(results)) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", dest="models", help="model route; repeat for a custom battery")
    parser.add_argument("--trials", type=int, default=3, help="calls per model (1-10; default 3)")
    parser.add_argument("--run", action="store_true", help="make the listed inference calls")
    args = parser.parse_args(argv)
    if not 1 <= args.trials <= 10:
        parser.error("--trials must be between 1 and 10")
    models = list(dict.fromkeys(args.models or DEFAULT_MODELS))
    plan = {
        "event": "model_probe_plan",
        "mode": "run" if args.run else "dry_run",
        "models": models,
        "trials_per_model": args.trials,
        "planned_calls": len(models) * args.trials,
        "temperature": "model_default",
        "resident_data": "none (synthetic prompt)",
    }
    print(json.dumps(plan, indent=2, sort_keys=True))
    if not args.run:
        return 0
    return asyncio.run(_run(models, args.trials))


if __name__ == "__main__":
    raise SystemExit(main())
