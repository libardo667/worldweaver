#!/usr/bin/env python
"""API-first, file-driven playtest harness for external LLM operators.

This harness is intentionally distinct from playtest_harness:
- It drives the game exclusively through HTTP endpoints (/next, /action).
- It persists turn and decision artifacts to disk each step.
- It supports agent-style workflows where an external LLM reads a turn file,
  writes decision JSON, then this harness advances one turn.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playtest_harness.long_run_harness import DEFAULT_BASE_URL, SCENARIOS

DEFAULT_OUT_DIR = Path("playtests") / "agent_runs" / "api_first"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 240.0
DEFAULT_STARTUP_TIMEOUT_SECONDS = 120.0
DEFAULT_STORYLET_COUNT = 8
DEFAULT_SPAWN_PORT = 8010


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ").lower()


def _split_csv(value: str) -> List[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _normalize_base_url(raw: str) -> str:
    base = str(raw or "").strip().rstrip("/")
    if not base:
        base = DEFAULT_BASE_URL
    if not base.endswith("/api"):
        base = f"{base}/api"
    return base


def _request_json(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    response = requests.request(method=method, url=url, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected object JSON response from {url}, got {type(data).__name__}")
    return data


def _wait_readiness(base_url: str, timeout_seconds: float) -> None:
    deadline = time.time() + max(1.0, float(timeout_seconds))
    last_error: Optional[str] = None
    while time.time() < deadline:
        try:
            payload = _request_json("GET", f"{base_url}/settings/readiness", timeout=5.0)
            if bool(payload.get("ready")):
                return
            missing = payload.get("missing", [])
            last_error = f"readiness pending; missing={missing}"
        except Exception as exc:  # pragma: no cover - transient startup states
            last_error = str(exc)
        time.sleep(1.0)
    raise RuntimeError(last_error or "backend readiness timed out")


def _json_dump(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _latest_turn_number(turns_dir: Path) -> int:
    turn_numbers: List[int] = []
    for turn_file in turns_dir.glob("turn_*.json"):
        stem = turn_file.stem
        try:
            turn_numbers.append(int(stem.split("_", 1)[1]))
        except Exception:
            continue
    if not turn_numbers:
        raise RuntimeError(f"No turn files found in {turns_dir}")
    return max(turn_numbers)


def _extract_narrative(turn_payload: Dict[str, Any]) -> str:
    text = turn_payload.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()
    narrative = turn_payload.get("narrative")
    if isinstance(narrative, str) and narrative.strip():
        return narrative.strip()
    return ""


def _normalize_choices(raw: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        if not label:
            continue
        set_payload = item.get("set", {})
        if not isinstance(set_payload, dict):
            set_payload = {}
        out.append({"label": label, "set": set_payload})
    return out


def _match_choice(choices: List[Dict[str, Any]], requested_label: str) -> Optional[Dict[str, Any]]:
    needle = str(requested_label or "").strip().lower()
    if not needle:
        return None
    for choice in choices:
        label = str(choice.get("label", "")).strip().lower()
        if label == needle:
            return choice
    for choice in choices:
        label = str(choice.get("label", "")).strip().lower()
        if needle in label or label in needle:
            return choice
    return None


def _scenario_world_payload(args: argparse.Namespace) -> Dict[str, Any]:
    scenario_id = str(args.scenario or "mystery")
    scenario = SCENARIOS.get(scenario_id)
    if not isinstance(scenario, dict):
        raise RuntimeError(f"Unknown scenario '{scenario_id}'")

    roles = scenario.get("roles") or ["adventurer"]
    role_default = str(roles[0]) if roles else "adventurer"
    role = str(args.role).strip() if args.role else role_default

    key_elements = _split_csv(args.key_elements) if args.key_elements else [str(x) for x in (scenario.get("key_elements") or [])]
    key_elements = [item.strip() for item in key_elements if item.strip()]
    if not key_elements:
        key_elements = ["risk", "tradeoff", "mystery"]

    return {
        "scenario_id": scenario_id,
        "scenario_title": str(scenario.get("title", scenario_id)),
        "theme": str(args.theme).strip() if args.theme else str(scenario.get("theme", "")),
        "role": role,
        "description": str(args.description).strip() if args.description else str(scenario.get("description", "")),
        "tone": str(args.tone).strip() if args.tone else str(scenario.get("tone", "")),
        "key_elements": key_elements,
    }


def _spawn_backend(run_dir: Path, port: int) -> Dict[str, Any]:
    out_path = run_dir / "backend.out.log"
    err_path = run_dir / "backend.err.log"
    out_handle = out_path.open("w", encoding="utf-8")
    err_handle = err_path.open("w", encoding="utf-8")
    cmd = [sys.executable, "-m", "uvicorn", "main:app", "--port", str(port)]
    process = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=out_handle,
        stderr=err_handle,
        text=True,
    )
    (run_dir / "backend.pid").write_text(str(process.pid), encoding="utf-8")
    return {
        "mode": "spawned",
        "pid": process.pid,
        "port": int(port),
        "command": cmd,
        "stdout_log": str(out_path),
        "stderr_log": str(err_path),
    }


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        line = (result.stdout or "").strip().lower()
        if not line:
            return False
        if "no tasks are running" in line:
            return False
        return str(pid) in line
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _stop_pid(pid: int, timeout_seconds: float = 8.0) -> bool:
    if not _pid_running(pid):
        return True
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T"],
            capture_output=True,
            text=True,
            check=False,
        )
        deadline = time.time() + max(0.5, float(timeout_seconds))
        while time.time() < deadline:
            if not _pid_running(pid):
                return True
            time.sleep(0.2)
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        time.sleep(0.2)
        return not _pid_running(pid)
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return not _pid_running(pid)

    deadline = time.time() + max(0.5, float(timeout_seconds))
    while time.time() < deadline:
        if not _pid_running(pid):
            return True
        time.sleep(0.2)

    # Last resort for stubborn process
    try:
        if hasattr(signal, "SIGKILL"):
            os.kill(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    time.sleep(0.2)
    return not _pid_running(pid)


def _load_manifest(run_dir: Path) -> Dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"manifest missing: {manifest_path}")
    payload = _load_json(manifest_path)
    if not isinstance(payload, dict):
        raise RuntimeError(f"invalid manifest JSON in {manifest_path}")
    return payload


def _save_manifest(run_dir: Path, manifest: Dict[str, Any]) -> None:
    _json_dump(run_dir / "manifest.json", manifest)


def _cmd_init(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    run_id = _timestamp_slug()
    run_dir = out_dir / run_id
    turns_dir = run_dir / "turns"
    decisions_dir = run_dir / "decisions"
    inbox_dir = run_dir / "inbox"
    run_dir.mkdir(parents=True, exist_ok=False)
    turns_dir.mkdir(parents=True, exist_ok=True)
    decisions_dir.mkdir(parents=True, exist_ok=True)
    inbox_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "LATEST.txt").write_text(run_id, encoding="utf-8")

    world = _scenario_world_payload(args)
    seed_value = int(args.seed)
    request_timeout = float(args.request_timeout_seconds)

    backend: Dict[str, Any] = {}
    base_url: str
    session_id = str(args.session_id).strip() if args.session_id else f"api-first-{run_id}"

    try:
        if args.reuse_backend:
            base_url = _normalize_base_url(args.base_url)
            backend = {"mode": "reuse", "spawned": False}
        else:
            port = int(args.spawn_port)
            backend = _spawn_backend(run_dir=run_dir, port=port)
            base_url = _normalize_base_url(f"http://127.0.0.1:{port}/api")

        _wait_readiness(base_url=base_url, timeout_seconds=float(args.startup_timeout_seconds))
        _request_json("POST", f"{base_url}/dev/hard-reset", timeout=request_timeout)

        bootstrap = _request_json(
            "POST",
            f"{base_url}/session/bootstrap",
            payload={
                "session_id": session_id,
                "world_theme": world["theme"],
                "player_role": world["role"],
                "description": world["description"],
                "key_elements": world["key_elements"],
                "tone": world["tone"],
                "storylet_count": int(args.storylet_count),
                "bootstrap_source": "api-first-harness",
            },
            timeout=request_timeout,
        )
        first_turn = _request_json(
            "POST",
            f"{base_url}/next",
            payload={"session_id": session_id, "vars": {}},
            timeout=request_timeout,
        )
    except Exception:
        if backend.get("mode") == "spawned":
            pid = int(backend.get("pid", 0) or 0)
            if pid:
                _stop_pid(pid)
        raise

    _json_dump(run_dir / "bootstrap.json", bootstrap)
    _json_dump(turns_dir / "turn_1.json", first_turn)
    (run_dir / "session.txt").write_text(session_id, encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "created_at": _utc_now_iso(),
        "status": "active",
        "seed": seed_value,
        "base_url": base_url,
        "request_timeout_seconds": request_timeout,
        "storylet_count": int(args.storylet_count),
        "current_turn": 1,
        "session_id": session_id,
        "world": world,
        "backend": backend,
    }
    _save_manifest(run_dir, manifest)

    print(f"[api-first] run dir: {run_dir}")
    print(f"[api-first] session: {session_id}")
    print("[api-first] created turn_1.json")
    print(
        "[api-first] next step: "
        f"python playtest_api_harness/api_first_llm_playtest.py emit-prompt --run-dir {run_dir}"
    )
    return 0


def _build_prompt_text(run_dir: Path, latest_turn_no: int, latest_turn: Dict[str, Any], history_turns: int) -> str:
    narrative = _extract_narrative(latest_turn)
    choices = _normalize_choices(latest_turn.get("choices", []))
    vars_payload = latest_turn.get("vars", {})
    if not isinstance(vars_payload, dict):
        vars_payload = {}

    decisions_dir = run_dir / "decisions"
    recent_decisions: List[Dict[str, Any]] = []
    start = max(1, latest_turn_no - max(1, int(history_turns)))
    for decision_turn in range(start, latest_turn_no + 1):
        path = decisions_dir / f"decision_{decision_turn}.json"
        if not path.exists():
            continue
        payload = _load_json(path)
        recent_decisions.append(
            {
                "from_turn": payload.get("from_turn"),
                "mode": payload.get("mode"),
                "choice_label": payload.get("choice_label"),
                "action_text": payload.get("action_text"),
                "rationale": payload.get("rationale"),
            }
        )

    choice_labels = [str(item.get("label", "")).strip() for item in choices]
    target_decision_file = run_dir / "inbox" / f"decision_{latest_turn_no}.json"
    schema = {
        "mode": "choice or freeform",
        "choice_label": "required when mode=choice",
        "action_text": "required when mode=freeform",
        "rationale": "short reason (optional but recommended)",
    }
    lines: List[str] = []
    lines.append("# LLM Turn Decision Prompt")
    lines.append("")
    lines.append(f"Turn Number: {latest_turn_no}")
    lines.append(f"Write JSON decision to: `{target_decision_file}`")
    lines.append("")
    lines.append("Return strict JSON object only with this schema:")
    lines.append("```json")
    lines.append(json.dumps(schema, indent=2, ensure_ascii=True))
    lines.append("```")
    lines.append("")
    lines.append("Current Narrative:")
    lines.append("```text")
    lines.append(narrative or "(empty narrative)")
    lines.append("```")
    lines.append("")
    lines.append("Available Choices (exact labels):")
    lines.append("```json")
    lines.append(json.dumps(choice_labels, indent=2, ensure_ascii=True))
    lines.append("```")
    lines.append("")
    lines.append("Current Vars Snapshot:")
    lines.append("```json")
    lines.append(json.dumps(vars_payload, indent=2, ensure_ascii=True))
    lines.append("```")
    lines.append("")
    lines.append("Recent Decisions:")
    lines.append("```json")
    lines.append(json.dumps(recent_decisions, indent=2, ensure_ascii=True))
    lines.append("```")
    return "\n".join(lines)


def _cmd_emit_prompt(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    manifest = _load_manifest(run_dir)
    turns_dir = run_dir / "turns"
    latest_turn_no = _latest_turn_number(turns_dir)
    latest_turn = _load_json(turns_dir / f"turn_{latest_turn_no}.json")
    prompt_text = _build_prompt_text(
        run_dir=run_dir,
        latest_turn_no=latest_turn_no,
        latest_turn=latest_turn,
        history_turns=int(args.history_turns),
    )

    out_path = Path(args.out_file) if args.out_file else (run_dir / "inbox" / f"prompt_turn_{latest_turn_no}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(prompt_text, encoding="utf-8")
    manifest["updated_at"] = _utc_now_iso()
    _save_manifest(run_dir, manifest)
    print(f"[api-first] prompt written: {out_path}")
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    manifest = _load_manifest(run_dir)
    turns_dir = run_dir / "turns"
    latest_turn_no = _latest_turn_number(turns_dir)
    latest_turn = _load_json(turns_dir / f"turn_{latest_turn_no}.json")
    choices = _normalize_choices(latest_turn.get("choices", []))
    next_decision_file = run_dir / "inbox" / f"decision_{latest_turn_no}.json"

    print(f"[api-first] run dir: {run_dir}")
    print(f"[api-first] status: {manifest.get('status', 'unknown')}")
    print(f"[api-first] latest turn: {latest_turn_no}")
    print(f"[api-first] decision file expected: {next_decision_file}")
    print(f"[api-first] choices available: {len(choices)}")
    for choice in choices:
        print(f"- {choice['label']}")
    return 0


def _cmd_step(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    manifest = _load_manifest(run_dir)
    turns_dir = run_dir / "turns"
    decisions_dir = run_dir / "decisions"

    latest_turn_no = _latest_turn_number(turns_dir)
    latest_turn = _load_json(turns_dir / f"turn_{latest_turn_no}.json")
    choices = _normalize_choices(latest_turn.get("choices", []))

    decision_path = Path(args.decision_file) if args.decision_file else (run_dir / "inbox" / f"decision_{latest_turn_no}.json")
    if not decision_path.exists():
        raise RuntimeError(f"decision file missing: {decision_path}")
    decision_raw = _load_json(decision_path)

    mode = str(decision_raw.get("mode", "choice")).strip().lower()
    if mode not in {"choice", "freeform"}:
        mode = "choice"
    rationale = str(decision_raw.get("rationale", "")).strip()

    base_url = _normalize_base_url(str(manifest.get("base_url", DEFAULT_BASE_URL)))
    session_id = str(manifest.get("session_id", "")).strip()
    if not session_id:
        raise RuntimeError("manifest missing session_id")

    request_timeout = float(args.request_timeout_seconds or manifest.get("request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS))

    normalized_decision: Dict[str, Any] = {
        "from_turn": latest_turn_no,
        "to_turn": latest_turn_no + 1,
        "timestamp_utc": _utc_now_iso(),
        "mode": mode,
        "rationale": rationale,
    }

    if mode == "freeform":
        action_text = str(decision_raw.get("action_text", "")).strip()
        if not action_text:
            raise RuntimeError("freeform decision missing action_text")
        response_payload = _request_json(
            "POST",
            f"{base_url}/action",
            payload={
                "session_id": session_id,
                "action": action_text,
                "idempotency_key": f"api-first-{session_id}-{latest_turn_no}",
            },
            timeout=request_timeout,
        )
        normalized_decision["action_text"] = action_text
        normalized_decision["choice_label"] = ""
        normalized_decision["fallback_used"] = False
    else:
        requested = str(decision_raw.get("choice_label", "")).strip()
        matched = _match_choice(choices, requested)
        fallback_used = False
        if matched is None:
            if not choices:
                raise RuntimeError("mode=choice but current turn has no choices; use mode=freeform")
            matched = choices[0]
            fallback_used = True
        vars_payload = matched.get("set", {})
        if not isinstance(vars_payload, dict):
            vars_payload = {}
        response_payload = _request_json(
            "POST",
            f"{base_url}/next",
            payload={"session_id": session_id, "vars": vars_payload},
            timeout=request_timeout,
        )
        normalized_decision["choice_label"] = str(matched.get("label", ""))
        normalized_decision["requested_choice_label"] = requested
        normalized_decision["vars_sent"] = vars_payload
        normalized_decision["fallback_used"] = fallback_used
        normalized_decision["action_text"] = ""

    _json_dump(decisions_dir / f"decision_{latest_turn_no}.json", normalized_decision)
    _json_dump(turns_dir / f"turn_{latest_turn_no + 1}.json", response_payload)

    manifest["current_turn"] = latest_turn_no + 1
    manifest["updated_at"] = _utc_now_iso()
    _save_manifest(run_dir, manifest)

    print(f"[api-first] wrote decision_{latest_turn_no}.json")
    print(f"[api-first] wrote turn_{latest_turn_no + 1}.json")
    print(
        "[api-first] next step: "
        f"python playtest_api_harness/api_first_llm_playtest.py emit-prompt --run-dir {run_dir}"
    )
    return 0


def _cmd_finalize(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    manifest = _load_manifest(run_dir)
    turns_dir = run_dir / "turns"
    decisions_dir = run_dir / "decisions"

    turn_numbers = sorted(
        int(path.stem.split("_", 1)[1])
        for path in turns_dir.glob("turn_*.json")
        if path.stem.startswith("turn_")
    )
    if not turn_numbers:
        raise RuntimeError(f"no turn files found in {turns_dir}")

    lines: List[str] = []
    lines.append("# API-First LLM Playtest Transcript")
    lines.append("")
    lines.append(f"Run ID: `{manifest.get('run_id', '')}`")
    lines.append(f"Session: `{manifest.get('session_id', '')}`")
    lines.append(f"Created: `{manifest.get('created_at', '')}`")
    lines.append("")

    for turn_no in turn_numbers:
        turn_payload = _load_json(turns_dir / f"turn_{turn_no}.json")
        narrative = _extract_narrative(turn_payload)
        choices = _normalize_choices(turn_payload.get("choices", []))
        decision_path = decisions_dir / f"decision_{turn_no}.json"
        decision_payload: Optional[Dict[str, Any]] = _load_json(decision_path) if decision_path.exists() else None

        lines.append(f"## Turn {turn_no}")
        lines.append("")
        lines.append(narrative or "(empty narrative)")
        lines.append("")
        if decision_payload:
            mode = str(decision_payload.get("mode", "")).strip()
            if mode == "freeform":
                lines.append(f"Action for next turn (freeform): `{decision_payload.get('action_text', '')}`")
            else:
                lines.append(f"Action for next turn (choice): `{decision_payload.get('choice_label', '')}`")
            reason = str(decision_payload.get("rationale", "")).strip()
            if reason:
                lines.append(f"Rationale: {reason}")
            lines.append("")
        if choices:
            lines.append("Choices shown:")
            for choice in choices:
                lines.append(f"- {choice['label']}")
            lines.append("")

    transcript_path = run_dir / "transcript.md"
    transcript_path.write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "turn_count": len(turn_numbers),
        "choice_decisions": len([p for p in decisions_dir.glob("decision_*.json") if _load_json(p).get("mode") == "choice"]),
        "freeform_decisions": len([p for p in decisions_dir.glob("decision_*.json") if _load_json(p).get("mode") == "freeform"]),
        "generated_at": _utc_now_iso(),
    }
    _json_dump(run_dir / "summary.json", summary)

    manifest["status"] = "finalized"
    manifest["updated_at"] = _utc_now_iso()
    _save_manifest(run_dir, manifest)

    print(f"[api-first] transcript: {transcript_path}")
    print(f"[api-first] summary: {run_dir / 'summary.json'}")
    return 0


def _cmd_stop(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    manifest = _load_manifest(run_dir)
    backend = manifest.get("backend", {})
    if not isinstance(backend, dict):
        backend = {}

    if backend.get("mode") != "spawned":
        print("[api-first] backend mode is reuse; nothing to stop")
        return 0

    pid = int(backend.get("pid", 0) or 0)
    if pid <= 0:
        print("[api-first] no pid recorded; nothing to stop")
        return 0

    stopped = _stop_pid(pid=pid, timeout_seconds=8.0)
    backend["stopped_at"] = _utc_now_iso()
    backend["stopped"] = bool(stopped)
    manifest["backend"] = backend
    manifest["updated_at"] = _utc_now_iso()
    if stopped and manifest.get("status") == "active":
        manifest["status"] = "stopped"
    _save_manifest(run_dir, manifest)

    if stopped:
        print(f"[api-first] stopped backend pid {pid}")
        return 0
    print(f"[api-first] failed to stop backend pid {pid}")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="API-first file-driven LLM playtest harness.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create a new run, optionally spawn backend, bootstrap, and fetch turn_1.")
    init_parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    init_parser.add_argument("--scenario", choices=sorted(SCENARIOS.keys()), default="mystery")
    init_parser.add_argument("--theme", default="")
    init_parser.add_argument("--role", default="")
    init_parser.add_argument("--description", default="")
    init_parser.add_argument("--key-elements", default="")
    init_parser.add_argument("--tone", default="")
    init_parser.add_argument("--storylet-count", type=int, default=DEFAULT_STORYLET_COUNT)
    init_parser.add_argument("--seed", type=int, default=20260305)
    init_parser.add_argument("--session-id", default="")
    init_parser.add_argument("--reuse-backend", action="store_true")
    init_parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    init_parser.add_argument("--spawn-port", type=int, default=DEFAULT_SPAWN_PORT)
    init_parser.add_argument("--startup-timeout-seconds", type=float, default=DEFAULT_STARTUP_TIMEOUT_SECONDS)
    init_parser.add_argument("--request-timeout-seconds", type=float, default=DEFAULT_REQUEST_TIMEOUT_SECONDS)

    status_parser = subparsers.add_parser("status", help="Show current run status and next expected decision file.")
    status_parser.add_argument("--run-dir", required=True)

    emit_parser = subparsers.add_parser("emit-prompt", help="Generate an LLM prompt file for the latest turn.")
    emit_parser.add_argument("--run-dir", required=True)
    emit_parser.add_argument("--out-file", default="")
    emit_parser.add_argument("--history-turns", type=int, default=4)

    step_parser = subparsers.add_parser("step", help="Apply one LLM decision JSON and advance exactly one turn.")
    step_parser.add_argument("--run-dir", required=True)
    step_parser.add_argument("--decision-file", default="")
    step_parser.add_argument("--request-timeout-seconds", type=float, default=0.0)

    finalize_parser = subparsers.add_parser("finalize", help="Render transcript + summary from turn and decision files.")
    finalize_parser.add_argument("--run-dir", required=True)

    stop_parser = subparsers.add_parser("stop", help="Stop backend process if this run spawned it.")
    stop_parser.add_argument("--run-dir", required=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        return _cmd_init(args)
    if args.command == "status":
        return _cmd_status(args)
    if args.command == "emit-prompt":
        return _cmd_emit_prompt(args)
    if args.command == "step":
        return _cmd_step(args)
    if args.command == "finalize":
        return _cmd_finalize(args)
    if args.command == "stop":
        return _cmd_stop(args)

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
