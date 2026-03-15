"""Goal domain: GoalMilestone, GoalState dataclasses and GoalDomain manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ._utils import _parse_dt


@dataclass
class GoalMilestone:
    """A single arc milestone event."""

    title: str
    status: str = "progressed"
    note: str = ""
    source: str = "system"
    urgency_delta: float = 0.0
    complication_delta: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "status": self.status,
            "note": self.note,
            "source": self.source,
            "urgency_delta": self.urgency_delta,
            "complication_delta": self.complication_delta,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalMilestone":
        return cls(
            title=str(data.get("title", "Milestone")),
            status=str(data.get("status", "progressed")),
            note=str(data.get("note", "")),
            source=str(data.get("source", "system")),
            urgency_delta=float(data.get("urgency_delta", 0.0)),
            complication_delta=float(data.get("complication_delta", 0.0)),
            timestamp=_parse_dt(data.get("timestamp")) or datetime.now(timezone.utc),
        )


@dataclass
class GoalState:
    """Structured goal tracking."""

    primary_goal: str = ""
    subgoals: List[str] = field(default_factory=list)
    urgency: float = 0.0
    complication: float = 0.0
    milestones: List[GoalMilestone] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_goal": self.primary_goal,
            "subgoals": list(self.subgoals),
            "urgency": float(self.urgency),
            "complication": float(self.complication),
            "milestones": [m.to_dict() for m in self.milestones],
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalState":
        milestones = [GoalMilestone.from_dict(m) for m in data.get("milestones", []) if isinstance(m, dict)]
        return cls(
            primary_goal=str(data.get("primary_goal", "")),
            subgoals=list(data.get("subgoals", [])),
            urgency=float(data.get("urgency", 0.0)),
            complication=float(data.get("complication", 0.0)),
            milestones=milestones,
            updated_at=_parse_dt(data.get("updated_at")) or datetime.now(timezone.utc),
        )


class GoalDomain:
    """Bounded goal state with milestone tracking."""

    _VALID_STATUSES = {"progressed", "complicated", "derailed", "branched", "completed"}

    def __init__(self) -> None:
        self._state = GoalState()

    @property
    def state(self) -> GoalState:
        return self._state

    def _clamp(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _record_milestone(
        self,
        title: str,
        status: str,
        *,
        note: str = "",
        source: str = "system",
        urgency_delta: float = 0.0,
        complication_delta: float = 0.0,
    ) -> GoalMilestone:
        clean_status = str(status).lower().strip()
        if clean_status not in self._VALID_STATUSES:
            clean_status = "progressed"

        milestone = GoalMilestone(
            title=str(title).strip() or "Milestone",
            status=clean_status,
            note=str(note or ""),
            source=str(source or "system"),
            urgency_delta=float(urgency_delta),
            complication_delta=float(complication_delta),
        )
        self._state.milestones.append(milestone)
        if len(self._state.milestones) > 50:
            self._state.milestones = self._state.milestones[-50:]
        self._state.updated_at = datetime.now(timezone.utc)
        return milestone

    def set_goal_state(
        self,
        *,
        primary_goal: Optional[str] = None,
        subgoals: Optional[List[str]] = None,
        urgency: Optional[float] = None,
        complication: Optional[float] = None,
        note: Optional[str] = None,
        source: str = "player",
    ) -> Dict[str, Any]:
        changed = False
        if primary_goal is not None:
            cleaned = str(primary_goal).strip()
            if cleaned and cleaned != self._state.primary_goal:
                self._state.primary_goal = cleaned
                changed = True
                self._record_milestone(
                    title=f"Primary goal set: {cleaned}",
                    status="branched",
                    note=str(note or ""),
                    source=source,
                )

        if subgoals is not None:
            cleaned_subgoals = [str(g).strip() for g in subgoals[:10] if str(g).strip()]
            self._state.subgoals = cleaned_subgoals
            changed = True

        if urgency is not None:
            self._state.urgency = self._clamp(float(urgency))
            changed = True

        if complication is not None:
            self._state.complication = self._clamp(float(complication))
            changed = True

        if changed:
            self._state.updated_at = datetime.now(timezone.utc)

        return self.get_state()

    def add_subgoal(self, subgoal: str, source: str = "system") -> None:
        cleaned = str(subgoal).strip()
        if not cleaned:
            return
        if cleaned not in self._state.subgoals:
            self._state.subgoals.append(cleaned)
            self._state.subgoals = self._state.subgoals[:10]
            self._record_milestone(
                title=f"New subgoal: {cleaned}",
                status="branched",
                source=source,
            )

    def mark_milestone(
        self,
        title: str,
        *,
        status: str = "progressed",
        note: str = "",
        source: str = "system",
        urgency_delta: float = 0.0,
        complication_delta: float = 0.0,
    ) -> Dict[str, Any]:
        self._state.urgency = self._clamp(self._state.urgency + float(urgency_delta))
        self._state.complication = self._clamp(self._state.complication + float(complication_delta))
        self._record_milestone(
            title=title,
            status=status,
            note=note,
            source=source,
            urgency_delta=urgency_delta,
            complication_delta=complication_delta,
        )
        return self.get_state()

    def apply_update(self, update: Dict[str, Any], *, source: str = "system") -> Dict[str, Any]:
        if not update:
            return self.get_state()

        status = str(update.get("status", "progressed")).lower()
        if status not in self._VALID_STATUSES:
            status = "progressed"

        milestone = str(update.get("milestone", "")).strip()
        note = str(update.get("note", "")).strip()
        subgoal = str(update.get("subgoal", "")).strip()
        urgency_delta = float(update.get("urgency_delta", 0.0))
        complication_delta = float(update.get("complication_delta", 0.0))
        # Auto-ratchet removed: urgency/complication only change when explicitly provided.

        primary_goal = update.get("primary_goal")
        if primary_goal is not None:
            self.set_goal_state(primary_goal=str(primary_goal), source=source, note=note)

        if subgoal:
            self.add_subgoal(subgoal, source=source)

        if milestone or urgency_delta or complication_delta:
            self.mark_milestone(
                milestone or "Goal state adjusted",
                status=status,
                note=note,
                source=source,
                urgency_delta=urgency_delta,
                complication_delta=complication_delta,
            )

        return self.get_state()

    def get_state(self) -> Dict[str, Any]:
        return self._state.to_dict()

    def get_lens_payload(self) -> Dict[str, Any]:
        milestones = [m.to_dict() for m in self._state.milestones[-3:]]
        return {
            "primary_goal": str(self._state.primary_goal or ""),
            "subgoals": list(self._state.subgoals),
            "urgency": float(self._state.urgency),
            "complication": float(self._state.complication),
            "recent_milestones": milestones,
        }

    def get_arc_timeline(self, limit: int = 20) -> List[Dict[str, Any]]:
        recent = self._state.milestones[-max(1, int(limit)) :]
        return [m.to_dict() for m in reversed(recent)]

    def get_embedding_context(self) -> str:
        if not self._state.primary_goal:
            return ""
        parts = [f"Primary goal: {self._state.primary_goal}"]
        if self._state.subgoals:
            parts.append("Subgoals: " + ", ".join(self._state.subgoals[:5]))
        parts.append(f"Goal urgency={self._state.urgency:.2f}, complication={self._state.complication:.2f}")
        if self._state.milestones:
            milestone_text = "; ".join(f"{m.status}: {m.title}" for m in self._state.milestones[-3:])
            parts.append("Recent arc milestones: " + milestone_text)
        return " ".join(parts)

    def backfill_primary_goal_if_empty(
        self,
        *,
        variables: Dict[str, Any],
        minimum_turn_count: int = 1,
        source: str = "system_goal_backfill",
    ) -> Dict[str, Any]:
        """Populate primary_goal once after turn 1 if still empty.

        Reads variables dict (owned by the orchestrator) for arc turn_count and
        world-context keys. Deterministic and idempotent.
        """
        _GOAL_BACKFILL_NOTE = "auto_backfill_after_initial_turn"
        _STORY_ARC_KEY = "_story_arc"

        current_goal = str(self._state.primary_goal or "").strip()
        if current_goal:
            return {
                "applied": False,
                "reason": "primary_goal_present",
                "primary_goal": current_goal,
            }

        arc_payload = variables.get(_STORY_ARC_KEY)
        if isinstance(arc_payload, dict):
            turn_count = max(0, int(arc_payload.get("turn_count", 0) or 0))
        else:
            turn_count = 0
        required = max(1, int(minimum_turn_count))
        if turn_count < required:
            return {
                "applied": False,
                "reason": "below_turn_threshold",
                "turn_count": turn_count,
                "minimum_turn_count": required,
                "primary_goal": "",
            }

        # Derive fallback goal from variables context
        role = ""
        for key in ("player_role", "character_profile", "role", "occupation"):
            candidate = str(variables.get(key, "")).strip()
            if candidate:
                role = candidate
                break
        role = role or "wanderer"

        _WORLD_BIBLE_KEY = "_world_bible"
        world_bible = variables.get(_WORLD_BIBLE_KEY)
        if not isinstance(world_bible, dict):
            world_bible = {}
        world_theme = str(variables.get("world_theme", "")).strip()

        if world_theme:
            fallback_goal = (f"As {role}, establish your footing in this {world_theme} world and secure a reliable way forward.")[:220]
        else:
            fallback_goal = f"As {role}, secure your footing and define a clear path forward."[:220]

        if not fallback_goal:
            return {
                "applied": False,
                "reason": "fallback_empty",
                "turn_count": turn_count,
                "primary_goal": "",
            }

        self.set_goal_state(
            primary_goal=fallback_goal,
            source=source,
            note=_GOAL_BACKFILL_NOTE,
        )
        return {
            "applied": True,
            "reason": "goal_backfilled",
            "turn_count": turn_count,
            "primary_goal": str(self._state.primary_goal or ""),
            "source": source,
            "note": _GOAL_BACKFILL_NOTE,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self._state.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalDomain":
        domain = cls()
        domain._state = GoalState.from_dict(data)
        return domain
