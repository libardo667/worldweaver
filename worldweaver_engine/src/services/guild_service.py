"""Guild participation, social feedback, and quest reducers."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy.orm import Session

from ..models import GuildMemberProfile, GuildQuest, RuntimeAdaptationState, SessionVars, SocialFeedbackEvent

VALID_MEMBER_TYPES = {"resident", "human"}
VALID_RANKS = {"apprentice", "journeyman", "guild_member", "elder"}
VALID_FEEDBACK_MODES = {"explicit", "inferred"}
VALID_FEEDBACK_CHANNELS = {"chat", "mail", "quest", "review_board", "mentor", "peer", "system"}
VALID_QUEST_STATUSES = {
    "assigned",
    "accepted",
    "in_progress",
    "completed",
    "declined",
    "cancelled",
    "reviewed",
}
VALID_QUEST_OBJECTIVE_TYPES = {
    "open_ended",
    "visit_location",
    "observe_location",
    "speak_with_person",
    "meet_person",
    "find_item",
    "deliver_message",
}
VALID_FEEDBACK_DIMENSIONS = (
    "sociability",
    "initiative",
    "repair",
    "follow_through",
    "caution",
    "mentorship_receptivity",
)
DEFAULT_BEHAVIOR_KNOBS = {
    "social_drive_bias": 0.0,
    "proactive_bias": 0.0,
    "mail_appetite_bias": 0.0,
    "movement_confidence_bias": 0.0,
    "conversation_caution_bias": 0.0,
    "quest_appetite_bias": 0.0,
    "repair_bias": 0.0,
}
DEFAULT_ENVIRONMENT_GUIDANCE = {
    "mentor_exposure": "normal",
    "solo_time": "normal",
    "social_density": "normal",
    "quest_band": "foundations",
    "branch_task_bias": "",
}
AUTO_GUILD_QUEST_ACTIVITY_SOURCES = {"slow_loop", "runtime_ledger"}
AUTO_GUILD_QUEST_UPDATE_COOLDOWN_SECONDS = 30.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utcnow().isoformat()


def _clamp(value: Any, low: float = -1.0, high: float = 1.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(low, min(high, numeric))


def _guidance_bucket(value: float, *, positive: str, negative: str, neutral: str = "normal") -> str:
    if value >= 0.35:
        return positive
    if value <= -0.35:
        return negative
    return neutral


def infer_member_type_for_session(row: SessionVars | None) -> str:
    if row is None:
        return "resident"
    return "human" if getattr(row, "player_id", None) else "resident"


def ensure_guild_member_profile(
    db: Session,
    *,
    actor_id: str,
    member_type: str = "resident",
) -> GuildMemberProfile:
    normalized_type = str(member_type or "resident").strip().lower()
    if normalized_type not in VALID_MEMBER_TYPES:
        normalized_type = "resident"
    row = db.get(GuildMemberProfile, actor_id)
    if row is None:
        row = GuildMemberProfile(
            actor_id=actor_id,
            member_type=normalized_type,
            rank="apprentice",
            branches=[],
            mentor_actor_ids=[],
            quest_band="foundations",
            review_status={"state": "unreviewed"},
            environment_guidance=dict(DEFAULT_ENVIRONMENT_GUIDANCE),
        )
        db.add(row)
        db.flush()
        return row
    if not getattr(row, "member_type", None):
        row.member_type = normalized_type
    return row


def serialize_guild_member_profile(row: GuildMemberProfile) -> dict[str, Any]:
    return {
        "actor_id": str(row.actor_id or "").strip(),
        "member_type": str(row.member_type or "resident").strip(),
        "rank": str(row.rank or "apprentice").strip(),
        "branches": list(row.branches or []),
        "mentor_actor_ids": list(row.mentor_actor_ids or []),
        "quest_band": str(row.quest_band or "foundations").strip(),
        "review_status": dict(row.review_status or {}),
        "environment_guidance": dict(row.environment_guidance or {}),
    }


def patch_guild_member_profile(row: GuildMemberProfile, payload: dict[str, Any]) -> GuildMemberProfile:
    member_type = str(payload.get("member_type") or row.member_type or "resident").strip().lower()
    if member_type in VALID_MEMBER_TYPES:
        row.member_type = member_type
    rank = str(payload.get("rank") or row.rank or "apprentice").strip().lower()
    if rank in VALID_RANKS:
        row.rank = rank
    if "branches" in payload:
        row.branches = [
            str(item or "").strip()
            for item in list(payload.get("branches") or [])
            if str(item or "").strip()
        ]
    if "mentor_actor_ids" in payload:
        row.mentor_actor_ids = [
            str(item or "").strip()
            for item in list(payload.get("mentor_actor_ids") or [])
            if str(item or "").strip()
        ]
    quest_band = str(payload.get("quest_band") or row.quest_band or "foundations").strip()
    row.quest_band = quest_band or "foundations"
    if "review_status" in payload:
        row.review_status = dict(payload.get("review_status") or {})
    if "environment_guidance" in payload:
        guidance = dict(DEFAULT_ENVIRONMENT_GUIDANCE)
        guidance.update(dict(payload.get("environment_guidance") or {}))
        row.environment_guidance = guidance
    return row


def normalize_dimension_scores(raw_scores: dict[str, Any]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for dimension in VALID_FEEDBACK_DIMENSIONS:
        if dimension not in raw_scores:
            continue
        normalized[dimension] = _clamp(raw_scores.get(dimension))
    return normalized


def serialize_social_feedback_event(row: SocialFeedbackEvent) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "target_actor_id": str(row.target_actor_id or "").strip(),
        "source_actor_id": str(row.source_actor_id or "").strip() or None,
        "source_system": str(row.source_system or "").strip() or None,
        "feedback_mode": str(row.feedback_mode or "inferred").strip(),
        "channel": str(row.channel or "system").strip(),
        "dimension_scores": dict(row.dimension_scores or {}),
        "summary": str(row.summary or "").strip(),
        "evidence_refs": list(row.evidence_refs or []),
        "branch_hint": str(row.branch_hint or "").strip() or None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_guild_quest(row: GuildQuest) -> dict[str, Any]:
    assignment_context = dict(row.assignment_context or {})
    objective = assignment_context.get("objective") if isinstance(assignment_context.get("objective"), dict) else {}
    return {
        "quest_id": int(row.id),
        "target_actor_id": str(row.target_actor_id or "").strip(),
        "source_actor_id": str(row.source_actor_id or "").strip() or None,
        "source_system": str(row.source_system or "").strip() or None,
        "title": str(row.title or "").strip(),
        "brief": str(row.brief or "").strip(),
        "branch": str(row.branch or "").strip() or None,
        "quest_band": str(row.quest_band or "foundations").strip(),
        "status": str(row.status or "assigned").strip(),
        "progress_note": str(row.progress_note or "").strip(),
        "outcome_summary": str(row.outcome_summary or "").strip(),
        "evidence_refs": list(row.evidence_refs or []),
        "activity_log": list(row.activity_log or []),
        "assignment_context": assignment_context,
        "objective": dict(objective or {}),
        "objective_type": str(objective.get("objective_type") or "").strip() or None,
        "target_location": str(objective.get("target_location") or "").strip() or None,
        "target_person": str(objective.get("target_person") or "").strip() or None,
        "target_person_actor_id": str(objective.get("target_person_actor_id") or "").strip() or None,
        "target_item": str(objective.get("target_item") or "").strip() or None,
        "success_signals": [
            str(item or "").strip()
            for item in list(objective.get("success_signals") or [])
            if str(item or "").strip()
        ],
        "review_status": dict(row.review_status or {}),
        "accepted_at": row.accepted_at.isoformat() if row.accepted_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _normalize_evidence_ref(item: Any) -> dict[str, Any] | str | None:
    if isinstance(item, str):
        value = item.strip()
        return value or None
    if not isinstance(item, dict):
        return None
    normalized = {
        str(key).strip(): value
        for key, value in item.items()
        if str(key).strip()
        and value not in (None, "", [], {})
    }
    return normalized or None


def _evidence_signature(item: Any) -> str:
    normalized = _normalize_evidence_ref(item)
    if normalized is None:
        return ""
    if isinstance(normalized, str):
        return normalized
    ordered = sorted((key, normalized[key]) for key in normalized)
    return repr(ordered)


def _merge_evidence_refs(existing: list[Any], incoming: list[Any]) -> list[dict[str, Any] | str]:
    merged: list[dict[str, Any] | str] = []
    seen: set[str] = set()
    for item in list(existing or []) + list(incoming or []):
        normalized = _normalize_evidence_ref(item)
        if normalized is None:
            continue
        signature = _evidence_signature(normalized)
        if not signature or signature in seen:
            continue
        seen.add(signature)
        merged.append(normalized)
    return merged


def _sanitize_activity_entry(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    kind = str(payload.get("kind") or payload.get("status") or "note").strip().lower().replace(" ", "_")
    summary = str(payload.get("summary") or payload.get("progress_note") or "").strip()
    status = str(payload.get("status") or "").strip().lower()
    source = str(payload.get("source") or payload.get("source_system") or payload.get("source_loop") or "").strip()
    entry: dict[str, Any] = {
        "ts": str(payload.get("ts") or _iso_now()).strip() or _iso_now(),
        "kind": kind or "note",
    }
    if status:
        entry["status"] = status
    if source:
        entry["source"] = source
    if summary:
        entry["summary"] = summary[:320]
    evidence_refs = _merge_evidence_refs([], list(payload.get("evidence_refs") or []))
    if evidence_refs:
        entry["evidence_refs"] = evidence_refs
    if "metadata" in payload and isinstance(payload.get("metadata"), dict):
        metadata = {
            str(key).strip(): value
            for key, value in dict(payload.get("metadata") or {}).items()
            if str(key).strip() and value not in (None, "", [], {})
        }
        if metadata:
            entry["metadata"] = metadata
    if len(entry) <= 2 and "status" not in entry:
        return None
    return entry


def append_guild_quest_activity(
    row: GuildQuest,
    *,
    entry: dict[str, Any] | None = None,
    summary: str = "",
    kind: str = "note",
    status: str | None = None,
    source: str = "",
    evidence_refs: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    candidate = entry
    if candidate is None:
        candidate = {
            "kind": kind,
            "status": status,
            "summary": summary,
            "source": source,
            "evidence_refs": list(evidence_refs or []),
            "metadata": dict(metadata or {}),
        }
    sanitized = _sanitize_activity_entry(candidate)
    if sanitized is None:
        return
    activity_log = list(row.activity_log or [])
    if activity_log:
        last = activity_log[-1]
        if isinstance(last, dict):
            if (
                str(last.get("kind") or "").strip() == str(sanitized.get("kind") or "").strip()
                and str(last.get("status") or "").strip() == str(sanitized.get("status") or "").strip()
                and str(last.get("summary") or "").strip() == str(sanitized.get("summary") or "").strip()
            ):
                last_evidence = _merge_evidence_refs([], list(last.get("evidence_refs") or []))
                next_evidence = _merge_evidence_refs(last_evidence, list(sanitized.get("evidence_refs") or []))
                if next_evidence:
                    last["evidence_refs"] = next_evidence
                row.activity_log = activity_log[-24:]
                return
    activity_log.append(sanitized)
    row.activity_log = activity_log[-24:]


def _activity_entry_signature(entry: dict[str, Any] | None) -> tuple[Any, ...]:
    if not isinstance(entry, dict):
        return tuple()
    evidence_signatures = tuple(
        sorted(
            _evidence_signature(item)
            for item in list(entry.get("evidence_refs") or [])
            if _evidence_signature(item)
        )
    )
    metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    metadata_signature = tuple(sorted((str(key).strip(), metadata[key]) for key in metadata if str(key).strip()))
    return (
        str(entry.get("kind") or "").strip(),
        str(entry.get("status") or "").strip(),
        str(entry.get("source") or "").strip(),
        str(entry.get("summary") or "").strip(),
        evidence_signatures,
        metadata_signature,
    )


def _activity_entries_equivalent(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    return _activity_entry_signature(left) == _activity_entry_signature(right)


def _coerce_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_guild_quest(
    db: Session,
    *,
    actor_id: str,
    payload: dict[str, Any],
    default_quest_band: str = "foundations",
) -> GuildQuest:
    status = str(payload.get("status") or "assigned").strip().lower()
    if status not in VALID_QUEST_STATUSES:
        status = "assigned"
    row = GuildQuest(
        target_actor_id=actor_id,
        source_actor_id=str(payload.get("source_actor_id") or "").strip() or None,
        source_system=str(payload.get("source_system") or "").strip() or None,
        title=str(payload.get("title") or "").strip(),
        brief=str(payload.get("brief") or "").strip(),
        branch=str(payload.get("branch") or "").strip() or None,
        quest_band=str(payload.get("quest_band") or default_quest_band or "foundations").strip() or "foundations",
        status=status,
        progress_note=str(payload.get("progress_note") or "").strip(),
        outcome_summary=str(payload.get("outcome_summary") or "").strip(),
        evidence_refs=list(payload.get("evidence_refs") or []),
        activity_log=[],
        assignment_context=dict(payload.get("assignment_context") or {}),
        review_status=dict(payload.get("review_status") or {}),
    )
    now = _utcnow()
    if status in {"accepted", "in_progress", "completed", "reviewed"}:
        row.accepted_at = now
    if status in {"completed", "reviewed"}:
        row.completed_at = now
    if status == "reviewed":
        row.reviewed_at = now
    append_guild_quest_activity(
        row,
        kind="assigned",
        status=status,
        summary=f"Quest assigned: {row.title}",
        source=str(row.source_system or row.source_actor_id or "guild"),
        evidence_refs=list(row.evidence_refs or []),
    )
    db.add(row)
    db.flush()
    return row


def patch_guild_quest(row: GuildQuest, payload: dict[str, Any]) -> bool:
    previous_status = str(row.status or "assigned").strip().lower()
    previous_progress_note = str(row.progress_note or "").strip()
    previous_outcome_summary = str(row.outcome_summary or "").strip()
    next_status = str(payload.get("status") or row.status or "assigned").strip().lower()
    now = _utcnow()
    next_title = str(payload.get("title") or row.title or "").strip() if "title" in payload else str(row.title or "").strip()
    next_brief = str(payload.get("brief") or "").strip() if "brief" in payload else str(row.brief or "").strip()
    next_branch = str(payload.get("branch") or "").strip() or None if "branch" in payload else (str(row.branch or "").strip() or None)
    next_quest_band = (
        str(payload.get("quest_band") or row.quest_band or "foundations").strip() or "foundations"
        if "quest_band" in payload
        else str(row.quest_band or "foundations").strip()
    )
    next_progress_note = str(payload.get("progress_note") or "").strip() if "progress_note" in payload else previous_progress_note
    next_outcome_summary = str(payload.get("outcome_summary") or "").strip() if "outcome_summary" in payload else previous_outcome_summary
    next_assignment_context = (
        dict(payload.get("assignment_context") or {})
        if "assignment_context" in payload
        else dict(row.assignment_context or {})
    )
    next_review_status = (
        dict(payload.get("review_status") or {})
        if "review_status" in payload
        else dict(row.review_status or {})
    )
    next_evidence_refs = list(row.evidence_refs or [])
    if "evidence_refs" in payload:
        next_evidence_refs = _merge_evidence_refs([], list(payload.get("evidence_refs") or []))
    if "append_evidence_refs" in payload:
        next_evidence_refs = _merge_evidence_refs(next_evidence_refs, list(payload.get("append_evidence_refs") or []))

    custom_activity = _sanitize_activity_entry(payload.get("activity_entry"))
    last_activity = list(row.activity_log or [])[-1] if list(row.activity_log or []) else None
    duplicate_custom_activity = (
        isinstance(last_activity, dict)
        and custom_activity is not None
        and _activity_entries_equivalent(last_activity, custom_activity)
    )
    has_structural_change = any(
        [
            next_title != str(row.title or "").strip(),
            next_brief != str(row.brief or "").strip(),
            next_branch != (str(row.branch or "").strip() or None),
            next_quest_band != str(row.quest_band or "foundations").strip(),
            next_status in VALID_QUEST_STATUSES and next_status != previous_status,
            next_progress_note != previous_progress_note,
            next_outcome_summary != previous_outcome_summary,
            next_evidence_refs != list(row.evidence_refs or []),
            next_assignment_context != dict(row.assignment_context or {}),
            next_review_status != dict(row.review_status or {}),
        ]
    )
    needs_timestamp_backfill = any(
        [
            next_status in {"accepted", "in_progress", "completed", "reviewed"} and row.accepted_at is None,
            next_status in {"completed", "reviewed"} and row.completed_at is None,
            next_status == "reviewed" and row.reviewed_at is None,
        ]
    )
    auto_source = str(custom_activity.get("source") or "").strip().lower() if custom_activity is not None else ""
    last_updated_at = _coerce_utc(getattr(row, "updated_at", None))
    recently_updated = (
        last_updated_at is not None
        and (now - last_updated_at).total_seconds() < AUTO_GUILD_QUEST_UPDATE_COOLDOWN_SECONDS
    )
    auto_payload_keys = {"status", "progress_note", "outcome_summary", "append_evidence_refs", "activity_entry"}
    if (
        auto_source in AUTO_GUILD_QUEST_ACTIVITY_SOURCES
        and recently_updated
        and not needs_timestamp_backfill
        and next_status == previous_status
        and next_evidence_refs == list(row.evidence_refs or [])
        and set(payload).issubset(auto_payload_keys)
    ):
        return False
    if not has_structural_change and not needs_timestamp_backfill:
        if custom_activity is None:
            return False
        if duplicate_custom_activity:
            return False

    if "title" in payload:
        row.title = next_title
    if "brief" in payload:
        row.brief = next_brief
    if "branch" in payload:
        row.branch = next_branch
    if "quest_band" in payload:
        row.quest_band = next_quest_band
    if "progress_note" in payload:
        row.progress_note = next_progress_note
    if "outcome_summary" in payload:
        row.outcome_summary = next_outcome_summary
    if "evidence_refs" in payload or "append_evidence_refs" in payload:
        row.evidence_refs = next_evidence_refs
    if "assignment_context" in payload:
        row.assignment_context = next_assignment_context
    if "review_status" in payload:
        row.review_status = next_review_status
    if next_status in VALID_QUEST_STATUSES:
        row.status = next_status
    if row.status in {"accepted", "in_progress", "completed", "reviewed"} and row.accepted_at is None:
        row.accepted_at = now
    if row.status in {"completed", "reviewed"} and row.completed_at is None:
        row.completed_at = now
    if row.status == "reviewed" and row.reviewed_at is None:
        row.reviewed_at = now
    if custom_activity is not None:
        append_guild_quest_activity(row, entry=custom_activity)
    else:
        if row.status != previous_status:
            status_summary = {
                "accepted": f"Quest accepted: {row.title}",
                "in_progress": f"Quest moved into active work: {row.title}",
                "completed": f"Quest completed: {row.title}",
                "reviewed": f"Quest reviewed: {row.title}",
                "declined": f"Quest declined: {row.title}",
                "cancelled": f"Quest cancelled: {row.title}",
            }.get(row.status, f"Quest status changed to {row.status}: {row.title}")
            append_guild_quest_activity(
                row,
                kind=row.status or "status_change",
                status=row.status,
                summary=status_summary,
                evidence_refs=list(payload.get("append_evidence_refs") or payload.get("evidence_refs") or []),
            )
        elif row.outcome_summary and row.outcome_summary != previous_outcome_summary:
            append_guild_quest_activity(
                row,
                kind="outcome",
                status=row.status,
                summary=row.outcome_summary,
                evidence_refs=list(payload.get("append_evidence_refs") or payload.get("evidence_refs") or []),
            )
        elif row.progress_note and row.progress_note != previous_progress_note:
            append_guild_quest_activity(
                row,
                kind="progress",
                status=row.status,
                summary=row.progress_note,
                evidence_refs=list(payload.get("append_evidence_refs") or payload.get("evidence_refs") or []),
            )
    return True


def derive_runtime_adaptation(
    feedback_rows: Iterable[SocialFeedbackEvent],
    *,
    default_quest_band: str = "foundations",
) -> dict[str, Any]:
    weighted_totals = {dimension: 0.0 for dimension in VALID_FEEDBACK_DIMENSIONS}
    weighted_counts = {dimension: 0.0 for dimension in VALID_FEEDBACK_DIMENSIONS}
    branch_counter: Counter[str] = Counter()
    source_feedback_ids: list[int] = []

    for row in feedback_rows:
        source_feedback_ids.append(int(row.id))
        mode_weight = 1.0 if str(row.feedback_mode or "").strip().lower() == "explicit" else 0.6
        for dimension, score in dict(row.dimension_scores or {}).items():
            if dimension not in weighted_totals:
                continue
            clamped = _clamp(score)
            weighted_totals[dimension] += clamped * mode_weight
            weighted_counts[dimension] += mode_weight
        branch_hint = str(row.branch_hint or "").strip()
        if branch_hint:
            branch_counter[branch_hint] += 1

    dimension_summary = {
        dimension: (
            weighted_totals[dimension] / weighted_counts[dimension]
            if weighted_counts[dimension] > 0
            else 0.0
        )
        for dimension in VALID_FEEDBACK_DIMENSIONS
    }
    sociability = dimension_summary["sociability"]
    initiative = dimension_summary["initiative"]
    repair = dimension_summary["repair"]
    follow_through = dimension_summary["follow_through"]
    caution = dimension_summary["caution"]
    mentorship = dimension_summary["mentorship_receptivity"]

    behavior_knobs = {
        "social_drive_bias": _clamp((sociability * 0.7) + (mentorship * 0.1)),
        "proactive_bias": _clamp((initiative * 0.7) + (follow_through * 0.2) - (caution * 0.2)),
        "mail_appetite_bias": _clamp((follow_through * 0.5) + (sociability * 0.35) - (caution * 0.2)),
        "movement_confidence_bias": _clamp((initiative * 0.45) - (caution * 0.55)),
        "conversation_caution_bias": _clamp((caution * 0.7) - (sociability * 0.15)),
        "quest_appetite_bias": _clamp((initiative * 0.5) + (follow_through * 0.4) - (caution * 0.15)),
        "repair_bias": _clamp((repair * 0.8) + (mentorship * 0.1)),
    }
    environment_guidance = {
        "mentor_exposure": _guidance_bucket(mentorship - initiative, positive="high", negative="low"),
        "solo_time": _guidance_bucket(caution - sociability, positive="high", negative="low"),
        "social_density": _guidance_bucket(sociability - caution, positive="high", negative="low"),
        "quest_band": (
            "supported_stretch"
            if (initiative + follow_through) >= 0.7
            else "steady_practice"
            if (initiative + follow_through) >= 0.25
            else default_quest_band or "foundations"
        ),
        "branch_task_bias": branch_counter.most_common(1)[0][0] if branch_counter else "",
    }
    return {
        "behavior_knobs": behavior_knobs,
        "environment_guidance": environment_guidance,
        "dimension_summary": dimension_summary,
        "source_feedback_ids": source_feedback_ids[-64:],
    }


def recompute_runtime_adaptation_state(
    db: Session,
    *,
    actor_id: str,
    quest_band: str = "foundations",
) -> RuntimeAdaptationState:
    row = db.get(RuntimeAdaptationState, actor_id)
    if row is None:
        row = RuntimeAdaptationState(
            actor_id=actor_id,
            behavior_knobs=dict(DEFAULT_BEHAVIOR_KNOBS),
            environment_guidance=dict(DEFAULT_ENVIRONMENT_GUIDANCE),
            source_feedback_ids=[],
        )
        db.add(row)

    feedback_rows = (
        db.query(SocialFeedbackEvent)
        .filter(SocialFeedbackEvent.target_actor_id == actor_id)
        .order_by(SocialFeedbackEvent.created_at.desc(), SocialFeedbackEvent.id.desc())
        .limit(120)
        .all()
    )
    derived = derive_runtime_adaptation(feedback_rows, default_quest_band=quest_band or "foundations")
    row.behavior_knobs = derived["behavior_knobs"]
    row.environment_guidance = derived["environment_guidance"]
    row.source_feedback_ids = derived["source_feedback_ids"]
    return row


def serialize_runtime_adaptation_state(row: RuntimeAdaptationState | None) -> dict[str, Any]:
    if row is None:
        return {
            "behavior_knobs": dict(DEFAULT_BEHAVIOR_KNOBS),
            "environment_guidance": dict(DEFAULT_ENVIRONMENT_GUIDANCE),
            "source_feedback_ids": [],
            "updated_at": None,
        }
    return {
        "behavior_knobs": dict(DEFAULT_BEHAVIOR_KNOBS) | dict(row.behavior_knobs or {}),
        "environment_guidance": dict(DEFAULT_ENVIRONMENT_GUIDANCE) | dict(row.environment_guidance or {}),
        "source_feedback_ids": list(row.source_feedback_ids or []),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
