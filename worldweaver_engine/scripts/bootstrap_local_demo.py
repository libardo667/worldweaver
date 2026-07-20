# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Create the ignored local state needed by the tracked Alderbank demo."""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
from pathlib import Path

from new_shard import (
    _ENV_CITY,
    _ENV_WORLD,
    _city_pack_timezone,
    _new_data_encryption_key,
)

from src.services.federation_node_auth import generate_node_identity
from src.services.hearth_transport import generate_hearth_transport_identity

MARKER_NAME = "local-demo.json"
MARKER_SCHEMA = "worldweaver.local-demo"
DEMO_CITY = "alderbank"


class DemoBootstrapError(RuntimeError):
    """The demo cannot be initialized without risking existing local state."""


def _marker(shard_dir: Path) -> Path:
    return shard_dir / "data" / MARKER_NAME


def _has_meaningful_files(path: Path) -> bool:
    if not path.exists():
        return False
    return any(
        candidate.is_file() and candidate.name != ".gitkeep"
        for candidate in path.rglob("*")
    )


def _has_local_state(shard_dir: Path) -> bool:
    direct_state = (
        shard_dir / ".env",
        shard_dir / "node.json",
        shard_dir / "identity" / "node.key",
        shard_dir / "hearth-host.json",
        shard_dir / "hearth-host" / "identity" / "transport.key",
    )
    return any(path.exists() for path in direct_state) or any(
        _has_meaningful_files(shard_dir / name) for name in ("data", "residents", "db")
    )


def _validate_existing_demo(world_dir: Path, city_dir: Path) -> None:
    required = (
        world_dir / ".env",
        world_dir / "node.json",
        world_dir / "identity" / "node.key",
        city_dir / ".env",
        city_dir / "node.json",
        city_dir / "identity" / "node.key",
        city_dir / "data" / "cities" / DEMO_CITY / "manifest.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise DemoBootstrapError(
            "The local demo marker exists, but required files are missing. "
            "Refusing to repair partial state automatically:\n  " + "\n  ".join(missing)
        )


def _write_private_env(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def bootstrap_local_demo(workspace_root: Path) -> bool:
    """Initialize a fresh local demo, returning False when it already exists."""
    workspace_root = workspace_root.resolve()
    engine_root = workspace_root / "worldweaver_engine"
    world_dir = workspace_root / "shards" / "ww_world"
    city_dir = workspace_root / "shards" / "ww_alderbank"
    city_pack = engine_root / "data" / "cities" / DEMO_CITY
    experience = (
        engine_root / "data" / "rulesets" / "private_constructive_game.v1.example.json"
    )

    required_source = (
        world_dir / "docker-compose.yml",
        city_dir / "docker-compose.yml",
        city_pack / "manifest.json",
        experience,
    )
    missing_source = [str(path) for path in required_source if not path.is_file()]
    if missing_source:
        raise DemoBootstrapError(
            "The tracked Alderbank demo scaffold is incomplete:\n  "
            + "\n  ".join(missing_source)
        )

    markers = (_marker(world_dir), _marker(city_dir))
    if all(path.is_file() for path in markers):
        _validate_existing_demo(world_dir, city_dir)
        return False
    if (
        any(path.exists() for path in markers)
        or _has_local_state(world_dir)
        or _has_local_state(city_dir)
    ):
        raise DemoBootstrapError(
            "Existing local shard state was found. Nothing was changed. "
            "Use the existing town, or move it aside before initializing a fresh demo."
        )

    federation_token = secrets.token_urlsafe(32)
    world_env = _ENV_WORLD.format(
        engine_image="local-build",
        shard_id="ww_world",
        port=9100,
        token=federation_token,
        db_external_port=15432,
        compose_project_name="ww_world",
        jwt_secret=secrets.token_urlsafe(48),
        data_encryption_key=_new_data_encryption_key(),
        db_password=secrets.token_urlsafe(32),
        public_url="http://localhost:9100",
        client_url="",
    ).replace(
        "WW_FEDERATION_ADMISSION_MODE=closed",
        "WW_FEDERATION_ADMISSION_MODE=open",
        1,
    )
    city_env = _ENV_CITY.format(
        engine_image="local-build",
        agent_image="local-build",
        city_id=DEMO_CITY,
        shard_id="ww_alderbank",
        port=8004,
        db_external_port=15435,
        city_timezone=_city_pack_timezone(city_pack),
        experience_path=f"/app/data/rulesets/{experience.name}",
        federation_url="http://localhost:9100",
        runtime_federation_url="http://ww_world-backend:8000",
        token=federation_token,
        compose_project_name="ww_alderbank",
        jwt_secret=secrets.token_urlsafe(48),
        data_encryption_key=_new_data_encryption_key(),
        db_password=secrets.token_urlsafe(32),
        public_url="http://localhost:8004",
        client_url="",
    )

    for shard_dir in (world_dir, city_dir):
        (shard_dir / "data").mkdir(parents=True, exist_ok=True)
        (shard_dir / "identity").mkdir(parents=True, exist_ok=True)
        (shard_dir / "residents").mkdir(parents=True, exist_ok=True)
    _write_private_env(world_dir / ".env", world_env)
    _write_private_env(city_dir / ".env", city_env)

    generate_node_identity(
        private_key_path=world_dir / "identity" / "node.key",
        descriptor_path=world_dir / "node.json",
        node_id="ww_world",
        shard_type="world",
        city_id=None,
    )
    generate_node_identity(
        private_key_path=city_dir / "identity" / "node.key",
        descriptor_path=city_dir / "node.json",
        node_id="ww_alderbank",
        shard_type="city",
        city_id=DEMO_CITY,
    )
    generate_hearth_transport_identity(
        private_key_path=city_dir / "hearth-host" / "identity" / "transport.key",
        descriptor_path=city_dir / "hearth-host.json",
    )

    shutil.copytree(city_pack, city_dir / "data" / "cities" / DEMO_CITY)
    ruleset_dir = city_dir / "data" / "rulesets"
    ruleset_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(experience, ruleset_dir / experience.name)

    marker_content = json.dumps(
        {
            "schema": MARKER_SCHEMA,
            "schema_version": 1,
            "city_id": DEMO_CITY,
            "purpose": "local tutorial",
        },
        indent=2,
        sort_keys=True,
    )
    for marker in markers:
        marker.write_text(f"{marker_content}\n", encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    try:
        created = bootstrap_local_demo(args.workspace_root)
    except DemoBootstrapError as exc:
        parser.error(str(exc))
    if created:
        print(
            "A fresh local Alderbank demo is ready. No residents were created or woken."
        )
    else:
        print("The local Alderbank demo is already initialized; nothing changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
