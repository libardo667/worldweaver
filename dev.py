#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One developer command for the WorldWeaver workspace."""

from __future__ import annotations

import argparse
import json
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
_SENSITIVE_FLAGS = frozenset({"--token", "--password", "--api-key", "--secret"})


def _duration_seconds(value: str) -> float:
    raw = str(value or "").strip().lower()
    units = {"s": 1.0, "m": 60.0, "h": 3600.0}
    suffix = raw[-1:] if raw[-1:] in units else "s"
    number = raw[:-1] if raw[-1:] in units else raw
    try:
        seconds = float(number) * units[suffix]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("duration must look like 30s, 15m, or 1h") from exc
    if not 0 < seconds <= 7200:
        raise argparse.ArgumentTypeError("duration must be greater than zero and at most 2h")
    return seconds


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _city_runtime_env(city_dir: Path) -> dict[str, str]:
    """Layer shared agent defaults with non-empty city-specific overrides."""
    from dotenv import dotenv_values

    runtime_env = os.environ.copy()
    for env_file in (AGENT_DIR / ".env", city_dir / ".env"):
        for key, value in dotenv_values(env_file).items():
            if value is None:
                continue
            # Generated shard files keep some optional settings as empty
            # placeholders. They must not erase a usable workspace-level model
            # URL, key, or default merely because the shard has no override.
            if value.strip() or not str(runtime_env.get(key) or "").strip():
                runtime_env[key] = value
    return runtime_env


def _run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> int:
    display: list[str] = []
    hide_next = False
    for argument in command:
        if hide_next:
            display.append("[hidden]")
            hide_next = False
            continue
        flag = argument.split("=", 1)[0]
        if flag in _SENSITIVE_FLAGS:
            display.append(f"{flag}=[hidden]" if "=" in argument else flag)
            hide_next = "=" not in argument
            continue
        display.append(argument)
    print(f"\n==> {' '.join(display)}", flush=True)
    try:
        return subprocess.call(command, cwd=cwd, env=env)
    except KeyboardInterrupt:
        return 130


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
    client_rc = _run(["npm", "--prefix", str(ENGINE_DIR / "client"), "ci"])
    if client_rc != 0:
        return client_rc
    return _run(["npm", "--prefix", str(ENGINE_DIR / "client-public"), "ci"])


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

    cwd = ENGINE_DIR if script.is_relative_to(ENGINE_DIR) else ROOT
    return _run([sys.executable, str(script), *args[1:]], cwd=cwd)


def _prepare_resident_city(city: str) -> tuple[Path, dict[str, str]] | int:
    """Resolve one stopped city and the host-side runtime used by bounded runners."""

    city_dir = ROOT / "shards" / city
    compose_file = city_dir / "docker-compose.yml"
    if not compose_file.is_file():
        print(f"City shard not found: {city}", file=sys.stderr)
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
            city,
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
    if "agent" in set(compose_status.stdout.splitlines()):
        print(
            f"Blocked: the {city} cohort agent service is already running.",
            file=sys.stderr,
        )
        return 1

    topology = _run(
        [
            sys.executable,
            "scripts/dev.py",
            "weave-status",
            "--city",
            city,
            "--strict",
        ],
        cwd=ENGINE_DIR,
    )
    if topology != 0:
        return topology

    runtime_env = _city_runtime_env(city_dir)
    backend_port = str(runtime_env.get("BACKEND_PORT") or "").strip()
    if not backend_port:
        print(f"BACKEND_PORT is missing from {city_dir / '.env'}.", file=sys.stderr)
        return 2
    runtime_env.update(
        {
            "WW_SERVER_URL": f"http://localhost:{backend_port}",
            "WW_RESIDENTS_DIR": str(city_dir / "residents"),
            "WW_DOULA": "0",
            "WW_PROMPT_TRACE": "0",
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
    return city_dir, runtime_env


def _resident(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python dev.py resident",
        description="Preflight or wake exactly one named resident against one city.",
    )
    parser.add_argument("--city", required=True, help="city shard directory name")
    parser.add_argument("--resident", required=True, help="exact resident directory name")
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--wake",
        action="store_true",
        help="wake after preflight; omitted means read-only",
    )
    action.add_argument(
        "--park",
        action="store_true",
        help="retire this resident's city session without running cognition",
    )
    action.add_argument(
        "--activate",
        action="store_true",
        help="activate a reviewed dormant hearth, then run read-only preflight",
    )
    limit = parser.add_mutually_exclusive_group()
    limit.add_argument("--ticks", type=int, help="bounded smoke-test tick count (1-20)")
    limit.add_argument(
        "--duration",
        type=_duration_seconds,
        help="natural-cadence run duration, such as 15m or 1h (maximum 2h)",
    )
    parser.add_argument(
        "--pause",
        type=float,
        help="seconds between smoke-test ticks (default 0.5; unavailable with --duration)",
    )
    parser.add_argument("--model", help="temporary pulse model for this run only")
    parser.add_argument(
        "--temperature",
        type=float,
        help="temporary sampling temperature; omitted model swaps use the model default",
    )
    parser.add_argument(
        "--action-tendency",
        action="store_true",
        help=("for this run only, let sustained restless fervor become a venture " "toward a reachable place"),
    )
    parser.add_argument(
        "--reach-continuations",
        type=int,
        choices=range(0, 9),
        metavar="0-8",
        help="requested reads per active pulse; the host maximum may lower it",
    )
    parser.add_argument(
        "--trace-prompts",
        action="store_true",
        help="capture exact private prompts for this bounded diagnostic run",
    )
    parsed = parser.parse_args(args)
    if parsed.ticks is None and parsed.duration is None:
        parsed.ticks = 3
    if parsed.duration is not None and parsed.pause is not None:
        parser.error("--duration uses the resident's natural cadence; do not pass --pause")
    if parsed.duration is None and parsed.pause is None:
        parsed.pause = 0.5
    if parsed.duration is not None:
        parsed.ticks = 0
        parsed.pause = None
    if parsed.duration is None and not 1 <= parsed.ticks <= 20:
        parser.error("--ticks must be between 1 and 20")
    if parsed.pause is not None and not 0 <= parsed.pause <= 60:
        parser.error("--pause must be between 0 and 60 seconds")
    if Path(parsed.city).name != parsed.city or Path(parsed.resident).name != parsed.resident:
        parser.error("--city and --resident must be single directory names")

    prepared_city = _prepare_resident_city(parsed.city)
    if isinstance(prepared_city, int):
        return prepared_city
    city_dir, runtime_env = prepared_city
    resident_home = city_dir / "residents" / parsed.resident
    if not resident_home.is_dir():
        print(
            f"Resident {parsed.resident!r} was not found in {parsed.city}.",
            file=sys.stderr,
        )
        return 2

    if parsed.activate:
        activation = _run(
            [
                sys.executable,
                str(AGENT_DIR / "scripts" / "hearth_activation.py"),
                str(resident_home),
                "--initialize",
            ],
            env=runtime_env,
        )
        if activation != 0:
            return activation
    command = [
        sys.executable,
        str(AGENT_DIR / "scripts" / "resident_once.py"),
        "--home",
        str(resident_home),
        "--server-url",
        runtime_env["WW_SERVER_URL"],
    ]
    if parsed.duration is not None:
        command.extend(["--duration", str(parsed.duration)])
    else:
        command.extend(["--ticks", str(parsed.ticks), "--pause", str(parsed.pause)])
    if parsed.model:
        command.extend(["--model", parsed.model])
    if parsed.temperature is not None:
        command.extend(["--temperature", str(parsed.temperature)])
    if parsed.action_tendency:
        command.append("--action-tendency")
    if parsed.reach_continuations is not None:
        command.extend(["--reach-continuations", str(parsed.reach_continuations)])
    if parsed.trace_prompts:
        command.append("--trace-prompts")
    if parsed.wake:
        command.append("--wake")
    if parsed.park:
        command.append("--park")
    return _run(command, env=runtime_env)


def _cohort(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python dev.py cohort",
        description="Preflight or wake a bounded group of residents in one city.",
    )
    parser.add_argument("--city", required=True, help="city shard directory name")
    parser.add_argument(
        "--resident",
        action="append",
        default=[],
        help="exact resident directory name; repeat to select a subset (default: every resident)",
    )
    parser.add_argument(
        "--wake",
        action="store_true",
        help="wake only after the whole cohort passes preflight; omitted means read-only",
    )
    parser.add_argument(
        "--duration",
        type=_duration_seconds,
        help="natural-cadence run duration, such as 30m or 1h (required with --wake)",
    )
    parser.add_argument("--model", help="temporary pulse model shared by this run")
    parser.add_argument("--temperature", type=float)
    parser.add_argument(
        "--stagger",
        type=float,
        default=1.5,
        help="seconds between resident starts (default: 1.5)",
    )
    parser.add_argument(
        "--action-tendency",
        action="store_true",
        help="let sustained restless fervor become a venture toward a reachable place",
    )
    parser.add_argument(
        "--reach-continuations",
        type=int,
        choices=range(0, 9),
        metavar="0-8",
        help="requested reads per active pulse; the resident host may lower it",
    )
    parser.add_argument(
        "--trace-prompts",
        action="store_true",
        help="capture exact private prompts for this bounded cohort diagnostic",
    )
    parser.add_argument(
        "--output-dir",
        help="optional empty destination for local structural logs (default: .runs/cohorts/...)",
    )
    parsed = parser.parse_args(args)
    if Path(parsed.city).name != parsed.city:
        parser.error("--city must be a single directory name")
    if any(Path(name).name != name for name in parsed.resident):
        parser.error("--resident values must be single directory names")
    if parsed.wake and parsed.duration is None:
        parser.error("--wake requires --duration")
    if not parsed.wake and parsed.duration is not None:
        parser.error("--duration is only meaningful with --wake")
    if not 0 <= parsed.stagger <= 10:
        parser.error("--stagger must be between 0 and 10 seconds")

    prepared_city = _prepare_resident_city(parsed.city)
    if isinstance(prepared_city, int):
        return prepared_city
    city_dir, runtime_env = prepared_city
    residents_dir = city_dir / "residents"
    names = list(dict.fromkeys(parsed.resident))
    if not names:
        names = sorted(path.name for path in residents_dir.iterdir() if path.is_dir() and not path.name.startswith(".") and (path / "identity" / "SOUL.md").is_file())
    if not 2 <= len(names) <= 5:
        parser.error("a cohort must contain between 2 and 5 residents")

    homes: list[Path] = []
    for name in names:
        home = residents_dir / name
        if not home.is_dir():
            print(f"Resident {name!r} was not found in {parsed.city}.", file=sys.stderr)
            return 2
        homes.append(home)

    command = [
        sys.executable,
        str(AGENT_DIR / "scripts" / "resident_cohort.py"),
        "--city",
        parsed.city,
        "--server-url",
        runtime_env["WW_SERVER_URL"],
        "--stagger",
        str(parsed.stagger),
    ]
    for home in homes:
        command.extend(["--home", str(home)])
    if parsed.wake:
        command.extend(["--wake", "--duration", str(parsed.duration)])
    if parsed.model:
        command.extend(["--model", parsed.model])
    if parsed.temperature is not None:
        command.extend(["--temperature", str(parsed.temperature)])
    if parsed.action_tendency:
        command.append("--action-tendency")
    if parsed.reach_continuations is not None:
        command.extend(["--reach-continuations", str(parsed.reach_continuations)])
    if parsed.trace_prompts:
        command.append("--trace-prompts")
    if parsed.output_dir:
        command.extend(["--output-dir", parsed.output_dir])
    return _run(command, env=runtime_env)


def _seed_residents(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python dev.py seed-residents",
        description="Plan or create a small dormant cohort in exactly one city.",
    )
    parser.add_argument("--city", required=True, help="city shard directory name")
    parser.add_argument("--count", type=int, default=3, help="resident count (1-5)")
    parser.add_argument("--seed", type=int, default=0, help="repeatable creation deal")
    parser.add_argument("--location", action="append", default=[])
    parser.add_argument("--apply", action="store_true", help="create homes; omitted means dry-run")
    parsed = parser.parse_args(args)
    if Path(parsed.city).name != parsed.city:
        parser.error("--city must be a single directory name")
    if not 1 <= parsed.count <= 5:
        parser.error("--count must be between 1 and 5")

    city_dir = ROOT / "shards" / parsed.city
    compose_file = city_dir / "docker-compose.yml"
    if not compose_file.is_file():
        print(f"City shard not found: {parsed.city}", file=sys.stderr)
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
        ],
        cwd=ENGINE_DIR,
    )
    if topology != 0:
        return topology

    runtime_env = _city_runtime_env(city_dir)
    backend_port = str(runtime_env.get("BACKEND_PORT") or "").strip()
    if not backend_port:
        print(f"BACKEND_PORT is missing from {city_dir / '.env'}.", file=sys.stderr)
        return 2
    runtime_env.update(
        {
            "WW_SERVER_URL": f"http://localhost:{backend_port}",
            "WW_RESIDENTS_DIR": str(city_dir / "residents"),
            "WW_DOULA": "0",
        }
    )
    command = [
        sys.executable,
        str(AGENT_DIR / "scripts" / "seed_residents.py"),
        "--residents-dir",
        runtime_env["WW_RESIDENTS_DIR"],
        "--server-url",
        runtime_env["WW_SERVER_URL"],
        "--count",
        str(parsed.count),
        "--seed",
        str(parsed.seed),
    ]
    for location in parsed.location:
        command.extend(["--location", location])
    if parsed.apply:
        command.append("--apply")
    return _run(command, env=runtime_env)


def _conversation_health(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python dev.py conversation-health",
        description="Measure aggregate public city-conversation health without printing source speech.",
    )
    parser.add_argument("--city", required=True, help="city shard directory name")
    parser.add_argument(
        "--since-hours",
        type=float,
        default=24.0,
        help="public chat lookback window (0.25-720 hours)",
    )
    parser.add_argument(
        "--minimum-speakers",
        type=int,
        default=3,
        help="minimum population for language metrics (3-100)",
    )
    parser.add_argument("--windows", type=int, default=3, help="ordered comparison windows (2-12)")
    parser.add_argument("--shuffle-seed", type=int, default=0, help="repeatable null-comparison seed")
    parsed = parser.parse_args(args)
    if Path(parsed.city).name != parsed.city:
        parser.error("--city must be a single directory name")
    if not 0.25 <= parsed.since_hours <= 720:
        parser.error("--since-hours must be between 0.25 and 720")
    if not 3 <= parsed.minimum_speakers <= 100:
        parser.error("--minimum-speakers must be between 3 and 100")
    if not 2 <= parsed.windows <= 12:
        parser.error("--windows must be between 2 and 12")

    city_dir = ROOT / "shards" / parsed.city
    compose_file = city_dir / "docker-compose.yml"
    if not compose_file.is_file():
        print(f"City shard not found: {parsed.city}", file=sys.stderr)
        return 2
    docker = shutil.which("docker")
    if not docker:
        print(
            "Docker is required to read the selected city's public chat store.",
            file=sys.stderr,
        )
        return 2

    command = [
        docker,
        "compose",
        "-p",
        parsed.city,
        "-f",
        str(compose_file),
        "exec",
        "-T",
        "backend",
        "python",
        "scripts/conversation_health.py",
        "--since-hours",
        str(parsed.since_hours),
        "--minimum-speakers",
        str(parsed.minimum_speakers),
        "--windows",
        str(parsed.windows),
        "--shuffle-seed",
        str(parsed.shuffle_seed),
    ]
    return _run(command, cwd=city_dir)


def _space_policy(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python dev.py space-policy",
        description="Assign one reviewed exact place to one activated resident without starting them.",
    )
    parser.add_argument("--city", required=True, help="city shard directory name")
    parser.add_argument("--location", required=True, help="exact canonical place name")
    parser.add_argument("--controller-resident", required=True, help="resident directory name")
    parser.add_argument(
        "--mode",
        choices=("public", "requestable", "private", "closed"),
        default="private",
    )
    parser.add_argument("--note", default="", help="short steward-visible setup note")
    parsed = parser.parse_args(args)
    if Path(parsed.city).name != parsed.city or Path(parsed.controller_resident).name != parsed.controller_resident:
        parser.error("--city and --controller-resident must be single directory names")

    city_dir = ROOT / "shards" / parsed.city
    compose_file = city_dir / "docker-compose.yml"
    resident_home = city_dir / "residents" / parsed.controller_resident
    if not compose_file.is_file():
        print(f"City shard not found: {parsed.city}", file=sys.stderr)
        return 2
    try:
        manifest = json.loads((resident_home / "identity" / "hearth_manifest.json").read_text(encoding="utf-8"))
        activation = json.loads((resident_home / "hearth_activation.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Resident hearth is not ready for stewardship: {exc}", file=sys.stderr)
        return 2
    actor_id = str(manifest.get("actor_id") or "").strip()
    if not actor_id or activation.get("state") != "active" or str(activation.get("actor_id") or "").strip() != actor_id:
        print(
            "Resident hearth must be active and match its stable actor ID.",
            file=sys.stderr,
        )
        return 2

    topology = _run(
        [
            sys.executable,
            "scripts/dev.py",
            "weave-status",
            "--city",
            parsed.city,
            "--strict",
        ],
        cwd=ENGINE_DIR,
    )
    if topology != 0:
        return topology
    docker = shutil.which("docker")
    if not docker:
        print(
            "Docker is required to reach the selected city's trusted setup seam.",
            file=sys.stderr,
        )
        return 2
    command = [
        docker,
        "compose",
        "-p",
        parsed.city,
        "-f",
        str(compose_file),
        "exec",
        "-T",
        "backend",
        "python",
        "scripts/setup_space_policy.py",
        "--location",
        parsed.location,
        "--controller-actor-id",
        actor_id,
        "--mode",
        parsed.mode,
    ]
    if parsed.note:
        command.extend(["--note", parsed.note])
    return _run(command, cwd=city_dir)


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
  python dev.py resident --city CITY --resident NAME --activate
                                        activate a dormant hearth, then preflight it without waking
  python dev.py resident --city CITY --resident NAME --wake --ticks 3
                                        smoke-test that resident with compressed ticks
  python dev.py resident --city CITY --resident NAME --wake --duration 15m
                                        observe that resident at their natural cadence
  python dev.py cohort --city CITY     preflight every resident without waking
  python dev.py cohort --city CITY --wake --duration 30m
                                        run a bounded cohort, then park everyone
  python dev.py seed-residents --city CITY --count 3
                                        plan a small dormant cohort (dry-run)
  python dev.py seed-residents --city CITY --count 3 --apply
                                        create homes without activating or waking them
  python dev.py conversation-health --city CITY --since-hours 24
                                        aggregate public speech without printing it
  python dev.py space-policy --city CITY --location PLACE --controller-resident NAME
                                        assign one reviewed place without waking its controller
  python dev.py new-shard CITY [options]
                                        create an isolated, folder-operated node
  python dev.py city-draft create --city CITY
                                        build a private draft and preview outside published packs
  python dev.py city-studio             open the private browser editor on this computer
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
    if command == "cohort":
        return _cohort(rest)
    if command == "seed-residents":
        return _seed_residents(rest)
    if command == "conversation-health":
        return _conversation_health(rest)
    if command == "space-policy":
        return _space_policy(rest)
    if command == "new-shard":
        return _run([sys.executable, "scripts/new_shard.py", *rest], cwd=ENGINE_DIR)
    if command == "city-draft":
        return _run([sys.executable, "scripts/city_draft.py", *rest], cwd=ENGINE_DIR)
    if command == "city-studio":
        return _run([sys.executable, "scripts/city_studio.py", *rest], cwd=ENGINE_DIR)
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
