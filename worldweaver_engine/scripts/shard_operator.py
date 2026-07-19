#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Operate one WorldWeaver node from its own folder."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
COMPOSE_FILE = ROOT / "docker-compose.yml"
ENV_FILE = ROOT / ".env"
NODE_FILE = ROOT / "node.json"
PRIVATE_KEY = ROOT / "identity" / "node.key"
BACKUP_SCHEMA = "worldweaver.node-backup"
BACKUP_SCHEMA_VERSION = 1
MUTABLE_IMAGE_TAGS = {"latest", "main", "master", "edge", "dev", "stable"}


class OperatorError(RuntimeError):
    pass


def _read_env(path: Path = ENV_FILE) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _write_env_values(updates: dict[str, str], path: Path = ENV_FILE) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)
    output: list[str] = []
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)
    output.extend(f"{key}={value}" for key, value in remaining.items())
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _compose(
    *arguments: str,
    check: bool = True,
    capture: bool = False,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess:
    command = ["docker", "compose", "--project-directory", str(ROOT), "-f", str(COMPOSE_FILE), *arguments]
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        input=input_bytes,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=False,
    )


def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def _services(*, running_only: bool = False) -> set[str]:
    arguments = ["ps", "--services"]
    if running_only:
        arguments.extend(["--status", "running"])
    result = _compose(*arguments, capture=True)
    return {line.strip() for line in result.stdout.decode("utf-8").splitlines() if line.strip()}


def _is_immutable_image(reference: str) -> bool:
    value = str(reference or "").strip()
    if re.search(r"@sha256:[0-9a-f]{64}$", value):
        return True
    last_component = value.rsplit("/", 1)[-1]
    if ":" not in last_component:
        return False
    tag = last_component.rsplit(":", 1)[-1].lower()
    if tag in MUTABLE_IMAGE_TAGS:
        return False
    return bool(re.fullmatch(r"sha-[0-9a-f]{7,40}", tag) or re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+][0-9a-z.-]+)?", tag))


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _secure_mode(path: Path) -> bool:
    return os.name == "nt" or path.stat().st_mode & 0o077 == 0


def _url_problem(label: str, value: str) -> str | None:
    if not value:
        return None
    from urllib.parse import urlparse

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return f"{label} is not a valid HTTP(S) URL."
    return None


def _https_url(value: str, label: str, *, origin_only: bool = False) -> str:
    from urllib.parse import urlparse

    normalized = str(value or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme != "https" or not parsed.netloc:
        raise OperatorError(f"{label} must be a complete HTTPS URL.")
    if origin_only and (parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise OperatorError(f"{label} must be an origin without a path, query, or fragment.")
    return normalized


def collect_problems(*, offline: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    env = _read_env()

    for path in (COMPOSE_FILE, ENV_FILE, NODE_FILE, PRIVATE_KEY):
        if not path.is_file():
            errors.append(f"Missing required file: {path.relative_to(ROOT)}")
    if errors:
        return errors, warnings

    for path in (ENV_FILE, PRIVATE_KEY):
        if not _secure_mode(path):
            errors.append(f"{path.relative_to(ROOT)} is readable by other local users; run setup to repair permissions.")

    try:
        descriptor = json.loads(NODE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        errors.append("node.json is not valid JSON.")
        descriptor = {}
    if descriptor.get("schema") != "worldweaver.node" or descriptor.get("schema_version") != 1:
        errors.append("node.json uses an unsupported descriptor version.")
    if str(descriptor.get("node_id") or "") != env.get("SHARD_ID", ""):
        errors.append("node.json and .env name different node IDs.")

    required = ("COMPOSE_PROJECT_NAME", "SHARD_ID", "BACKEND_PORT", "WW_DB_EXTERNAL_PORT", "WW_DB_PASSWORD", "WW_JWT_SECRET", "WW_DATA_ENCRYPTION_KEY", "WW_ENGINE_IMAGE")
    for key in required:
        if not env.get(key):
            errors.append(f"{key} is missing from .env.")
    if env.get("SHARD_TYPE") != "world" and not env.get("WW_AGENT_IMAGE"):
        errors.append("WW_AGENT_IMAGE is missing from this city node.")
    if env.get("SHARD_TYPE") == "world":
        admission_mode = env.get("WW_FEDERATION_ADMISSION_MODE", "")
        if admission_mode not in {"closed", "open"}:
            errors.append("WW_FEDERATION_ADMISSION_MODE must be 'closed' or 'open' on a federation directory.")
        elif admission_mode == "open":
            warnings.append("This federation directory admits any new node that can sign its registration request.")

    for key in ("WW_ENGINE_IMAGE", "WW_AGENT_IMAGE"):
        if env.get(key) and not _is_immutable_image(env[key]):
            errors.append(f"{key} must use a version tag or image digest, not a moving tag.")
    if env.get("WW_DB_PASSWORD") in {"postgres", "password", "CHANGE_ME"}:
        errors.append("WW_DB_PASSWORD still uses a placeholder value.")
    if len(env.get("WW_JWT_SECRET", "")) < 48:
        errors.append("WW_JWT_SECRET is too short.")
    if len(env.get("WW_DATA_ENCRYPTION_KEY", "")) != 44:
        errors.append("WW_DATA_ENCRYPTION_KEY is not a generated Fernet key.")
    if env.get("FEDERATION_TOKEN"):
        warnings.append("FEDERATION_TOKEN is set. Signed node identity should replace shared federation secrets.")
    if env.get("WW_ENABLE_DEV_RESET", "").lower() in {"1", "true", "yes"}:
        warnings.append("Initial world seeding is enabled. Run seed before exposing this node publicly.")

    for label, key in (("public API URL", "WW_PUBLIC_URL"), ("public client URL", "WW_CLIENT_URL"), ("federation URL", "FEDERATION_URL")):
        problem = _url_problem(label, env.get(key, ""))
        if problem:
            errors.append(problem)

    public_url = env.get("WW_PUBLIC_URL", "")
    if public_url.startswith("https://"):
        if env.get("WW_CORS_ORIGINS", "*") == "*":
            warnings.append("Public HTTPS is configured but browser CORS still allows every origin.")
        if env.get("WW_TRUST_CLOUDFLARE_PROXY", "false").lower() in {"1", "true", "yes"} and env.get("WW_INGRESS_PROVIDER", "").lower() != "cloudflare":
            errors.append("Cloudflare visitor headers may only be trusted when WW_INGRESS_PROVIDER=cloudflare.")

    try:
        backend_port = int(env.get("BACKEND_PORT", "0"))
        db_port = int(env.get("WW_DB_EXTERNAL_PORT", "0"))
        if not (1 <= backend_port <= 65535 and 1 <= db_port <= 65535):
            raise ValueError
        if backend_port == db_port:
            errors.append("The backend and database cannot publish the same host port.")
    except ValueError:
        errors.append("BACKEND_PORT and WW_DB_EXTERNAL_PORT must be valid port numbers.")
        backend_port = db_port = 0

    if offline:
        return errors, warnings
    if not _docker_available():
        errors.append("Docker is not running or cannot be reached.")
        return errors, warnings
    try:
        _compose("config", "--quiet", capture=True)
        running = _services(running_only=True)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        errors.append(f"Docker Compose rejected this folder: {detail or 'invalid configuration'}")
        return errors, warnings
    if not running:
        for label, port in (("backend", backend_port), ("database", db_port)):
            if port and not _port_is_free(port):
                errors.append(f"Host port {port} for the {label} is already in use.")
    return errors, warnings


def command_check(args: argparse.Namespace) -> int:
    errors, warnings = collect_problems(offline=args.offline)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        print(f"Check failed with {len(errors)} problem(s).", file=sys.stderr)
        return 1
    print("Node folder check passed.")
    return 0


def command_setup(args: argparse.Namespace) -> int:
    for directory in (ROOT / "data", ROOT / "residents", ROOT / "identity", ROOT / "backups"):
        directory.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        if ENV_FILE.exists():
            ENV_FILE.chmod(0o600)
        if PRIVATE_KEY.exists():
            PRIVATE_KEY.chmod(0o600)
        PRIVATE_KEY.parent.chmod(0o700)
    if command_check(argparse.Namespace(offline=False)):
        return 1
    if not args.no_pull:
        _compose("pull")
    print("Setup complete. Agents remain stopped until start --agents is requested.")
    return 0


def _wait_for_backend(timeout: int = 90) -> bool:
    env = _read_env()
    url = f"http://127.0.0.1:{env.get('BACKEND_PORT', '')}/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 300:
                    return True
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            time.sleep(1)
    return False


def command_start(args: argparse.Namespace) -> int:
    if command_check(argparse.Namespace(offline=False)):
        return 1
    services = ["db", "backend"]
    if args.agents and _read_env().get("SHARD_TYPE") != "world":
        services.append("agent")
    _compose("up", "-d", *services)
    if not _wait_for_backend():
        raise OperatorError("The backend did not become healthy within 90 seconds.")
    print("Node is healthy.")
    if "agent" not in services and _read_env().get("SHARD_TYPE") != "world":
        print("Residents are still stopped. Use: python ww.py start --agents")
    return 0


def command_stop(_args: argparse.Namespace) -> int:
    if not _docker_available():
        raise OperatorError("Docker is not running or cannot be reached.")
    _compose("stop")
    print("Node stopped. Data and containers were kept.")
    return 0


def command_status(_args: argparse.Namespace) -> int:
    if not _docker_available():
        raise OperatorError("Docker is not running or cannot be reached.")
    _compose("ps")
    if "backend" in _services(running_only=True):
        print("Backend health: healthy" if _wait_for_backend(timeout=3) else "Backend health: not responding")
    return 0


def command_seed(_args: argparse.Namespace) -> int:
    env = _read_env()
    if env.get("SHARD_TYPE") == "world":
        raise OperatorError("A federation root has no city pack to seed.")
    if "backend" not in _services(running_only=True):
        raise OperatorError("Start the node before seeding its city pack.")
    port = env["BACKEND_PORT"]
    world_id_url = f"http://127.0.0.1:{port}/api/world/id"
    with urllib.request.urlopen(world_id_url, timeout=10) as response:
        existing = json.loads(response.read().decode("utf-8"))
    if existing.get("seeded"):
        print(f"City is already seeded as {existing.get('world_id')}.")
    else:
        city_id = env.get("CITY_ID", "").strip()
        city_name = city_id.replace("_", " ").title()
        payload = {
            "world_theme": f"Everyday life in {city_name}, using the places defined by its city pack.",
            "player_role": "A resident of this city.",
            "description": f"A persistent shared city in {city_name}.",
            "tone": "grounded and observational",
            "seed_from_city_pack": True,
            "enrich_city_pack": False,
            "city_id": city_id,
        }
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/world/seed",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            seeded = json.loads(response.read().decode("utf-8"))
        print(f"Seeded {seeded.get('nodes_seeded', 0)} places as {seeded.get('world_id')}.")
    _write_env_values({"WW_ENABLE_DEV_RESET": "false"})
    _compose("up", "-d", "--no-deps", "--force-recreate", "backend")
    if not _wait_for_backend():
        raise OperatorError("Backend did not become healthy after closing the seed/reset endpoint.")
    print("The seed/reset endpoint is now disabled for routine operation.")
    return 0


def command_update(args: argparse.Namespace) -> int:
    env = _read_env()
    updates = {key: value for key, value in (("WW_ENGINE_IMAGE", args.engine_image), ("WW_AGENT_IMAGE", args.agent_image)) if value}
    for key, value in updates.items():
        if not _is_immutable_image(value):
            raise OperatorError(f"{key} must use a version tag or image digest.")
    original = {key: env.get(key, "") for key in updates}
    agents_were_running = "agent" in _services(running_only=True) if _docker_available() else False
    if updates:
        _write_env_values(updates)
    try:
        if command_check(argparse.Namespace(offline=False)):
            raise OperatorError("The updated folder did not pass its safety check.")
        _compose("pull")
    except Exception:
        if original:
            _write_env_values(original)
        raise
    services = ["db", "backend"]
    if (args.agents or agents_were_running) and _read_env().get("SHARD_TYPE") != "world":
        services.append("agent")
    _compose("up", "-d", *services)
    if not _wait_for_backend():
        raise OperatorError("Updated backend did not become healthy within 90 seconds.")
    print("Node update complete.")
    return 0


def _database_dump() -> bytes:
    env = _read_env()
    result = _compose(
        "exec",
        "-T",
        "db",
        "pg_dump",
        "--format=custom",
        "--create",
        "--clean",
        "--if-exists",
        "-U",
        env["WW_DB_USER"],
        "-d",
        env["WW_DB_NAME"],
        capture=True,
    )
    return result.stdout


def command_backup(args: argparse.Namespace) -> int:
    if "db" not in _services(running_only=True):
        raise OperatorError("Start the node database before making a backup.")
    descriptor = json.loads(NODE_FILE.read_text(encoding="utf-8"))
    destination_dir = Path(args.output).expanduser().resolve() if args.output else ROOT / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = destination_dir / f"{descriptor['node_id']}-{timestamp}.tar.gz"
    with tempfile.TemporaryDirectory(prefix="worldweaver-backup-") as temporary_name:
        temporary = Path(temporary_name)
        (temporary / "database.dump").write_bytes(_database_dump())
        manifest = {
            "schema": BACKUP_SCHEMA,
            "schema_version": BACKUP_SCHEMA_VERSION,
            "node_id": descriptor["node_id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "contains_private_identity": True,
            "contains_resident_state": True,
        }
        (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(temporary / "manifest.json", arcname="manifest.json")
            bundle.add(temporary / "database.dump", arcname="database.dump")
            for relative in (".env", "docker-compose.yml", "node.json", "identity", "data", "residents"):
                path = ROOT / relative
                if path.exists():
                    bundle.add(path, arcname=relative)
    archive.chmod(0o600)
    print(f"Backup written to {archive}")
    print("This file contains credentials, the node private key, and private resident state. Store it accordingly.")
    return 0


def _safe_archive_members(bundle: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = bundle.getmembers()
    for member in members:
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
            raise OperatorError("Backup contains an unsafe path or link.")
    return members


def command_restore(args: argparse.Namespace) -> int:
    archive = Path(args.archive).expanduser().resolve()
    if not archive.is_file():
        raise OperatorError(f"Backup does not exist: {archive}")
    if not args.yes:
        raise OperatorError("Restore replaces this node's private state. Re-run with --yes after checking the backup path.")
    if _docker_available() and _services(running_only=True):
        raise OperatorError("Stop the node before restoring a backup.")

    with tempfile.TemporaryDirectory(prefix="worldweaver-restore-") as temporary_name:
        staging = Path(temporary_name)
        with tarfile.open(archive, "r:gz") as bundle:
            members = _safe_archive_members(bundle)
            bundle.extractall(staging, members=members, filter="fully_trusted")
        manifest = json.loads((staging / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("schema") != BACKUP_SCHEMA or manifest.get("schema_version") != BACKUP_SCHEMA_VERSION:
            raise OperatorError("Backup uses an unsupported format.")
        if NODE_FILE.exists():
            current = json.loads(NODE_FILE.read_text(encoding="utf-8"))
            if current.get("node_id") != manifest.get("node_id"):
                raise OperatorError("Backup belongs to a different node identity.")

        for relative in (".env", "docker-compose.yml", "node.json"):
            source = staging / relative
            if not source.is_file():
                raise OperatorError(f"Backup is missing {relative}.")
            shutil.copy2(source, ROOT / relative)
        for relative in ("identity", "data", "residents"):
            source = staging / relative
            destination = ROOT / relative
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
        if os.name != "nt":
            ENV_FILE.chmod(0o600)
            PRIVATE_KEY.chmod(0o600)
            PRIVATE_KEY.parent.chmod(0o700)

        _compose("up", "-d", "db")
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            result = _compose("exec", "-T", "db", "pg_isready", check=False, capture=True)
            if result.returncode == 0:
                break
            time.sleep(1)
        else:
            raise OperatorError("Restored database container did not become ready.")
        env = _read_env()
        dump = (staging / "database.dump").read_bytes()
        _compose(
            "exec",
            "-T",
            "db",
            "pg_restore",
            "--clean",
            "--create",
            "--if-exists",
            "--exit-on-error",
            "-U",
            env["WW_DB_USER"],
            "-d",
            "postgres",
            input_bytes=dump,
        )
        _compose("stop", "db")
    print("Restore complete. Run check, then start the node when ready.")
    return 0


def _public_node_descriptor(path_value: str) -> dict[str, str]:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OperatorError(f"Could not read public node descriptor {path}: {exc}") from exc
    if raw.get("schema") != "worldweaver.node" or raw.get("schema_version") != 1:
        raise OperatorError("The public node descriptor uses an unsupported format.")
    node_id = str(raw.get("node_id") or "").strip()
    shard_type = str(raw.get("shard_type") or "").strip()
    public_key = str(raw.get("public_key") or "").strip()
    city_id = str(raw.get("city_id") or "").strip()
    if not node_id or len(node_id) > 80 or any(character.isspace() for character in node_id):
        raise OperatorError("The public node descriptor has an invalid node ID.")
    if shard_type not in {"city", "world", "neighborhood"}:
        raise OperatorError("The public node descriptor has an invalid shard type.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", public_key):
        raise OperatorError("The public node descriptor does not contain a valid Ed25519 public key.")
    return {
        "node_id": node_id,
        "shard_type": shard_type,
        "public_key": public_key,
        "city_id": city_id,
    }


def command_node(args: argparse.Namespace) -> int:
    if _read_env().get("SHARD_TYPE") != "world":
        raise OperatorError("Node admission is managed by a federation directory, not a city node.")
    if "backend" not in _services(running_only=True):
        raise OperatorError("Start the federation directory before managing admitted nodes.")

    command = ["exec", "-T", "backend", "python", "scripts/federation_nodes.py", args.node_action]
    if args.node_action in {"admit", "recover"}:
        descriptor = _public_node_descriptor(args.descriptor)
        command.extend(
            [
                "--node-id",
                descriptor["node_id"],
                "--public-key",
                descriptor["public_key"],
                "--shard-type",
                descriptor["shard_type"],
                "--city-id",
                descriptor["city_id"],
                "--reason",
                args.reason,
            ]
        )
    elif args.node_action == "revoke":
        command.extend([args.node_id, "--reason", args.reason])
    elif args.node_action == "history":
        command.append(args.node_id)
    _compose(*command)
    return 0


def command_public_config(args: argparse.Namespace) -> int:
    env = _read_env()
    if env.get("SHARD_TYPE") != "world" and env.get("WW_ENABLE_DEV_RESET", "").lower() in {"1", "true", "yes"}:
        raise OperatorError("Seed the city and close its reset endpoint before configuring public ingress.")
    if args.ingress_provider == "cloudflare":
        compose = COMPOSE_FILE.read_text(encoding="utf-8")
        if not re.search(r"127\.0\.0\.1:\$\{BACKEND_PORT(?::-[0-9]+)?\}:8000", compose):
            raise OperatorError("Cloudflare ingress requires the backend port to bind only to 127.0.0.1.")

    api_url = _https_url(args.api_url, "API URL")
    client_url = _https_url(args.client_url, "client URL") if args.client_url else ""
    cors_origins = [_https_url(value, "CORS origin", origin_only=True) for value in args.cors_origin]
    if not cors_origins:
        raise OperatorError("At least one exact --cors-origin is required for public ingress.")
    updates = {
        "WW_PUBLIC_URL": api_url,
        "WW_CLIENT_URL": client_url,
        "WW_CORS_ORIGINS": ",".join(cors_origins),
        "WW_INGRESS_PROVIDER": args.ingress_provider,
        "WW_TRUST_CLOUDFLARE_PROXY": "true" if args.ingress_provider == "cloudflare" else "false",
    }
    if env.get("SHARD_TYPE") != "world":
        federation_url = _https_url(args.federation_url, "federation URL")
        updates["FEDERATION_URL"] = federation_url
        updates["WW_RUNTIME_FEDERATION_URL"] = federation_url

    original = {key: env.get(key, "") for key in updates}
    was_running = _docker_available() and "backend" in _services(running_only=True)
    _write_env_values(updates)
    try:
        if command_check(argparse.Namespace(offline=not _docker_available())):
            raise OperatorError("Public configuration did not pass the node folder safety check.")
        if was_running:
            _compose("up", "-d", "--no-deps", "--force-recreate", "backend")
            if not _wait_for_backend():
                raise OperatorError("Backend did not become healthy after applying public configuration.")
    except Exception:
        _write_env_values(original)
        if was_running:
            _compose("up", "-d", "--no-deps", "--force-recreate", "backend", check=False)
            _wait_for_backend()
        raise
    print("Public node configuration saved.")
    print("This command did not create DNS records or start an ingress tunnel.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate this WorldWeaver node folder.")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="check configuration, permissions, ports, images, and Docker")
    check.add_argument("--offline", action="store_true", help="check files without contacting Docker or testing ports")
    check.set_defaults(handler=command_check)

    setup = commands.add_parser("setup", help="prepare folders, permissions, and images without starting residents")
    setup.add_argument("--no-pull", action="store_true", help="do not download container images")
    setup.set_defaults(handler=command_setup)

    start = commands.add_parser("start", help="start the database and world server")
    start.add_argument("--agents", action="store_true", help="also wake residents in this city")
    start.set_defaults(handler=command_start)

    stop = commands.add_parser("stop", help="stop this node without deleting data")
    stop.set_defaults(handler=command_stop)

    status = commands.add_parser("status", help="show this node's containers and backend health")
    status.set_defaults(handler=command_status)

    seed = commands.add_parser("seed", help="seed this city pack once, then disable the reset endpoint")
    seed.set_defaults(handler=command_seed)

    update = commands.add_parser("update", help="pull a chosen immutable version and restart running services")
    update.add_argument("--engine-image", default="")
    update.add_argument("--agent-image", default="")
    update.add_argument("--agents", action="store_true", help="wake residents after updating")
    update.set_defaults(handler=command_update)

    backup = commands.add_parser("backup", help="make a restricted full-node backup")
    backup.add_argument("--output", default="", help="backup directory (default: ./backups)")
    backup.set_defaults(handler=command_backup)

    restore = commands.add_parser("restore", help="restore a full-node backup into this folder")
    restore.add_argument("archive")
    restore.add_argument("--yes", action="store_true", help="confirm replacement of current private node state")
    restore.set_defaults(handler=command_restore)

    node = commands.add_parser("node", help="manage nodes trusted by this federation directory")
    node_commands = node.add_subparsers(dest="node_action", required=True)
    node_commands.add_parser("list", help="list admitted and revoked nodes")
    history = node_commands.add_parser("history", help="show the trust history for one node")
    history.add_argument("node_id")
    admit = node_commands.add_parser("admit", help="admit a safe-to-share node.json descriptor")
    admit.add_argument("descriptor")
    admit.add_argument("--reason", required=True)
    revoke = node_commands.add_parser("revoke", help="block a known node from private federation routes")
    revoke.add_argument("node_id")
    revoke.add_argument("--reason", required=True)
    recover = node_commands.add_parser("recover", help="replace the key for a previously revoked node")
    recover.add_argument("descriptor")
    recover.add_argument("--reason", required=True)
    node.set_defaults(handler=command_node)

    public = commands.add_parser("public-config", help="set reviewed HTTPS and browser-origin configuration")
    public.add_argument("--api-url", required=True, help="public HTTPS API address for this node")
    public.add_argument("--client-url", default="", help="public HTTPS human client address")
    public.add_argument("--federation-url", default="", help="public HTTPS directory address (required for city nodes)")
    public.add_argument("--cors-origin", action="append", default=[], help="exact HTTPS browser origin; may be repeated")
    public.add_argument("--ingress-provider", required=True, choices=("cloudflare", "reverse-proxy"))
    public.set_defaults(handler=command_public_config)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.handler(args) or 0)
    except (OperatorError, subprocess.CalledProcessError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
