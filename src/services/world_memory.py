"""World memory service: records and queries persistent world events."""

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from ..config import settings
from ..models import WorldEdge, WorldEvent, WorldFact, WorldNode, WorldProjection
from .llm_client import get_trace_id

logger = logging.getLogger(__name__)

EVENT_TYPE_STORYLET_FIRED = "storylet_fired"
EVENT_TYPE_FREEFORM_ACTION = "freeform_action"
EVENT_TYPE_SYSTEM = "system"
EVENT_TYPE_SIMULATION_TICK = "simulation_tick"
PERMANENT_EVENT_TYPE = "permanent_change"
UNKNOWN_EVENT_FALLBACK_TYPE = EVENT_TYPE_SYSTEM
APPROVED_EVENT_TYPES = frozenset(
    {
        EVENT_TYPE_STORYLET_FIRED,
        EVENT_TYPE_FREEFORM_ACTION,
        EVENT_TYPE_SYSTEM,
        EVENT_TYPE_SIMULATION_TICK,
        PERMANENT_EVENT_TYPE,
    }
)
EVENT_TYPE_ALIASES = {
    "storylet": EVENT_TYPE_STORYLET_FIRED,
    "storyletfired": EVENT_TYPE_STORYLET_FIRED,
    "storylet_fire": EVENT_TYPE_STORYLET_FIRED,
    "story_event": EVENT_TYPE_STORYLET_FIRED,
    "freeform": EVENT_TYPE_FREEFORM_ACTION,
    "action": EVENT_TYPE_FREEFORM_ACTION,
    "player_action": EVENT_TYPE_FREEFORM_ACTION,
    "permanent": PERMANENT_EVENT_TYPE,
    "permanent_event": PERMANENT_EVENT_TYPE,
}
DELTA_TOP_LEVEL_KEY_ALIASES = {
    "vars": "variables",
    "var": "variables",
    "state": "variables",
    "state_vars": "variables",
    "world_state": "variables",
    "worldstate": "variables",
    "env": "environment",
    "world_env": "environment",
    "spatial": "spatial_nodes",
    "spatialnodes": "spatial_nodes",
    "locations": "spatial_nodes",
    "is_permanent": "permanent",
}
PERMANENT_EVENT_WEIGHT = 3.0
HIGH_IMPACT_DELTA_TOKENS = (
    "bridge",
    "destroy",
    "burn",
    "broken",
    "collapse",
    "flood",
    "dead",
    "killed",
    "sealed",
    "ruin",
)
HIGH_IMPACT_KEYS = {"environment", "spatial_nodes", "location", "danger_level"}
ACTION_METADATA_KEY = "__action_meta__"
ACTION_IDEMPOTENCY_KEY = "idempotency_key"
ACTION_IDEMPOTENCY_RESPONSE_KEY = "idempotency_response"
INTERNAL_DELTA_KEYS = {ACTION_METADATA_KEY}
RESERVED_DELTA_KEYS = {
    "variables",
    "environment",
    "spatial_nodes",
    "permanent",
    "_permanent",
    ACTION_METADATA_KEY,
}
NODE_TYPE_CONCEPT = "concept"
NODE_TYPE_LOCATION = "location"
NODE_TYPE_ENTITY = "entity"
PROJECTION_ROOT_VARIABLES = "variables"
PROJECTION_ROOT_ENVIRONMENT = "environment"
PROJECTION_ROOT_LOCATIONS = "locations"
PROJECTION_DELETE_MARKERS = {"_delete", "__delete__", "_tombstone", "__tombstone__"}
PLAYER_SCOPED_PREFIXES = ("player_", "session_")
ACTION_FACT_MAX_SNIPPET_CHARS = 220
ACTION_FACT_MAX_TOTAL_CHARS = 1800
IDEMPOTENCY_LOOKBACK_LIMIT = 200
SUMMARY_STATUS_VERB_MAP = {
    "burn": "burned",
    "burned": "burned",
    "destroy": "destroyed",
    "destroyed": "destroyed",
    "damage": "damaged",
    "damaged": "damaged",
    "collapse": "collapsed",
    "collapsed": "collapsed",
    "seal": "sealed",
    "sealed": "sealed",
    "flood": "flooded",
    "flooded": "flooded",
    "ruin": "ruined",
    "ruined": "ruined",
    "block": "blocked",
    "blocked": "blocked",
}
SUMMARY_LOCATION_PATTERN = re.compile(
    r"\b(?:in|at|near)\s+(?:the\s+)?(?P<location>[a-z][a-z0-9 _-]{1,60})\b",
    flags=re.IGNORECASE,
)
SUMMARY_PASSIVE_STATUS_PATTERN = re.compile(
    r"\b(?:the\s+)?(?P<subject>[a-z][a-z0-9 _-]{1,60})\s+" r"(?:is|was|remains|became|becomes)\s+" r"(?P<status>burned|destroyed|damaged|collapsed|sealed|flooded|ruined|blocked)\b",
    flags=re.IGNORECASE,
)
SUMMARY_ACTION_OBJECT_PATTERN = re.compile(
    r"\b(?:i|we|they|someone|the player)\s+" r"(?P<verb>burn|burned|destroy|destroyed|damage|damaged|collapse|collapsed|" r"seal|sealed|flood|flooded|ruin|ruined|block|blocked)\s+" r"(?:the\s+)?(?P<object>[a-z][a-z0-9 _-]{1,60})\b",
    flags=re.IGNORECASE,
)
SUMMARY_ACTION_PREFIX_PATTERN = re.compile(
    r"player action:\s*(?P<action>[^.]+)",
    flags=re.IGNORECASE,
)


@dataclass
class FactDraft:
    """Intermediary assertion extracted from an event delta or summary."""

    subject_name: str
    subject_type: str
    predicate: str
    value: Any
    summary: str
    confidence: float = 0.8
    location_name: Optional[str] = None


@dataclass
class ProjectionUpdate:
    """Single projection path mutation derived from an event."""

    path: str
    value: Any
    is_deleted: bool
    confidence: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


def _normalize_event_type_token(raw_event_type: Any) -> str:
    """Normalize event-type text to a stable token."""
    token = str(raw_event_type or "").strip().lower()
    token = re.sub(r"[\s-]+", "_", token)
    return re.sub(r"[^a-z0-9_]", "", token)


def normalize_event_type(event_type: Any) -> str:
    """Normalize inbound event-type values to approved taxonomy constants."""
    token = _normalize_event_type_token(event_type)
    if token in APPROVED_EVENT_TYPES:
        return token
    if token in EVENT_TYPE_ALIASES:
        return EVENT_TYPE_ALIASES[token]
    logger.warning(
        "Unknown world event type '%s'; falling back to '%s'.",
        event_type,
        UNKNOWN_EVENT_FALLBACK_TYPE,
    )
    return UNKNOWN_EVENT_FALLBACK_TYPE


def _normalize_delta_key(raw_key: Any) -> str:
    """Normalize arbitrary delta keys to stable snake_case-like identifiers."""
    token = str(raw_key or "").strip().lower()
    token = re.sub(r"[\s-]+", "_", token)
    return re.sub(r"[^a-z0-9_.]", "", token)


def _normalize_top_level_delta_key(raw_key: Any) -> str:
    """Normalize + alias top-level delta keys to canonical root keys."""
    normalized = _normalize_delta_key(raw_key)
    return DELTA_TOP_LEVEL_KEY_ALIASES.get(normalized, normalized)


def _normalize_delta_mapping(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize nested dict keys used by delta payload sections."""
    normalized: Dict[str, Any] = {}
    for raw_key, raw_value in mapping.items():
        key = _normalize_delta_key(raw_key)
        if not key:
            continue
        if isinstance(raw_value, dict):
            normalized[key] = _normalize_delta_mapping(raw_value)
        else:
            normalized[key] = raw_value
    return normalized


def _normalize_spatial_nodes_delta(raw_value: Any) -> Any:
    """Normalize spatial node payloads while preserving human-readable location names."""
    if not isinstance(raw_value, dict):
        return raw_value

    normalized: Dict[str, Any] = {}
    for raw_location, location_delta in raw_value.items():
        location_key = re.sub(
            r"[^a-z0-9 _-]",
            "",
            re.sub(r"\s+", " ", str(raw_location or "").strip().lower()),
        )
        if not location_key:
            continue
        if isinstance(location_delta, dict):
            normalized[location_key] = _normalize_delta_mapping(location_delta)
        else:
            normalized[location_key] = location_delta
    return normalized


def _normalize_delta(delta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a safe dict for world-state deltas."""
    if not isinstance(delta, dict):
        return {}

    normalized: Dict[str, Any] = {}
    for raw_key, raw_value in delta.items():
        key = _normalize_top_level_delta_key(raw_key)
        if not key:
            continue
        if key == "spatial_nodes":
            normalized[key] = _normalize_spatial_nodes_delta(raw_value)
        elif key in {"variables", "environment"} and isinstance(raw_value, dict):
            normalized[key] = _normalize_delta_mapping(raw_value)
        elif isinstance(raw_value, dict):
            normalized[key] = _normalize_delta_mapping(raw_value)
        else:
            normalized[key] = raw_value
    return normalized


def _sanitize_metadata_value(value: Any, depth: int = 0) -> Any:
    """Ensure metadata is JSON-serializable and bounded."""
    if depth > 3:
        return None
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [_sanitize_metadata_value(item, depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in list(value.items())[:30]:
            sanitized[str(key)] = _sanitize_metadata_value(item, depth + 1)
        return sanitized
    return str(value)


def _attach_internal_metadata(
    delta: Dict[str, Any],
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Attach internal action metadata to persisted delta without mutating state."""
    if not isinstance(metadata, dict) or not metadata:
        return delta
    persisted = dict(delta)
    persisted[ACTION_METADATA_KEY] = _sanitize_metadata_value(metadata)
    return persisted


def _extract_internal_metadata(delta: Any) -> Dict[str, Any]:
    """Read internal action metadata from a persisted delta payload."""
    if not isinstance(delta, dict):
        return {}
    metadata = delta.get(ACTION_METADATA_KEY)
    if isinstance(metadata, dict):
        return metadata
    return {}


def _normalize_idempotency_key(value: Any) -> str:
    """Normalize idempotency keys for stable comparisons."""
    key = str(value or "").strip()
    if not key:
        return ""
    return key[:128]


def _event_idempotency_key(event: WorldEvent) -> str:
    """Extract idempotency key from one world event, if present."""
    metadata = _extract_internal_metadata(event.world_state_delta)
    return _normalize_idempotency_key(metadata.get(ACTION_IDEMPOTENCY_KEY))


def _find_event_by_idempotency_key(
    db: Session,
    session_id: str,
    idempotency_key: str,
    limit: int = IDEMPOTENCY_LOOKBACK_LIMIT,
) -> Optional[WorldEvent]:
    """Find the newest session event with a matching idempotency key."""
    normalized_key = _normalize_idempotency_key(idempotency_key)
    if not normalized_key:
        return None

    events = db.query(WorldEvent).filter(WorldEvent.session_id == session_id).order_by(desc(WorldEvent.id)).limit(limit).all()
    for event in events:
        if _event_idempotency_key(event) == normalized_key:
            return event
    return None


def get_action_idempotent_response(
    db: Session,
    session_id: str,
    idempotency_key: str,
) -> Optional[Dict[str, Any]]:
    """Return the persisted action response snapshot for a duplicate request."""
    existing = _find_event_by_idempotency_key(db, session_id, idempotency_key)
    if existing is None:
        return None
    metadata = _extract_internal_metadata(existing.world_state_delta)
    payload = metadata.get(ACTION_IDEMPOTENCY_RESPONSE_KEY)
    if isinstance(payload, dict):
        return payload
    return None


def persist_action_idempotent_response(
    db: Session,
    event_id: int,
    response_payload: Dict[str, Any],
) -> None:
    """Store deterministic response payload under internal action metadata."""
    event = db.get(WorldEvent, event_id)
    if event is None:
        return

    delta = event.world_state_delta if isinstance(event.world_state_delta, dict) else {}
    merged_delta = dict(delta)
    metadata = _extract_internal_metadata(merged_delta)
    metadata = dict(metadata)
    metadata[ACTION_IDEMPOTENCY_RESPONSE_KEY] = _sanitize_metadata_value(response_payload)
    merged_delta[ACTION_METADATA_KEY] = metadata
    event.world_state_delta = merged_delta
    db.add(event)
    db.commit()
    db.refresh(event)


def _is_permanent_delta(delta: Dict[str, Any]) -> bool:
    """Heuristic for deltas that imply permanent world change."""
    if not delta:
        return False

    if bool(delta.get("permanent")) or bool(delta.get("_permanent")):
        return True

    for key, value in delta.items():
        key_lower = str(key).lower()
        if key_lower in HIGH_IMPACT_KEYS:
            return True
        if any(token in key_lower for token in HIGH_IMPACT_DELTA_TOKENS):
            return True
        if isinstance(value, bool) and value and any(token in key_lower for token in HIGH_IMPACT_DELTA_TOKENS):
            return True

    return False


def _normalize_node_name(name: str) -> str:
    """Normalize names to stable identity keys."""
    cleaned = re.sub(r"\s+", " ", str(name or "").strip().lower())
    cleaned = re.sub(r"[^a-z0-9 _-]", "", cleaned)

    # Remove leading articles for canonical identity
    for article in ("the ", "a ", "an ", "some "):
        if cleaned.startswith(article):
            cleaned = cleaned[len(article) :]
            break

    return cleaned.strip()


def _derive_subject_predicate(key: str) -> tuple[str, str]:
    """Infer subject and predicate from flattened delta key."""
    if "." in key:
        parts = [p for p in key.split(".") if p]
        if len(parts) >= 2:
            return parts[0], ".".join(parts[1:])
    if "_" in key:
        parts = [p for p in key.split("_") if p]
        if len(parts) >= 2:
            return " ".join(parts[:-1]), parts[-1]
    return "world", key


def _trim_summary_token(value: str) -> str:
    """Normalize parser captures to stable names."""
    cleaned = re.sub(r"\s+", " ", value.strip(" \n\r\t.,;:!?\"'"))
    return cleaned


def _normalize_fact_snippet(value: Any, max_len: int = ACTION_FACT_MAX_SNIPPET_CHARS) -> str:
    """Normalize and cap fact snippets used in action-grounding prompt context."""
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 3].rstrip()}..."


def _extract_summary_fact_drafts(summary: str) -> List[FactDraft]:
    """Heuristic extraction for narrative-only summaries with no structured delta."""
    cleaned_summary = re.sub(r"\s+", " ", str(summary or "").strip())
    if not cleaned_summary:
        return []

    action_summary = cleaned_summary
    action_match = SUMMARY_ACTION_PREFIX_PATTERN.search(cleaned_summary)
    if action_match:
        action_summary = _trim_summary_token(action_match.group("action"))

    location_name: Optional[str] = None
    location_match = SUMMARY_LOCATION_PATTERN.search(cleaned_summary)
    if location_match:
        location_name = _trim_summary_token(location_match.group("location"))

    drafts: List[FactDraft] = []

    passive_match = SUMMARY_PASSIVE_STATUS_PATTERN.search(cleaned_summary)
    if passive_match:
        subject_name = _trim_summary_token(passive_match.group("subject"))
        raw_status = passive_match.group("status").lower()
        drafts.append(
            FactDraft(
                subject_name=subject_name,
                subject_type=NODE_TYPE_ENTITY,
                predicate="status",
                value=SUMMARY_STATUS_VERB_MAP.get(raw_status, raw_status),
                summary=cleaned_summary,
                confidence=0.65,
                location_name=location_name,
            )
        )
        return drafts

    action_match = SUMMARY_ACTION_OBJECT_PATTERN.search(action_summary)
    if action_match:
        subject_name = _trim_summary_token(action_match.group("object"))
        raw_verb = action_match.group("verb").lower()
        drafts.append(
            FactDraft(
                subject_name=subject_name,
                subject_type=NODE_TYPE_ENTITY,
                predicate="status",
                value=SUMMARY_STATUS_VERB_MAP.get(raw_verb, raw_verb),
                summary=cleaned_summary,
                confidence=0.6,
                location_name=location_name,
            )
        )

    return drafts


def _session_filter_for_facts(query: Any, session_id: Optional[str]) -> Any:
    """Filter facts to session-local + global rows."""
    if not session_id:
        return query
    return query.filter(or_(WorldFact.session_id == session_id, WorldFact.session_id.is_(None)))


def infer_event_type(event_type: str, delta: Optional[Dict[str, Any]] = None) -> str:
    """Map a base event type to permanent_change when delta implies permanence."""
    normalized_delta = _normalize_delta(delta)
    normalized_event_type = normalize_event_type(event_type)
    if normalized_event_type == PERMANENT_EVENT_TYPE:
        return normalized_event_type
    if _is_permanent_delta(normalized_delta):
        return PERMANENT_EVENT_TYPE
    return normalized_event_type


def should_trigger_storylet(event_type: str, delta: Optional[Dict[str, Any]] = None) -> bool:
    """Return True when an event should immediately trigger new narrative."""
    normalized_delta = _normalize_delta(delta)
    resolved_event_type = infer_event_type(event_type, normalized_delta)
    if resolved_event_type == PERMANENT_EVENT_TYPE:
        return True
    return _is_permanent_delta(normalized_delta)


def apply_event_delta_to_state(state_manager: Any, delta: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Apply event deltas into the active state manager."""
    normalized_delta = _normalize_delta(delta)
    normalized_delta = {key: value for key, value in normalized_delta.items() if key not in INTERNAL_DELTA_KEYS}
    if not normalized_delta:
        return {"variables": {}, "environment": {}, "spatial_nodes": {}}

    if hasattr(state_manager, "apply_world_delta"):
        return state_manager.apply_world_delta(normalized_delta)

    applied: Dict[str, Dict[str, Any]] = {
        "variables": {},
        "environment": {},
        "spatial_nodes": {},
    }
    for key, value in normalized_delta.items():
        if hasattr(state_manager, "set_variable"):
            state_manager.set_variable(key, value)
            applied["variables"][key] = value
    return applied


def _normalize_projection_segment(segment: Any) -> str:
    """Normalize a projection key/path segment."""
    raw = str(segment or "").strip().lower()
    collapsed = re.sub(r"\s+", "_", raw)
    return re.sub(r"[^a-z0-9_.-]", "", collapsed)


def _join_projection_path(*segments: Any) -> str:
    """Build a projection path from normalized non-empty segments."""
    parts = [_normalize_projection_segment(s) for s in segments if str(s or "").strip()]
    return ".".join(part for part in parts if part)


def _extract_projection_value(value: Any) -> tuple[Any, bool, float, Dict[str, Any]]:
    """Resolve delete/tombstone markers from projection input values."""
    confidence = 1.0
    metadata: Dict[str, Any] = {}
    if isinstance(value, dict):
        conf_raw = value.get("confidence")
        if isinstance(conf_raw, (int, float)):
            confidence = max(0.0, min(1.0, float(conf_raw)))
        meta_raw = value.get("metadata")
        if isinstance(meta_raw, dict):
            metadata.update(meta_raw)
        for marker in PROJECTION_DELETE_MARKERS:
            if value.get(marker) is True:
                return None, True, confidence, metadata
        if "value" in value and len(value.keys()) <= 3:
            extracted = value.get("value")
            return extracted, extracted is None, confidence, metadata
    return value, value is None, confidence, metadata


def _collect_projection_updates_from_delta(delta: Dict[str, Any]) -> List[ProjectionUpdate]:
    """Convert an event delta into deterministic projection mutations."""
    updates: List[ProjectionUpdate] = []

    environment = delta.get(PROJECTION_ROOT_ENVIRONMENT)
    if isinstance(environment, dict):
        for key, raw_value in environment.items():
            value, is_deleted, confidence, metadata = _extract_projection_value(raw_value)
            updates.append(
                ProjectionUpdate(
                    path=_join_projection_path(PROJECTION_ROOT_ENVIRONMENT, key),
                    value=value,
                    is_deleted=is_deleted,
                    confidence=confidence,
                    metadata=metadata,
                )
            )

    spatial_nodes = delta.get("spatial_nodes")
    if isinstance(spatial_nodes, dict):
        for location, location_delta in spatial_nodes.items():
            location_key = _normalize_projection_segment(location)
            if isinstance(location_delta, dict):
                for attr, raw_value in location_delta.items():
                    value, is_deleted, confidence, metadata = _extract_projection_value(raw_value)
                    updates.append(
                        ProjectionUpdate(
                            path=_join_projection_path(
                                PROJECTION_ROOT_LOCATIONS,
                                location_key,
                                attr,
                            ),
                            value=value,
                            is_deleted=is_deleted,
                            confidence=confidence,
                            metadata=metadata,
                        )
                    )
            else:
                value, is_deleted, confidence, metadata = _extract_projection_value(location_delta)
                updates.append(
                    ProjectionUpdate(
                        path=_join_projection_path(
                            PROJECTION_ROOT_LOCATIONS,
                            location_key,
                            "state",
                        ),
                        value=value,
                        is_deleted=is_deleted,
                        confidence=confidence,
                        metadata=metadata,
                    )
                )

    variables = delta.get(PROJECTION_ROOT_VARIABLES)
    if isinstance(variables, dict):
        for key, raw_value in variables.items():
            value, is_deleted, confidence, metadata = _extract_projection_value(raw_value)
            updates.append(
                ProjectionUpdate(
                    path=_join_projection_path(PROJECTION_ROOT_VARIABLES, key),
                    value=value,
                    is_deleted=is_deleted,
                    confidence=confidence,
                    metadata=metadata,
                )
            )

    for key, raw_value in delta.items():
        if key in RESERVED_DELTA_KEYS:
            continue
        value, is_deleted, confidence, metadata = _extract_projection_value(raw_value)
        updates.append(
            ProjectionUpdate(
                path=_join_projection_path(PROJECTION_ROOT_VARIABLES, key),
                value=value,
                is_deleted=is_deleted,
                confidence=confidence,
                metadata=metadata,
            )
        )

    deduped: Dict[str, ProjectionUpdate] = {}
    for update in updates:
        if update.path:
            deduped[update.path] = update
    return list(deduped.values())


def apply_event_to_projection(db: Session, event: WorldEvent) -> int:
    """Apply one event delta to the persistent world projection table."""
    delta = _normalize_delta(event.world_state_delta)
    if not delta:
        return 0

    updates = _collect_projection_updates_from_delta(delta)
    if not updates:
        return 0

    applied = 0
    event_cache: Dict[int, Optional[WorldEvent]] = {int(event.id or 0): event}

    def _event_time_key(item: Optional[WorldEvent]) -> datetime:
        if item is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        dt = item.created_at
        if dt is None:
            dt = datetime.min.replace(tzinfo=timezone.utc)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def _source_event_by_id(event_id: int) -> Optional[WorldEvent]:
        if event_id not in event_cache:
            event_cache[event_id] = db.get(WorldEvent, event_id)
        return event_cache[event_id]

    for update in updates:
        row = db.query(WorldProjection).filter(WorldProjection.path == update.path).one_or_none()
        if row is None:
            row = WorldProjection(
                path=update.path,
                value=update.value,
                is_deleted=update.is_deleted,
                confidence=update.confidence,
                source_event_id=event.id,
                metadata_json={
                    **(update.metadata or {}),
                    "source_event_type": event.event_type,
                },
            )
            db.add(row)
            db.flush()
            applied += 1
            continue

        existing_event_id = int(row.source_event_id or 0)
        existing_event = _source_event_by_id(existing_event_id)
        incoming_time = _event_time_key(event)
        existing_time = _event_time_key(existing_event)
        if existing_time > incoming_time:
            continue
        if existing_time == incoming_time and float(row.confidence or 0.0) > update.confidence:
            continue
        if existing_time == incoming_time and float(row.confidence or 0.0) == update.confidence and existing_event_id > int(event.id or 0):
            continue

        row.value = update.value
        row.is_deleted = update.is_deleted
        row.confidence = update.confidence
        row.source_event_id = event.id
        merged_metadata = dict(row.metadata_json or {})
        merged_metadata["source_event_type"] = event.event_type
        if update.metadata:
            merged_metadata.update(update.metadata)
        row.metadata_json = merged_metadata
        applied += 1

    return applied


def get_world_projection(
    db: Session,
    prefix: Optional[str] = None,
    include_deleted: bool = False,
    limit: int = 500,
) -> List[WorldProjection]:
    """Return projection entries ordered by path."""
    query = db.query(WorldProjection)
    if prefix:
        normalized = _normalize_projection_segment(prefix)
        query = query.filter(WorldProjection.path.like(f"{normalized}%"))
    if not include_deleted:
        query = query.filter(WorldProjection.is_deleted.is_(False))
    return query.order_by(WorldProjection.path.asc(), desc(WorldProjection.id)).limit(limit).all()


def rebuild_world_projection(
    db: Session,
    clear_existing: bool = True,
    session_id: Optional[str] = None,
) -> Dict[str, int]:
    """Rebuild projection state deterministically from event history."""
    query = db.query(WorldEvent)
    if session_id:
        query = query.filter(WorldEvent.session_id == session_id)
    events = query.order_by(WorldEvent.id.asc()).all()

    if clear_existing:
        if session_id:
            touched_paths = {update.path for event in events for update in _collect_projection_updates_from_delta(_normalize_delta(event.world_state_delta)) if update.path}
            if touched_paths:
                db.query(WorldProjection).filter(WorldProjection.path.in_(sorted(touched_paths))).delete(synchronize_session=False)
        else:
            db.query(WorldProjection).delete()
        db.flush()

    processed = 0
    updated = 0
    for event in events:
        updated += apply_event_to_projection(db, event)
        processed += 1
    db.commit()

    total_rows = db.query(WorldProjection).count()
    return {
        "events_processed": processed,
        "updates_applied": updated,
        "projection_rows": int(total_rows),
    }


def apply_projection_overlay_to_state_manager(
    db: Session,
    state_manager: Any,
    player_scoped_variable_keys: Optional[set[str]] = None,
    preserve_existing_player_values: bool = True,
) -> Dict[str, int]:
    """Apply world projection defaults into a session state manager."""
    rows = get_world_projection(db=db, include_deleted=True, limit=5000)
    applied = {"variables": 0, "environment": 0, "locations": 0}
    if not rows:
        return applied

    player_keys = set(player_scoped_variable_keys or set())
    spatial_nodes = state_manager.get_variable("spatial_nodes", {})
    if not isinstance(spatial_nodes, dict):
        spatial_nodes = {}
    spatial_changed = False

    for row in rows:
        path = str(row.path or "")
        if not path:
            continue
        segments = path.split(".")
        if not segments:
            continue

        root = segments[0]
        if root == PROJECTION_ROOT_ENVIRONMENT and len(segments) >= 2:
            attr = segments[1]
            if bool(row.is_deleted):
                continue
            if hasattr(state_manager.environment, attr):
                current_value = getattr(state_manager.environment, attr, None)
                if current_value != row.value:
                    state_manager.update_environment({attr: row.value})
                    applied["environment"] += 1
            continue

        if root == PROJECTION_ROOT_VARIABLES and len(segments) >= 2:
            key = ".".join(segments[1:])
            is_player_scoped = key in player_keys or key.startswith(PLAYER_SCOPED_PREFIXES)
            if bool(row.is_deleted):
                if preserve_existing_player_values and is_player_scoped:
                    continue
                if key in state_manager.variables:
                    state_manager.variables.pop(key, None)
                continue
            if preserve_existing_player_values and is_player_scoped and key in state_manager.variables:
                continue
            if state_manager.get_variable(key) != row.value:
                state_manager.set_variable(key, row.value)
                applied["variables"] += 1
            continue

        if root == PROJECTION_ROOT_LOCATIONS and len(segments) >= 3:
            location_key = segments[1]
            attr = ".".join(segments[2:])
            location_blob = spatial_nodes.get(location_key, {})
            if not isinstance(location_blob, dict):
                location_blob = {}
            if bool(row.is_deleted):
                if attr in location_blob:
                    location_blob.pop(attr, None)
                    spatial_changed = True
            else:
                if location_blob.get(attr) != row.value:
                    location_blob[attr] = row.value
                    applied["locations"] += 1
                    spatial_changed = True
            spatial_nodes[location_key] = location_blob

    if spatial_changed:
        state_manager.set_variable("spatial_nodes", spatial_nodes)
    return applied


def _upsert_world_node(
    db: Session,
    name: str,
    node_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> WorldNode:
    """Upsert graph node by (type, normalized_name)."""
    from .embedding_service import embed_text

    normalized_name = _normalize_node_name(name)
    node = (
        db.query(WorldNode)
        .filter(
            WorldNode.node_type == node_type,
            WorldNode.normalized_name == normalized_name,
        )
        .one_or_none()
    )
    if node is not None:
        if name and node.name != name:
            node.name = name
        if metadata:
            existing = dict(node.metadata_json or {})
            existing.update(metadata)
            node.metadata_json = existing
        return node

    node = WorldNode(
        node_type=node_type,
        name=name,
        normalized_name=normalized_name,
        embedding=embed_text(f"{node_type}:{name}"),
        metadata_json=metadata or {},
    )
    db.add(node)
    db.flush()
    return node


def _upsert_world_edge(
    db: Session,
    source_node_id: int,
    target_node_id: int,
    edge_type: str,
    source_event_id: Optional[int],
    confidence: float = 0.8,
    weight: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> WorldEdge:
    """Upsert relation edge between nodes."""
    edge = (
        db.query(WorldEdge)
        .filter(
            WorldEdge.source_node_id == source_node_id,
            WorldEdge.target_node_id == target_node_id,
            WorldEdge.edge_type == edge_type,
        )
        .one_or_none()
    )
    if edge is None:
        edge = WorldEdge(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            source_event_id=source_event_id,
            confidence=confidence,
            weight=weight,
            metadata_json=metadata or {},
        )
        db.add(edge)
        db.flush()
        return edge

    edge.source_event_id = source_event_id
    edge.confidence = max(float(edge.confidence or 0.0), confidence)
    edge.weight = max(float(edge.weight or 0.0), weight)
    if metadata:
        existing = dict(edge.metadata_json or {})
        existing.update(metadata)
        edge.metadata_json = existing
    return edge


def _upsert_world_fact(
    db: Session,
    event: WorldEvent,
    subject_node_id: int,
    predicate: str,
    value: Any,
    summary: str,
    confidence: float = 0.8,
    location_node_id: Optional[int] = None,
) -> WorldFact:
    """Insert or update an active fact assertion."""
    from .embedding_service import embed_text

    active = (
        db.query(WorldFact)
        .filter(
            WorldFact.is_active.is_(True),
            WorldFact.session_id == event.session_id,
            WorldFact.subject_node_id == subject_node_id,
            WorldFact.location_node_id == location_node_id,
            WorldFact.predicate == predicate,
        )
        .order_by(desc(WorldFact.id))
        .first()
    )

    if active is not None and active.value == value:
        active.source_event_id = event.id
        active.summary = summary
        active.confidence = max(float(active.confidence or 0.0), confidence)
        return active

    if active is not None:
        active.is_active = False
        active.valid_to = datetime.now(timezone.utc)

    fact_text = f"{summary} subject={subject_node_id} predicate={predicate} value={value}"
    fact = WorldFact(
        session_id=event.session_id,
        subject_node_id=subject_node_id,
        location_node_id=location_node_id,
        predicate=predicate,
        value=value,
        confidence=confidence,
        is_active=True,
        source_event_id=event.id,
        summary=summary,
        embedding=embed_text(fact_text),
    )
    db.add(fact)
    db.flush()
    return fact


def _extract_fact_drafts(delta: Dict[str, Any], summary: str) -> List[FactDraft]:
    """Build fact drafts from structured deltas and summary fallback."""
    drafts: List[FactDraft] = []
    if not delta:
        if summary:
            drafts.extend(_extract_summary_fact_drafts(summary))
        if not drafts and summary:
            drafts.append(
                FactDraft(
                    subject_name="world",
                    subject_type=NODE_TYPE_CONCEPT,
                    predicate="event_summary",
                    value=summary,
                    summary=summary,
                    confidence=0.5,
                )
            )
        return drafts

    environment = delta.get("environment")
    if isinstance(environment, dict):
        for attr, value in environment.items():
            drafts.append(
                FactDraft(
                    subject_name="world",
                    subject_type=NODE_TYPE_CONCEPT,
                    predicate=f"environment.{attr}",
                    value=value,
                    summary=summary,
                    confidence=0.8,
                )
            )

    spatial_nodes = delta.get("spatial_nodes")
    if isinstance(spatial_nodes, dict):
        for location_name, location_delta in spatial_nodes.items():
            if isinstance(location_delta, dict):
                for attr, value in location_delta.items():
                    drafts.append(
                        FactDraft(
                            subject_name=str(location_name),
                            subject_type=NODE_TYPE_LOCATION,
                            predicate=str(attr),
                            value=value,
                            summary=summary,
                            confidence=0.9,
                            location_name=str(location_name),
                        )
                    )
            else:
                drafts.append(
                    FactDraft(
                        subject_name=str(location_name),
                        subject_type=NODE_TYPE_LOCATION,
                        predicate="state",
                        value=location_delta,
                        summary=summary,
                        confidence=0.8,
                        location_name=str(location_name),
                    )
                )

    variables = delta.get("variables")
    if isinstance(variables, dict):
        for key, value in variables.items():
            subject, predicate = _derive_subject_predicate(str(key))
            drafts.append(
                FactDraft(
                    subject_name=subject,
                    subject_type=NODE_TYPE_ENTITY if subject != "world" else NODE_TYPE_CONCEPT,
                    predicate=predicate,
                    value=value,
                    summary=summary,
                )
            )

    for key, value in delta.items():
        if key in RESERVED_DELTA_KEYS:
            continue
        subject, predicate = _derive_subject_predicate(str(key))
        drafts.append(
            FactDraft(
                subject_name=subject,
                subject_type=NODE_TYPE_ENTITY if subject != "world" else NODE_TYPE_CONCEPT,
                predicate=predicate,
                value=value,
                summary=summary,
            )
        )

    if not drafts and summary:
        drafts.extend(_extract_summary_fact_drafts(summary))
    if not drafts and summary:
        drafts.append(
            FactDraft(
                subject_name="world",
                subject_type=NODE_TYPE_CONCEPT,
                predicate="event_summary",
                value=summary,
                summary=summary,
                confidence=0.5,
            )
        )
    return drafts


def _record_graph_assertions(db: Session, event: WorldEvent) -> Dict[str, int]:
    """Extract graph assertions from event and upsert nodes/edges/facts."""
    delta = _normalize_delta(event.world_state_delta)
    drafts = _extract_fact_drafts(delta, event.summary)
    created = {"nodes": 0, "edges": 0, "facts": 0}

    for draft in drafts:
        subject_node = _upsert_world_node(
            db,
            name=draft.subject_name,
            node_type=draft.subject_type,
            metadata={"source_event_id": event.id},
        )
        if subject_node.id is not None:
            created["nodes"] += 1

        location_node_id: Optional[int] = None
        if draft.location_name:
            location_node = _upsert_world_node(
                db,
                name=draft.location_name,
                node_type=NODE_TYPE_LOCATION,
                metadata={"source_event_id": event.id},
            )
            if location_node.id is not None:
                location_node_id = int(location_node.id)
                _upsert_world_edge(
                    db=db,
                    source_node_id=int(subject_node.id),
                    target_node_id=location_node_id,
                    edge_type="located_at",
                    source_event_id=event.id,
                    confidence=draft.confidence,
                )
                created["edges"] += 1

        _upsert_world_fact(
            db=db,
            event=event,
            subject_node_id=int(subject_node.id),
            location_node_id=location_node_id,
            predicate=draft.predicate,
            value=draft.value,
            summary=draft.summary,
            confidence=draft.confidence,
        )
        created["facts"] += 1

        if isinstance(draft.value, str):
            normalized_target = _normalize_node_name(draft.value)
            if normalized_target and normalized_target != subject_node.normalized_name:
                target_node = db.query(WorldNode).filter(WorldNode.normalized_name == normalized_target).order_by(desc(WorldNode.id)).first()
                if target_node:
                    _upsert_world_edge(
                        db=db,
                        source_node_id=int(subject_node.id),
                        target_node_id=int(target_node.id),
                        edge_type=draft.predicate[:80],
                        source_event_id=event.id,
                        confidence=draft.confidence,
                    )
                    created["edges"] += 1

    return created


def record_event(
    db: Session,
    session_id: Optional[str],
    storylet_id: Optional[int],
    event_type: str,
    summary: str,
    delta: Optional[Dict[str, Any]] = None,
    state_manager: Optional[Any] = None,
    metadata: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
) -> WorldEvent:
    """Create a WorldEvent, apply deltas, embed summary, and persist it."""
    from .embedding_service import embed_text

    normalized_idempotency_key = _normalize_idempotency_key(idempotency_key)
    if normalized_idempotency_key and session_id:
        existing_event = _find_event_by_idempotency_key(
            db=db,
            session_id=session_id,
            idempotency_key=normalized_idempotency_key,
        )
        if existing_event is not None:
            logger.info(
                "Skipped duplicate world event for session=%s key=%s",
                session_id,
                normalized_idempotency_key,
            )
            return existing_event

    normalized_delta = _normalize_delta(delta)
    merged_metadata = dict(metadata or {})
    if normalized_idempotency_key:
        merged_metadata[ACTION_IDEMPOTENCY_KEY] = normalized_idempotency_key
    persisted_delta = _attach_internal_metadata(normalized_delta, merged_metadata)
    resolved_event_type = infer_event_type(event_type, normalized_delta)
    if state_manager is not None and normalized_delta:
        applied = apply_event_delta_to_state(state_manager, normalized_delta)
        logger.debug("Applied world delta to state: %s", applied)

    event = WorldEvent(
        session_id=session_id,
        storylet_id=storylet_id,
        event_type=resolved_event_type,
        summary=summary,
        embedding=embed_text(summary),
        world_state_delta=persisted_delta,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    if settings.enable_world_projection:
        try:
            projection_updates = apply_event_to_projection(db, event)
            db.commit()
            logger.debug("World projection updated rows: %s", projection_updates)
        except Exception as e:
            db.rollback()
            logger.warning("Failed to update world projection for event %s: %s", event.id, e)

    if settings.enable_world_graph_extraction:
        try:
            counts = _record_graph_assertions(db, event)
            db.commit()
            logger.debug("Graph assertions updated: %s", counts)
        except Exception as e:
            db.rollback()
            logger.warning("Failed to extract graph assertions for event %s: %s", event.id, e)

    logger.info("Recorded world event: [%s] %s", resolved_event_type, summary[:80])
    return event


def _to_utc_naive(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize optional datetimes to naive UTC for SQLite comparisons."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def get_world_history(
    db: Session,
    session_id: Optional[str] = None,
    limit: int = 50,
    event_type: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> List[WorldEvent]:
    """Get recent world events in reverse chronological order."""
    query = db.query(WorldEvent).order_by(desc(WorldEvent.id))
    if session_id:
        query = query.filter(WorldEvent.session_id == session_id)
    if event_type:
        normalized_event_type = _normalize_event_type_token(event_type)
        if normalized_event_type:
            query = query.filter(WorldEvent.event_type == normalized_event_type)
    since_utc = _to_utc_naive(since)
    if since_utc is not None:
        query = query.filter(WorldEvent.created_at >= since_utc)
    until_utc = _to_utc_naive(until)
    if until_utc is not None:
        query = query.filter(WorldEvent.created_at <= until_utc)
    return query.limit(limit).all()


def reembed_world_events(
    db: Session,
    batch_size: int = 50,
    dry_run: bool = False,
) -> Dict[str, int]:
    """Recompute embeddings for world events in bounded, failure-tolerant batches."""
    from .embedding_service import embed_text

    safe_batch_size = max(1, int(batch_size))
    total = int(db.query(WorldEvent).count())

    if dry_run:
        return {"scanned": total, "updated": 0, "failed": 0}

    scanned = 0
    updated = 0
    failed = 0
    last_id = 0

    while True:
        rows = db.query(WorldEvent).filter(WorldEvent.id > last_id).order_by(WorldEvent.id.asc()).limit(safe_batch_size).all()
        if not rows:
            break

        for row in rows:
            row_id = int(row.id or 0)
            if row_id > last_id:
                last_id = row_id
            scanned += 1
            try:
                row.embedding = embed_text(str(row.summary or ""))
                db.add(row)
                db.commit()
                updated += 1
            except Exception as exc:
                db.rollback()
                failed += 1
                logger.warning(
                    "Failed to re-embed world event id=%s type=%s: %s",
                    row.id,
                    row.event_type,
                    exc,
                )

    return {"scanned": scanned, "updated": updated, "failed": failed}


def get_world_context_vector(
    db: Session,
    session_id: Optional[str] = None,
    limit: int = 20,
) -> Optional[List[float]]:
    """Compute an average embedding of recent world events.

    Returns None if no events with embeddings exist.
    """
    events = get_world_history(db, session_id=session_id, limit=limit)
    weighted_vectors = []
    weight_total = 0.0

    for event in events:
        if not event.embedding:
            continue
        event_delta = event.world_state_delta if isinstance(event.world_state_delta, dict) else {}
        resolved_type = infer_event_type(event.event_type, event_delta)
        weight = PERMANENT_EVENT_WEIGHT if resolved_type == PERMANENT_EVENT_TYPE else 1.0
        weighted_vectors.append((event.embedding, weight))
        weight_total += weight

    if not weighted_vectors or weight_total <= 0.0:
        return None

    dim = len(weighted_vectors[0][0])
    avg = [0.0] * dim
    for vec, weight in weighted_vectors:
        for i in range(dim):
            avg[i] += vec[i] * weight
    for i in range(dim):
        avg[i] /= weight_total

    return avg


def query_world_facts(
    db: Session,
    query: str,
    session_id: Optional[str] = None,
    limit: int = 10,
) -> List[WorldEvent]:
    """Semantic search over world events by cosine similarity."""
    from .embedding_service import cosine_similarity, embed_text

    query_vector = embed_text(query)

    events = get_world_history(db, session_id=session_id, limit=200)

    scored = []
    for event in events:
        if event.embedding:
            sim = cosine_similarity(query_vector, event.embedding)
            scored.append((event, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [event for event, _ in scored[:limit]]


def query_graph_facts(
    db: Session,
    query: str,
    session_id: Optional[str] = None,
    limit: int = 10,
) -> List[WorldFact]:
    """Semantic search over active world facts by cosine similarity."""
    from .embedding_service import cosine_similarity, embed_text

    if not query.strip():
        base = db.query(WorldFact).filter(WorldFact.is_active.is_(True))
        base = _session_filter_for_facts(base, session_id)
        return base.order_by(desc(WorldFact.updated_at), desc(WorldFact.id)).limit(limit).all()

    query_vector = embed_text(query)
    base = db.query(WorldFact).filter(WorldFact.is_active.is_(True))
    base = _session_filter_for_facts(base, session_id)
    facts = base.order_by(desc(WorldFact.id)).limit(300).all()

    scored: List[tuple[WorldFact, float]] = []
    q_lower = query.lower()
    for fact in facts:
        if fact.embedding:
            score = cosine_similarity(query_vector, fact.embedding)
        else:
            blob = f"{fact.predicate} {fact.summary}".lower()
            score = 1.0 if q_lower in blob else 0.0
        scored.append((fact, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [fact for fact, _ in scored[:limit]]


def get_recent_graph_fact_summaries(
    db: Session,
    session_id: Optional[str] = None,
    limit: int = 5,
) -> List[str]:
    """Return recent active fact summaries for prompt/context injection."""
    facts = query_graph_facts(
        db=db,
        query="",
        session_id=session_id,
        limit=limit,
    )
    summaries: List[str] = []
    for fact in facts:
        if fact.summary:
            snippet = _normalize_fact_snippet(fact.summary)
            if snippet:
                summaries.append(snippet)
        else:
            snippet = _normalize_fact_snippet(f"{fact.predicate}={fact.value}")
            if snippet:
                summaries.append(snippet)
    return summaries


def get_relevant_action_facts(
    db: Session,
    action: str,
    session_id: Optional[str] = None,
    location: Optional[str] = None,
    limit: int = 8,
) -> List[str]:
    """Return a concise fact pack to ground freeform action interpretation."""
    request_started = time.perf_counter()
    timings_ms: Dict[str, float] = {}
    snippets: List[str] = []

    graph_started = time.perf_counter()
    try:
        graph_facts = query_graph_facts(
            db=db,
            query=action,
            session_id=session_id,
            limit=limit,
        )
        for fact in graph_facts:
            summary = str(fact.summary or "").strip()
            if summary:
                snippets.append(summary)
            else:
                snippets.append(f"{fact.predicate}={fact.value}")
    except Exception as e:
        logger.debug("Unable to fetch graph facts for action grounding: %s", e)
    finally:
        timings_ms["graph_facts"] = round((time.perf_counter() - graph_started) * 1000.0, 3)

    location_started = time.perf_counter()
    if location:
        try:
            location_facts = get_location_facts(
                db=db,
                location=location,
                session_id=session_id,
                limit=max(3, limit // 2),
            )
            for fact in location_facts:
                summary = str(fact.summary or "").strip()
                if summary:
                    snippets.append(summary)
        except Exception as e:
            logger.debug("Unable to fetch location facts for action grounding: %s", e)
    timings_ms["location_facts"] = round((time.perf_counter() - location_started) * 1000.0, 3)

    projection_started = time.perf_counter()
    try:
        projection_rows = get_world_projection(
            db=db,
            prefix="locations.",
            include_deleted=False,
            limit=max(5, limit),
        )
        for row in projection_rows:
            path = str(row.path or "").strip()
            if not path:
                continue
            snippets.append(f"{path}={row.value}")
    except Exception as e:
        logger.debug("Unable to fetch projection facts for action grounding: %s", e)
    finally:
        timings_ms["projection_overlay"] = round((time.perf_counter() - projection_started) * 1000.0, 3)

    deduped: List[str] = []
    seen: set[str] = set()
    consumed_chars = 0
    for snippet in snippets:
        text = _normalize_fact_snippet(snippet)
        if not text:
            continue
        if text in seen:
            continue
        projected = consumed_chars + (2 if deduped else 0) + len(text)
        if projected > ACTION_FACT_MAX_TOTAL_CHARS:
            break
        seen.add(text)
        deduped.append(text)
        consumed_chars = projected
        if len(deduped) >= limit:
            break

    logger.info(
        '{"event":"world_fact_pack_timing","trace_id":"%s","session_id":"%s","duration_ms":%.3f,' '"timings_ms":{"graph_facts":%.3f,"location_facts":%.3f,"projection_overlay":%.3f},' '"returned_fact_count":%d}',
        get_trace_id(),
        session_id or "",
        (time.perf_counter() - request_started) * 1000.0,
        timings_ms.get("graph_facts", 0.0),
        timings_ms.get("location_facts", 0.0),
        timings_ms.get("projection_overlay", 0.0),
        len(deduped),
    )

    return deduped


def get_node_neighborhood(
    db: Session,
    node_name: str,
    node_type: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """Get a node and its nearby edges/facts for graph inspection."""
    normalized = _normalize_node_name(node_name)
    query = db.query(WorldNode).filter(WorldNode.normalized_name == normalized)
    if node_type:
        query = query.filter(WorldNode.node_type == node_type)
    node = query.order_by(desc(WorldNode.id)).first()
    if node is None:
        return {"node": None, "edges": [], "facts": []}

    edges = (
        db.query(WorldEdge)
        .filter(
            or_(
                WorldEdge.source_node_id == node.id,
                WorldEdge.target_node_id == node.id,
            )
        )
        .order_by(desc(WorldEdge.updated_at), desc(WorldEdge.id))
        .limit(limit)
        .all()
    )

    node_ids = {int(node.id)}
    for edge in edges:
        node_ids.add(int(edge.source_node_id))
        node_ids.add(int(edge.target_node_id))
    nodes = db.query(WorldNode).filter(WorldNode.id.in_(list(node_ids))).all()
    node_map = {int(n.id): n for n in nodes}

    facts = (
        db.query(WorldFact)
        .filter(
            WorldFact.is_active.is_(True),
            or_(
                WorldFact.subject_node_id == node.id,
                WorldFact.location_node_id == node.id,
            ),
        )
        .order_by(desc(WorldFact.updated_at), desc(WorldFact.id))
        .limit(limit)
        .all()
    )

    return {
        "node": node,
        "edges": [
            {
                "id": edge.id,
                "edge_type": edge.edge_type,
                "source_node": node_map.get(int(edge.source_node_id)),
                "target_node": node_map.get(int(edge.target_node_id)),
                "weight": edge.weight,
                "confidence": edge.confidence,
                "source_event_id": edge.source_event_id,
                "metadata": edge.metadata_json or {},
            }
            for edge in edges
        ],
        "facts": facts,
    }


def get_relationships(
    db: Session,
    subject_name: Optional[str] = None,
    target_name: Optional[str] = None,
    edge_type: Optional[str] = None,
    limit: int = 100,
) -> List[WorldEdge]:
    """Query structured graph relationships by canonical identity."""
    query = db.query(WorldEdge)

    if subject_name:
        normalized_subject = _normalize_node_name(subject_name)
        subject_node = db.query(WorldNode).filter(WorldNode.normalized_name == normalized_subject).order_by(desc(WorldNode.id)).first()
        if subject_node:
            query = query.filter(WorldEdge.source_node_id == subject_node.id)
        else:
            return []

    if target_name:
        normalized_target = _normalize_node_name(target_name)
        target_node = db.query(WorldNode).filter(WorldNode.normalized_name == normalized_target).order_by(desc(WorldNode.id)).first()
        if target_node:
            query = query.filter(WorldEdge.target_node_id == target_node.id)
        else:
            return []

    if edge_type:
        query = query.filter(WorldEdge.edge_type == edge_type)

    return query.order_by(desc(WorldEdge.updated_at)).limit(limit).all()


def get_node_facts(
    db: Session,
    node_name: str,
    session_id: Optional[str] = None,
    predicate: Optional[str] = None,
    limit: int = 100,
) -> List[WorldFact]:
    """Retrieve active facts exactly matching a canonical subject identity."""
    normalized = _normalize_node_name(node_name)
    subject_node = db.query(WorldNode).filter(WorldNode.normalized_name == normalized).order_by(desc(WorldNode.id)).first()
    if not subject_node:
        return []

    query = db.query(WorldFact).filter(WorldFact.subject_node_id == subject_node.id, WorldFact.is_active.is_(True))
    if session_id:
        query = query.filter(or_(WorldFact.session_id == session_id, WorldFact.session_id.is_(None)))
    if predicate:
        query = query.filter(WorldFact.predicate == predicate)

    return query.order_by(desc(WorldFact.updated_at)).limit(limit).all()


def get_location_facts(
    db: Session,
    location: str,
    session_id: Optional[str] = None,
    limit: int = 20,
) -> List[WorldFact]:
    """Get active facts tied to a location node."""
    normalized = _normalize_node_name(location)
    location_node = (
        db.query(WorldNode)
        .filter(
            WorldNode.normalized_name == normalized,
            WorldNode.node_type == NODE_TYPE_LOCATION,
        )
        .order_by(desc(WorldNode.id))
        .first()
    )
    if location_node is None:
        location_node = db.query(WorldNode).filter(WorldNode.normalized_name == normalized).order_by(desc(WorldNode.id)).first()
    if location_node is None:
        return []

    query = db.query(WorldFact).filter(
        WorldFact.is_active.is_(True),
        or_(
            WorldFact.location_node_id == location_node.id,
            WorldFact.subject_node_id == location_node.id,
        ),
    )
    query = _session_filter_for_facts(query, session_id)
    return query.order_by(desc(WorldFact.updated_at), desc(WorldFact.id)).limit(limit).all()
