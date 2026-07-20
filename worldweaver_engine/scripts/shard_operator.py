#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Operate one WorldWeaver node from its own folder."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
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
HEARTH_HOST_DIR = ROOT / "hearth-host"
HEARTH_TRANSPORT_KEY = HEARTH_HOST_DIR / "identity" / "transport.key"
HEARTH_TRANSPORT_DESCRIPTOR = ROOT / "hearth-host.json"
BACKUP_SCHEMA = "worldweaver.node-backup"
BACKUP_SCHEMA_VERSION = 1
MUTABLE_IMAGE_TAGS = {"latest", "main", "master", "edge", "dev", "stable"}
MAP_PUBLISH_UNCHANGED_FILES = (
    "neighborhoods.json",
    "transit_graph.json",
    "landmarks.json",
    "street_corridors.json",
    "travel_hubs.json",
    "inter_city.json",
    "stoops.json",
    "weather_config.json",
    "transit_config.json",
)


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


def _hearth_transport_descriptor(raw: object) -> dict[str, object]:
    """Validate the small public half of a hearth-host transport identity."""

    fields = {
        "schema",
        "schema_version",
        "transport_key_id",
        "transport_public_key",
    }
    if not isinstance(raw, dict) or set(raw) != fields:
        raise OperatorError("hearth-host.json has unexpected fields.")
    encoded = raw.get("transport_public_key")
    if not isinstance(encoded, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", encoded):
        raise OperatorError("hearth-host.json has an invalid public key.")
    try:
        public_key = base64.urlsafe_b64decode(encoded + "=")
    except ValueError as exc:
        raise OperatorError("hearth-host.json has an invalid public key.") from exc
    expected_key_id = f"x25519:{hashlib.sha256(public_key).hexdigest()[:32]}"
    if len(public_key) != 32 or raw.get("schema") != "worldweaver.hearth-transport" or type(raw.get("schema_version")) is not int or raw.get("schema_version") != 1 or raw.get("transport_key_id") != expected_key_id:
        raise OperatorError("hearth-host.json is not a valid hearth transport descriptor.")
    return raw


def _read_hearth_transport_descriptor() -> dict[str, object]:
    try:
        return _hearth_transport_descriptor(json.loads(HEARTH_TRANSPORT_DESCRIPTOR.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise OperatorError("hearth-host.json could not be read.") from exc


def _write_new_public_descriptor(descriptor: dict[str, object]) -> None:
    HEARTH_TRANSPORT_DESCRIPTOR.parent.mkdir(parents=True, exist_ok=True)
    try:
        with HEARTH_TRANSPORT_DESCRIPTOR.open("x", encoding="utf-8") as handle:
            json.dump(descriptor, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise OperatorError("Refusing to replace the existing hearth-host.json.") from exc


def collect_problems(*, offline: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    env = _read_env()

    required_paths = [COMPOSE_FILE, ENV_FILE, NODE_FILE, PRIVATE_KEY]
    for path in required_paths:
        if not path.is_file():
            errors.append(f"Missing required file: {path.relative_to(ROOT)}")
    if errors:
        return errors, warnings

    private_paths = [ENV_FILE, PRIVATE_KEY]
    if HEARTH_TRANSPORT_KEY.is_file():
        private_paths.append(HEARTH_TRANSPORT_KEY)
    for path in private_paths:
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

    if env.get("SHARD_TYPE") != "world" and (HEARTH_TRANSPORT_KEY.exists() or HEARTH_TRANSPORT_DESCRIPTOR.exists()):
        if not HEARTH_TRANSPORT_KEY.is_file() or HEARTH_TRANSPORT_KEY.is_symlink() or not HEARTH_TRANSPORT_DESCRIPTOR.is_file() or HEARTH_TRANSPORT_DESCRIPTOR.is_symlink():
            errors.append("Hearth transport identity is incomplete; both the private key and public descriptor are required.")
        else:
            try:
                _read_hearth_transport_descriptor()
            except OperatorError:
                errors.append("hearth-host.json is not a valid hearth transport descriptor.")
    elif env.get("SHARD_TYPE") != "world":
        warnings.append("This legacy city folder has no hearth transport key and cannot receive encrypted hearth packages.")

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
    directories = [ROOT / "data", ROOT / "residents", ROOT / "identity", ROOT / "backups"]
    if _read_env().get("SHARD_TYPE") != "world":
        directories.append(HEARTH_TRANSPORT_KEY.parent)
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        if ENV_FILE.exists():
            ENV_FILE.chmod(0o600)
        if PRIVATE_KEY.exists():
            PRIVATE_KEY.chmod(0o600)
        if HEARTH_TRANSPORT_KEY.exists():
            HEARTH_TRANSPORT_KEY.chmod(0o600)
        PRIVATE_KEY.parent.chmod(0o700)
        if HEARTH_TRANSPORT_KEY.parent.exists():
            HEARTH_TRANSPORT_KEY.parent.chmod(0o700)
    if command_check(argparse.Namespace(offline=False)):
        return 1
    if not args.no_pull:
        _compose("pull")
    print("Setup complete. Agents remain stopped until start --agents is requested.")
    return 0


def command_hearth_host(args: argparse.Namespace) -> int:
    """Create or verify the city's host-only package decryption identity."""

    if args.hearth_host_action != "initialize":
        raise OperatorError("Unsupported hearth-host action.")
    if _read_env().get("SHARD_TYPE") == "world":
        raise OperatorError("A federation directory does not host resident hearths.")

    private_present = HEARTH_TRANSPORT_KEY.exists() or HEARTH_TRANSPORT_KEY.is_symlink()
    public_present = HEARTH_TRANSPORT_DESCRIPTOR.exists() or HEARTH_TRANSPORT_DESCRIPTOR.is_symlink()
    if HEARTH_TRANSPORT_KEY.is_symlink() or HEARTH_TRANSPORT_DESCRIPTOR.is_symlink():
        raise OperatorError("Hearth transport identity paths must not be symbolic links.")
    if public_present and not private_present:
        raise OperatorError("Refusing to replace a hearth-host descriptor whose private key is missing.")
    if private_present and not HEARTH_TRANSPORT_KEY.is_file():
        raise OperatorError("The hearth transport private key is not a regular file.")
    if public_present and not HEARTH_TRANSPORT_DESCRIPTOR.is_file():
        raise OperatorError("hearth-host.json is not a regular file.")
    if not _docker_available():
        raise OperatorError("Docker is required to initialize a folder-owned hearth host.")

    HEARTH_TRANSPORT_KEY.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        HEARTH_TRANSPORT_KEY.parent.chmod(0o700)
    run_options = ["run", "--rm", "--no-deps"]
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if callable(getuid) and callable(getgid):
        run_options.extend(["--user", f"{getuid()}:{getgid()}"])
    run_options.extend(
        [
            "--volume",
            f"{HEARTH_HOST_DIR.resolve()}:/hearth-host",
            "backend",
            "python",
            "scripts/hearth_transport_identity.py",
            "--private-key",
            "/hearth-host/identity/transport.key",
        ]
    )
    try:
        result = _compose(*run_options, capture=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise OperatorError("The engine image could not initialize the hearth host. " "Update this folder to a current version first." + (f" Details: {detail}" if detail else "")) from exc
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
        descriptor = _hearth_transport_descriptor(payload["descriptor"])
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError, OperatorError) as exc:
        raise OperatorError("The engine image returned an invalid public descriptor.") from exc

    if public_present:
        if _read_hearth_transport_descriptor() != descriptor:
            raise OperatorError("hearth-host.json does not match the folder's private transport key.")
        status = "already ready"
    else:
        _write_new_public_descriptor(descriptor)
        status = "repaired" if private_present else "created"
    if os.name != "nt":
        HEARTH_TRANSPORT_KEY.chmod(0o600)
    print(f"Hearth host identity {status}.")
    print(f"Safe-to-share descriptor: {HEARTH_TRANSPORT_DESCRIPTOR}")
    print("The private transport key stayed inside hearth-host/.")
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


def _canonical_json_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _read_map_release(pack_value: str) -> tuple[Path, dict, dict, str]:
    pack_dir = Path(pack_value).expanduser().resolve()
    manifest_path = pack_dir / "manifest.json"
    artifact_path = pack_dir / "generated_map.json"
    svg_path = pack_dir / "generated_map.svg"
    for path in (manifest_path, artifact_path, svg_path):
        if not path.is_file():
            raise OperatorError(f"Map release is missing {path.name}: {pack_dir}")
    if artifact_path.stat().st_size > 10 * 1024 * 1024 or svg_path.stat().st_size > 20 * 1024 * 1024:
        raise OperatorError("Map release is too large for the folder-local publisher.")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    svg = svg_path.read_text(encoding="utf-8")
    if not isinstance(manifest, dict) or not isinstance(artifact, dict):
        raise OperatorError("Map release manifest and artifact must be JSON objects.")
    city_id = str(manifest.get("city_id") or "").strip()
    version = str(manifest.get("version") or "").strip()
    if not city_id or not version:
        raise OperatorError("Map release manifest needs a city ID and pack version.")
    source = artifact.get("source") if isinstance(artifact.get("source"), dict) else {}
    if str(source.get("city_id") or "").strip() != city_id or str(source.get("pack_version") or "").strip() != version:
        raise OperatorError("Generated map source does not match its manifest city and version.")
    if artifact.get("schema_version") != "1.0.0":
        raise OperatorError("Generated map uses an unsupported schema version.")

    svg_meta = artifact.get("svg") if isinstance(artifact.get("svg"), dict) else {}
    if svg_meta.get("filename") != "generated_map.svg":
        raise OperatorError("Generated map names an unsupported SVG file.")
    if hashlib.sha256(svg.encode("utf-8")).hexdigest() != str(svg_meta.get("sha256") or ""):
        raise OperatorError("Generated map SVG does not match its recorded hash.")
    unsafe_svg_tokens = ("<!doctype", "<script", "<foreignobject", "javascript:", "href=", "url(")
    lowered_svg = svg.lower()
    if not svg.lstrip().startswith("<?xml") or "<svg" not in lowered_svg or any(token in lowered_svg for token in unsafe_svg_tokens):
        raise OperatorError("Generated map SVG contains unsupported active or external content.")

    claimed_hash = str(artifact.get("artifact_sha256") or "").strip()
    hash_payload = dict(artifact)
    hash_payload.pop("artifact_sha256", None)
    if not re.fullmatch(r"[a-f0-9]{64}", claimed_hash) or _canonical_json_hash(hash_payload) != claimed_hash:
        raise OperatorError("Generated map artifact does not match its recorded hash.")
    manifest_map = manifest.get("generated_map") if isinstance(manifest.get("generated_map"), dict) else {}
    if manifest_map.get("artifact_sha256") != claimed_hash:
        raise OperatorError("Manifest and generated map name different artifacts.")

    neighborhoods_path = pack_dir / "neighborhoods.json"
    neighborhoods = json.loads(neighborhoods_path.read_text(encoding="utf-8")) if neighborhoods_path.is_file() else None
    if not isinstance(neighborhoods, list) or not all(isinstance(item, dict) for item in neighborhoods):
        raise OperatorError("Map release needs a neighborhood graph for route verification.")
    expected_routes: set[str] = set()
    for neighborhood in neighborhoods:
        source_id = str(neighborhood.get("id") or "").strip()
        adjacent = neighborhood.get("adjacent_to") if isinstance(neighborhood.get("adjacent_to"), list) else []
        for target_value in adjacent:
            pair = tuple(sorted((source_id, str(target_value or "").strip())))
            if pair[0] and pair[1] and pair[0] != pair[1]:
                expected_routes.add(f"path:{pair[0]}:{pair[1]}")
    routes = artifact.get("routes") if isinstance(artifact.get("routes"), list) else []
    route_ids = {str(route.get("id") or "").strip() for route in routes if isinstance(route, dict)}
    if route_ids != expected_routes:
        raise OperatorError("Generated map routes do not match the release's canonical neighborhood paths.")
    return pack_dir, manifest, artifact, svg


def command_map(args: argparse.Namespace) -> int:
    pack_dir, manifest, artifact, svg = _read_map_release(args.pack_dir)
    city_id = str(manifest["city_id"])
    version = str(manifest["version"])
    digest = str(artifact["artifact_sha256"])
    if args.map_action == "inspect":
        print(f"Verified generated map for {city_id} pack {version} ({digest[:16]}).")
        return 0

    env = _read_env()
    if env.get("SHARD_TYPE") == "world":
        raise OperatorError("A federation directory does not publish a city map.")
    if city_id != env.get("CITY_ID", ""):
        raise OperatorError(f"Map release belongs to {city_id}, not this node's {env.get('CITY_ID', '')} city pack.")
    current_pack_dir = ROOT / "data" / "cities" / city_id
    for filename in MAP_PUBLISH_UNCHANGED_FILES:
        release_file = pack_dir / filename
        current_file = current_pack_dir / filename
        if not release_file.is_file() or not current_file.is_file() or release_file.read_bytes() != current_file.read_bytes():
            raise OperatorError(f"Map-only publication cannot change canonical city-pack file {filename}.")
    if not args.yes:
        raise OperatorError("Map publication replaces this node's public drawing. Re-run with --yes after inspecting the release.")
    if not _docker_available() or "db" not in _services(running_only=True):
        raise OperatorError("Start the node database so a full backup can be made before map publication.")
    if "agent" in _services(running_only=True):
        raise OperatorError("Stop resident agents before publishing a new map drawing.")

    command_backup(argparse.Namespace(output=""))
    target_dir = current_pack_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path]] = []
    for filename, content in (
        ("generated_map.json", json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"),
        ("generated_map.svg", svg),
        ("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"),
    ):
        temporary = target_dir / f".{filename}.publish-{os.getpid()}"
        temporary.write_text(content, encoding="utf-8")
        staged.append((temporary, target_dir / filename))
    # The manifest moves last and acts as the release pointer. Every individual
    # replacement is atomic on the node folder's filesystem.
    for temporary, destination in staged:
        temporary.replace(destination)

    if "backend" in _services(running_only=True):
        _compose("up", "-d", "--no-deps", "--force-recreate", "backend")
        if not _wait_for_backend():
            raise OperatorError("Backend did not become healthy after map publication; restore the backup just created.")
    print(f"Published generated map for {city_id} pack {version} from {pack_dir}.")
    print("Resident agents remain stopped.")
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
            "contains_hearth_transport_identity": (HEARTH_TRANSPORT_KEY.is_file() and HEARTH_TRANSPORT_DESCRIPTOR.is_file()),
        }
        (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(temporary / "manifest.json", arcname="manifest.json")
            bundle.add(temporary / "database.dump", arcname="database.dump")
            for relative in (
                ".env",
                "docker-compose.yml",
                "node.json",
                "hearth-host.json",
                "identity",
                "hearth-host",
                "data",
                "residents",
            ):
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

        required_files = [".env", "docker-compose.yml", "node.json"]
        carries_hearth_transport = bool(manifest.get("contains_hearth_transport_identity"))
        if carries_hearth_transport:
            required_files.append("hearth-host.json")
        for relative in required_files:
            source = staging / relative
            if not source.is_file():
                raise OperatorError(f"Backup is missing {relative}.")
            shutil.copy2(source, ROOT / relative)
        required_directories = ["identity", "data", "residents"]
        if carries_hearth_transport:
            required_directories.append("hearth-host")
        for relative in required_directories:
            source = staging / relative
            destination = ROOT / relative
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
        if os.name != "nt":
            ENV_FILE.chmod(0o600)
            PRIVATE_KEY.chmod(0o600)
            PRIVATE_KEY.parent.chmod(0o700)
            if HEARTH_TRANSPORT_KEY.exists():
                HEARTH_TRANSPORT_KEY.chmod(0o600)
                HEARTH_TRANSPORT_KEY.parent.chmod(0o700)

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


def command_resident_authority(args: argparse.Namespace) -> int:
    if _read_env().get("SHARD_TYPE") == "world":
        raise OperatorError("Resident identities are admitted by a city node, not a federation directory.")
    if "backend" not in _services(running_only=True):
        raise OperatorError("Start this city before managing admitted resident identities.")

    command = [
        "exec",
        "-T",
        "backend",
        "python",
        "scripts/resident_authorities.py",
        args.resident_authority_action,
    ]
    if args.resident_authority_action == "admit":
        descriptor_path = Path(args.descriptor).expanduser()
        if not descriptor_path.is_absolute():
            descriptor_path = ROOT / descriptor_path
        if not descriptor_path.is_file() or descriptor_path.is_symlink():
            raise OperatorError(f"Resident identity descriptor is not a regular file: {descriptor_path}")
        descriptor = descriptor_path.read_bytes()
        if len(descriptor) > 16 * 1024:
            raise OperatorError("Resident identity descriptor is too large.")
        command.extend(["--descriptor-stdin", "--reason", args.reason])
        _compose(*command, input_bytes=descriptor)
        return 0
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

    hearth_host = commands.add_parser(
        "hearth-host",
        help="manage this city's folder-owned encrypted-package receiver",
    )
    hearth_host_commands = hearth_host.add_subparsers(
        dest="hearth_host_action",
        required=True,
    )
    hearth_host_commands.add_parser(
        "initialize",
        help="create, repair, or verify the private receiver key and public descriptor",
    )
    hearth_host.set_defaults(handler=command_hearth_host)

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

    map_command = commands.add_parser("map", help="inspect or publish one verified generated city map")
    map_commands = map_command.add_subparsers(dest="map_action", required=True)
    map_inspect = map_commands.add_parser("inspect", help="verify a generated map release without changing the node")
    map_inspect.add_argument("pack_dir", help="built city-pack directory containing manifest and generated map files")
    map_publish = map_commands.add_parser("publish", help="back up the node and publish only its generated map drawing")
    map_publish.add_argument("pack_dir", help="built city-pack directory containing manifest and generated map files")
    map_publish.add_argument("--yes", action="store_true", help="confirm replacement of the current public map drawing")
    map_command.set_defaults(handler=command_map)

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

    resident_authority = commands.add_parser(
        "resident-authority",
        help="manage resident public identities admitted by this city",
    )
    resident_authority_commands = resident_authority.add_subparsers(
        dest="resident_authority_action",
        required=True,
    )
    resident_authority_commands.add_parser("list", help="list admitted resident public identities")
    admit_resident = resident_authority_commands.add_parser(
        "admit",
        help="verify and admit one reviewed public resident identity card",
    )
    admit_resident.add_argument("descriptor")
    admit_resident.add_argument("--reason", required=True)
    resident_authority.set_defaults(handler=command_resident_authority)

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
