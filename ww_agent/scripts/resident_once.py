#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Preflight or wake exactly one resident for a bounded live-city check."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(AGENT_ROOT / ".env", override=False)

from src.identity.hearth_activation import (  # noqa: E402
    inspect_hearth_activation,
    inspect_runtime_lock,
)
from src.identity.hearth_package import inventory_hearth  # noqa: E402
from src.inference.client import InferenceClient  # noqa: E402
from src.familiar.local_world import LocalWorld  # noqa: E402
from src.resident import Resident  # noqa: E402
from src.world.city_world import CityWorld  # noqa: E402
from src.world.client import WorldWeaverClient  # noqa: E402


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "status": "pass" if ok else "fail", "detail": detail}


def _did_execute(result: Any) -> bool:
    if isinstance(result, dict):
        return bool(result.get("executed"))
    return bool(result)


def _attachment_kind(world: Any) -> str:
    if isinstance(world, LocalWorld):
        return "hearth"
    if isinstance(world, CityWorld):
        return "city"
    return world.__class__.__name__.lower() or "unknown"


def _record_tick(
    stats: dict[str, Any], world: Any, result: dict[str, Any], tick: int
) -> dict[str, Any]:
    attachment = _attachment_kind(world)
    act_result = result.get("act_executed")
    act_executed = _did_execute(act_result)
    act_kind = str(act_result.get("kind") or "") if isinstance(act_result, dict) else ""
    status = str(result.get("status") or "unknown")
    choice = str(result.get("choice") or "none")
    outcome = str(result.get("action_outcome") or "")
    reads = int(result.get("reads") or 0)
    stats["ticks"] = tick
    stats["activations"] += int(status != "idle")
    stats["idle_polls"] += int(status == "idle")
    stats["information_reads"] += reads
    stats["actions_attempted"] += int(choice == "act")
    stats["actions_confirmed"] += int(outcome == "confirmed")
    stats["actions_declined"] += int(outcome == "declined")
    stats["actions_unknown"] += int(outcome == "unknown")
    stats["private_continuations"] += int(choice == "continue")
    stats["waits"] += int(choice == "wait")
    stats["ticks_by_attachment"][attachment] = (
        stats["ticks_by_attachment"].get(attachment, 0) + 1
    )
    if act_executed:
        stats["actions_by_attachment"][attachment] = (
            stats["actions_by_attachment"].get(attachment, 0) + 1
        )
        stats["action_kinds"][act_kind or "unknown"] = (
            stats["action_kinds"].get(act_kind or "unknown", 0) + 1
        )
    return {
        "event": "resident_tick",
        "tick": tick,
        "attachment": attachment,
        "status": status,
        "choice": choice,
        "information_reads": reads,
        "action_outcome": outcome or None,
        "act_executed": act_executed,
        "act_kind": act_kind or None,
    }


def _parse_duration(value: str) -> float:
    """Parse a small operator-facing duration without adding a scheduler dependency."""
    raw = str(value or "").strip().lower()
    units = {"s": 1.0, "m": 60.0, "h": 3600.0}
    suffix = raw[-1:] if raw[-1:] in units else "s"
    number = raw[:-1] if raw[-1:] in units else raw
    try:
        seconds = float(number) * units[suffix]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "duration must look like 30s, 15m, or 1h"
        ) from exc
    if not 0 < seconds <= 7200:
        raise argparse.ArgumentTypeError(
            "duration must be greater than zero and at most 2h"
        )
    return seconds


def inspect_resident_home(home: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read one home and report whether it is safe to hand to the live runner."""
    checks: list[dict[str, Any]] = []
    checks.append(
        _check("resident_home", home.is_dir(), "exists" if home.is_dir() else "missing")
    )
    soul = home / "identity" / "SOUL.md"
    resident_id = home / "identity" / "resident_id.txt"
    checks.append(
        _check(
            "identity",
            soul.is_file() and resident_id.is_file(),
            (
                "required identity files present"
                if soul.is_file() and resident_id.is_file()
                else "identity/SOUL.md or identity/resident_id.txt is missing"
            ),
        )
    )
    if not home.is_dir():
        return checks, {"status": "invalid"}
    try:
        inventory = inventory_hearth(home)
        inventory_report = inventory.to_dict()
        checks.append(
            _check(
                "portable_inventory", not inventory.blocked, inventory_report["status"]
            )
        )
    except (OSError, ValueError) as exc:
        inventory_report = {"status": "invalid", "error": str(exc)}
        checks.append(_check("portable_inventory", False, str(exc)))
    activation = inspect_hearth_activation(home)
    activation_status = str(activation.get("status") or "invalid")
    checks.append(
        _check(
            "hearth_activation",
            activation_status == "active",
            activation_status,
        )
    )
    lock = inspect_runtime_lock(home)
    lock_status = str(lock.get("status") or "invalid")
    checks.append(_check("runtime_lock", lock_status == "available", lock_status))
    return checks, {
        "inventory": {
            "status": inventory_report.get("status"),
            "counts": inventory_report.get("counts", {}),
        },
        "activation": activation,
        "runtime_lock": lock,
    }


def _effective_model(home: Path, default_model: str) -> str:
    path = home / "identity" / "tuning.json"
    if not path.is_file():
        return default_model
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(raw, dict):
        return ""
    slow = raw.get("slow") if isinstance(raw.get("slow"), dict) else {}
    fast = raw.get("fast") if isinstance(raw.get("fast"), dict) else {}
    return str(slow.get("model") or fast.get("model") or default_model).strip()


def _inactive_tuning_fields(home: Path) -> list[str]:
    """Name known loop-era controls that load safely but no longer own behavior."""
    path = home / "identity" / "tuning.json"
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, dict):
        return []
    inactive: list[str] = []
    for section in ("wander", "ground", "mail", "rest"):
        if section in raw:
            inactive.append(section)
    for section, active_keys in (
        ("fast", {"model", "temperature"}),
        ("slow", {"model"}),
    ):
        values = raw.get(section)
        if not isinstance(values, dict):
            continue
        inactive.extend(f"{section}.{key}" for key in values if key not in active_keys)
    return sorted(inactive)


def _inference_checks(
    home: Path,
    model_override: str | None = None,
) -> list[dict[str, Any]]:
    key_present = bool(str(os.environ.get("WW_INFERENCE_KEY") or "").strip())
    inference_url = str(os.environ.get("WW_INFERENCE_URL") or "").strip()
    default_model = str(os.environ.get("WW_INFERENCE_MODEL") or "").strip()
    inference_model = str(model_override or "").strip() or _effective_model(
        home, default_model
    )

    def safe_endpoint(value: str) -> str:
        if not value:
            return "missing"
        parts = urllib.parse.urlsplit(value)
        hostname = parts.hostname or ""
        if parts.port:
            hostname = f"{hostname}:{parts.port}"
        return urllib.parse.urlunsplit((parts.scheme, hostname, "", "", ""))

    return [
        _check(
            "inference_key", key_present, "configured" if key_present else "missing"
        ),
        _check("inference_endpoint", bool(inference_url), safe_endpoint(inference_url)),
        _check("inference_model", bool(inference_model), inference_model or "missing"),
    ]


async def _run(args: argparse.Namespace) -> int:
    home = Path(args.home).expanduser().resolve()
    server_url = str(args.server_url).rstrip("/")
    checks, home_report = inspect_resident_home(home)
    checks.extend(_inference_checks(home, args.model))
    inactive_tuning = _inactive_tuning_fields(home)
    checks.append(
        _check(
            "tuning_compatibility",
            True,
            (
                "ignored loop-era fields: " + ", ".join(inactive_tuning)
                if inactive_tuning
                else "no inactive loop-era fields"
            ),
        )
    )

    world = WorldWeaverClient(base_url=server_url)
    world_id = ""
    try:
        healthy = await world.health()
        checks.append(_check("city_health", healthy, server_url))
        if healthy:
            world_id = await world.get_world_id() or ""
        checks.append(_check("world_seed", bool(world_id), world_id or "missing"))

        ready = all(check["status"] == "pass" for check in checks)
        report = {
            "status": "ready" if ready else "blocked",
            "mode": "wake" if args.wake else "park" if args.park else "preflight",
            "resident": home.name,
            "home": str(home),
            "city_url": server_url,
            "checks": checks,
            "hearth": home_report,
        }
        print(
            json.dumps(
                report,
                indent=None if args.compact else 2,
                sort_keys=True,
            ),
            flush=True,
        )
        if not ready:
            return 1
        if not args.wake and not args.park:
            return 0

        if args.park:
            resident = Resident(home, world, object())
            await resident.start(world_id)
            await resident.park_at_hearth_and_stop()
            print(
                json.dumps(
                    {"event": "resident_parked_at_hearth", "resident": resident.name},
                    sort_keys=True,
                )
            )
            return 0

        llm = InferenceClient(
            base_url=os.environ["WW_INFERENCE_URL"],
            api_key=os.environ["WW_INFERENCE_KEY"],
            default_model=os.environ["WW_INFERENCE_MODEL"],
            timeout=float(os.environ.get("WW_INFERENCE_TIMEOUT", "200")),
        )

        stats = {
            "ticks": 0,
            "activations": 0,
            "idle_polls": 0,
            "information_reads": 0,
            "actions_attempted": 0,
            "actions_confirmed": 0,
            "actions_declined": 0,
            "actions_unknown": 0,
            "private_continuations": 0,
            "waits": 0,
            "ticks_by_attachment": {},
            "actions_by_attachment": {},
            "action_kinds": {},
        }

        async def observe_tick(_identity, _world, _core, result, tick):
            print(
                json.dumps(_record_tick(stats, _world, result, tick), sort_keys=True),
                flush=True,
            )

        resident_kwargs: dict[str, Any] = {"tick_observer": observe_tick}
        if args.model:
            resident_kwargs["pulse_model"] = args.model
            # A temporary model swap uses that model's own sampling default
            # unless the steward explicitly supplies a compatible temperature.
            resident_kwargs["pulse_temperature"] = args.temperature
        elif args.temperature is not None:
            resident_kwargs["pulse_temperature"] = args.temperature
        resident = Resident(home, world, llm, **resident_kwargs)
        effective_model = str(args.model or "").strip() or _effective_model(
            home,
            str(os.environ.get("WW_INFERENCE_MODEL") or "").strip(),
        )
        started_at = time.monotonic()
        try:
            await resident.start(world_id)
            print(
                json.dumps(
                    {
                        "event": "resident_started",
                        "resident": resident.name,
                        "ticks": args.ticks,
                        "duration_seconds": args.duration,
                        "cadence": (
                            "natural" if args.duration is not None else f"{args.pause}s"
                        ),
                        "model": effective_model,
                        "temperature": (
                            args.temperature
                            if args.temperature is not None
                            else ("model_default" if args.model else "resident_tuning")
                        ),
                        "resident_loop": "reference-v1",
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            await resident.run(
                max_ticks=args.ticks,
                max_duration_seconds=args.duration,
                pause_seconds=args.pause,
                park_at_hearth_on_stop=True,
            )
            elapsed = time.monotonic() - started_at
            print(
                json.dumps(
                    {
                        "event": "resident_run_summary",
                        "resident": resident.name,
                        "model": effective_model,
                        "stop_condition": (
                            "duration" if args.duration is not None else "ticks"
                        ),
                        "requested_duration_seconds": args.duration,
                        "requested_ticks": args.ticks,
                        "elapsed_seconds": round(elapsed, 3),
                        "resident_loop": "reference-v1",
                        **stats,
                        "inference_calls": llm.total_calls,
                        "prompt_tokens": llm.total_prompt_tokens,
                        "completion_tokens": llm.total_completion_tokens,
                        "recovered_json_responses": llm.recovered_json_responses,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            print(
                json.dumps(
                    {"event": "resident_parked_at_hearth", "resident": resident.name},
                    sort_keys=True,
                ),
                flush=True,
            )
        finally:
            await llm.close()
        return 0
    finally:
        await world.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, help="exact resident home path")
    parser.add_argument("--server-url", required=True, help="one city backend URL")
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--wake",
        action="store_true",
        help="perform the bounded run after preflight; omitted means read-only",
    )
    action.add_argument(
        "--park",
        action="store_true",
        help="retire an existing city session without running cognition",
    )
    limit = parser.add_mutually_exclusive_group()
    limit.add_argument("--ticks", type=int, help="bounded smoke-test tick count (1-20)")
    limit.add_argument(
        "--duration",
        type=_parse_duration,
        help="natural-cadence run duration, such as 15m or 1h (maximum 2h)",
    )
    parser.add_argument(
        "--pause",
        type=float,
        help="seconds between bounded smoke-test ticks (default 0.5; unavailable with --duration)",
    )
    parser.add_argument("--model", help="temporary resident model for this run only")
    parser.add_argument(
        "--temperature",
        type=float,
        help="temporary sampling temperature; omitted model swaps use the model default",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)
    if args.ticks is None and args.duration is None:
        args.ticks = 3
    if args.duration is not None and args.pause is not None:
        parser.error(
            "--duration uses the resident's natural cadence; do not pass --pause"
        )
    if args.duration is None and args.pause is None:
        args.pause = 0.5
    if args.duration is not None:
        args.ticks = 0
        args.pause = None
    if args.duration is None and not 1 <= args.ticks <= 20:
        parser.error("--ticks must be between 1 and 20")
    if args.pause is not None and not 0 <= args.pause <= 60:
        parser.error("--pause must be between 0 and 60 seconds")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
