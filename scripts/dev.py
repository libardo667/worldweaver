#!/usr/bin/env python
"""Developer command surface for local WorldWeaver workflows."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
CLIENT_ENV_FILE = ROOT / "client" / ".env.local"
API_KEY_NAMES = ("OPENROUTER_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")


def _load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        data[key] = value
    return data


def _print_result(kind: str, message: str) -> None:
    print(f"[{kind}] {message}")


def _run(cmd: list[str]) -> int:
    executable = shutil.which(cmd[0]) or cmd[0]
    resolved = [executable, *cmd[1:]]
    return subprocess.call(resolved, cwd=str(ROOT))


def run_preflight() -> int:
    failures = 0

    _print_result("INFO", f"Running preflight from: {ROOT}")

    # Tooling checks
    python_bin = sys.executable
    if python_bin:
        _print_result("PASS", f"python: {python_bin}")
    else:
        failures += 1
        _print_result("FAIL", "python executable unavailable in current shell")

    for tool in ("node", "npm"):
        path = shutil.which(tool)
        if path:
            _print_result("PASS", f"{tool}: {path}")
        else:
            failures += 1
            _print_result(
                "FAIL",
                f"{tool} not found in PATH (install Node.js and reopen your shell)",
            )

    docker_path = shutil.which("docker")
    if docker_path:
        _print_result("PASS", f"docker (optional): {docker_path}")
    else:
        _print_result("WARN", "docker not found (optional until major 46 runtime stack)")

    # Env file checks
    if ENV_FILE.exists():
        _print_result("PASS", ".env present")
    else:
        failures += 1
        _print_result("FAIL", "missing .env (copy .env.example to .env)")

    if CLIENT_ENV_FILE.exists():
        _print_result("PASS", "client/.env.local present")
    else:
        _print_result(
            "WARN",
            "client/.env.local missing (create if you need client-only overrides)",
        )

    # API key checks (non-secret pass/fail only)
    file_env = _load_env_file(ENV_FILE)
    has_api_key = any(
        (os.environ.get(name) or file_env.get(name) or "").strip()
        for name in API_KEY_NAMES
    )
    if has_api_key:
        _print_result("PASS", "at least one API key is configured")
    else:
        failures += 1
        _print_result(
            "FAIL",
            "set one of OPENROUTER_API_KEY, LLM_API_KEY, or OPENAI_API_KEY in .env",
        )

    if failures:
        _print_result(
            "FAIL",
            f"preflight failed with {failures} blocking issue(s); fix and rerun",
        )
        return 1

    _print_result("PASS", "preflight passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="WorldWeaver dev command surface")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("preflight", help="validate local runtime prerequisites")
    sub.add_parser("backend", help="run backend server")
    sub.add_parser("client", help="run client dev server")
    sub.add_parser("test", help="run backend test suite")
    sub.add_parser("build", help="run client build")
    sub.add_parser("verify", help="run tests + build checks")
    sub.add_parser("eval", help="run full narrative evaluation harness with thresholds")
    sub.add_parser("eval-smoke", help="run smoke narrative evaluation harness with thresholds")

    args = parser.parse_args()

    if args.command == "preflight":
        return run_preflight()
    if args.command == "backend":
        return _run([sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"])
    if args.command == "client":
        return _run(["npm", "--prefix", "client", "run", "dev"])
    if args.command == "test":
        return _run([sys.executable, "-m", "pytest", "-q"])
    if args.command == "build":
        return _run(["npm", "--prefix", "client", "run", "build"])
    if args.command == "verify":
        test_rc = _run([sys.executable, "-m", "pytest", "-q"])
        if test_rc != 0:
            return test_rc
        return _run(["npm", "--prefix", "client", "run", "build"])
    if args.command == "eval":
        return _run([sys.executable, "scripts/eval_narrative.py", "--enforce"])
    if args.command == "eval-smoke":
        return _run([sys.executable, "scripts/eval_narrative.py", "--smoke", "--enforce"])

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
