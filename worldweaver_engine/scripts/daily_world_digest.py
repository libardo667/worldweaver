#!/usr/bin/env python3
"""Build a steward-facing digest for one or more city shards."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
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
        cleaned = value.strip()
        if cleaned[:1] not in {'"', "'"} and " #" in cleaned:
            cleaned = cleaned.split(" #", 1)[0].rstrip()
        data[key.strip()] = cleaned.strip('"').strip("'")
    return data


def _prime_process_env(paths: list[Path]) -> None:
    for path in paths:
        for key, value in _load_env_file(path).items():
            if key and value and key not in os.environ:
                os.environ[key] = value


_prime_process_env([ROOT / ".env"])


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


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _payload_summary(intent_type: str, payload: Any) -> str:
    data = payload if isinstance(payload, dict) else {}
    if intent_type == "act":
        return str(data.get("action") or "").strip()
    if intent_type == "move":
        return str(data.get("destination") or data.get("location") or "").strip()
    if intent_type in {"chat", "city_broadcast"}:
        return str(data.get("utterance") or data.get("message") or "").strip()
    if intent_type == "mail_draft":
        return str(data.get("recipient") or "").strip()
    if intent_type == "ground":
        return str(data.get("query") or "").strip()
    return str(data.get("content") or data.get("text") or "").strip()


def _build_intent_heartbeat(*, residents_dir: Path, since_utc: datetime) -> dict[str, Any]:
    current_top_pulls: list[dict[str, Any]] = []
    high_priority_moments: list[dict[str, Any]] = []
    intent_counts: Counter[str] = Counter()
    intent_priority_totals: defaultdict[str, float] = defaultdict(float)
    trigger_counts: Counter[str] = Counter()

    for resident_dir in _resident_dirs(residents_dir):
        resident_name = _display_name_from_slug(resident_dir.name)
        memory_dir = resident_dir / "memory"

        snapshot_path = memory_dir / "runtime_snapshot.json"
        if snapshot_path.exists():
            try:
                snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                snapshot = {}
            queued = list(snapshot.get("queued_intents") or []) if isinstance(snapshot, dict) else []
            queued = [item for item in queued if isinstance(item, dict)]
            if queued:
                top = sorted(
                    queued,
                    key=lambda item: (-float(item.get("priority") or 0.0), str(item.get("created_at") or "")),
                )[0]
                current_top_pulls.append(
                    {
                        "resident": resident_name,
                        "intent_type": str(top.get("intent_type") or "").strip(),
                        "priority": round(float(top.get("priority") or 0.0), 3),
                        "target_loop": str(top.get("target_loop") or "").strip(),
                        "summary": _payload_summary(str(top.get("intent_type") or "").strip(), top.get("payload") or {}),
                    }
                )

        events = _parse_jsonl(memory_dir / "runtime_ledger.jsonl")
        packet_type_by_id: dict[str, str] = {}
        for event in events:
            if str(event.get("event_type") or "").strip() != "packet_emitted":
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            packet_id = str(payload.get("packet_id") or "").strip()
            packet_type = str(payload.get("packet_type") or "").strip()
            if packet_id and packet_type:
                packet_type_by_id[packet_id] = packet_type

        for event in events:
            event_type = str(event.get("event_type") or "").strip()
            if event_type != "intent_staged":
                continue
            event_ts = _parse_iso(event.get("ts"))
            if event_ts is None or event_ts < since_utc:
                continue
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            intent_type = str(payload.get("intent_type") or "").strip()
            if not intent_type:
                continue
            try:
                priority = float(payload.get("priority") or 0.0)
            except (TypeError, ValueError):
                priority = 0.0
            intent_counts[intent_type] += 1
            intent_priority_totals[intent_type] += priority

            source_packet_ids = [
                str(item).strip()
                for item in list(payload.get("source_packet_ids") or [])
                if str(item).strip()
            ]
            source_types = [packet_type_by_id[item] for item in source_packet_ids if item in packet_type_by_id]
            for source_type in source_types:
                trigger_counts[source_type] += 1

            if priority >= 0.75:
                high_priority_moments.append(
                    {
                        "resident": resident_name,
                        "ts": event_ts.isoformat(),
                        "intent_type": intent_type,
                        "priority": round(priority, 3),
                        "summary": _payload_summary(intent_type, payload.get("payload") or {}),
                        "source_types": source_types[:4],
                    }
                )

    current_top_pulls.sort(key=lambda item: (-float(item["priority"]), item["resident"]))
    high_priority_moments.sort(key=lambda item: (-float(item["priority"]), item["ts"], item["resident"]), reverse=False)
    dominant_pulls = sorted(
        (
            (
                intent_type,
                count,
                round(intent_priority_totals[intent_type] / count, 2),
            )
            for intent_type, count in intent_counts.items()
            if count > 0
        ),
        key=lambda item: (-item[1], -item[2], item[0]),
    )
    dominant_triggers = trigger_counts.most_common(5)
    return {
        "current_top_pulls": current_top_pulls[:8],
        "high_priority_moments": high_priority_moments[:8],
        "dominant_pulls": dominant_pulls[:6],
        "dominant_triggers": dominant_triggers,
    }


def _build_guild_watch(
    *,
    resident_actor_ids: list[str],
    actor_slug_map: dict[str, str],
    guild_profiles: list[Any],
    adaptation_rows: list[Any],
    feedback_rows: list[Any],
    quest_rows: list[Any],
    growth_rows: list[Any],
) -> dict[str, Any]:
    profile_by_actor = {
        str(getattr(row, "actor_id", "") or "").strip(): row
        for row in guild_profiles
        if str(getattr(row, "actor_id", "") or "").strip()
    }
    adaptation_by_actor = {
        str(getattr(row, "actor_id", "") or "").strip(): row
        for row in adaptation_rows
        if str(getattr(row, "actor_id", "") or "").strip()
    }
    feedback_by_actor: defaultdict[str, list[Any]] = defaultdict(list)
    for row in feedback_rows:
        actor_id = str(getattr(row, "target_actor_id", "") or "").strip()
        if actor_id:
            feedback_by_actor[actor_id].append(row)
    quests_by_actor: defaultdict[str, list[Any]] = defaultdict(list)
    for row in quest_rows:
        actor_id = str(getattr(row, "target_actor_id", "") or "").strip()
        if actor_id:
            quests_by_actor[actor_id].append(row)

    branch_distribution: Counter[str] = Counter()
    quest_bands: Counter[str] = Counter()
    mentor_exposure: Counter[str] = Counter()
    social_density: Counter[str] = Counter()
    solo_time: Counter[str] = Counter()
    active_quest_branches: Counter[str] = Counter()
    active_watch: list[dict[str, Any]] = []
    top_quests: list[tuple[str, str, str]] = []
    quest_statuses: Counter[str] = Counter()
    recent_quest_activity: list[dict[str, Any]] = []

    for actor_id in resident_actor_ids:
        profile = profile_by_actor.get(actor_id)
        adaptation = adaptation_by_actor.get(actor_id)
        feedback = feedback_by_actor.get(actor_id, [])
        quests = quests_by_actor.get(actor_id, [])
        resident_name = _display_name_from_slug(actor_slug_map.get(actor_id, actor_id))

        branches = list(getattr(profile, "branches", []) or [])
        for branch in branches:
            branch_name = str(branch or "").strip()
            if branch_name:
                branch_distribution[branch_name] += 1

        quest_band = str(getattr(profile, "quest_band", "") or "").strip()
        if quest_band:
            quest_bands[quest_band] += 1

        guidance = dict(getattr(adaptation, "environment_guidance", {}) or {})
        mentor_value = str(guidance.get("mentor_exposure") or "").strip()
        if mentor_value:
            mentor_exposure[mentor_value] += 1
        density_value = str(guidance.get("social_density") or "").strip()
        if density_value:
            social_density[density_value] += 1
        solo_value = str(guidance.get("solo_time") or "").strip()
        if solo_value:
            solo_time[solo_value] += 1

        if not feedback and not guidance:
            if not quests:
                continue

        dimension_totals: defaultdict[str, float] = defaultdict(float)
        dimension_counts: Counter[str] = Counter()
        explicit_count = 0
        inferred_count = 0
        for row in feedback:
            if str(getattr(row, "feedback_mode", "") or "").strip().lower() == "explicit":
                explicit_count += 1
            else:
                inferred_count += 1
            for dimension, score in dict(getattr(row, "dimension_scores", {}) or {}).items():
                try:
                    numeric = float(score)
                except (TypeError, ValueError):
                    continue
                dimension_totals[str(dimension)] += numeric
                dimension_counts[str(dimension)] += 1

        strongest_dimensions = sorted(
            (
                (dimension, round(dimension_totals[dimension] / count, 2))
                for dimension, count in dimension_counts.items()
                if count > 0
            ),
            key=lambda item: (-abs(item[1]), item[0]),
        )[:2]
        active_quests = []
        for quest in quests:
            status = str(getattr(quest, "status", "") or "").strip().lower()
            if status:
                quest_statuses[status] += 1
            activity_log = list(getattr(quest, "activity_log", []) or [])
            for entry in activity_log[-6:]:
                if not isinstance(entry, dict):
                    continue
                summary = str(entry.get("summary") or "").strip()
                if not summary:
                    continue
                ts = _parse_iso(entry.get("ts"))
                recent_quest_activity.append(
                    {
                        "resident": resident_name,
                        "title": str(getattr(quest, "title", "") or "").strip(),
                        "status": status,
                        "kind": str(entry.get("kind") or "").strip(),
                        "summary": summary,
                        "ts": ts or datetime.min.replace(tzinfo=timezone.utc),
                    }
                )
            if status not in {"assigned", "accepted", "in_progress"}:
                continue
            active_quests.append(quest)
            branch_name = str(getattr(quest, "branch", "") or "").strip()
            if branch_name:
                active_quest_branches[branch_name] += 1
            top_quests.append(
                (
                    resident_name,
                    str(getattr(quest, "title", "") or "").strip(),
                    status,
                )
            )

        active_watch.append(
            {
                "resident": resident_name,
                "rank": str(getattr(profile, "rank", "apprentice") or "apprentice").strip(),
                "branches": branches[:3],
                "quest_band": quest_band or str(guidance.get("quest_band") or "").strip() or "foundations",
                "recent_feedback": len(feedback),
                "recent_explicit": explicit_count,
                "recent_inferred": inferred_count,
                "active_quest_count": len(active_quests),
                "branch_task_bias": str(guidance.get("branch_task_bias") or "").strip(),
                "strongest_dimensions": strongest_dimensions,
            }
        )

    growth_proposal_residents: list[str] = []
    proposed_total = 0
    promoted_total = 0
    for row in growth_rows:
        actor_id = str(getattr(row, "actor_id", "") or "").strip()
        if actor_id not in resident_actor_ids:
            continue
        proposals = list(getattr(row, "growth_proposals", []) or [])
        resident_name = _display_name_from_slug(actor_slug_map.get(actor_id, actor_id))
        resident_has_proposal = False
        for proposal in proposals:
            if not isinstance(proposal, dict):
                continue
            status = str(proposal.get("status") or "").strip().lower()
            if status == "promoted":
                promoted_total += 1
            else:
                proposed_total += 1
            resident_has_proposal = True
        if resident_has_proposal:
            growth_proposal_residents.append(resident_name)

    active_watch.sort(
        key=lambda item: (-int(item["recent_feedback"]), -int(item["recent_explicit"]), item["resident"])
    )
    recent_quest_activity.sort(
        key=lambda item: (item["ts"], item["resident"], item["title"]),
        reverse=True,
    )
    return {
        "feedback_active_residents": active_watch[:8],
        "branch_distribution": branch_distribution.most_common(6),
        "quest_bands": quest_bands.most_common(6),
        "quest_statuses": quest_statuses.most_common(8),
        "guidance_distribution": {
            "mentor_exposure": mentor_exposure.most_common(3),
            "social_density": social_density.most_common(3),
            "solo_time": solo_time.most_common(3),
        },
        "active_quests": {
            "count": len(top_quests),
            "branches": active_quest_branches.most_common(6),
            "top_titles": top_quests[:8],
            "recent_activity": [
                (
                    item["resident"],
                    item["title"],
                    item["kind"],
                    item["summary"],
                    item["status"],
                )
                for item in recent_quest_activity[:8]
            ],
        },
        "growth_proposals": {
            "proposed": proposed_total,
            "promoted": promoted_total,
            "residents": sorted(set(growth_proposal_residents))[:8],
        },
    }


def _render_bullets(items: list[str], *, empty: str) -> list[str]:
    if not items:
        return [f"- {empty}"]
    return [f"- {item}" for item in items]


def _chat_message_ts(row: Any) -> datetime:
    return _parse_iso(getattr(row, "created_at", None)) or datetime.min.replace(tzinfo=timezone.utc)


def _sample_conversation_lines(recent_chat: list[Any], *, max_messages: int) -> list[str]:
    ordered = sorted(recent_chat, key=_chat_message_ts, reverse=True)
    samples: list[str] = []
    seen: set[tuple[str, str, str]] = set()
    for row in ordered:
        location = str(getattr(row, "location", "") or "").strip()
        speaker = str(getattr(row, "display_name", "") or getattr(row, "session_id", "") or "").strip()
        message = " ".join(str(getattr(row, "message", "") or "").strip().split())
        if not location or not speaker or not message:
            continue
        key = (location.lower(), speaker.lower(), message.lower())
        if key in seen:
            continue
        seen.add(key)
        samples.append(f"[{location}] {speaker}: {message}")
        if len(samples) >= max(1, int(max_messages)):
            break
    samples.reverse()
    return samples


def _extract_text_response(response: Any) -> str:
    try:
        choice = response.choices[0]
    except Exception:
        return ""
    message = getattr(choice, "message", None)
    if message is None:
        return ""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None) if not isinstance(item, dict) else item.get("text")
            if text:
                parts.append(str(text))
        return "\n".join(parts).strip()
    return str(content or "").strip()


def _parse_theme_analysis(raw_text: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return {"status": "empty"}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {"status": "parse_error", "raw": text}
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {"status": "parse_error", "raw": text}
    if not isinstance(payload, dict):
        return {"status": "parse_error", "raw": text}
    themes = [str(item).strip() for item in list(payload.get("themes") or []) if str(item).strip()]
    tensions = [str(item).strip() for item in list(payload.get("tensions") or []) if str(item).strip()]
    oddities = [str(item).strip() for item in list(payload.get("oddities") or []) if str(item).strip()]
    summary = str(payload.get("summary") or "").strip()
    return {
        "status": "ok",
        "summary": summary,
        "themes": themes[:5],
        "tensions": tensions[:5],
        "oddities": oddities[:5],
    }


def _summarize_conversation_themes_with_llm(
    *,
    shard_name: str,
    city_id: str,
    lines: list[str],
    model: str = "",
) -> dict[str, Any]:
    from src.services.llm_client import get_llm_client, get_model, platform_shared_policy

    client = get_llm_client(policy=platform_shared_policy(owner_id=f"daily_world_digest:{shard_name}"))
    if client is None:
        return {"status": "unavailable", "reason": "no_llm_client"}

    chosen_model = str(model or "").strip() or get_model()
    system_prompt = (
        "You are writing a steward-facing thematic read of a living city shard's recent public conversations. "
        "Be grounded and diagnostic, not romantic or overly flattering. "
        "Return JSON only with keys: summary, themes, tensions, oddities. "
        "summary must be one concise paragraph. themes, tensions, oddities must each be arrays of short strings. "
        "Focus on repeated motifs, cluster dynamics, shared obsessions, groundedness vs abstraction, and whether the talk sounds socially healthy."
    )
    user_prompt = (
        f"City: {city_id}\n"
        f"Shard: {shard_name}\n"
        f"Recent public chat lines ({len(lines)}):\n"
        + "\n".join(lines)
    )
    response = client.chat.completions.create(
        model=chosen_model,
        temperature=0.2,
        max_tokens=350,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    parsed = _parse_theme_analysis(_extract_text_response(response))
    parsed["model"] = chosen_model
    return parsed


def _build_conversation_themes(
    *,
    shard_name: str,
    city_id: str,
    recent_chat: list[Any],
    max_messages: int,
    theme_model: str = "",
    summarizer: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    lines = _sample_conversation_lines(recent_chat, max_messages=max_messages)
    if not lines:
        return {"status": "no_chat", "sample_count": 0, "summary": "", "themes": [], "tensions": [], "oddities": []}
    analyzer = summarizer or _summarize_conversation_themes_with_llm
    try:
        result = analyzer(shard_name=shard_name, city_id=city_id, lines=lines, model=theme_model)
    except Exception as exc:
        result = {"status": "error", "reason": f"{exc.__class__.__name__}: {exc}"}
    if not isinstance(result, dict):
        result = {"status": "error", "reason": "invalid_theme_result"}
    result.setdefault("status", "ok")
    result["sample_count"] = len(lines)
    result["sample_preview"] = lines[:8]
    return result


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
    include_conversation_themes: bool = False,
    theme_message_limit: int = 60,
    theme_model: str = "",
    theme_summarizer: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    db_url = _compose_postgres_url(shard.env, host_accessible=True)
    if not db_url:
        raise RuntimeError(f"Could not resolve DB URL for shard {shard.name}")

    from src.models import (
        DirectMessage,
        GuildMemberProfile,
        GuildQuest,
        LocationChat,
        ResidentIdentityGrowth,
        RuntimeAdaptationState,
        SessionVars,
        SocialFeedbackEvent,
        WorldEvent,
    )

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
            and str(getattr(row, "actor_id", "") or "").strip() in actor_slug_map
        ]
        orphan_rows = [
            row
            for row in live_rows
            if str(getattr(row, "session_id", "") or "").strip()
            and str(getattr(row, "actor_id", "") or "").strip()
            and str(getattr(row, "actor_id", "") or "").strip() not in actor_slug_map
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
        resident_actor_ids = [
            str(getattr(row, "actor_id", "") or "").strip()
            for row in resident_rows
            if str(getattr(row, "actor_id", "") or "").strip()
        ]
        guild_profile_rows = (
            session.query(GuildMemberProfile)
            .filter(GuildMemberProfile.actor_id.in_(resident_actor_ids))
            .all()
            if resident_actor_ids
            else []
        )
        adaptation_rows = (
            session.query(RuntimeAdaptationState)
            .filter(RuntimeAdaptationState.actor_id.in_(resident_actor_ids))
            .all()
            if resident_actor_ids
            else []
        )
        feedback_rows = (
            session.query(SocialFeedbackEvent)
            .filter(
                SocialFeedbackEvent.target_actor_id.in_(resident_actor_ids),
                SocialFeedbackEvent.created_at >= since_utc,
            )
            .order_by(SocialFeedbackEvent.created_at.desc(), SocialFeedbackEvent.id.desc())
            .all()
            if resident_actor_ids
            else []
        )
        quest_rows = (
            session.query(GuildQuest)
            .filter(GuildQuest.target_actor_id.in_(resident_actor_ids))
            .order_by(GuildQuest.created_at.desc(), GuildQuest.id.desc())
            .all()
            if resident_actor_ids
            else []
        )

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
    orphan_sessions = sorted(
        f"{str(getattr(row, 'session_id', '') or '').strip()} @ {str(_current_location_from_vars(getattr(row, 'vars', {}) or {}) or 'unknown')}"
        for row in orphan_rows
    )
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
        "guild_watch": _build_guild_watch(
            resident_actor_ids=resident_actor_ids,
            actor_slug_map=actor_slug_map,
            guild_profiles=guild_profile_rows,
            adaptation_rows=adaptation_rows,
            feedback_rows=feedback_rows,
            quest_rows=quest_rows,
            growth_rows=growth_rows,
        ),
        "intent_heartbeat": _build_intent_heartbeat(
            residents_dir=residents_dir,
            since_utc=since_utc,
        ),
        "alerts": {
            "duplicate_live_names": duplicate_names,
            "research_saturation": saturated[:8],
            "orphan_live_sessions": orphan_sessions[:12],
        },
        "narrative_weather": _build_narrative_weather(
            live_count=live_count,
            top_cluster=top_cluster,
            event_counts=event_counts,
            promotion_count=len(promotions),
        ),
    }
    if include_conversation_themes:
        report["conversation_themes"] = _build_conversation_themes(
            shard_name=shard.name,
            city_id=shard.city_id,
            recent_chat=recent_chat,
            max_messages=theme_message_limit,
            theme_model=theme_model,
            summarizer=theme_summarizer,
        )
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

    lines.extend(["", "**Intent Heartbeat**"])
    heartbeat = report["intent_heartbeat"]
    heartbeat_items: list[str] = []
    if heartbeat["current_top_pulls"]:
        heartbeat_items.append(
            "current top pulls: "
            + ", ".join(
                f"{item['resident']} -> {item['intent_type']} {item['priority']}"
                + (f" ({item['summary']})" if item.get("summary") else "")
                for item in heartbeat["current_top_pulls"]
            )
        )
    if heartbeat["dominant_pulls"]:
        heartbeat_items.append(
            "dominant pulls this window: "
            + ", ".join(
                f"{intent_type} ({count}, avg {avg_priority})"
                for intent_type, count, avg_priority in heartbeat["dominant_pulls"]
            )
        )
    if heartbeat["high_priority_moments"]:
        heartbeat_items.append(
            "high-priority moments: "
            + "; ".join(
                f"{item['resident']} -> {item['intent_type']} {item['priority']}"
                + (f" via {', '.join(item['source_types'])}" if item.get("source_types") else "")
                + (f" ({item['summary']})" if item.get("summary") else "")
                for item in heartbeat["high_priority_moments"][:5]
            )
        )
    if heartbeat["dominant_triggers"]:
        heartbeat_items.append(
            "common triggers: "
            + ", ".join(f"{trigger} ({count})" for trigger, count in heartbeat["dominant_triggers"])
        )
    lines.extend(_render_bullets(heartbeat_items, empty="No intent-heartbeat signal yet."))

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

    if report.get("conversation_themes"):
        lines.extend(["", "**Conversation Themes**"])
        themes = report["conversation_themes"]
        theme_items: list[str] = []
        status = str(themes.get("status") or "").strip()
        sample_count = int(themes.get("sample_count") or 0)
        if status == "ok":
            summary = str(themes.get("summary") or "").strip()
            if summary:
                theme_items.append(f"summary ({sample_count} sampled lines): {summary}")
            if themes.get("themes"):
                theme_items.append("recurring themes: " + "; ".join(str(item) for item in themes["themes"]))
            if themes.get("tensions"):
                theme_items.append("tensions: " + "; ".join(str(item) for item in themes["tensions"]))
            if themes.get("oddities"):
                theme_items.append("oddities: " + "; ".join(str(item) for item in themes["oddities"]))
        elif status == "no_chat":
            theme_items.append("No public chat to analyze in this window.")
        elif status == "unavailable":
            theme_items.append("Conversation theme analysis unavailable because no LLM client is configured.")
        else:
            reason = str(themes.get("reason") or themes.get("raw") or status).strip()
            theme_items.append(f"Conversation theme analysis unavailable: {reason}")
        lines.extend(_render_bullets(theme_items, empty="No conversation-theme signal yet."))

    lines.extend(["", "**Guild Watch**"])
    guild_watch = report.get("guild_watch") or {}
    guild_items: list[str] = []
    if guild_watch.get("feedback_active_residents"):
        guild_items.append(
            "feedback-active residents: "
            + ", ".join(
                f"{item['resident']} ({item['recent_feedback']} events"
                + (f", {item['quest_band']}" if item.get("quest_band") else "")
                + (
                    f", dims: {', '.join(f'{name} {score}' for name, score in item['strongest_dimensions'])}"
                    if item.get("strongest_dimensions")
                    else ""
                )
                + ")"
                for item in guild_watch["feedback_active_residents"][:5]
            )
        )
    if guild_watch.get("branch_distribution"):
        guild_items.append(
            "branch distribution: "
            + ", ".join(f"{branch} ({count})" for branch, count in guild_watch["branch_distribution"])
        )
    if guild_watch.get("quest_bands"):
        guild_items.append(
            "quest bands: "
            + ", ".join(f"{band} ({count})" for band, count in guild_watch["quest_bands"])
        )
    if guild_watch.get("quest_statuses"):
        guild_items.append(
            "quest statuses: "
            + ", ".join(f"{status} ({count})" for status, count in guild_watch["quest_statuses"][:5])
        )
    guidance = guild_watch.get("guidance_distribution") or {}
    if guidance.get("mentor_exposure"):
        guild_items.append(
            "mentor exposure: "
            + ", ".join(f"{value} ({count})" for value, count in guidance["mentor_exposure"])
        )
    active_quests = guild_watch.get("active_quests") or {}
    if int(active_quests.get("count") or 0) > 0:
        guild_items.append(
            f"active quests: {int(active_quests.get('count') or 0)}"
            + (
                " | branches: "
                + ", ".join(f"{branch} ({count})" for branch, count in list(active_quests.get("branches") or [])[:4])
                if active_quests.get("branches")
                else ""
            )
            + (
                " | titles: "
                + "; ".join(f"{resident}: {title} [{status}]" for resident, title, status in list(active_quests.get("top_titles") or [])[:4] if title)
                if active_quests.get("top_titles")
                else ""
            )
        )
    if active_quests.get("recent_activity"):
        guild_items.append(
            "quest trail: "
            + "; ".join(
                f"{resident}: {summary} [{kind or status}]"
                for resident, _title, kind, summary, status in list(active_quests.get("recent_activity") or [])[:4]
            )
        )
    growth_watch = guild_watch.get("growth_proposals") or {}
    if growth_watch.get("proposed") or growth_watch.get("promoted"):
        guild_items.append(
            f"growth proposals: proposed={int(growth_watch.get('proposed') or 0)}, promoted={int(growth_watch.get('promoted') or 0)}"
            + (
                f" ({', '.join(growth_watch.get('residents') or [])})"
                if growth_watch.get("residents")
                else ""
            )
        )
    lines.extend(_render_bullets(guild_items, empty="No guild-feedback or adaptation signal yet."))

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
    if alerts.get("orphan_live_sessions"):
        alert_items.append("orphan live sessions: " + "; ".join(alerts["orphan_live_sessions"]))
    lines.extend(_render_bullets(alert_items, empty="No steward alerts."))
    lines.append("")
    return "\n".join(lines)


def _publication_city_summary(report: dict[str, Any]) -> str:
    city_name = str(report["city_id"]).replace("_", " ").title()
    movement = report["movement"]
    social = report["social"]
    heartbeat = report["intent_heartbeat"]
    themes = report.get("conversation_themes") or {}

    cluster_text = "no dominant cluster"
    if movement["top_clusters"]:
        location, count = movement["top_clusters"][0]
        cluster_text = f"the strongest cluster was in {location} ({count})"

    movement_text = "movement was quiet"
    if movement["top_movement_locations"]:
        location, count = movement["top_movement_locations"][0]
        movement_text = f"movement pulled most often toward {location} ({count})"

    conversation_text = "public conversation stayed quiet"
    if themes.get("status") == "ok" and str(themes.get("summary") or "").strip():
        conversation_text = str(themes["summary"]).strip()
    elif social["top_chat_locations"]:
        location, count = social["top_chat_locations"][0]
        conversation_text = f"public talk concentrated most around {location} ({count} lines)"

    pull_text = ""
    if heartbeat["dominant_pulls"]:
        intent_type, count, avg_priority = heartbeat["dominant_pulls"][0]
        pull_text = f" The strongest pull type was {intent_type} ({count} staged, avg priority {avg_priority})."

    return (
        f"In {city_name}, {cluster_text}, and {movement_text}. "
        f"{conversation_text.rstrip('.')}.{pull_text}"
    )


def render_publication_markdown(
    reports: list[dict[str, Any]],
    *,
    lookback_hours: int,
    timezone_name: str,
) -> str:
    generated_values = [
        _parse_iso(report.get("generated_at_local"))
        for report in reports
        if _parse_iso(report.get("generated_at_local")) is not None
    ]
    generated_local = ""
    if generated_values:
        generated_local = max(generated_values).astimezone(ZoneInfo(timezone_name)).strftime("%Y-%m-%d %I:%M %p %Z")

    lines = [
        "# Guild of the Humane Arts Morning Brief",
        "",
        f"_Window: last {int(lookback_hours)} hour(s)._",
    ]
    if generated_local:
        lines.append(f"_Generated: {generated_local}._")
    lines.extend(["", "## At a Glance", ""])
    for report in reports:
        city_name = str(report["city_id"]).replace("_", " ").title()
        lines.append(f"- **{city_name}:** {_publication_city_summary(report)}")

    for report in reports:
        city_name = str(report["city_id"]).replace("_", " ").title()
        population = report["population"]
        movement = report["movement"]
        social = report["social"]
        heartbeat = report["intent_heartbeat"]
        health = report["behavioral_health"]
        identity = report["identity"]
        alerts = report["alerts"]
        themes = report.get("conversation_themes") or {}

        lines.extend(["", f"## {city_name}", "", report["narrative_weather"], ""])

        if themes:
            status = str(themes.get("status") or "").strip()
            if status == "ok" and str(themes.get("summary") or "").strip():
                lines.append(f"{str(themes['summary']).strip()}")
                lines.append("")
            elif status == "unavailable":
                lines.append("Conversation-theme analysis was unavailable for this run.")
                lines.append("")

        lines.append("**Where The Day Gathered**")
        gathered: list[str] = []
        if movement["top_clusters"]:
            gathered.append(
                "Current clusters: "
                + ", ".join(f"{location} ({count})" for location, count in movement["top_clusters"][:4])
            )
        if movement["top_movement_locations"]:
            gathered.append(
                "Main destinations: "
                + ", ".join(f"{location} ({count})" for location, count in movement["top_movement_locations"][:4])
            )
        if social["top_chat_locations"]:
            gathered.append(
                "Conversation centers: "
                + ", ".join(f"{location} ({count})" for location, count in social["top_chat_locations"][:4])
            )
        lines.extend(_render_bullets(gathered, empty="No strong geographic or social clustering yet."))

        lines.extend(["", "**What Residents Were Pulled Toward**"])
        pulls: list[str] = []
        if heartbeat["dominant_pulls"]:
            pulls.append(
                "Dominant pulls: "
                + ", ".join(
                    f"{intent_type} ({count}, avg priority {avg_priority})"
                    for intent_type, count, avg_priority in heartbeat["dominant_pulls"][:5]
                )
            )
        if heartbeat["current_top_pulls"]:
            pulls.append(
                "Current top pulls: "
                + ", ".join(
                    f"{item['resident']} -> {item['intent_type']}"
                    + (f" ({item['summary']})" if item.get("summary") else "")
                    for item in heartbeat["current_top_pulls"][:5]
                )
            )
        if heartbeat["dominant_triggers"]:
            pulls.append(
                "Common triggers: "
                + ", ".join(f"{trigger} ({count})" for trigger, count in heartbeat["dominant_triggers"][:4])
            )
        lines.extend(_render_bullets(pulls, empty="No strong intent heartbeat yet."))

        lines.extend(["", "**What The Guild Is Watching**"])
        guild_watch = report.get("guild_watch") or {}
        guild_notes: list[str] = []
        if guild_watch.get("feedback_active_residents"):
            guild_notes.append(
                "Most watched members: "
                + ", ".join(
                    f"{item['resident']} ({item['recent_feedback']} feedback events"
                    + (
                        f"; {', '.join(f'{name} {score}' for name, score in item['strongest_dimensions'])}"
                        if item.get("strongest_dimensions")
                        else ""
                    )
                    + ")"
                    for item in guild_watch["feedback_active_residents"][:5]
                )
            )
        if guild_watch.get("branch_distribution"):
            guild_notes.append(
                "Active branches: "
                + ", ".join(f"{branch} ({count})" for branch, count in guild_watch["branch_distribution"][:4])
            )
        if guild_watch.get("quest_bands"):
            guild_notes.append(
                "Quest bands: "
                + ", ".join(f"{band} ({count})" for band, count in guild_watch["quest_bands"][:4])
            )
        if guild_watch.get("quest_statuses"):
            guild_notes.append(
                "Quest statuses: "
                + ", ".join(f"{status} ({count})" for status, count in guild_watch["quest_statuses"][:5])
            )
        active_quests = guild_watch.get("active_quests") or {}
        if int(active_quests.get("count") or 0) > 0:
            guild_notes.append(
                "Active quests: "
                + "; ".join(
                    f"{resident}: {title} [{status}]"
                    for resident, title, status in list(active_quests.get("top_titles") or [])[:4]
                    if title
                )
            )
        if active_quests.get("recent_activity"):
            guild_notes.append(
                "Quest trail: "
                + "; ".join(
                    f"{resident}: {summary} [{kind or status}]"
                    for resident, _title, kind, summary, status in list(active_quests.get("recent_activity") or [])[:4]
                )
            )
        growth_watch = guild_watch.get("growth_proposals") or {}
        if growth_watch.get("proposed") or growth_watch.get("promoted"):
            guild_notes.append(
                f"Growth proposals: proposed={int(growth_watch.get('proposed') or 0)}, promoted={int(growth_watch.get('promoted') or 0)}"
            )
        lines.extend(_render_bullets(guild_notes, empty="No strong guild-feedback or adaptation signal yet."))

        lines.extend(["", "**Notable Developments**"])
        developments: list[str] = []
        if population["new_residents"]:
            developments.append("New residents: " + ", ".join(population["new_residents"][:8]))
        if social["strongest_dialogue_pairs"]:
            developments.append(
                "Strongest dialogue pairs: "
                + ", ".join(
                    f"{pair} (urgency {urgency})"
                    for pair, _count, urgency in social["strongest_dialogue_pairs"][:4]
                )
            )
        developments.append(
            "Activity mix: "
            + ", ".join(
                f"{label}={int(health['event_counts'].get(label, 0))}"
                for label in ("utterance", "movement", "freeform_action")
            )
        )
        developments.append(
            f"Research pressure averaged {health['average_pending_research']}; pressure signals averaged {health['average_pressure_signals']}."
        )
        if themes.get("status") == "ok":
            if themes.get("themes"):
                developments.append("Recurring themes: " + "; ".join(str(item) for item in themes["themes"][:4]))
            if themes.get("tensions"):
                developments.append("Tensions: " + "; ".join(str(item) for item in themes["tensions"][:3]))
            if themes.get("oddities"):
                developments.append("Oddities: " + "; ".join(str(item) for item in themes["oddities"][:3]))
        if identity["promotions"]:
            developments.append(
                "Soul-growth promotions: "
                + "; ".join(f"{item['resident']}: {item['preview']}" for item in identity["promotions"][:3])
            )
        lines.extend(_render_bullets(developments, empty="No notable developments yet."))

        lines.extend(["", "**Steward Notes**"])
        steward_notes: list[str] = []
        if alerts["duplicate_live_names"]:
            steward_notes.append("Duplicate live names: " + ", ".join(alerts["duplicate_live_names"]))
        if alerts["research_saturation"]:
            steward_notes.append("Research saturation: " + ", ".join(alerts["research_saturation"]))
        if alerts.get("orphan_live_sessions"):
            steward_notes.append("Orphan live sessions: " + "; ".join(alerts["orphan_live_sessions"][:6]))
        if not steward_notes:
            steward_notes.append("No immediate stewardship alerts in this window.")
        lines.extend(_render_bullets(steward_notes, empty="No immediate stewardship alerts in this window."))

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a daily steward digest for WorldWeaver shards.")
    parser.add_argument("--shard-dir", default="", help="Specific shard dir relative to workspace, e.g. shards/ww_sfo")
    parser.add_argument("--all-cities", action="store_true", help="Report every city shard instead of just one")
    parser.add_argument("--lookback-hours", type=int, default=24, help="Lookback window in hours (default: 24)")
    parser.add_argument("--timezone", default="America/Los_Angeles", help="Output timezone (default: America/Los_Angeles)")
    parser.add_argument("--format", choices=("markdown", "json", "publication_markdown"), default="markdown")
    parser.add_argument("--output", default="", help="Optional output file path")
    parser.add_argument("--conversation-themes", action="store_true", help="Use the platform LLM to summarize recent public-chat themes")
    parser.add_argument("--theme-message-limit", type=int, default=60, help="Max recent public chat lines to sample for theme analysis")
    parser.add_argument("--theme-model", default="", help="Optional model override for conversation theme analysis")
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
                    include_conversation_themes=bool(args.conversation_themes),
                    theme_message_limit=max(1, int(args.theme_message_limit)),
                    theme_model=str(args.theme_model or "").strip(),
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
    elif args.format == "publication_markdown":
        rendered = render_publication_markdown(
            reports,
            lookback_hours=int(args.lookback_hours),
            timezone_name=str(args.timezone),
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
