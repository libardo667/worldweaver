# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Structural result for two branches restored from one resident-gym checkpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .resident_gym import GymEpisodeResult


@dataclass(frozen=True, slots=True)
class GymCounterfactualBranch:
    """One independently resumed branch and its content-safe summary."""

    branch_id: str
    condition: str
    summary: dict[str, Any]
    episode: GymEpisodeResult

    def as_payload(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "condition": self.condition,
            "summary": dict(self.summary),
            "episode": self.episode.as_payload(),
        }


@dataclass(frozen=True, slots=True)
class GymCounterfactualResult:
    """Two matched branches with explicit common-state and intervention proof."""

    episode: str
    source_checkpoint_id: str
    private_artifact_id: str
    common_record_count: int
    controlled_variable: str
    branches: tuple[GymCounterfactualBranch, ...]

    def as_payload(self) -> dict[str, Any]:
        return {
            "schema": "worldweaver.resident-gym.counterfactual",
            "schema_version": 1,
            "episode": self.episode,
            "source_checkpoint_id": self.source_checkpoint_id,
            "private_artifact_id": self.private_artifact_id,
            "common_record_count": self.common_record_count,
            "controlled_variable": self.controlled_variable,
            "invariants": {
                "same_engine_checkpoint": True,
                "same_private_artifact": True,
                "independent_engine_databases": True,
                "independent_resident_homes": True,
                "one_declared_intervention": True,
            },
            "branches": [branch.as_payload() for branch in self.branches],
        }
