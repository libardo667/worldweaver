#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One developer command for the WorldWeaver workspace."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
ENGINE_DIR = ROOT / "worldweaver_engine"
AGENT_DIR = ROOT / "ww_agent"
REQUIREMENTS = ROOT / "requirements.txt"


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _run(command: list[str], *, cwd: Path = ROOT) -> int:
    print(f"\n==> {' '.join(command)}", flush=True)
    return subprocess.call(command, cwd=cwd)


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
        print("The shared environment is missing or unusable. Run: python dev.py install", file=sys.stderr)
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
