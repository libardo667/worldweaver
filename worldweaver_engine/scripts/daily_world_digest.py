#!/usr/bin/env python3
"""Build a steward-facing digest for one or more city shards."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

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

    @property
    def city_id(self) -> str:
        return str(self.env.get("CITY_ID") or self.name).strip() or self.name

    @property
    def display_name(self) -> str:
        return self.city_id.replace("_", " ")


def _load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _normalize_database_url(url: str) -> str:
    normalized = str(url or "").strip()
    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+psycopg://", 1)
    return normalized


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


def _discover_city_shards() -> list[ShardSpec]:
    shards: list[ShardSpec] = []
    if not SHARDS_ROOT.exists():
        return shards
    for shard_dir in sorted(path for path in SHARDS_ROOT.iterdir() if path.is_dir()):
        env = _load_env_file(shard_dir / ".env")
        if str(env.get("SHARD_TYPE") or "").strip().lower() == "world":
            continue
        if not (
            str(env.get("WW_DB_NAME") or "").strip()
            and (str(env.get("WW_DB_EXTERNAL_PORT") or "").strip() or str(env.get("WW_DB_HOST") or "").strip())
        ):
            continue
        shards.append(ShardSpec(name=shard_dir.name, shard_dir=shard_dir, env=env))
    return shards


def _resolve_shards(*, shard_dir: str | None, all_cities: bool) -> list[ShardSpec]:
    shards = _discover_city_shards()
    if shard_dir:
        target = (WORKSPACE_ROOT / shard_dir).resolve()
        env = _load_env_file(target / ".env")
        return [ShardSpec(name=target.name, shard_dir=target, env=env)]
    if all_cities:
        return shards
    return shards[:1]


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _ensure_aware(parsed)


def _display_name_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in str(slug or "").replace("-", "_").split("_") if part)


def _session_display_name(session_id: str) -> str:
    raw = str(session_id or "").strip()
    if "-" in raw:
        raw = raw.split("-", 1)[0]
    return _display_name_from_slug(raw)


def _resident_dirs(residents_dir: Path) -> list[Path]:
    if not residents_dir.exists():
        return []
    return [
        path
        for path in sorted(residents_dir.iterdir())
        if path.is_dir() and not path.name.startswith("_")
    ]


def _actor_to_slug(residents_dir: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for resident_dir in _resident_dirs(residents_dir):
        id_path = resident_dir / "identity" / "resident_id.txt"
        if not id_path.exists():
            continue
        actor_id = str(id_path.read_text(encoding="utf-8").strip())
        if actor_id:
            mapping[actor_id] = resident_dir.name
    return mapping


def _vars_root(vars_payload: Any) -> dict[str, Any]:
    if not isinstance(vars_payload, dict):
        return {}
    variables = vars_payload.get("variables")
    if isinstance(variables, dict):
        return variables
    return vars_payload


def _pending_research_count(vars_payload: Any) -> int:
    root = _vars_root(vars_payload)
    memory_projection = root.get("_resident_memory_projection") or {}
    pending = []
    if isinstance(memory_projection, dict):
        pending = list(memory_projection.get("pending_research") or [])
    return len(pending)


def _pressure_signal_count(vars_payload: Any) -> int:
    root = _vars_root(vars_payload)
    subjective_projection = root.get("_resident_subjective_projection") or {}
    state_pressure = subjective_projection.get("state_pressure") or {}
    if isinstance(state_pressure, dict):
        return len(list(state_pressure.get("signals") or []))
    return 0


def _dialogue_pair(vars_payload: Any, self_name: str) -> tuple[str, float] | None:
    root = _vars_root(vars_payload)
    subjective_projection = root.get("_resident_subjective_projection") or {}
    dialogue_state = subjective_projection.get("dialogue_state") or {}
    if not isinstance(dialogue_state, dict):
        return None
    partner = str(dialogue_state.get("active_partner") or "").strip()
    if not partner:
        return None
    try:
        urgency = float(dialogue_state.get("direct_urgency") or 0.0)
    except (TypeError, ValueError):
        urgency = 0.0
    pair = " / ".join(sorted([self_name, partner]))
    return pair, urgency


def _rest_state(vars_payload: Any) -> str:
    root = _vars_root(vars_payload)
    return str(root.get("_rest_state") or "").strip().lower()


def _location_from_event_delta(delta: Any) -> str:
    if not isinstance(delta, dict):
        return ""
    raw = str(delta.get("destination") or delta.get("location") or "").strip()
    if raw:
        return raw
    variables = delta.get("variables") if isinstance(delta.get("variables"), dict) else {}
    return str(variables.get("location") or "").strip()


def _current_location_from_vars(vars_payload: Any) -> str:
    root = _vars_root(vars_payload)
    return str(root.get("location") or "").strip()


def _render_bullets(items: list[str], *, empty: str) -> list[str]:
    if not items:
        return [f"- {empty}"]
    return [f"- {item}" for item in items]


def _build_narrative_weather(
    *,
    live_count: int,
    top_cluster: tuple[str, int] | None,
    event_counts: Counter[str],
    promotion_count: int,
) -> str:
    movement = int(event_counts.get("movement", 0))
    utterance = int(event_counts.get("utterance", 0))
    actions = int(event_counts.get("freeform_action", 0))
    if top_cluster is not None:
        cluster_text = f"around {top_cluster[0]} ({top_cluster[1]} residents)"
    else:
        cluster_text = "without a dominant cluster"
    return (
        f"The shard held {live_count} live residents, clustering most strongly {cluster_text}. "
        f"In the last window it logged {utterance} utterances, {movement} movements, and {actions} embodied actions. "
        f"{promotion_count} soul-growth promotion(s) landed."
    )


def build_digest_for_shard(
    *,
    shard: ShardSpec,
    lookback_hours: int,
    tz_name: str,
) -> dict[str, Any]:
    db_url = _compose_postgres_url(shard.env, host_accessible=True)
    if not db_url:
        raise RuntimeError(f"Could not resolve DB URL for shard {shard.name}")

    from src.models import DirectMessage, LocationChat, ResidentIdentityGrowth, SessionVars, WorldEvent

    engine = create_engine(_normalize_database_url(db_url), future=True)
    Session = sessionmaker(bind=engine)

    now_utc = datetime.now(timezone.utc)
    since_utc = now_utc - timedelta(hours=int(lookback_hours))
    local_tz = ZoneInfo(tz_name)
    residents_dir = shard.shard_dir / "residents"
    actor_slug_map = _actor_to_slug(residents_dir)

    with Session() as session:
        live_rows = (
            session.query(SessionVars)
            .filter(SessionVars.actor_id.is_not(None))
            .all()
        )
        resident_rows = [
            row
            for row in live_rows
            if str(getattr(row, "session_id", "") or "").strip()
            and not str(getattr(row, "session_id", "") or "").startswith("ww-")
        ]

        recent_events = (
            session.query(WorldEvent)
            .filter(WorldEvent.created_at >= since_utc)
            .all()
        )
        recent_chat = (
            session.query(LocationChat)
            .filter(LocationChat.created_at >= since_utc)
            .all()
        )
        recent_dm = (
            session.query(DirectMessage)
            .filter(DirectMessage.sent_at >= since_utc)
            .all()
        )
        growth_rows = session.query(ResidentIdentityGrowth).all()

    live_count = len(resident_rows)
    resident_dir_count = len(_resident_dirs(residents_dir))
    new_residents = []
    for resident_dir in _resident_dirs(residents_dir):
        created = datetime.fromtimestamp(resident_dir.stat().st_mtime, tz=timezone.utc)
        if created >= since_utc:
            new_residents.append(resident_dir.name)

    location_counts: Counter[str] = Counter()
    research_counts: list[int] = []
    pressure_counts: list[int] = []
    rest_counts: Counter[str] = Counter()
    duplicate_name_counts: Counter[str] = Counter()
    dialogue_pairs: dict[str, list[float]] = defaultdict(list)

    for row in resident_rows:
        vars_payload = getattr(row, "vars", {}) or {}
        current_location = _current_location_from_vars(vars_payload)
        if current_location:
            location_counts[current_location] += 1
        session_name = _session_display_name(str(getattr(row, "session_id", "") or ""))
        duplicate_name_counts[session_name] += 1
        research_counts.append(_pending_research_count(vars_payload))
        pressure_counts.append(_pressure_signal_count(vars_payload))
        rest = _rest_state(vars_payload)
        if rest:
            rest_counts[rest] += 1
        pair = _dialogue_pair(vars_payload, session_name)
        if pair is not None:
            pair_name, urgency = pair
            dialogue_pairs[pair_name].append(urgency)

    event_counts: Counter[str] = Counter(str(getattr(event, "event_type", "") or "").strip() for event in recent_events)
    movement_locations: Counter[str] = Counter()
    roamers: dict[str, set[str]] = defaultdict(set)
    for event in recent_events:
        if str(getattr(event, "event_type", "") or "").strip() != "movement":
            continue
        destination = _location_from_event_delta(getattr(event, "world_state_delta", {}) or {})
        if not destination:
            continue
        movement_locations[destination] += 1
        sid = str(getattr(event, "session_id", "") or "").strip()
        if sid:
            roamers[_session_display_name(sid)].add(destination)

    top_clusters = location_counts.most_common(5)
    top_movement_locations = movement_locations.most_common(5)
    top_roamers = sorted(
        ((name, len(locations)) for name, locations in roamers.items()),
        key=lambda item: (-item[1], item[0]),
    )[:5]
    top_chat_locations = Counter(str(getattr(row, "location", "") or "").strip() for row in recent_chat if str(getattr(row, "location", "") or "").strip()).most_common(5)
    strongest_pairs = sorted(
        (
            (pair_name, len(urgencies), round(sum(urgencies) / len(urgencies), 2))
            for pair_name, urgencies in dialogue_pairs.items()
        ),
        key=lambda item: (-item[2], -item[1], item[0]),
    )[:5]
    unread_dm_count = sum(1 for row in recent_dm if getattr(row, "read_at", None) is None)
    duplicate_names = sorted(name for name, count in duplicate_name_counts.items() if name and count > 1)
    saturated = []
    for row in resident_rows:
        count = _pending_research_count(getattr(row, "vars", {}) or {})
        if count >= 6:
            saturated.append(_session_display_name(str(getattr(row, "session_id", "") or "")))
    saturated = sorted(set(saturated))

    promotions: list[dict[str, Any]] = []
    for row in growth_rows:
        metadata = dict(getattr(row, "growth_metadata", {}) or {})
        preview = str(metadata.get("growth_preview") or str(getattr(row, "growth_text", "") or "")[:120]).strip()
        promoted_at = _parse_iso(metadata.get("promoted_at"))
        if promoted_at is None or not preview:
            continue
        if promoted_at is None or promoted_at < since_utc:
            continue
        actor_id = str(getattr(row, "actor_id", "") or "").strip()
        slug = actor_slug_map.get(actor_id, actor_id)
        promotions.append(
            {
                "resident": _display_name_from_slug(slug),
                "promoted_at": promoted_at.astimezone(local_tz).isoformat(),
                "preview": preview,
            }
        )
    promotions.sort(key=lambda item: item["promoted_at"], reverse=True)

    avg_research = round(sum(research_counts) / len(research_counts), 2) if research_counts else 0.0
    avg_pressure = round(sum(pressure_counts) / len(pressure_counts), 2) if pressure_counts else 0.0

    top_cluster = top_clusters[0] if top_clusters else None
    report = {
        "shard": shard.name,
        "city_id": shard.city_id,
        "window_hours": int(lookback_hours),
        "generated_at_local": now_utc.astimezone(local_tz).isoformat(),
        "population": {
            "live_residents": live_count,
            "resident_dirs": resident_dir_count,
            "new_residents": [_display_name_from_slug(slug) for slug in new_residents],
        },
        "movement": {
            "top_clusters": top_clusters,
            "top_movement_locations": top_movement_locations,
            "top_roamers": top_roamers,
        },
        "social": {
            "top_chat_locations": top_chat_locations,
            "strongest_dialogue_pairs": strongest_pairs,
            "direct_messages_sent": len(recent_dm),
            "direct_messages_unread": unread_dm_count,
        },
        "behavioral_health": {
            "event_counts": dict(event_counts),
            "average_pending_research": avg_research,
            "average_pressure_signals": avg_pressure,
            "rest_snapshot": dict(rest_counts),
        },
        "identity": {
            "promotions": promotions[:5],
        },
        "alerts": {
            "duplicate_live_names": duplicate_names,
            "research_saturation": saturated[:8],
        },
        "narrative_weather": _build_narrative_weather(
            live_count=live_count,
            top_cluster=top_cluster,
            event_counts=event_counts,
            promotion_count=len(promotions),
        ),
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"## {str(report['city_id']).replace('_', ' ').title()}",
        "",
        report["narrative_weather"],
        "",
        "**Population**",
    ]
    population = report["population"]
    lines.extend(
        _render_bullets(
            [
                f"{population['live_residents']} live resident session(s)",
                f"{population['resident_dirs']} resident director(ies) on disk",
                (
                    "new residents: " + ", ".join(population["new_residents"])
                    if population["new_residents"]
                    else "new residents: none"
                ),
            ],
            empty="No population data.",
        )
    )
    lines.extend(["", "**Movement**"])
    movement = report["movement"]
    movement_items: list[str] = []
    if movement["top_clusters"]:
        movement_items.append(
            "current clusters: "
            + ", ".join(f"{location} ({count})" for location, count in movement["top_clusters"])
        )
    if movement["top_movement_locations"]:
        movement_items.append(
            "movement destinations: "
            + ", ".join(f"{location} ({count})" for location, count in movement["top_movement_locations"])
        )
    if movement["top_roamers"]:
        movement_items.append(
            "widest ranging: "
            + ", ".join(f"{name} ({count} locations)" for name, count in movement["top_roamers"])
        )
    lines.extend(_render_bullets(movement_items, empty="No movement signal yet."))

    lines.extend(["", "**Social Life**"])
    social = report["social"]
    social_items: list[str] = []
    if social["top_chat_locations"]:
        social_items.append(
            "top chat locations: "
            + ", ".join(f"{location} ({count})" for location, count in social["top_chat_locations"])
        )
    if social["strongest_dialogue_pairs"]:
        social_items.append(
            "dialogue pairs: "
            + ", ".join(
                f"{pair} (urgency {urgency}, {count} resident views)"
                for pair, count, urgency in social["strongest_dialogue_pairs"]
            )
        )
    social_items.append(
        f"direct messages: {social['direct_messages_sent']} sent in window, {social['direct_messages_unread']} unread"
    )
    lines.extend(_render_bullets(social_items, empty="No social signal yet."))

    lines.extend(["", "**Behavioral Health**"])
    health = report["behavioral_health"]
    event_counts = health["event_counts"]
    health_items = [
        "world events: "
        + ", ".join(
            f"{label}={int(event_counts.get(label, 0))}"
            for label in ("utterance", "movement", "freeform_action")
        ),
        f"average pending research: {health['average_pending_research']}",
        f"average pressure signals: {health['average_pressure_signals']}",
    ]
    if health["rest_snapshot"]:
        health_items.append(
            "rest snapshot: "
            + ", ".join(f"{state}={count}" for state, count in sorted(health["rest_snapshot"].items()))
        )
    lines.extend(_render_bullets(health_items, empty="No behavioral signal yet."))

    lines.extend(["", "**Identity**"])
    promotions = report["identity"]["promotions"]
    if promotions:
        lines.extend(
            _render_bullets(
                [
                    f"{item['resident']} at {item['promoted_at']}: {item['preview']}"
                    for item in promotions
                ],
                empty="No identity activity.",
            )
        )
    else:
        lines.extend(_render_bullets([], empty="No soul-growth promotions in this window."))

    lines.extend(["", "**Alerts**"])
    alerts = report["alerts"]
    alert_items: list[str] = []
    if alerts["duplicate_live_names"]:
        alert_items.append("duplicate live names: " + ", ".join(alerts["duplicate_live_names"]))
    if alerts["research_saturation"]:
        alert_items.append("research saturation: " + ", ".join(alerts["research_saturation"]))
    lines.extend(_render_bullets(alert_items, empty="No steward alerts."))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a daily steward digest for WorldWeaver shards.")
    parser.add_argument("--shard-dir", default="", help="Specific shard dir relative to workspace, e.g. shards/ww_sfo")
    parser.add_argument("--all-cities", action="store_true", help="Report every city shard instead of just one")
    parser.add_argument("--lookback-hours", type=int, default=24, help="Lookback window in hours (default: 24)")
    parser.add_argument("--timezone", default="America/Los_Angeles", help="Output timezone (default: America/Los_Angeles)")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", default="", help="Optional output file path")
    args = parser.parse_args()

    shards = _resolve_shards(shard_dir=str(args.shard_dir or "").strip() or None, all_cities=bool(args.all_cities))
    if not shards:
        print("No city shards found.")
        return 1

    reports: list[dict[str, Any]] = []
    skipped: list[str] = []
    for shard in shards:
        try:
            reports.append(
                build_digest_for_shard(
                    shard=shard,
                    lookback_hours=int(args.lookback_hours),
                    tz_name=str(args.timezone),
                )
            )
        except RuntimeError as exc:
            skipped.append(f"{shard.name}: {exc}")

    if not reports:
        for line in skipped:
            print(line)
        return 1

    if args.format == "json":
        rendered = json.dumps(
            {
                "generated": datetime.now(timezone.utc).isoformat(),
                "reports": reports,
                "skipped": skipped,
            },
            indent=2,
            ensure_ascii=False,
        )
    else:
        header = [
            "# Daily World Digest",
            "",
            f"- Window: last {int(args.lookback_hours)} hour(s)",
            f"- Timezone: {args.timezone}",
            "",
        ]
        if skipped:
            header.extend(["- Skipped shards: " + "; ".join(skipped), ""])
        rendered = "\n".join(header + [render_markdown(report) for report in reports])

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + ("\n" if not rendered.endswith("\n") else ""), encoding="utf-8")
        print(str(output_path))
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
