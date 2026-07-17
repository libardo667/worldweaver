#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One developer command for the WorldWeaver workspace."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
ENGINE_DIR = ROOT / "worldweaver_engine"
AGENT_DIR = ROOT / "ww_agent"
REQUIREMENTS = ROOT / "requirements.txt"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> int:
    print(f"\n==> {' '.join(command)}", flush=True)
    return subprocess.call(command, cwd=cwd, env=env)


def _python_works(path: Path) -> bool:
    if not path.exists():
        return False
    return (
        subprocess.call(
            [str(path), "-c", "pass"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        == 0
    )


def _install() -> int:
    if sys.version_info < (3, 11):
        print("WorldWeaver requires Python 3.11 or newer.", file=sys.stderr)
        return 2
    uv = shutil.which("uv")
    python_path = _venv_python()
    if not _python_works(python_path):
        action = "Rebuilding" if VENV_DIR.exists() else "Creating"
        print(f"{action} shared environment at {VENV_DIR}", flush=True)
        create_command = [uv, "venv", "--clear", str(VENV_DIR), "--python", sys.executable] if uv else [sys.executable, "-m", "venv", "--clear", str(VENV_DIR)]
        created = _run(create_command)
        if created != 0:
            return created
    python = str(python_path)
    install_command = [uv, "pip", "install", "--upgrade", "--python", python, "-r", str(REQUIREMENTS)] if uv else [python, "-m", "pip", "install", "--upgrade", "-r", str(REQUIREMENTS)]
    dependencies = _run(install_command)
    if dependencies != 0:
        return dependencies
    return _run(["npm", "--prefix", str(ENGINE_DIR / "client"), "ci"])


def _ensure_shared_environment(args: list[str]) -> None:
    python = _venv_python()
    if not _python_works(python):
        print(
            "The shared environment is missing or unusable. Run: python dev.py install",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if Path(sys.prefix).resolve() != VENV_DIR.resolve():
        os.execv(str(python), [str(python), str(Path(__file__).resolve()), *args])


def _target_and_args(args: list[str]) -> tuple[str, list[str]]:
    if args and args[0] in {"all", "engine", "agent"}:
        return args[0], args[1:]
    return "all", args


def _pytest(project: str, extra: list[str]) -> int:
    directory = ENGINE_DIR if project == "engine" else AGENT_DIR
    print(f"\n--- {project} tests ---", flush=True)
    return _run([sys.executable, "-m", "pytest", "-q", *extra], cwd=directory)


def _test(args: list[str]) -> int:
    target, extra = _target_and_args(args)
    if target in {"all", "engine"}:
        result = _pytest("engine", extra)
        if result != 0:
            return result
    if target in {"all", "agent"}:
        return _pytest("agent", extra)
    return 0


def _check_workspace_command() -> int:
    config = str(ENGINE_DIR / "pyproject.toml")
    linted = _run([sys.executable, "-m", "ruff", "check", "--config", config, "dev.py"])
    if linted != 0:
        return linted
    return _run([sys.executable, "-m", "black", "--check", "--config", config, "dev.py"])


def _check(args: list[str]) -> int:
    target, extra = _target_and_args(args)
    result = _check_workspace_command()
    if result != 0:
        return result
    if target in {"all", "engine"}:
        print("\n--- engine lint and build ---", flush=True)
        result = _run([sys.executable, "scripts/dev.py", "gate3-strict"], cwd=ENGINE_DIR)
        if result != 0:
            return result
        result = _pytest("engine", extra)
        if result != 0:
            return result
    if target in {"all", "agent"}:
        return _pytest("agent", extra)
    return 0


def _run_repo_script(args: list[str]) -> int:
    if not args:
        print("Usage: python dev.py run <script> [args...]", file=sys.stderr)
        return 2

    script = (ROOT / args[0]).resolve()
    try:
        script.relative_to(ROOT)
    except ValueError:
        print("The script must be inside the WorldWeaver repository.", file=sys.stderr)
        return 2
    if not script.is_file():
        print(f"Script not found: {args[0]}", file=sys.stderr)
        return 2

    return _run([sys.executable, str(script), *args[1:]])


def _resident(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python dev.py resident",
        description="Preflight or wake exactly one named resident against one city.",
    )
    parser.add_argument("--city", required=True, help="city shard directory name")
    parser.add_argument("--resident", required=True, help="exact resident directory name")
    parser.add_argument(
        "--wake",
        action="store_true",
        help="wake after preflight; omitted means read-only",
    )
    parser.add_argument("--ticks", type=int, default=3, help="bounded tick count (1-20)")
    parser.add_argument("--pause", type=float, default=0.5, help="seconds between ticks")
    parsed = parser.parse_args(args)
    if not 1 <= parsed.ticks <= 20:
        parser.error("--ticks must be between 1 and 20")
    if not 0 <= parsed.pause <= 60:
        parser.error("--pause must be between 0 and 60 seconds")
    if Path(parsed.city).name != parsed.city or Path(parsed.resident).name != parsed.resident:
        parser.error("--city and --resident must be single directory names")

    city_dir = ROOT / "shards" / parsed.city
    compose_file = city_dir / "docker-compose.yml"
    resident_home = city_dir / "residents" / parsed.resident
    if not compose_file.is_file():
        print(f"City shard not found: {parsed.city}", file=sys.stderr)
        return 2
    if not resident_home.is_dir():
        print(
            f"Resident {parsed.resident!r} was not found in {parsed.city}.",
            file=sys.stderr,
        )
        return 2

    docker = shutil.which("docker")
    if not docker:
        print("Docker is required for city and agent-process preflight.", file=sys.stderr)
        return 2
    compose_status = subprocess.run(
        [
            docker,
            "compose",
            "-p",
            parsed.city,
            "-f",
            str(compose_file),
            "ps",
            "--status",
            "running",
            "--services",
        ],
        cwd=city_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    if compose_status.returncode != 0:
        print("Could not inspect the selected city containers.", file=sys.stderr)
        return compose_status.returncode
    running_services = set(compose_status.stdout.splitlines())
    if "agent" in running_services:
        print(
            f"Blocked: the {parsed.city} cohort agent service is already running.",
            file=sys.stderr,
        )
        return 1

    topology = _run(
        [
            sys.executable,
            "scripts/dev.py",
            "weave-status",
            "--city",
            parsed.city,
            "--strict",
            "--require-travel",
        ],
        cwd=ENGINE_DIR,
    )
    if topology != 0:
        return topology

    from dotenv import dotenv_values

    runtime_env = os.environ.copy()
    for env_file in (AGENT_DIR / ".env", city_dir / ".env"):
        for key, value in dotenv_values(env_file).items():
            if value is not None:
                runtime_env[key] = value
    backend_port = str(runtime_env.get("BACKEND_PORT") or "").strip()
    if not backend_port:
        print(f"BACKEND_PORT is missing from {city_dir / '.env'}.", file=sys.stderr)
        return 2
    runtime_env.update(
        {
            "WW_SERVER_URL": f"http://localhost:{backend_port}",
            "WW_RESIDENTS_DIR": str(city_dir / "residents"),
            "WW_DOULA": "0",
            "WW_PROMPT_TRACE": "1",
        }
    )
    embedding_url = str(runtime_env.get("WW_EMBEDDING_URL") or "").strip()
    if embedding_url:
        parsed_embedding = urllib.parse.urlsplit(embedding_url)

        def ollama_reachable(parts: urllib.parse.SplitResult) -> bool:
            tags_url = urllib.parse.urlunsplit((parts.scheme or "http", parts.netloc, "/api/tags", "", ""))
            try:
                with urllib.request.urlopen(tags_url, timeout=2) as response:
                    return response.status == 200
            except Exception:
                return False

        if not ollama_reachable(parsed_embedding):
            local_embedding = parsed_embedding._replace(netloc=f"localhost:{parsed_embedding.port or 11434}")
            if ollama_reachable(local_embedding):
                runtime_env["WW_EMBEDDING_URL"] = urllib.parse.urlunsplit(local_embedding)
                print(
                    "Host-side embedder resolved to localhost; the shard's Docker hostname was unreachable.",
                    flush=True,
                )
    command = [
        sys.executable,
        str(AGENT_DIR / "scripts" / "resident_once.py"),
        "--home",
        str(resident_home),
        "--server-url",
        runtime_env["WW_SERVER_URL"],
        "--ticks",
        str(parsed.ticks),
        "--pause",
        str(parsed.pause),
    ]
    if parsed.wake:
        command.append("--wake")
    return _run(command, env=runtime_env)


def _help() -> None:
    print("""WorldWeaver workspace commands

  python dev.py install                 create/update the shared .venv and install client packages
  python dev.py test                    run engine and agent tests
  python dev.py test engine [pytest...] run only engine tests
  python dev.py test agent [pytest...]  run only agent tests
  python dev.py check                   run engine lint/build plus all Python tests
  python dev.py check engine            run only the engine checks
  python dev.py check agent             run only the agent tests
  python dev.py agent                   run the resident process
  python dev.py resident --city CITY --resident NAME
                                        preflight exactly one resident (read-only)
  python dev.py resident --city CITY --resident NAME --wake --ticks 3
                                        wake only that resident for bounded ticks
  python dev.py run <script> [args...]  run a repository Python script

Other commands are passed to worldweaver_engine/scripts/dev.py, so commands such as
`python dev.py weave-up --city ww_sfo` work from the repository root.
""")


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help", "help"}:
        _help()
        return 0
    if args[0] == "install":
        return _install()

    _ensure_shared_environment(args)
    command, rest = args[0], args[1:]
    if command == "test":
        return _test(rest)
    if command == "check":
        return _check(rest)
    if command == "run":
        return _run_repo_script(rest)
    if command == "resident":
        return _resident(rest)
    if command == "agent":
        return _run([sys.executable, "-m", "src.main", *rest], cwd=AGENT_DIR)
    if command == "engine":
        if not rest:
            _help()
            return 2
        command, rest = rest[0], rest[1:]
    return _run([sys.executable, "scripts/dev.py", command, *rest], cwd=ENGINE_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
