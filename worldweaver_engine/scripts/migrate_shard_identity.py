#!/usr/bin/env python
"""Give an existing shard folder its own signing identity safely and idempotently."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.federation_node_auth import (  # noqa: E402
    generate_node_identity,
    public_key_for_private_key,
    write_public_descriptor,
)

_KEY_SETTING = "WW_NODE_PRIVATE_KEY_PATH"
_KEY_RELATIVE_PATH = "identity/node.key"
_IDENTITY_MOUNT = "      - ./identity:/app/identity:ro"


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _set_env_value(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    replacement = f"{key}={value}"
    for index, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[index] = replacement
            break
    else:
        lines.append(replacement)
    return "\n".join(lines) + "\n"


def _with_backend_identity_mount(text: str) -> str:
    if _IDENTITY_MOUNT.strip() in {line.strip() for line in text.splitlines()}:
        return text
    lines = text.splitlines()
    backend_index = next(
        (index for index, line in enumerate(lines) if line == "  backend:"), None
    )
    if backend_index is None:
        raise ValueError("Compose file has no top-level backend service.")
    volumes_index = next(
        (
            index
            for index in range(backend_index + 1, len(lines))
            if lines[index] == "    volumes:"
        ),
        None,
    )
    if volumes_index is None:
        raise ValueError("Backend service has no volumes section.")
    insert_at = volumes_index + 1
    while insert_at < len(lines) and lines[insert_at].startswith("      - "):
        insert_at += 1
    lines.insert(insert_at, _IDENTITY_MOUNT)
    return "\n".join(lines) + "\n"


def _with_private_key_ignored(text: str) -> str:
    lines = text.splitlines()
    if "identity/node.key" not in {line.strip() for line in lines}:
        lines.append("identity/node.key")
    return "\n".join(lines) + "\n"


def migrate_shard_identity(
    shard_dir: Path,
    *,
    drop_legacy_token: bool = False,
) -> dict[str, object]:
    shard_dir = shard_dir.resolve()
    env_path = shard_dir / ".env"
    compose_path = shard_dir / "docker-compose.yml"
    gitignore_path = shard_dir / ".gitignore"
    if not env_path.is_file() or not compose_path.is_file():
        raise ValueError("Shard folder must contain .env and docker-compose.yml.")
    env = _load_env(env_path)
    node_id = str(env.get("SHARD_ID") or env.get("CITY_ID") or shard_dir.name).strip()
    shard_type = str(env.get("SHARD_TYPE") or "city").strip()
    city_id = str(env.get("CITY_ID") or "").strip() or None
    configured_path = str(env.get(_KEY_SETTING) or _KEY_RELATIVE_PATH).strip()
    private_key_path = Path(configured_path)
    if private_key_path.is_absolute():
        raise ValueError("Node key path must stay relative to the shard folder.")
    private_key_path = shard_dir / private_key_path
    descriptor_path = shard_dir / "node.json"
    if private_key_path.exists():
        public_key = public_key_for_private_key(private_key_path)
        descriptor = write_public_descriptor(
            descriptor_path=descriptor_path,
            node_id=node_id,
            shard_type=shard_type,
            city_id=city_id,
            public_key=public_key,
        )
        private_key_path.parent.chmod(0o700)
        private_key_path.chmod(0o600)
    else:
        descriptor = generate_node_identity(
            private_key_path=private_key_path,
            descriptor_path=descriptor_path,
            node_id=node_id,
            shard_type=shard_type,
            city_id=city_id,
        )

    env_text = _set_env_value(
        env_path.read_text(encoding="utf-8"), _KEY_SETTING, configured_path
    )
    if drop_legacy_token:
        env_text = _set_env_value(env_text, "FEDERATION_TOKEN", "")
    env_path.write_text(env_text, encoding="utf-8")
    env_path.chmod(0o600)
    compose_path.write_text(
        _with_backend_identity_mount(compose_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    gitignore_text = (
        gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    )
    gitignore_path.write_text(
        _with_private_key_ignored(gitignore_text), encoding="utf-8"
    )
    return descriptor


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shard_dir", type=Path, help="Existing shard folder")
    parser.add_argument(
        "--drop-legacy-token",
        action="store_true",
        help="Clear FEDERATION_TOKEN after this node's public key is bound at its directory",
    )
    args = parser.parse_args()
    try:
        descriptor = migrate_shard_identity(
            args.shard_dir,
            drop_legacy_token=args.drop_legacy_token,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(
        json.dumps(
            {
                "migrated": True,
                "node_id": descriptor["node_id"],
                "public_descriptor": str(args.shard_dir.resolve() / "node.json"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
