#!/usr/bin/env python
"""Developer command surface for local WorldWeaver workflows."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
CLIENT_ENV_FILE = ROOT / "client" / ".env.local"
API_KEY_NAMES = ("OPENROUTER_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY")
DEFAULT_LINT_SCOPE = ("src/api", "src/services", "src/models", "main.py")
DEFAULT_LINT_EXTENDED_SCOPE = (
    "src/api",
    "src/services",
    "src/models",
    "tests",
    "scripts",
    "main.py",
)
DEFAULT_WARNING_BUDGET_FILE = ROOT / "improvements" / "pytest-warning-baseline.json"
PYTEST_WARNING_RE = re.compile(r"(\d+)\s+warnings?\b", re.IGNORECASE)
DEFAULT_RUNTIME_DB_PATHS = ("worldweaver.db", "db/worldweaver.db")
DEFAULT_TEST_DB_PATHS = ("test_database.db", "test_env_integration.db")


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


def _has_api_key(file_env: dict[str, str]) -> bool:
    return any((os.environ.get(name) or file_env.get(name) or "").strip() for name in API_KEY_NAMES)


def _resolve_compose_command() -> list[str] | None:
    docker_path = shutil.which("docker")
    if docker_path:
        try:
            rc = subprocess.call(
                [docker_path, "compose", "version"],
                cwd=str(ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            rc = 1
        if rc == 0:
            return ["docker", "compose"]

    legacy = shutil.which("docker-compose")
    if legacy:
        return ["docker-compose"]

    return None


def run_install() -> int:
    pip_rc = _run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    if pip_rc != 0:
        return pip_rc
    return _run(["npm", "--prefix", "client", "install"])


def run_static_checks() -> int:
    """Run baseline static checks that are expected to stay green."""
    build_rc = _run(["npm", "--prefix", "client", "run", "build"])
    if build_rc != 0:
        return build_rc
    return _run([sys.executable, "-m", "compileall", "src", "main.py"])


def run_lint(paths: list[str]) -> int:
    ruff_rc = _run([sys.executable, "-m", "ruff", "check", *paths])
    if ruff_rc != 0:
        return ruff_rc
    return _run([sys.executable, "-m", "black", "--check", *paths])


def run_gate3() -> int:
    """Run Gate 3 static health checks on canonical backend scope."""
    lint_rc = run_lint(list(DEFAULT_LINT_SCOPE))
    if lint_rc != 0:
        return lint_rc
    return run_static_checks()


def run_gate3_strict() -> int:
    """Run strict Gate 3 checks on extended backend scope."""
    lint_rc = run_lint(list(DEFAULT_LINT_EXTENDED_SCOPE))
    if lint_rc != 0:
        return lint_rc
    return run_static_checks()


def _extract_pytest_warning_count(output: str) -> int:
    """Parse warning count from pytest output summary."""
    matches = PYTEST_WARNING_RE.findall(output)
    if not matches:
        return 0
    return int(matches[-1])


def _load_pytest_warning_budget(path: Path) -> tuple[int, int]:
    """Load warning baseline + allowed increase from artifact."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    baseline = int(payload.get("baseline_warning_count", 0))
    max_increase = int(payload.get("max_allowed_increase", 0))
    return baseline, max_increase


def run_pytest_warning_budget(*, budget_file: Path = DEFAULT_WARNING_BUDGET_FILE) -> int:
    """Run pytest and fail when warning count exceeds budget."""
    if not budget_file.exists():
        _print_result(
            "FAIL",
            f"warning budget artifact not found: {budget_file}",
        )
        return 2

    baseline, max_increase = _load_pytest_warning_budget(budget_file)
    allowed = baseline + max_increase

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    if result.returncode != 0:
        return int(result.returncode)

    output = f"{result.stdout}\n{result.stderr}"
    actual = _extract_pytest_warning_count(output)
    _print_result(
        "INFO",
        ("pytest warning budget check: " f"actual={actual}, baseline={baseline}, max_increase={max_increase}, allowed={allowed}"),
    )
    if actual > allowed:
        _print_result(
            "FAIL",
            f"pytest warning budget exceeded by {actual - allowed} warning(s)",
        )
        return 1
    _print_result("PASS", "pytest warning budget check passed")
    return 0


def run_quality_strict() -> int:
    """Run strict static gates plus pytest warning-budget enforcement."""
    gate_rc = run_gate3_strict()
    if gate_rc != 0:
        return gate_rc
    return run_pytest_warning_budget()


def run_preflight(*, require_docker: bool = False) -> int:
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

    compose_cmd = _resolve_compose_command()
    if compose_cmd:
        _print_result("PASS", f"docker compose: {' '.join(compose_cmd)}")
    elif require_docker:
        failures += 1
        _print_result(
            "FAIL",
            "docker compose unavailable (install Docker Desktop or docker-compose)",
        )
    else:
        _print_result("WARN", "docker compose not found (optional for manual runtime path)")

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
    has_api_key = _has_api_key(file_env)
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


def run_stack_up(*, build: bool) -> int:
    preflight_rc = run_preflight(require_docker=True)
    if preflight_rc != 0:
        return preflight_rc

    compose_cmd = _resolve_compose_command()
    if not compose_cmd:
        _print_result("FAIL", "docker compose command unavailable")
        return 1

    cmd = [*compose_cmd, "up", "-d"]
    if build:
        cmd.append("--build")
    return _run(cmd)


def run_stack_down(*, volumes: bool) -> int:
    compose_cmd = _resolve_compose_command()
    if not compose_cmd:
        _print_result("FAIL", "docker compose command unavailable")
        return 1

    cmd = [*compose_cmd, "down", "--remove-orphans"]
    if volumes:
        cmd.append("--volumes")
    return _run(cmd)


def run_stack_logs(*, service: str | None, follow: bool) -> int:
    compose_cmd = _resolve_compose_command()
    if not compose_cmd:
        _print_result("FAIL", "docker compose command unavailable")
        return 1

    cmd = [*compose_cmd, "logs"]
    if follow:
        cmd.append("--follow")
    if service:
        cmd.append(service)
    return _run(cmd)


def _collect_db_reset_targets(*, include_test_dbs: bool) -> list[Path]:
    targets: list[Path] = []
    for rel_path in DEFAULT_RUNTIME_DB_PATHS:
        targets.append(ROOT / rel_path)

    env_values = _load_env_file(ENV_FILE)
    custom_path_raw = (os.environ.get("DW_DB_PATH") or env_values.get("DW_DB_PATH") or "").strip()
    if custom_path_raw:
        custom = Path(custom_path_raw)
        if not custom.is_absolute():
            custom = ROOT / custom
        if ROOT in custom.resolve().parents or custom.resolve() == ROOT:
            targets.append(custom)

    if include_test_dbs:
        for rel_path in DEFAULT_TEST_DB_PATHS:
            targets.append(ROOT / rel_path)

    # De-duplicate while preserving order.
    seen: set[str] = set()
    deduped: list[Path] = []
    for target in targets:
        key = str(target.resolve())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(target)
    return deduped


def run_reset_data(*, confirm: bool, include_test_dbs: bool) -> int:
    targets = _collect_db_reset_targets(include_test_dbs=include_test_dbs)
    existing = [path for path in targets if path.exists()]

    if not existing:
        _print_result("PASS", "no local sqlite files matched reset targets")
        return 0

    if not confirm:
        _print_result("FAIL", "reset-data requires --yes to delete local sqlite files")
        for path in existing:
            _print_result("INFO", f"target: {path}")
        return 2

    for path in existing:
        path.unlink()
        _print_result("PASS", f"deleted {path}")
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "sweep":
        return _run([sys.executable, "playtest_harness/parameter_sweep.py", *sys.argv[2:]])
    if len(sys.argv) >= 2 and sys.argv[1] == "benchmark-three-layer":
        return _run([sys.executable, "scripts/benchmark_three_layer.py", *sys.argv[2:]])

    parser = argparse.ArgumentParser(description="WorldWeaver dev command surface")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("install", help="install backend and client dependencies")
    sub.add_parser("preflight", help="validate local runtime prerequisites")
    stack_up_parser = sub.add_parser("stack-up", help="start docker compose dev stack")
    stack_up_parser.add_argument(
        "--no-build",
        action="store_true",
        help="skip image rebuild while starting the stack",
    )
    stack_down_parser = sub.add_parser("stack-down", help="stop docker compose dev stack")
    stack_down_parser.add_argument(
        "--volumes",
        action="store_true",
        help="also remove compose volumes",
    )
    stack_logs_parser = sub.add_parser("stack-logs", help="view docker compose logs")
    stack_logs_parser.add_argument("service", nargs="?", help="optional compose service name")
    stack_logs_parser.add_argument(
        "--follow",
        action="store_true",
        help="stream log output",
    )
    sub.add_parser("backend", help="run backend server")
    sub.add_parser("client", help="run client dev server")
    sub.add_parser("test", help="run backend test suite")
    sub.add_parser("build", help="run client build")
    sub.add_parser("static", help="run baseline static checks (client build + compileall)")
    lint_parser = sub.add_parser(
        "lint",
        help="run ruff + black checks on explicit paths (or use --all for canonical scope)",
    )
    lint_parser.add_argument("paths", nargs="*", help="files/directories to lint")
    lint_parser.add_argument(
        "--all",
        action="store_true",
        help="lint canonical backend scope (src/api src/services src/models main.py)",
    )
    sub.add_parser(
        "lint-all",
        help="lint canonical backend scope (ruff + black check)",
    )
    sub.add_parser(
        "lint-extended",
        help="lint extended backend scope (src/api src/services src/models tests scripts main.py)",
    )
    sub.add_parser(
        "gate3",
        help="run Gate 3 static health checks (lint-all + static)",
    )
    sub.add_parser(
        "gate3-strict",
        help="run strict Gate 3 static health checks (lint-extended + static)",
    )
    sub.add_parser(
        "pytest-warning-budget",
        help="run pytest and enforce warning budget from improvements/pytest-warning-baseline.json",
    )
    sub.add_parser(
        "quality-strict",
        help="run strict static checks plus pytest warning budget",
    )
    sub.add_parser("verify", help="run tests + baseline static checks")
    sub.add_parser("eval", help="run full narrative evaluation harness with thresholds")
    sub.add_parser("eval-smoke", help="run smoke narrative evaluation harness with thresholds")
    sub.add_parser("sweep", help="run two-phase LLM parameter sweep harness")
    sub.add_parser(
        "benchmark-three-layer",
        help="benchmark strict 3-layer OFF vs ON storylet generation latency",
    )
    reset_parser = sub.add_parser("reset-data", help="delete local runtime sqlite data files")
    reset_parser.add_argument(
        "--yes",
        action="store_true",
        help="confirm deletion of matched files",
    )
    reset_parser.add_argument(
        "--include-test-dbs",
        action="store_true",
        help="also delete test sqlite files",
    )

    args = parser.parse_args()

    if args.command == "install":
        return run_install()
    if args.command == "preflight":
        return run_preflight()
    if args.command == "stack-up":
        return run_stack_up(build=not bool(args.no_build))
    if args.command == "stack-down":
        return run_stack_down(volumes=bool(args.volumes))
    if args.command == "stack-logs":
        return run_stack_logs(
            service=(str(args.service).strip() if args.service else None),
            follow=bool(args.follow),
        )
    if args.command == "backend":
        return _run([sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"])
    if args.command == "client":
        return _run(["npm", "--prefix", "client", "run", "dev"])
    if args.command == "test":
        return _run([sys.executable, "-m", "pytest", "-q"])
    if args.command == "build":
        return _run(["npm", "--prefix", "client", "run", "build"])
    if args.command == "static":
        return run_static_checks()
    if args.command == "lint":
        lint_paths = list(args.paths)
        if args.all:
            lint_paths.extend(DEFAULT_LINT_SCOPE)

        # Preserve first occurrence order while removing duplicates.
        seen: set[str] = set()
        ordered_paths: list[str] = []
        for path in lint_paths:
            if path not in seen:
                ordered_paths.append(path)
                seen.add(path)

        if not ordered_paths:
            ordered_paths = list(DEFAULT_LINT_SCOPE)

        return run_lint(ordered_paths)
    if args.command == "lint-all":
        return run_lint(list(DEFAULT_LINT_SCOPE))
    if args.command == "lint-extended":
        return run_lint(list(DEFAULT_LINT_EXTENDED_SCOPE))
    if args.command == "gate3":
        return run_gate3()
    if args.command == "gate3-strict":
        return run_gate3_strict()
    if args.command == "pytest-warning-budget":
        return run_pytest_warning_budget()
    if args.command == "quality-strict":
        return run_quality_strict()
    if args.command == "verify":
        test_rc = _run([sys.executable, "-m", "pytest", "-q"])
        if test_rc != 0:
            return test_rc
        return run_static_checks()
    if args.command == "eval":
        return _run([sys.executable, "scripts/eval_narrative.py", "--enforce"])
    if args.command == "eval-smoke":
        return _run([sys.executable, "scripts/eval_narrative.py", "--smoke", "--enforce"])
    if args.command == "benchmark-three-layer":
        return _run([sys.executable, "scripts/benchmark_three_layer.py"])
    if args.command == "reset-data":
        return run_reset_data(
            confirm=bool(args.yes),
            include_test_dbs=bool(args.include_test_dbs),
        )

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
