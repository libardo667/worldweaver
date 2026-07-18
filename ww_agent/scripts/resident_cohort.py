#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Preflight or run a bounded resident cohort with guaranteed cleanup."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from itertools import combinations
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
import urllib.request

AGENT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = AGENT_ROOT.parent
RESIDENT_ONCE = Path(__file__).with_name("resident_once.py")

SUMMARY_FIELDS = (
    "resident",
    "model",
    "elapsed_seconds",
    "ticks",
    "ignitions",
    "settling_pulses",
    "fervor_pulses",
    "venture_pulses",
    "pulse_attempts",
    "unrouted_pulse_attempts",
    "pulses_routed",
    "information_reads",
    "acts_executed",
    "resting_ticks",
    "ticks_by_attachment",
    "actions_by_attachment",
    "action_kinds",
    "venture_gate_reasons",
    "inference_calls",
    "prompt_tokens",
    "completion_tokens",
    "recovered_json_responses",
    "action_tendency",
)


def _new_presence_report(homes: list[Path]) -> dict[str, Any]:
    return {
        "samples": 0,
        "samples_with_colocation": 0,
        "max_colocated_residents": 0,
        "resident_samples": {home.name: 0 for home in homes},
        "locations_seen": {home.name: set() for home in homes},
        "colocation_pairs": {},
        "read_failures": 0,
    }


def _sample_presence(server_url: str, homes: list[Path], report: dict[str, Any]) -> None:
    """Count resident overlap from public roster structure without reading prose."""

    try:
        with urllib.request.urlopen(f"{server_url.rstrip('/')}/api/world/digest", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        report["read_failures"] += 1
        return

    prefixes = {home.name: f"{home.name}-" for home in homes}
    locations: dict[str, str] = {}
    for row in payload.get("roster", []) if isinstance(payload, dict) else []:
        if not isinstance(row, dict) or row.get("status") == "resting":
            continue
        session_id = str(row.get("session_id") or "")
        location = str(row.get("location") or "").strip()
        if not location or location == "unknown":
            continue
        for name, prefix in prefixes.items():
            if session_id.startswith(prefix):
                locations[name] = location
                break

    report["samples"] += 1
    by_location: dict[str, list[str]] = {}
    for name, location in locations.items():
        report["resident_samples"][name] += 1
        report["locations_seen"][name].add(location)
        by_location.setdefault(location, []).append(name)

    colocated_groups = [sorted(names) for names in by_location.values() if len(names) >= 2]
    if colocated_groups:
        report["samples_with_colocation"] += 1
        report["max_colocated_residents"] = max(
            report["max_colocated_residents"],
            max(len(group) for group in colocated_groups),
        )
    for group in colocated_groups:
        for left, right in combinations(group, 2):
            pair = f"{left}|{right}"
            report["colocation_pairs"][pair] = report["colocation_pairs"].get(pair, 0) + 1


def _finalize_presence(report: dict[str, Any]) -> dict[str, Any]:
    return {
        **report,
        "locations_seen": {name: sorted(locations) for name, locations in report["locations_seen"].items()},
    }


def _resident_command(
    home: Path,
    server_url: str,
    *,
    wake: bool = False,
    park: bool = False,
    duration: float | None = None,
    model: str | None = None,
    temperature: float | None = None,
    action_tendency: bool = False,
) -> list[str]:
    command = [
        sys.executable,
        str(RESIDENT_ONCE),
        "--home",
        str(home),
        "--server-url",
        server_url,
        "--compact",
    ]
    if wake:
        command.append("--wake")
    if park:
        command.append("--park")
    if duration is not None:
        command.extend(["--duration", str(duration)])
    if model:
        command.extend(["--model", model])
    if temperature is not None:
        command.extend(["--temperature", str(temperature)])
    if action_tendency:
        command.append("--action-tendency")
    return command


def _event_from_log(path: Path, event_name: str) -> dict[str, Any] | None:
    """Read only compact structural JSON events; ignore all other runtime text."""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        candidate = line.strip()
        if not candidate.startswith("{") or not candidate.endswith("}"):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event") == event_name:
            return payload
    return None


def _preflight(home: Path, server_url: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            _resident_command(home, server_url),
            cwd=WORKSPACE_ROOT,
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "preflight timed out"
    if result.returncode == 0:
        return True, "ready"
    detail = (result.stderr or result.stdout or "preflight failed").strip()
    return False, detail[-1200:]


def _park(home: Path, server_url: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            _resident_command(home, server_url, park=True),
            cwd=WORKSPACE_ROOT,
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "cleanup timed out"
    if result.returncode == 0:
        return True, "parked"
    detail = (result.stderr or result.stdout or "cleanup failed").strip()
    return False, detail[-1200:]


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _run(args: argparse.Namespace) -> int:
    homes = [Path(raw).expanduser().resolve() for raw in args.home]
    preflight: dict[str, dict[str, Any]] = {}
    for home in homes:
        ok, detail = _preflight(home, args.server_url)
        preflight[home.name] = {"ok": ok, "detail": detail}
        print(f"[{'PASS' if ok else 'FAIL'}] {home.name}: {detail}", flush=True)

    if not all(item["ok"] for item in preflight.values()):
        print(json.dumps({"event": "cohort_preflight", "ready": False, "residents": preflight}, sort_keys=True))
        return 1

    print(json.dumps({"event": "cohort_preflight", "ready": True, "residents": sorted(preflight)}, sort_keys=True))
    if not args.wake:
        return 0

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else WORKSPACE_ROOT / ".runs" / "cohorts" / f"{timestamp}-{args.city}"
    output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)

    processes: dict[str, subprocess.Popen[str]] = {}
    streams: dict[str, Any] = {}
    logs: dict[str, Path] = {}
    return_codes: dict[str, int] = {}
    interrupted = False
    failure_seen = False
    presence = _new_presence_report(homes)
    next_presence_sample = 0.0

    try:
        for index, home in enumerate(homes):
            log_path = output_dir / f"{home.name}.log"
            stream = log_path.open("w", encoding="utf-8")
            log_path.chmod(0o600)
            command = _resident_command(
                home,
                args.server_url,
                wake=True,
                duration=args.duration,
                model=args.model,
                temperature=args.temperature,
                action_tendency=args.action_tendency,
            )
            process = subprocess.Popen(
                command,
                cwd=WORKSPACE_ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
            )
            processes[home.name] = process
            streams[home.name] = stream
            logs[home.name] = log_path
            print(f"[START] {home.name} -> {log_path}", flush=True)
            if index < len(homes) - 1 and args.stagger > 0:
                time.sleep(args.stagger)

        while len(return_codes) < len(processes):
            now = time.monotonic()
            if now >= next_presence_sample:
                _sample_presence(args.server_url, homes, presence)
                next_presence_sample = now + 5.0
            for name, process in processes.items():
                if name in return_codes:
                    continue
                code = process.poll()
                if code is None:
                    continue
                return_codes[name] = int(code)
                print(f"[DONE] {name}: exit {code}", flush=True)
                if code != 0:
                    failure_seen = True
            if failure_seen:
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        interrupted = True
        print("[STOP] interrupt received; stopping cohort and parking every resident", flush=True)
    finally:
        for process in processes.values():
            _terminate(process)
        for name, process in processes.items():
            return_codes.setdefault(name, int(process.returncode or 0))
        for stream in streams.values():
            stream.close()

    cleanup: dict[str, dict[str, Any]] = {}
    for home in homes:
        ok, detail = _park(home, args.server_url)
        cleanup[home.name] = {"ok": ok, "detail": detail}
        print(f"[{'PASS' if ok else 'FAIL'}] cleanup {home.name}: {detail}", flush=True)

    summaries: dict[str, dict[str, Any]] = {}
    for home in homes:
        payload = _event_from_log(logs[home.name], "resident_run_summary")
        if payload is not None:
            summaries[home.name] = {key: payload.get(key) for key in SUMMARY_FIELDS}

    totals: dict[str, Any] = {
        "ticks": 0,
        "pulse_attempts": 0,
        "pulses_routed": 0,
        "information_reads": 0,
        "acts_executed": 0,
        "inference_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "action_kinds": {},
    }
    for summary in summaries.values():
        for field in (
            "ticks",
            "pulse_attempts",
            "pulses_routed",
            "information_reads",
            "acts_executed",
            "inference_calls",
            "prompt_tokens",
            "completion_tokens",
        ):
            totals[field] += int(summary.get(field) or 0)
        for kind, count in (summary.get("action_kinds") or {}).items():
            totals["action_kinds"][kind] = totals["action_kinds"].get(kind, 0) + int(count or 0)

    succeeded = not interrupted and all(code == 0 for code in return_codes.values()) and all(item["ok"] for item in cleanup.values()) and len(summaries) == len(homes)
    aggregate = {
        "event": "cohort_run_summary",
        "status": "complete" if succeeded else "incomplete",
        "city": args.city,
        "requested_duration_seconds": args.duration,
        "startup_stagger_seconds": args.stagger,
        "action_tendency": bool(args.action_tendency),
        "residents": summaries,
        "totals": totals,
        "presence": _finalize_presence(presence),
        "return_codes": return_codes,
        "cleanup": cleanup,
        "output_dir": str(output_dir),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.chmod(0o600)
    print(json.dumps(aggregate, sort_keys=True), flush=True)
    return 0 if succeeded else 130 if interrupted else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", required=True, help="city label stored in the structural summary")
    parser.add_argument("--server-url", required=True, help="selected city backend URL")
    parser.add_argument("--home", action="append", required=True, help="exact resident home; repeat for the cohort")
    parser.add_argument("--wake", action="store_true", help="wake after every resident passes preflight")
    parser.add_argument("--duration", type=float, help="natural-cadence duration in seconds")
    parser.add_argument("--model", help="temporary model shared by this run")
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--action-tendency", action="store_true")
    parser.add_argument("--stagger", type=float, default=1.5, help="seconds between resident starts")
    parser.add_argument("--output-dir", help="optional empty destination for structural run logs")
    args = parser.parse_args(argv)
    if args.wake and (args.duration is None or not 0 < args.duration <= 7200):
        parser.error("--wake requires --duration between 1 and 7200 seconds")
    if not args.wake and args.duration is not None:
        parser.error("--duration is only meaningful with --wake")
    if not 2 <= len(args.home) <= 5:
        parser.error("a cohort must contain between 2 and 5 resident homes")
    if len(set(args.home)) != len(args.home):
        parser.error("resident homes must be unique")
    if not 0 <= args.stagger <= 10:
        parser.error("--stagger must be between 0 and 10 seconds")
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
