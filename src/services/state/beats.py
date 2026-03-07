"""Narrative beats domain: NarrativeBeatsDomain manager."""

from __future__ import annotations

from typing import Any, Dict, List, Union

from ...models import NarrativeBeat


class NarrativeBeatsDomain:
    """Bounded narrative-beat state with add/decay/expiry lifecycle."""

    def __init__(self) -> None:
        self._beats: List[NarrativeBeat] = []

    @property
    def beats(self) -> List[NarrativeBeat]:
        return self._beats

    def add(self, beat: Union[NarrativeBeat, Dict[str, Any]]) -> None:
        """Add or merge a beat. Merges by name (case-insensitive)."""
        normalized = beat if isinstance(beat, NarrativeBeat) else NarrativeBeat.from_dict(beat)
        normalized.name = str(normalized.name or "").strip() or "ThematicResonance"
        normalized.intensity = max(0.0, float(normalized.intensity))
        normalized.turns_remaining = max(0, int(normalized.turns_remaining))
        normalized.decay = max(0.0, min(1.0, float(normalized.decay)))
        if not normalized.is_active():
            return

        for idx, existing in enumerate(self._beats):
            if existing.name.lower() == normalized.name.lower():
                merged = NarrativeBeat(
                    name=existing.name,
                    intensity=max(0.0, float(existing.intensity) + float(normalized.intensity)),
                    turns_remaining=max(existing.turns_remaining, normalized.turns_remaining),
                    decay=min(float(existing.decay), float(normalized.decay)),
                    vector=normalized.vector or existing.vector,
                    source=normalized.source or existing.source,
                )
                self._beats[idx] = merged
                return

        self._beats.append(normalized)

    def get_active(self) -> List[NarrativeBeat]:
        self._beats = [b for b in self._beats if b.is_active()]
        return list(self._beats)

    def decay(self) -> None:
        if not self._beats:
            return
        for beat in self._beats:
            beat.consume_turn()
        self._beats = [b for b in self._beats if b.is_active()]

    def to_dict(self) -> List[Dict[str, Any]]:
        return [b.to_dict() for b in self._beats if b.is_active()]

    @classmethod
    def from_dict(cls, data: List[Any]) -> "NarrativeBeatsDomain":
        domain = cls()
        for payload in data:
            if not isinstance(payload, dict):
                continue
            try:
                domain.add(NarrativeBeat.from_dict(payload))
            except Exception:
                continue
        return domain
