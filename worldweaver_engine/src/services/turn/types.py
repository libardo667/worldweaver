"""Shared action result types for the turn pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ActionResult:
    """Result of interpreting a freeform player action."""

    narrative_text: str
    public_summary: str = ""
    state_deltas: Dict[str, Any] = field(default_factory=dict)
    should_trigger_storylet: bool = False
    follow_up_choices: List[Dict[str, Any]] = field(default_factory=list)
    suggested_beats: List[Dict[str, Any]] = field(default_factory=list)
    plausible: bool = True
    reasoning_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StagedActionIntent:
    """Stage-A output: validated deterministic deltas plus immediate ack line."""

    ack_line: str
    result: ActionResult
