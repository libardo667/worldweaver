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
from src.resident import Resident  # noqa: E402
from src.world.client import WorldWeaverClient  # noqa: E402


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "status": "pass" if ok else "fail", "detail": detail}


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


def _embedding_available(url: str, model: str, key: str) -> bool:
    if not url or not model:
        return False
    request = urllib.request.Request(
        url.rstrip("/") + "/embeddings",
        data=json.dumps({"model": model, "input": ["WorldWeaver preflight"]}).encode(
            "utf-8"
        ),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key or 'ollama'}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except Exception:
        return False
    data = payload.get("data") if isinstance(payload, dict) else None
    vector = (
        data[0].get("embedding")
        if isinstance(data, list) and data and isinstance(data[0], dict)
        else None
    )
    return isinstance(vector, list) and bool(vector)


def _inference_checks(home: Path) -> list[dict[str, Any]]:
    key_present = bool(str(os.environ.get("WW_INFERENCE_KEY") or "").strip())
    inference_url = str(os.environ.get("WW_INFERENCE_URL") or "").strip()
    default_model = str(os.environ.get("WW_INFERENCE_MODEL") or "").strip()
    inference_model = _effective_model(home, default_model)
    embedding_url = str(os.environ.get("WW_EMBEDDING_URL") or "").strip()
    embedding_model = str(os.environ.get("WW_EMBEDDING_MODEL") or "").strip()
    embedding_key = str(os.environ.get("WW_EMBEDDING_KEY") or "ollama").strip()
    embedding_available = _embedding_available(
        embedding_url, embedding_model, embedding_key
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
        _check(
            "embedding_endpoint",
            embedding_available,
            safe_endpoint(embedding_url) if embedding_available else "unreachable",
        ),
        _check("embedding_model", bool(embedding_model), embedding_model or "missing"),
        _check(
            "prompt_trace",
            str(os.environ.get("WW_PROMPT_TRACE", "1")).strip().lower()
            not in {"0", "false", "no", "off"},
            (
                "enabled"
                if str(os.environ.get("WW_PROMPT_TRACE", "1")).strip().lower()
                not in {"0", "false", "no", "off"}
                else "disabled"
            ),
        ),
    ]


async def _run(args: argparse.Namespace) -> int:
    home = Path(args.home).expanduser().resolve()
    server_url = str(args.server_url).rstrip("/")
    checks, home_report = inspect_resident_home(home)
    checks.extend(_inference_checks(home))

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
            "mode": "wake" if args.wake else "preflight",
            "resident": home.name,
            "home": str(home),
            "city_url": server_url,
            "checks": checks,
            "hearth": home_report,
        }
        print(json.dumps(report, indent=2, sort_keys=True))
        if not ready:
            return 1
        if not args.wake:
            return 0

        llm = InferenceClient(
            base_url=os.environ["WW_INFERENCE_URL"],
            api_key=os.environ["WW_INFERENCE_KEY"],
            default_model=os.environ["WW_INFERENCE_MODEL"],
            timeout=float(os.environ.get("WW_INFERENCE_TIMEOUT", "200")),
        )

        async def observe_tick(_identity, _world, _core, result, tick):
            print(
                json.dumps(
                    {
                        "event": "resident_tick",
                        "tick": tick,
                        "ignited": bool(result.get("ignited")),
                        "pulse_routed": bool(result.get("pulse_routed")),
                        "act_executed": bool(result.get("act_executed")),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

        resident = Resident(
            home,
            world,
            llm,
            tick_observer=observe_tick,
        )
        try:
            await resident.start(world_id)
            print(
                json.dumps(
                    {
                        "event": "resident_started",
                        "resident": resident.name,
                        "ticks": args.ticks,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            await resident.run(max_ticks=args.ticks, pause_seconds=args.pause)
            print(
                json.dumps(
                    {"event": "resident_stopped", "resident": resident.name},
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
    parser.add_argument(
        "--wake",
        action="store_true",
        help="perform the bounded run after preflight; omitted means read-only",
    )
    parser.add_argument(
        "--ticks", type=int, default=3, help="bounded tick count (1-20)"
    )
    parser.add_argument(
        "--pause", type=float, default=0.5, help="seconds between bounded ticks"
    )
    args = parser.parse_args(argv)
    if not 1 <= args.ticks <= 20:
        parser.error("--ticks must be between 1 and 20")
    if not 0 <= args.pause <= 60:
        parser.error("--pause must be between 0 and 60 seconds")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
