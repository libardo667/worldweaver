#!/usr/bin/env python
"""Developer command surface for local WorldWeaver workflows."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = ROOT.parent
SHARDS_ROOT = WORKSPACE_ROOT / "shards"
ENV_FILE = ROOT / ".env"
CLIENT_ENV_FILE = ROOT / "client" / ".env.local"
CLIENT_COMPOSE_FILE = ROOT / "docker-compose.yml"
LEGACY_STACK_COMPOSE_FILE = ROOT / "docker-compose.legacy.yml"
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
HARNESS_COMMANDS = ("eval", "eval-smoke", "sweep", "llm-playtest", "benchmark-three-layer")
CLIENT_PROJECT = "ww_client"


@dataclass(frozen=True)
class ShardSpec:
    dir_name: str
    shard_dir: Path
    compose_file: Path
    env_file: Path
    shard_type: str
    city_id: str | None
    backend_port: str | None

    @property
    def display_name(self) -> str:
        return self.city_id or self.dir_name


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


def _print_legacy_stack_warning() -> None:
    _print_result(
        "WARN",
        "stack-* commands use docker-compose.legacy.yml. Prefer weave-up / weave-down / weave-logs for shard-first runtime.",
    )


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> int:
    executable = shutil.which(cmd[0]) or cmd[0]
    resolved = [executable, *cmd[1:]]
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.call(resolved, cwd=str(cwd or ROOT), env=merged_env)


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


def _compose(
    compose_cmd: list[str],
    *,
    project_name: str,
    compose_file: Path,
    args: list[str],
    env: dict[str, str] | None = None,
) -> int:
    return _run(
        [*compose_cmd, "-p", project_name, "-f", str(compose_file), *args],
        cwd=WORKSPACE_ROOT,
        env=env,
    )


def _load_shard_specs() -> list[ShardSpec]:
    specs: list[ShardSpec] = []
    if not SHARDS_ROOT.exists():
        return specs

    for shard_dir in sorted(path for path in SHARDS_ROOT.iterdir() if path.is_dir()):
        compose_file = shard_dir / "docker-compose.yml"
        env_file = shard_dir / ".env"
        if not compose_file.exists():
            continue
        env_values = _load_env_file(env_file)
        specs.append(
            ShardSpec(
                dir_name=shard_dir.name,
                shard_dir=shard_dir,
                compose_file=compose_file,
                env_file=env_file,
                shard_type=str(env_values.get("SHARD_TYPE") or "").strip() or "city",
                city_id=(str(env_values.get("CITY_ID") or "").strip() or None),
                backend_port=(str(env_values.get("BACKEND_PORT") or "").strip() or None),
            )
        )
    return specs


def _resolve_world_shard(shards: list[ShardSpec]) -> ShardSpec | None:
    for shard in shards:
        if shard.dir_name == "ww_world" or shard.shard_type == "world":
            return shard
    return None


def _resolve_city_shard(shards: list[ShardSpec], requested: str | None) -> ShardSpec | None:
    city_shards = [shard for shard in shards if shard.shard_type != "world"]
    if not city_shards:
        return None

    requested_key = str(requested or "").strip()
    if requested_key:
        requested_lower = requested_key.lower()
        for shard in city_shards:
            if shard.dir_name.lower() == requested_lower or str(shard.city_id or "").lower() == requested_lower:
                return shard
        return None

    preferred = os.environ.get("WW_DEV_CITY_SHARD", "").strip().lower()
    if preferred:
        for shard in city_shards:
            if shard.dir_name.lower() == preferred or str(shard.city_id or "").lower() == preferred:
                return shard

    for shard in city_shards:
        if shard.dir_name == "ww_sfo":
            return shard

    return sorted(city_shards, key=lambda item: item.dir_name)[0]


def _validate_shard_spec(shard: ShardSpec, *, label: str) -> int:
    failures = 0
    if not shard.compose_file.exists():
        _print_result("FAIL", f"{label} compose file missing: {shard.compose_file}")
        failures += 1
    if not shard.env_file.exists():
        _print_result("FAIL", f"{label} env file missing: {shard.env_file}")
        failures += 1
    if not shard.backend_port:
        _print_result("FAIL", f"{label} BACKEND_PORT missing in {shard.env_file}")
        failures += 1
    return failures


def _local_backend_url(shard: ShardSpec) -> str:
    return f"http://localhost:{shard.backend_port}"


def _docker_host_backend_url(shard: ShardSpec) -> str:
    return f"http://host.docker.internal:{shard.backend_port}"


def _client_proxy_env(*, world_shard: ShardSpec, city_shard: ShardSpec, all_shards: list[ShardSpec]) -> dict[str, str]:
    env = {
        "VITE_PROXY_TARGET": _docker_host_backend_url(city_shard),
        "VITE_WW_WORLD_URL": _docker_host_backend_url(world_shard),
    }
    for shard in all_shards:
        if shard.dir_name == "ww_sfo":
            env["VITE_WW_SFO_URL"] = _docker_host_backend_url(shard)
        if shard.dir_name == "ww_pdx":
            env["VITE_WW_PDX_URL"] = _docker_host_backend_url(shard)
    return env


def _client_host_env(*, world_shard: ShardSpec, city_shard: ShardSpec, all_shards: list[ShardSpec]) -> dict[str, str]:
    env = {
        "VITE_PROXY_TARGET": _local_backend_url(city_shard),
        "VITE_WW_WORLD_URL": _local_backend_url(world_shard),
    }
    for shard in all_shards:
        if shard.dir_name == "ww_sfo":
            env["VITE_WW_SFO_URL"] = _local_backend_url(shard)
        if shard.dir_name == "ww_pdx":
            env["VITE_WW_PDX_URL"] = _local_backend_url(shard)
    return env


def _print_weave_summary(*, world_shard: ShardSpec, city_shard: ShardSpec, client_started: bool) -> None:
    _print_result("INFO", "Shard-first dev runtime")
    _print_result("INFO", f"world root: {world_shard.dir_name} -> {_local_backend_url(world_shard)}")
    _print_result("INFO", f"city shard: {city_shard.dir_name} ({city_shard.display_name}) -> {_local_backend_url(city_shard)}")
    if client_started:
        _print_result("INFO", "client: http://localhost:5173")
        _print_result("INFO", f"default client API target: {_local_backend_url(city_shard)}")
    _print_result("INFO", f"world registry proxy target: {_local_backend_url(world_shard)}")
    _print_result("INFO", f"use 'python scripts/dev.py weave-logs --city {city_shard.dir_name}' to inspect stack logs")


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
    _print_legacy_stack_warning()
    preflight_rc = run_preflight(require_docker=True)
    if preflight_rc != 0:
        return preflight_rc

    compose_cmd = _resolve_compose_command()
    if not compose_cmd:
        _print_result("FAIL", "docker compose command unavailable")
        return 1

    cmd = [*compose_cmd, "-p", "worldweaver_engine", "-f", str(LEGACY_STACK_COMPOSE_FILE), "up", "-d"]
    if build:
        cmd.append("--build")
    return _run(cmd, cwd=WORKSPACE_ROOT)


def run_stack_restart(*, service: str | None) -> int:
    _print_legacy_stack_warning()
    compose_cmd = _resolve_compose_command()
    if not compose_cmd:
        _print_result("FAIL", "docker compose command unavailable")
        return 1

    cmd = [*compose_cmd, "-p", "worldweaver_engine", "-f", str(LEGACY_STACK_COMPOSE_FILE), "restart"]
    if service:
        cmd.append(service)
    return _run(cmd, cwd=WORKSPACE_ROOT)


def run_stack_down(*, volumes: bool) -> int:
    _print_legacy_stack_warning()
    compose_cmd = _resolve_compose_command()
    if not compose_cmd:
        _print_result("FAIL", "docker compose command unavailable")
        return 1

    cmd = [*compose_cmd, "-p", "worldweaver_engine", "-f", str(LEGACY_STACK_COMPOSE_FILE), "down", "--remove-orphans"]
    if volumes:
        cmd.append("--volumes")
    return _run(cmd, cwd=WORKSPACE_ROOT)


def run_stack_tunnel(*, build: bool) -> int:
    _print_legacy_stack_warning()
    """Start the docker stack and open a Cloudflare quick-tunnel to the client port.

    Requires `cloudflared` to be installed:
        Windows:  winget install Cloudflare.cloudflared
        macOS:    brew install cloudflare/cloudflare/cloudflared
        Linux:    https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

    The tunnel URL is printed to the console. Share it to join from any device
    on any network (mobile data, different wifi, etc.). No router config needed.
    """
    import threading
    import time

    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        _print_result("FAIL", "cloudflared not found — install it first:")
        print("  Windows: winget install Cloudflare.cloudflared")
        print("  macOS:   brew install cloudflare/cloudflare/cloudflared")
        print("  Linux:   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
        return 1

    # Start the docker stack first
    rc = run_stack_up(build=build)
    if rc != 0:
        return rc

    print()
    _print_result("INFO", "waiting for client to be ready on port 5173...")
    # Give the stack a moment to come up before starting the tunnel
    time.sleep(3)

    print()
    _print_result("INFO", "opening Cloudflare quick-tunnel → http://localhost:5173")
    print("  The public URL will appear below. Ctrl-C to close the tunnel.")
    print()

    tunnel_proc = subprocess.Popen(
        [cloudflared, "tunnel", "--url", "http://localhost:5173"],
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        text=True,
    )

    def _stream_output() -> None:
        assert tunnel_proc.stdout
        for line in tunnel_proc.stdout:
            print(line, end="", flush=True)

    t = threading.Thread(target=_stream_output, daemon=True)
    t.start()

    try:
        tunnel_proc.wait()
    except KeyboardInterrupt:
        tunnel_proc.terminate()
        print()
        _print_result("INFO", "tunnel closed")

    return 0


def run_stack_logs(*, service: str | None, follow: bool) -> int:
    _print_legacy_stack_warning()
    compose_cmd = _resolve_compose_command()
    if not compose_cmd:
        _print_result("FAIL", "docker compose command unavailable")
        return 1

    cmd = [*compose_cmd, "-p", "worldweaver_engine", "-f", str(LEGACY_STACK_COMPOSE_FILE), "logs"]
    if follow:
        cmd.append("--follow")
    if service:
        cmd.append(service)
    return _run(cmd, cwd=WORKSPACE_ROOT)


def run_weave_up(*, city: str | None, build: bool, include_client: bool, dry_run: bool) -> int:
    compose_cmd = _resolve_compose_command()
    if not compose_cmd:
        _print_result("FAIL", "docker compose command unavailable")
        return 1

    shards = _load_shard_specs()
    world_shard = _resolve_world_shard(shards)
    city_shard = _resolve_city_shard(shards, city)
    if world_shard is None:
        _print_result("FAIL", f"world shard not found under {SHARDS_ROOT}")
        return 1
    if city_shard is None:
        requested = f" matching '{city}'" if city else ""
        _print_result("FAIL", f"city shard not found{requested} under {SHARDS_ROOT}")
        return 1

    failures = 0
    failures += _validate_shard_spec(world_shard, label="world shard")
    failures += _validate_shard_spec(city_shard, label="city shard")
    if include_client and not CLIENT_COMPOSE_FILE.exists():
        _print_result("FAIL", f"client compose file missing: {CLIENT_COMPOSE_FILE}")
        failures += 1
    if failures:
        _print_result("FAIL", f"weave-up blocked by {failures} configuration issue(s)")
        return 1

    world_args = ["up", "-d"]
    city_args = ["up", "-d"]
    client_args = ["up", "-d", "client"]
    if build:
        world_args.append("--build")
        city_args.append("--build")
        client_args.append("--build")

    client_env = _client_proxy_env(world_shard=world_shard, city_shard=city_shard, all_shards=shards)

    _print_weave_summary(world_shard=world_shard, city_shard=city_shard, client_started=include_client)
    if dry_run:
        _print_result("INFO", f"dry-run world command: {' '.join([*compose_cmd, '-p', world_shard.dir_name, '-f', str(world_shard.compose_file), *world_args])}")
        _print_result("INFO", f"dry-run city command: {' '.join([*compose_cmd, '-p', city_shard.dir_name, '-f', str(city_shard.compose_file), *city_args])}")
        if include_client:
            _print_result("INFO", f"dry-run client command: {' '.join([*compose_cmd, '-p', CLIENT_PROJECT, '-f', str(CLIENT_COMPOSE_FILE), *client_args])}")
        return 0

    world_rc = _compose(
        compose_cmd,
        project_name=world_shard.dir_name,
        compose_file=world_shard.compose_file,
        args=world_args,
    )
    if world_rc != 0:
        return world_rc

    city_rc = _compose(
        compose_cmd,
        project_name=city_shard.dir_name,
        compose_file=city_shard.compose_file,
        args=city_args,
    )
    if city_rc != 0:
        return city_rc

    if include_client:
        client_rc = _compose(
            compose_cmd,
            project_name=CLIENT_PROJECT,
            compose_file=CLIENT_COMPOSE_FILE,
            args=client_args,
            env=client_env,
        )
        if client_rc != 0:
            return client_rc

    _print_result("PASS", "weave-up finished")
    return 0


def run_weave_down(*, city: str | None, volumes: bool, include_client: bool, dry_run: bool) -> int:
    compose_cmd = _resolve_compose_command()
    if not compose_cmd:
        _print_result("FAIL", "docker compose command unavailable")
        return 1

    shards = _load_shard_specs()
    world_shard = _resolve_world_shard(shards)
    city_shard = _resolve_city_shard(shards, city)
    if world_shard is None or city_shard is None:
        _print_result("FAIL", "could not resolve world shard and city shard for weave-down")
        return 1

    down_args = ["down", "--remove-orphans"]
    if volumes:
        down_args.append("--volumes")

    client_args = ["down", "--remove-orphans"]
    if volumes:
        client_args.append("--volumes")

    if dry_run:
        _print_result("INFO", f"dry-run city down: {' '.join([*compose_cmd, '-p', city_shard.dir_name, '-f', str(city_shard.compose_file), *down_args])}")
        _print_result("INFO", f"dry-run world down: {' '.join([*compose_cmd, '-p', world_shard.dir_name, '-f', str(world_shard.compose_file), *down_args])}")
        if include_client:
            _print_result("INFO", f"dry-run client down: {' '.join([*compose_cmd, '-p', CLIENT_PROJECT, '-f', str(CLIENT_COMPOSE_FILE), *client_args])}")
        return 0

    rc = 0
    if include_client and CLIENT_COMPOSE_FILE.exists():
        rc = _compose(
            compose_cmd,
            project_name=CLIENT_PROJECT,
            compose_file=CLIENT_COMPOSE_FILE,
            args=client_args,
        )
        if rc != 0:
            return rc

    rc = _compose(
        compose_cmd,
        project_name=city_shard.dir_name,
        compose_file=city_shard.compose_file,
        args=down_args,
    )
    if rc != 0:
        return rc

    rc = _compose(
        compose_cmd,
        project_name=world_shard.dir_name,
        compose_file=world_shard.compose_file,
        args=down_args,
    )
    if rc != 0:
        return rc

    _print_result("PASS", "weave-down finished")
    return 0


def run_weave_logs(*, city: str | None, target: str, follow: bool) -> int:
    compose_cmd = _resolve_compose_command()
    if not compose_cmd:
        _print_result("FAIL", "docker compose command unavailable")
        return 1

    shards = _load_shard_specs()
    world_shard = _resolve_world_shard(shards)
    city_shard = _resolve_city_shard(shards, city)
    if world_shard is None or city_shard is None:
        _print_result("FAIL", "could not resolve world shard and city shard for weave-logs")
        return 1

    log_args = ["logs"]
    if follow:
        log_args.append("--follow")

    if target == "world":
        return _compose(
            compose_cmd,
            project_name=world_shard.dir_name,
            compose_file=world_shard.compose_file,
            args=log_args,
        )
    if target == "client":
        return _compose(
            compose_cmd,
            project_name=CLIENT_PROJECT,
            compose_file=CLIENT_COMPOSE_FILE,
            args=[*log_args, "client"],
        )
    if target == "city-backend":
        return _compose(
            compose_cmd,
            project_name=city_shard.dir_name,
            compose_file=city_shard.compose_file,
            args=[*log_args, "backend"],
        )
    if target == "city-agent":
        return _compose(
            compose_cmd,
            project_name=city_shard.dir_name,
            compose_file=city_shard.compose_file,
            args=[*log_args, "agent"],
    )
    return _compose(
        compose_cmd,
        project_name=city_shard.dir_name,
        compose_file=city_shard.compose_file,
        args=log_args,
    )


def run_weave_client(*, city: str | None, lan: bool) -> int:
    shards = _load_shard_specs()
    world_shard = _resolve_world_shard(shards)
    city_shard = _resolve_city_shard(shards, city)
    if world_shard is None:
        _print_result("FAIL", f"world shard not found under {SHARDS_ROOT}")
        return 1
    if city_shard is None:
        requested = f" matching '{city}'" if city else ""
        _print_result("FAIL", f"city shard not found{requested} under {SHARDS_ROOT}")
        return 1

    failures = 0
    failures += _validate_shard_spec(world_shard, label="world shard")
    failures += _validate_shard_spec(city_shard, label="city shard")
    if failures:
        _print_result("FAIL", f"weave-client blocked by {failures} configuration issue(s)")
        return 1

    env = _client_host_env(world_shard=world_shard, city_shard=city_shard, all_shards=shards)
    _print_result("INFO", f"starting local client on http://localhost:5173 for {city_shard.dir_name} -> {_local_backend_url(city_shard)}")
    _print_result("INFO", f"world registry target: {_local_backend_url(world_shard)}")

    cmd = ["npm", "--prefix", "client", "run", "dev"]
    if lan:
        cmd += ["--", "--host"]
    return _run(cmd, cwd=ROOT, env=env)


def _collect_db_reset_targets(*, include_test_dbs: bool) -> list[Path]:
    targets: list[Path] = []
    for rel_path in DEFAULT_RUNTIME_DB_PATHS:
        targets.append(ROOT / rel_path)

    env_values = _load_env_file(ENV_FILE)
    custom_path_raw = (os.environ.get("WW_DB_PATH") or env_values.get("WW_DB_PATH") or "").strip()
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


def run_fact_audit(db_url: str | None = None) -> int:
    """Run read-only graph-fact audit and emit machine-readable JSON report."""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
    except ImportError:
        _print_result("FAIL", "sqlalchemy is required for fact-audit (run: pip install sqlalchemy)")
        return 1

    resolved_url = db_url or os.environ.get("DATABASE_URL") or ""
    if not resolved_url:
        # Try default sqlite path relative to project root
        for rel in ("worldweaver.db", "db/worldweaver.db"):
            candidate = ROOT / rel
            if candidate.exists():
                resolved_url = f"sqlite:///{candidate}"
                break

    if not resolved_url:
        _print_result("FAIL", "No database URL found. Set DATABASE_URL or ensure worldweaver.db exists.")
        return 1

    try:
        engine = create_engine(resolved_url, connect_args={"check_same_thread": False} if "sqlite" in resolved_url else {})
        Session = sessionmaker(bind=engine)
        with Session() as session:
            # Import here so dev.py can run without a full src install check upfront
            sys.path.insert(0, str(ROOT))
            from src.services.world_memory import audit_graph_facts

            report = audit_graph_facts(session)
        print(json.dumps(report, indent=2))
        anomalies = report["duplicate_entity_key_count"] + report["duplicate_active_fact_count"] + report["orphan_fact_link_count"]
        if anomalies > 0:
            _print_result("WARN", f"fact-audit found {anomalies} anomaly(ies); see report above")
            return 1
        _print_result("PASS", "fact-audit: no anomalies found")
        return 0
    except Exception as exc:
        _print_result("FAIL", f"fact-audit error: {exc}")
        return 1


def run_harness_workflow(
    harness_command: str,
    harness_args: list[str] | None = None,
    *,
    legacy_alias: bool = False,
) -> int:
    args = list(harness_args or [])

    if legacy_alias:
        _print_result(
            "WARN",
            (f"'{harness_command}' is a legacy alias. " f"Use: python scripts/dev.py harness {harness_command} ..."),
        )

    if harness_command == "eval":
        return _run([sys.executable, "scripts/eval_narrative.py", "--enforce", *args])
    if harness_command == "eval-smoke":
        return _run(
            [sys.executable, "scripts/eval_narrative.py", "--smoke", "--enforce", *args],
        )
    if harness_command == "sweep":
        return _run([sys.executable, "playtest_harness/parameter_sweep.py", *args])
    if harness_command == "llm-playtest":
        return _run([sys.executable, "playtest_harness/llm_playtest.py", *args])
    if harness_command == "benchmark-three-layer":
        return _run([sys.executable, "scripts/benchmark_three_layer.py", *args])

    _print_result("FAIL", f"unknown harness command: {harness_command}")
    return 2


def main() -> int:
    # Legacy aliases need raw pass-through so option-like tokens are preserved
    # (e.g., `dev.py sweep --phase both`) without requiring `--`.
    if len(sys.argv) >= 2 and sys.argv[1] in HARNESS_COMMANDS:
        return run_harness_workflow(
            str(sys.argv[1]),
            list(sys.argv[2:]),
            legacy_alias=True,
        )

    parser = argparse.ArgumentParser(description="WorldWeaver dev command surface")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("install", help="install backend and client dependencies")
    sub.add_parser("preflight", help="validate local runtime prerequisites")
    weave_up_parser = sub.add_parser(
        "weave-up",
        help="start ww_world + one city shard + the client through the shard-first runtime path",
    )
    weave_up_parser.add_argument(
        "--city",
        default=None,
        help="city shard dir or CITY_ID to launch (default: WW_DEV_CITY_SHARD, then ww_sfo, then first city shard)",
    )
    weave_up_parser.add_argument(
        "--build",
        action="store_true",
        help="rebuild images before starting",
    )
    weave_up_parser.add_argument(
        "--no-client",
        action="store_true",
        help="start only ww_world + the city shard; skip the Vite client container",
    )
    weave_up_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the resolved shard-first commands without executing them",
    )
    weave_down_parser = sub.add_parser(
        "weave-down",
        help="stop the shard-first dev runtime started by weave-up",
    )
    weave_down_parser.add_argument(
        "--city",
        default=None,
        help="city shard dir or CITY_ID to stop (default resolution matches weave-up)",
    )
    weave_down_parser.add_argument(
        "--volumes",
        action="store_true",
        help="also remove compose volumes for the selected city/world/client projects",
    )
    weave_down_parser.add_argument(
        "--no-client",
        action="store_true",
        help="leave the dedicated client compose project alone",
    )
    weave_down_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the resolved shard-first shutdown commands without executing them",
    )
    weave_logs_parser = sub.add_parser(
        "weave-logs",
        help="view logs for the shard-first runtime",
    )
    weave_logs_parser.add_argument(
        "--city",
        default=None,
        help="city shard dir or CITY_ID to inspect (default resolution matches weave-up)",
    )
    weave_logs_parser.add_argument(
        "--target",
        choices=("city", "city-backend", "city-agent", "world", "client"),
        default="city",
        help="which part of the shard-first runtime to inspect",
    )
    weave_logs_parser.add_argument(
        "--follow",
        action="store_true",
        help="stream log output",
    )
    weave_client_parser = sub.add_parser(
        "weave-client",
        help="run the Vite client locally against the shard-first runtime",
    )
    weave_client_parser.add_argument(
        "--city",
        default=None,
        help="city shard dir or CITY_ID to target (default resolution matches weave-up)",
    )
    weave_client_parser.add_argument(
        "--lan",
        action="store_true",
        help="expose Vite on all interfaces for LAN access",
    )
    stack_up_parser = sub.add_parser("stack-up", help="legacy engine-root docker compose stack (prefer weave-up for shard-first dev)")
    stack_up_parser.add_argument(
        "--build",
        action="store_true",
        help="rebuild images before starting (needed when requirements.txt or package.json change)",
    )
    stack_restart_parser = sub.add_parser("stack-restart", help="restart running services without rebuild (fast bounce)")
    stack_restart_parser.add_argument("service", nargs="?", help="optional service name (backend or client); omit for both")
    stack_tunnel_parser = sub.add_parser(
        "stack-tunnel",
        help="start docker stack and open a Cloudflare quick-tunnel so you can join from any network (mobile data, etc.)",
    )
    stack_tunnel_parser.add_argument(
        "--build",
        action="store_true",
        help="rebuild images before starting",
    )
    stack_down_parser = sub.add_parser("stack-down", help="stop legacy engine-root docker compose dev stack")
    stack_down_parser.add_argument(
        "--volumes",
        action="store_true",
        help="also remove compose volumes",
    )
    stack_logs_parser = sub.add_parser("stack-logs", help="view legacy engine-root docker compose logs")
    stack_logs_parser.add_argument("service", nargs="?", help="optional compose service name")
    stack_logs_parser.add_argument(
        "--follow",
        action="store_true",
        help="stream log output",
    )
    backend_parser = sub.add_parser("backend", help="run backend server")
    backend_parser.add_argument(
        "--lan",
        action="store_true",
        help="bind to 0.0.0.0 so devices on the local network can reach the server",
    )
    client_parser = sub.add_parser("client", help="run client dev server")
    client_parser.add_argument(
        "--lan",
        action="store_true",
        help="expose Vite dev server on all interfaces (for phone/LAN access)",
    )
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
    harness_parser = sub.add_parser(
        "harness",
        help="run optional harness/evaluation workflows (demoted from default path)",
    )
    harness_parser.add_argument("harness_command", choices=HARNESS_COMMANDS)
    harness_parser.add_argument(
        "harness_args",
        nargs=argparse.REMAINDER,
        help="arguments passed through to the harness workflow",
    )
    for legacy_command in HARNESS_COMMANDS:
        legacy = sub.add_parser(
            legacy_command,
            help=(f"legacy alias for 'harness {legacy_command}'"),
        )
        legacy.add_argument(
            "harness_args",
            nargs=argparse.REMAINDER,
            help="arguments passed through to the harness workflow",
        )
    fact_audit_parser = sub.add_parser(
        "fact-audit",
        help="scan world graph tables for canonicalization and dedupe anomalies (read-only)",
    )
    fact_audit_parser.add_argument(
        "--db-url",
        default=None,
        help="SQLAlchemy database URL (defaults to DATABASE_URL env var or local worldweaver.db)",
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
    if args.command == "weave-up":
        return run_weave_up(
            city=getattr(args, "city", None),
            build=bool(args.build),
            include_client=not bool(getattr(args, "no_client", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
        )
    if args.command == "weave-down":
        return run_weave_down(
            city=getattr(args, "city", None),
            volumes=bool(args.volumes),
            include_client=not bool(getattr(args, "no_client", False)),
            dry_run=bool(getattr(args, "dry_run", False)),
        )
    if args.command == "weave-logs":
        return run_weave_logs(
            city=getattr(args, "city", None),
            target=str(getattr(args, "target", "city")),
            follow=bool(getattr(args, "follow", False)),
        )
    if args.command == "weave-client":
        return run_weave_client(
            city=getattr(args, "city", None),
            lan=bool(getattr(args, "lan", False)),
        )
    if args.command == "stack-up":
        return run_stack_up(build=bool(args.build))
    if args.command == "stack-restart":
        return run_stack_restart(service=(str(args.service).strip() if args.service else None))
    if args.command == "stack-tunnel":
        return run_stack_tunnel(build=bool(args.build))
    if args.command == "stack-down":
        return run_stack_down(volumes=bool(args.volumes))
    if args.command == "stack-logs":
        return run_stack_logs(
            service=(str(args.service).strip() if args.service else None),
            follow=bool(args.follow),
        )
    if args.command == "backend":
        cmd = [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"]
        if getattr(args, "lan", False):
            cmd += ["--host", "0.0.0.0"]
        return _run(cmd)
    if args.command == "client":
        cmd = ["npm", "--prefix", "client", "run", "dev"]
        if getattr(args, "lan", False):
            cmd += ["--", "--host"]
        return _run(cmd)
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
    if args.command == "harness":
        return run_harness_workflow(
            str(args.harness_command),
            list(args.harness_args),
            legacy_alias=False,
        )
    if args.command in HARNESS_COMMANDS:
        return run_harness_workflow(
            str(args.command),
            list(args.harness_args),
            legacy_alias=True,
        )
    if args.command == "fact-audit":
        return run_fact_audit(db_url=getattr(args, "db_url", None))
    if args.command == "reset-data":
        return run_reset_data(
            confirm=bool(args.yes),
            include_test_dbs=bool(args.include_test_dbs),
        )

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
