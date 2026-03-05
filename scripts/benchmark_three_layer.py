#!/usr/bin/env python
"""Benchmark strict 3-layer architecture latency impact."""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Sequence

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUT_DIR = ROOT / "reports" / "benchmarks" / "three_layer"
DEFAULT_TIMEOUT_SECONDS = 300.0
DEFAULT_STARTUP_TIMEOUT_SECONDS = 45.0
DEFAULT_TURNS = 20
DEFAULT_STORYLET_COUNT = 5
DEFAULT_SEED = 20260305

DEFAULT_WORLD_THEME = "cyberpunk noir"
DEFAULT_PLAYER_ROLE = "rogue AI hunter"
DEFAULT_DESCRIPTION = "A rain-soaked megacity with unstable AI traces."
DEFAULT_KEY_ELEMENTS = [
    "neon reflections",
    "patrol drones",
    "memory brokers",
]
DEFAULT_TONE = "gritty"


@dataclass(frozen=True)
class ModeConfig:
    label: str
    strict_three_layer: bool
    port: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _path_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path.resolve())


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        value = result.stdout.strip()
        return value or "unknown"
    except Exception:
        return "unknown"


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    samples = sorted(float(item) for item in values)
    if len(samples) == 1:
        return samples[0]
    clamped_q = max(0.0, min(1.0, float(q)))
    position = clamped_q * (len(samples) - 1)
    lower = int(position)
    upper = min(lower + 1, len(samples) - 1)
    fraction = position - lower
    return (samples[lower] * (1.0 - fraction)) + (samples[upper] * fraction)


def summarize_latencies(latencies_ms: Sequence[float]) -> Dict[str, float]:
    values = [float(item) for item in latencies_ms]
    if not values:
        return {
            "count": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "avg_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
        }
    return {
        "count": float(len(values)),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
        "avg_ms": round(sum(values) / float(len(values)), 3),
        "p50_ms": round(_percentile(values, 0.5), 3),
        "p95_ms": round(_percentile(values, 0.95), 3),
    }


def _safe_percent_delta(new_value: float, baseline: float) -> float:
    if abs(float(baseline)) < 1e-9:
        return 0.0
    return round(((float(new_value) - float(baseline)) / float(baseline)) * 100.0, 3)


def _build_comparison(
    baseline: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    baseline_bootstrap_ms = float(baseline.get("bootstrap_ms", 0.0))
    candidate_bootstrap_ms = float(candidate.get("bootstrap_ms", 0.0))
    baseline_summary = baseline.get("turn_latency_summary", {})
    candidate_summary = candidate.get("turn_latency_summary", {})

    metric_names = ("avg_ms", "p50_ms", "p95_ms")
    turn_deltas: Dict[str, Dict[str, float]] = {}
    for metric in metric_names:
        baseline_value = float(baseline_summary.get(metric, 0.0))
        candidate_value = float(candidate_summary.get(metric, 0.0))
        turn_deltas[metric] = {
            "baseline": round(baseline_value, 3),
            "candidate": round(candidate_value, 3),
            "delta_ms": round(candidate_value - baseline_value, 3),
            "delta_pct": _safe_percent_delta(candidate_value, baseline_value),
        }

    return {
        "baseline_mode": str(baseline.get("mode", "off")),
        "candidate_mode": str(candidate.get("mode", "on")),
        "bootstrap": {
            "baseline_ms": round(baseline_bootstrap_ms, 3),
            "candidate_ms": round(candidate_bootstrap_ms, 3),
            "delta_ms": round(candidate_bootstrap_ms - baseline_bootstrap_ms, 3),
            "delta_pct": _safe_percent_delta(candidate_bootstrap_ms, baseline_bootstrap_ms),
        },
        "turn_latency_deltas": turn_deltas,
    }


def _request_json(
    method: str,
    url: str,
    *,
    timeout_seconds: float,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    response = requests.request(
        method=method,
        url=url,
        json=payload,
        timeout=float(timeout_seconds),
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"{method} {url} failed: {response.status_code} {response.text.strip()}") from exc
    body = response.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"{method} {url} returned unexpected payload type.")
    return body


def _normalize_choices(raw_choices: Any) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    if not isinstance(raw_choices, list):
        return output
    for item in raw_choices:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        set_payload = item.get("set")
        if not isinstance(set_payload, dict):
            set_payload = {}
        output.append({"label": label, "set": set_payload})
    return output


def _pick_choice_vars(
    *,
    rng: random.Random,
    choices: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    valid = [item for item in choices if isinstance(item.get("set"), dict)]
    if not valid:
        return {}
    picked = rng.choice(valid)
    return dict(picked["set"])


def _wait_for_backend(base_url: str, process: subprocess.Popen[Any], startup_timeout_seconds: float) -> None:
    deadline = time.time() + float(startup_timeout_seconds)
    root_url = base_url.rsplit("/api", 1)[0] if "/api" in base_url else base_url.rstrip("/")
    health_url = f"{root_url}/health"
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("backend process exited before readiness checks passed")
        try:
            response = requests.get(health_url, timeout=1.5)
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.4)
    raise RuntimeError(f"timed out waiting for backend readiness: {health_url}")


@contextmanager
def managed_backend(
    *,
    mode: ModeConfig,
    startup_timeout_seconds: float,
    extra_env: Dict[str, str],
    log_path: Path,
) -> Iterator[str]:
    env = os.environ.copy()
    env.update(extra_env)
    env["WW_ENABLE_STRICT_THREE_LAYER_ARCHITECTURE"] = "1" if mode.strict_three_layer else "0"
    env["PYTHONUNBUFFERED"] = "1"
    base_url = f"http://127.0.0.1:{mode.port}/api"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as handle:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--port", str(mode.port)],
            cwd=str(ROOT),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_for_backend(base_url, process, startup_timeout_seconds)
            yield base_url
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5.0)


def _timed_request(
    method: str,
    url: str,
    *,
    timeout_seconds: float,
    payload: Dict[str, Any] | None = None,
) -> tuple[Dict[str, Any], float]:
    started = time.perf_counter()
    response_payload = _request_json(
        method,
        url,
        timeout_seconds=timeout_seconds,
        payload=payload,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    return response_payload, elapsed_ms


def run_mode_benchmark(
    *,
    mode: ModeConfig,
    base_output_dir: Path,
    timeout_seconds: float,
    startup_timeout_seconds: float,
    turns: int,
    storylet_count: int,
    seed: int,
    model_id: str,
    world_theme: str,
    player_role: str,
    description: str,
    key_elements: Sequence[str],
    tone: str,
    include_bootstrap: bool,
    extra_env: Dict[str, str],
) -> Dict[str, Any]:
    logs_dir = base_output_dir / "backend_logs"
    log_path = logs_dir / f"{mode.label}.log"
    session_id = f"bench-{mode.label}-{_timestamp_slug().lower()}"
    rng = random.Random(seed)
    bootstrap_ms = 0.0
    next_latencies_ms: List[float] = []
    errors: List[str] = []

    with managed_backend(
        mode=mode,
        startup_timeout_seconds=startup_timeout_seconds,
        extra_env=extra_env,
        log_path=log_path,
    ) as base_url:
        _request_json(
            "POST",
            f"{base_url}/dev/hard-reset",
            timeout_seconds=timeout_seconds,
            payload={},
        )
        if model_id:
            _request_json(
                "PUT",
                f"{base_url}/model",
                timeout_seconds=timeout_seconds,
                payload={"model_id": model_id},
            )

        if include_bootstrap:
            bootstrap_payload = {
                "session_id": session_id,
                "world_theme": world_theme,
                "player_role": player_role,
                "description": description,
                "key_elements": list(key_elements),
                "tone": tone,
                "storylet_count": int(storylet_count),
                "bootstrap_source": "benchmark-three-layer",
            }
            _, bootstrap_ms = _timed_request(
                "POST",
                f"{base_url}/session/bootstrap",
                timeout_seconds=timeout_seconds,
                payload=bootstrap_payload,
            )

        first_response, first_ms = _timed_request(
            "POST",
            f"{base_url}/next",
            timeout_seconds=timeout_seconds,
            payload={"session_id": session_id, "vars": {}},
        )
        next_latencies_ms.append(first_ms)
        current_choices = _normalize_choices(first_response.get("choices", []))

        for _ in range(2, int(turns) + 1):
            vars_payload = _pick_choice_vars(rng=rng, choices=current_choices)
            try:
                response_payload, elapsed_ms = _timed_request(
                    "POST",
                    f"{base_url}/next",
                    timeout_seconds=timeout_seconds,
                    payload={"session_id": session_id, "vars": vars_payload},
                )
            except Exception as exc:
                errors.append(str(exc))
                break
            next_latencies_ms.append(elapsed_ms)
            current_choices = _normalize_choices(response_payload.get("choices", []))

    summary = summarize_latencies(next_latencies_ms)
    turns_completed = len(next_latencies_ms)
    throughput_tps = 0.0
    if next_latencies_ms:
        total_seconds = sum(next_latencies_ms) / 1000.0
        if total_seconds > 0:
            throughput_tps = turns_completed / total_seconds

    return {
        "mode": mode.label,
        "strict_three_layer_enabled": bool(mode.strict_three_layer),
        "session_id": session_id,
        "turns_requested": int(turns),
        "turns_completed": int(turns_completed),
        "storylet_count": int(storylet_count),
        "bootstrap_ms": round(float(bootstrap_ms), 3),
        "next_latencies_ms": [round(float(item), 3) for item in next_latencies_ms],
        "turn_latency_summary": summary,
        "throughput_turns_per_second": round(float(throughput_tps), 4),
        "error_count": len(errors),
        "errors": errors,
        "log_path": _path_label(log_path),
    }


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _render_markdown(report: Dict[str, Any]) -> str:
    baseline = report["modes"][0]
    candidate = report["modes"][1]
    comparison = report["comparison"]
    turn_deltas = comparison["turn_latency_deltas"]

    lines = [
        "# 3-Layer Latency Benchmark",
        "",
        f"- Timestamp UTC: `{report['timestamp_utc']}`",
        f"- Commit: `{report['commit']}`",
        f"- Model: `{report['model_id'] or 'unchanged'}`",
        f"- Turns Requested (per mode): `{report['turns']}`",
        f"- Storylet Count: `{report['storylet_count']}`",
        "",
        "## Modes",
        "",
        f"- Baseline: `{baseline['mode']}` (strict={baseline['strict_three_layer_enabled']})",
        f"- Candidate: `{candidate['mode']}` (strict={candidate['strict_three_layer_enabled']})",
        "",
        "## Bootstrap",
        "",
        f"- Baseline: `{comparison['bootstrap']['baseline_ms']} ms`",
        f"- Candidate: `{comparison['bootstrap']['candidate_ms']} ms`",
        f"- Delta: `{comparison['bootstrap']['delta_ms']} ms` (`{comparison['bootstrap']['delta_pct']}%`)",
        "",
        "## /next Turn Latency",
        "",
        f"- Avg delta: `{turn_deltas['avg_ms']['delta_ms']} ms` (`{turn_deltas['avg_ms']['delta_pct']}%`)",
        f"- P50 delta: `{turn_deltas['p50_ms']['delta_ms']} ms` (`{turn_deltas['p50_ms']['delta_pct']}%`)",
        f"- P95 delta: `{turn_deltas['p95_ms']['delta_ms']} ms` (`{turn_deltas['p95_ms']['delta_pct']}%`)",
        "",
        "## Throughput",
        "",
        f"- Baseline turns/sec: `{baseline['throughput_turns_per_second']}`",
        f"- Candidate turns/sec: `{candidate['throughput_turns_per_second']}`",
        "",
    ]
    return "\n".join(lines).strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark strict 3-layer architecture impact on storylet (/next) generation latency.",
    )
    parser.add_argument("--turns", type=int, default=DEFAULT_TURNS)
    parser.add_argument("--storylet-count", type=int, default=DEFAULT_STORYLET_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--model-id", default="")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--startup-timeout-seconds", type=float, default=DEFAULT_STARTUP_TIMEOUT_SECONDS)
    parser.add_argument("--off-port", type=int, default=8011)
    parser.add_argument("--on-port", type=int, default=8012)
    parser.add_argument("--world-theme", default=DEFAULT_WORLD_THEME)
    parser.add_argument("--player-role", default=DEFAULT_PLAYER_ROLE)
    parser.add_argument("--description", default=DEFAULT_DESCRIPTION)
    parser.add_argument("--key-elements", default=",".join(DEFAULT_KEY_ELEMENTS))
    parser.add_argument("--tone", default=DEFAULT_TONE)
    parser.add_argument("--skip-bootstrap", action="store_true")
    parser.add_argument("--disable-ai", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if int(args.turns) < 1:
        print("Error: --turns must be >= 1", file=sys.stderr)
        return 2
    if int(args.storylet_count) < 5:
        print("Error: --storylet-count must be >= 5", file=sys.stderr)
        return 2
    if float(args.timeout_seconds) < 5.0:
        print("Error: --timeout-seconds must be >= 5", file=sys.stderr)
        return 2
    if int(args.off_port) == int(args.on_port):
        print("Error: --off-port and --on-port must differ", file=sys.stderr)
        return 2

    key_elements = [part.strip() for part in str(args.key_elements).split(",") if part.strip()]
    if not key_elements:
        key_elements = list(DEFAULT_KEY_ELEMENTS)

    out_root = (ROOT / args.out_dir).resolve()
    run_dir = out_root / _timestamp_slug().lower()
    run_dir.mkdir(parents=True, exist_ok=True)

    extra_env: Dict[str, str] = {}
    if bool(args.disable_ai):
        extra_env["DW_DISABLE_AI"] = "1"
    modes = [
        ModeConfig(label="strict_off", strict_three_layer=False, port=int(args.off_port)),
        ModeConfig(label="strict_on", strict_three_layer=True, port=int(args.on_port)),
    ]

    print(f"[benchmark] run dir: {_path_label(run_dir)}")
    print(f"[benchmark] turns per mode: {int(args.turns)}")
    print(f"[benchmark] timeout seconds: {float(args.timeout_seconds)}")
    print(f"[benchmark] model: {str(args.model_id or 'unchanged')}")

    mode_results: List[Dict[str, Any]] = []
    for mode in modes:
        print(f"[benchmark] mode={mode.label} strict={mode.strict_three_layer} port={mode.port}")
        result = run_mode_benchmark(
            mode=mode,
            base_output_dir=run_dir,
            timeout_seconds=float(args.timeout_seconds),
            startup_timeout_seconds=float(args.startup_timeout_seconds),
            turns=int(args.turns),
            storylet_count=int(args.storylet_count),
            seed=int(args.seed),
            model_id=str(args.model_id or "").strip(),
            world_theme=str(args.world_theme).strip(),
            player_role=str(args.player_role).strip(),
            description=str(args.description).strip(),
            key_elements=key_elements,
            tone=str(args.tone).strip(),
            include_bootstrap=not bool(args.skip_bootstrap),
            extra_env=extra_env,
        )
        mode_results.append(result)

    comparison = _build_comparison(mode_results[0], mode_results[1])
    report = {
        "timestamp_utc": _utc_now(),
        "commit": _git_commit(),
        "turns": int(args.turns),
        "storylet_count": int(args.storylet_count),
        "timeout_seconds": float(args.timeout_seconds),
        "startup_timeout_seconds": float(args.startup_timeout_seconds),
        "skip_bootstrap": bool(args.skip_bootstrap),
        "disable_ai": bool(args.disable_ai),
        "model_id": str(args.model_id or "").strip(),
        "modes": mode_results,
        "comparison": comparison,
    }

    report_json_path = run_dir / "benchmark_three_layer.json"
    report_md_path = run_dir / "benchmark_three_layer.md"
    _write_json(report_json_path, report)
    report_md_path.write_text(_render_markdown(report), encoding="utf-8")

    print(f"[benchmark] report json: {_path_label(report_json_path)}")
    print(f"[benchmark] report md: {_path_label(report_md_path)}")
    print(f"[benchmark] avg /next delta (strict_on - strict_off): " f"{comparison['turn_latency_deltas']['avg_ms']['delta_ms']} ms " f"({comparison['turn_latency_deltas']['avg_ms']['delta_pct']}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
