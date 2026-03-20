#!/usr/bin/env python3
"""Export branch-labeled training traces from resident decision logs and guild state."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = ROOT.parent
SHARDS_ROOT = WORKSPACE_ROOT / "shards"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@dataclass(frozen=True)
class ShardSpec:
    name: str
    shard_dir: Path
    env: dict[str, str]


def _load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        cleaned = value.strip()
        if cleaned[:1] not in {'"', "'"} and " #" in cleaned:
            cleaned = cleaned.split(" #", 1)[0].rstrip()
        data[key.strip()] = cleaned.strip('"').strip("'")
    return data


def _compose_postgres_url(env: dict[str, str], *, host_accessible: bool) -> str:
    host = str(env.get("WW_DB_HOST") or "").strip()
    name = str(env.get("WW_DB_NAME") or "").strip()
    if not host or not name:
        return ""
    user = str(env.get("WW_DB_USER") or "postgres").strip() or "postgres"
    password = str(env.get("WW_DB_PASSWORD") or "postgres")
    port = str(env.get("WW_DB_PORT") or "5432").strip() or "5432"
    if host_accessible and host in {"db", "postgres", "host.docker.internal"}:
        host = "127.0.0.1"
        port = str(env.get("WW_DB_EXTERNAL_PORT") or port).strip() or port
    return (
        "postgresql+psycopg://"
        f"{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(name)}"
    )


def _resolve_shards(*, shard_dir: str | None, all_cities: bool) -> list[ShardSpec]:
    if shard_dir:
        target = (WORKSPACE_ROOT / shard_dir).resolve()
        return [ShardSpec(name=target.name, shard_dir=target, env=_load_env_file(target / ".env"))]
    shards: list[ShardSpec] = []
    if not SHARDS_ROOT.exists():
        return shards
    for directory in sorted(path for path in SHARDS_ROOT.iterdir() if path.is_dir()):
        env = _load_env_file(directory / ".env")
        if str(env.get("SHARD_TYPE") or "").strip().lower() == "world":
            continue
        if all_cities or not shard_dir:
            shards.append(ShardSpec(name=directory.name, shard_dir=directory, env=env))
    return shards


def _resident_actor_map(residents_dir: Path) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    if not residents_dir.exists():
        return mapping
    for resident_dir in sorted(path for path in residents_dir.iterdir() if path.is_dir() and not path.name.startswith("_")):
        actor_path = resident_dir / "identity" / "resident_id.txt"
        if not actor_path.exists():
            continue
        actor_id = str(actor_path.read_text(encoding="utf-8").strip())
        if actor_id:
            mapping[actor_id] = resident_dir
    return mapping


def _load_decision_payloads(resident_dir: Path, *, max_per_actor: int) -> list[dict[str, Any]]:
    decisions_dir = resident_dir / "decisions"
    if not decisions_dir.exists():
        return []
    payloads: list[dict[str, Any]] = []
    for decision_path in sorted(decisions_dir.glob("decision_*.json"))[-max_per_actor:]:
        try:
            payloads.append(json.loads(decision_path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return payloads


def build_traces_for_shard(shard: ShardSpec, *, max_per_actor: int = 20) -> list[dict[str, Any]]:
    from src.models import GuildMemberProfile, SocialFeedbackEvent

    db_url = _compose_postgres_url(shard.env, host_accessible=True)
    if not db_url:
        return []
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    residents_dir = shard.shard_dir / "residents"
    actor_map = _resident_actor_map(residents_dir)
    traces: list[dict[str, Any]] = []

    with Session() as session:
        for actor_id, resident_dir in actor_map.items():
            guild_profile = session.get(GuildMemberProfile, actor_id)
            branches = list(getattr(guild_profile, "branches", []) or []) or ["general"]
            rank = str(getattr(guild_profile, "rank", "") or "apprentice").strip()
            feedback_rows = (
                session.query(SocialFeedbackEvent)
                .filter(SocialFeedbackEvent.target_actor_id == actor_id)
                .order_by(SocialFeedbackEvent.created_at.desc(), SocialFeedbackEvent.id.desc())
                .limit(20)
                .all()
            )
            feedback_summaries = [
                {
                    "id": int(row.id),
                    "feedback_mode": str(row.feedback_mode or ""),
                    "channel": str(row.channel or ""),
                    "dimension_scores": dict(row.dimension_scores or {}),
                    "summary": str(row.summary or ""),
                    "branch_hint": str(row.branch_hint or ""),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in feedback_rows
            ]
            for branch in branches:
                for decision in _load_decision_payloads(resident_dir, max_per_actor=max_per_actor):
                    traces.append(
                        {
                            "trace_type": "branch_training_trace",
                            "shard": shard.name,
                            "actor_id": actor_id,
                            "resident_slug": resident_dir.name,
                            "branch": str(branch or "").strip() or "general",
                            "rank": rank,
                            "guild_profile": {
                                "rank": rank,
                                "branches": branches,
                                "quest_band": str(getattr(guild_profile, "quest_band", "") or "foundations"),
                                "environment_guidance": dict(getattr(guild_profile, "environment_guidance", {}) or {}),
                            },
                            "feedback_summaries": feedback_summaries,
                            "selected_context": {
                                "reflection_prompt": str(decision.get("reflection_prompt") or ""),
                                "subconscious_prompt": str(decision.get("subconscious_prompt") or ""),
                                "guild_snapshot": dict(decision.get("guild_snapshot") or {}),
                            },
                            "outputs": {
                                "reflection": str(decision.get("reflection") or ""),
                                "subconscious": str(decision.get("subconscious") or ""),
                                "queued_intents": list(decision.get("queued_intents") or []),
                                "soul_note": str(decision.get("soul_note") or ""),
                            },
                            "outcome_labels": {
                                "rest_started": bool(decision.get("rest_started")),
                                "letter_to": str(decision.get("letter_to") or ""),
                            },
                            "ts": str(decision.get("ts") or ""),
                        }
                    )

    engine.dispose()
    return traces


def main() -> None:
    parser = argparse.ArgumentParser(description="Export branch-labeled training traces from shard decision logs.")
    parser.add_argument("--shard-dir", default=None)
    parser.add_argument("--all-cities", action="store_true")
    parser.add_argument("--max-per-actor", type=int, default=20)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    shards = _resolve_shards(shard_dir=args.shard_dir, all_cities=args.all_cities)
    traces: list[dict[str, Any]] = []
    for shard in shards:
        traces.extend(build_traces_for_shard(shard, max_per_actor=max(1, int(args.max_per_actor))))

    rendered = "\n".join(json.dumps(item, ensure_ascii=False) for item in traces)
    if rendered:
        rendered += "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
