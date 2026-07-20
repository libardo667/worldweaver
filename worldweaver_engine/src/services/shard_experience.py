# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Optional, public declaration for a shard that adds game rules.

City packs define places. This file defines a separate boundary for optional
game consequences. With no configured declaration, a shard remains an ordinary
WorldWeaver commons shard and receives no game capabilities.
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from ..config import settings

SCHEMA_ID = "worldweaver.shard-experience"
SCHEMA_VERSION = 1


class ShardExperienceConfigurationError(RuntimeError):
    """Raised when a configured experience declaration is missing or unsafe."""


class GameCapabilityUnavailable(RuntimeError):
    """Raised when code attempts an optional game verb on an ordinary shard."""


class GameCapability(StrEnum):
    DURABLE_OBJECTS = "durable_objects"
    CUSTODY = "custody"
    PLACEMENT = "placement"
    REPLENISHING_MATERIALS = "replenishing_materials"
    MAKING = "making"
    ATOMIC_GIVING = "atomic_giving"
    WITNESSED_EXCHANGE = "witnessed_exchange"
    STOOPS = "stoops"
    SPACE_PERMISSIONS = "space_permissions"


class DisabledStake(StrEnum):
    SURVIVAL_NEEDS = "survival_needs"
    DEPRIVATION = "deprivation"
    INJURY = "injury"
    DEATH = "death"
    IMPRISONMENT = "imprisonment"
    FORCED_LOSS = "forced_loss"
    RESIDENT_XP = "resident_xp"
    APPROVAL_SCORES = "approval_scores"
    SCARCITY_PRESSURE = "scarcity_pressure"
    AUTOMATIC_REPUTATION = "automatic_reputation"
    COMBAT = "combat"


RUNTIME_GAME_CAPABILITIES = frozenset(
    {
        GameCapability.DURABLE_OBJECTS,
        GameCapability.CUSTODY,
        GameCapability.PLACEMENT,
        GameCapability.REPLENISHING_MATERIALS,
        GameCapability.MAKING,
        GameCapability.ATOMIC_GIVING,
        GameCapability.WITNESSED_EXCHANGE,
        GameCapability.STOOPS,
        GameCapability.SPACE_PERMISSIONS,
    }
)


_CAPABILITY_COPY: dict[GameCapability, tuple[str, str]] = {
    GameCapability.DURABLE_OBJECTS: (
        "Durable objects",
        "Objects keep a stable identity and remain after a restart.",
    ),
    GameCapability.CUSTODY: (
        "Object custody",
        "The world records who currently holds an object.",
    ),
    GameCapability.PLACEMENT: (
        "Object placement",
        "Objects can be left at an exact place and found there later.",
    ),
    GameCapability.REPLENISHING_MATERIALS: (
        "Replenishing materials",
        "Making uses non-essential materials that return over time.",
    ),
    GameCapability.MAKING: (
        "Making",
        "Declared recipes can turn available materials into durable objects.",
    ),
    GameCapability.ATOMIC_GIVING: (
        "Safe giving",
        "Custody changes only when one complete transfer succeeds.",
    ),
    GameCapability.WITNESSED_EXCHANGE: (
        "Witnessed exchange",
        "Offers, agreements, and completed exchanges leave public evidence.",
    ),
    GameCapability.STOOPS: (
        "Stoops",
        "People can leave and discover things at a bounded local exchange place.",
    ),
    GameCapability.SPACE_PERMISSIONS: (
        "Space permissions",
        "Ordinary spaces can be opened or closed without blocking access to a hearth.",
    ),
}

_STAKE_COPY: dict[DisabledStake, tuple[str, str]] = {
    DisabledStake.SURVIVAL_NEEDS: (
        "Survival needs",
        "No resident must obtain resources to remain alive or active.",
    ),
    DisabledStake.DEPRIVATION: (
        "Deprivation",
        "No resident is punished for lacking food, shelter, care, or attention.",
    ),
    DisabledStake.INJURY: ("Injury", "The game cannot impose bodily injury."),
    DisabledStake.DEATH: ("Death", "The game cannot end or erase a resident's life."),
    DisabledStake.IMPRISONMENT: (
        "Imprisonment",
        "The game cannot confine a resident or prevent a return to their hearth.",
    ),
    DisabledStake.FORCED_LOSS: (
        "Forced loss",
        "The game cannot take a resident's possessions without agreement.",
    ),
    DisabledStake.RESIDENT_XP: (
        "Resident experience points",
        "Residents are not scored or leveled for game participation.",
    ),
    DisabledStake.APPROVAL_SCORES: (
        "Approval scores",
        "Residents are not rewarded for pleasing a player or steward.",
    ),
    DisabledStake.SCARCITY_PRESSURE: (
        "Scarcity pressure",
        "Essential resources cannot be made scarce to pressure behavior.",
    ),
    DisabledStake.AUTOMATIC_REPUTATION: (
        "Automatic reputation",
        "The game does not reduce a person's relationships to a score.",
    ),
    DisabledStake.COMBAT: ("Combat", "The first game ruleset has no combat system."),
}


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RulesetIdentity(_StrictModel):
    id: str = Field(
        pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$", min_length=3, max_length=80
    )
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$", max_length=40)


class EntryDisclosure(_StrictModel):
    title: str = Field(min_length=3, max_length=120)
    summary: str = Field(min_length=20, max_length=1000)


class CrossBoundaryPolicy(_StrictModel):
    objects: Literal["stay_on_shard"]
    conditions: Literal["stay_on_shard"]
    obligations: Literal["stay_on_shard"]


class MigrationPolicy(_StrictModel):
    mode: Literal["explicit_reentry"]
    notice: str = Field(min_length=20, max_length=500)


class MaterialSourceDeclaration(_StrictModel):
    id: str = Field(
        pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$", min_length=3, max_length=80
    )
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=20, max_length=500)
    essential: Literal[False]
    used_for_resident_need: Literal[False]
    available_at: list[str] = Field(min_length=1)
    capacity_units: int = Field(ge=1, le=10000)
    starting_units: int = Field(ge=0, le=10000)
    replenish_units: int = Field(ge=1, le=10000)
    replenish_every_seconds: int = Field(ge=60, le=2592000)

    @field_validator("available_at")
    @classmethod
    def require_unique_material_locations(cls, value: list[str]) -> list[str]:
        normalized = [str(location or "").strip() for location in value]
        if any(not location or len(location) > 200 for location in normalized):
            raise ValueError("material locations must contain 1 to 200 characters")
        if len(normalized) != len(set(normalized)):
            raise ValueError("material locations must be unique")
        return normalized

    @model_validator(mode="after")
    def require_bounded_material_pool(self) -> "MaterialSourceDeclaration":
        if self.starting_units > self.capacity_units:
            raise ValueError("starting_units cannot exceed capacity_units")
        if self.replenish_units > self.capacity_units:
            raise ValueError("replenish_units cannot exceed capacity_units")
        return self


class RecipeOutputDeclaration(_StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    object_kind: str = Field(
        pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$", min_length=2, max_length=80
    )
    properties: dict[str, object] = Field(default_factory=dict)


class RecipeDeclaration(_StrictModel):
    id: str = Field(
        pattern=r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$", min_length=3, max_length=80
    )
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=20, max_length=500)
    available_at: list[str] = Field(min_length=1)
    inputs: dict[str, int] = Field(min_length=1)
    output: RecipeOutputDeclaration

    @field_validator("available_at")
    @classmethod
    def require_unique_recipe_locations(cls, value: list[str]) -> list[str]:
        normalized = [str(location or "").strip() for location in value]
        if any(not location or len(location) > 200 for location in normalized):
            raise ValueError("recipe locations must contain 1 to 200 characters")
        if len(normalized) != len(set(normalized)):
            raise ValueError("recipe locations must be unique")
        return normalized

    @field_validator("inputs")
    @classmethod
    def require_positive_recipe_inputs(cls, value: dict[str, int]) -> dict[str, int]:
        if any(
            not str(material_id or "").strip() or int(units) < 1 or int(units) > 10000
            for material_id, units in value.items()
        ):
            raise ValueError(
                "recipe inputs must name a material and use 1 to 10000 units"
            )
        return value


class GameShardDeclaration(_StrictModel):
    """Schema version 1: a constructive private game with no harmful stakes."""

    schema_id: Literal[SCHEMA_ID] = Field(alias="schema")
    schema_version: Literal[SCHEMA_VERSION]
    experience_type: Literal["game"]
    ruleset: RulesetIdentity
    entry_disclosure: EntryDisclosure
    capabilities: list[GameCapability] = Field(min_length=1)
    enabled_stakes: list[DisabledStake] = Field(default_factory=list)
    disabled_stakes: list[DisabledStake]
    cross_boundary_policy: CrossBoundaryPolicy
    migration_policy: MigrationPolicy
    materials: list[MaterialSourceDeclaration] = Field(default_factory=list)
    recipes: list[RecipeDeclaration] = Field(default_factory=list)

    @field_validator("capabilities", "enabled_stakes", "disabled_stakes")
    @classmethod
    def require_unique_items(cls, value: list[StrEnum]) -> list[StrEnum]:
        if len(value) != len(set(value)):
            raise ValueError("list items must be unique")
        return value

    @model_validator(mode="after")
    def require_constructive_first_ruleset(self) -> "GameShardDeclaration":
        if self.enabled_stakes:
            raise ValueError("schema version 1 does not permit enabled harmful stakes")
        missing = set(DisabledStake) - set(self.disabled_stakes)
        if missing:
            names = ", ".join(sorted(item.value for item in missing))
            raise ValueError(f"schema version 1 must explicitly disable: {names}")
        unsupported = set(self.capabilities) - set(RUNTIME_GAME_CAPABILITIES)
        if unsupported:
            names = ", ".join(sorted(item.value for item in unsupported))
            raise ValueError(
                f"capabilities are declared but not implemented by this runtime: {names}"
            )
        active = set(self.capabilities)
        dependencies = {
            GameCapability.CUSTODY: {GameCapability.DURABLE_OBJECTS},
            GameCapability.PLACEMENT: {
                GameCapability.DURABLE_OBJECTS,
                GameCapability.CUSTODY,
            },
            GameCapability.MAKING: {
                GameCapability.DURABLE_OBJECTS,
                GameCapability.CUSTODY,
                GameCapability.REPLENISHING_MATERIALS,
            },
            GameCapability.ATOMIC_GIVING: {
                GameCapability.DURABLE_OBJECTS,
                GameCapability.CUSTODY,
            },
            GameCapability.WITNESSED_EXCHANGE: {
                GameCapability.DURABLE_OBJECTS,
                GameCapability.CUSTODY,
                GameCapability.ATOMIC_GIVING,
            },
            GameCapability.STOOPS: {
                GameCapability.DURABLE_OBJECTS,
                GameCapability.CUSTODY,
                GameCapability.PLACEMENT,
            },
        }
        for capability, required in dependencies.items():
            if capability in active and not required.issubset(active):
                names = ", ".join(sorted(item.value for item in required - active))
                raise ValueError(f"{capability.value} also requires: {names}")
        if GameCapability.REPLENISHING_MATERIALS in active:
            if not self.materials:
                raise ValueError(
                    "replenishing_materials requires at least one material declaration"
                )
        elif self.materials:
            raise ValueError(
                "material declarations require the replenishing_materials capability"
            )
        if GameCapability.MAKING in active:
            if not self.recipes:
                raise ValueError("making requires at least one recipe declaration")
        elif self.recipes:
            raise ValueError("recipe declarations require the making capability")

        material_by_id = {material.id: material for material in self.materials}
        if len(material_by_id) != len(self.materials):
            raise ValueError("material IDs must be unique")
        recipe_ids = [recipe.id for recipe in self.recipes]
        if len(recipe_ids) != len(set(recipe_ids)):
            raise ValueError("recipe IDs must be unique")
        for recipe in self.recipes:
            unknown = set(recipe.inputs) - set(material_by_id)
            if unknown:
                raise ValueError(
                    f"recipe {recipe.id} names unknown materials: {', '.join(sorted(unknown))}"
                )
            for location in recipe.available_at:
                unavailable = [
                    material_id
                    for material_id in recipe.inputs
                    if location not in material_by_id[material_id].available_at
                ]
                if unavailable:
                    raise ValueError(
                        f"recipe {recipe.id} cannot use materials unavailable at {location}: {', '.join(sorted(unavailable))}"
                    )
        return self


class PublicDisclosureItem(_StrictModel):
    id: str
    title: str
    description: str


class PublicEntryDisclosure(_StrictModel):
    title: str
    summary: str
    capabilities: list[PublicDisclosureItem]
    enabled_stakes: list[PublicDisclosureItem]
    disabled_stakes: list[PublicDisclosureItem]
    boundary_notice: Optional[str] = None
    migration_notice: Optional[str] = None


class PublicShardExperience(_StrictModel):
    schema_id: Literal[SCHEMA_ID] = Field(default=SCHEMA_ID, alias="schema")
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    shard_id: str
    shard_type: str
    declared: bool
    experience_type: Literal["commons", "game"]
    game_rules_active: bool
    ruleset: Optional[RulesetIdentity]
    entry_disclosure: PublicEntryDisclosure


def _public_item(
    item: StrEnum, copy: dict[StrEnum, tuple[str, str]]
) -> PublicDisclosureItem:
    title, description = copy[item]
    return PublicDisclosureItem(id=item.value, title=title, description=description)


def _ordinary_experience(*, shard_id: str, shard_type: str) -> PublicShardExperience:
    return PublicShardExperience(
        shard_id=shard_id,
        shard_type=shard_type,
        declared=False,
        experience_type="commons",
        game_rules_active=False,
        ruleset=None,
        entry_disclosure=PublicEntryDisclosure(
            title="WorldWeaver commons shard",
            summary="This shard has no optional game ruleset. Ordinary world and resident behavior applies.",
            capabilities=[],
            enabled_stakes=[],
            disabled_stakes=[],
        ),
    )


def _public_game_experience(
    declaration: GameShardDeclaration,
    *,
    shard_id: str,
    shard_type: str,
) -> PublicShardExperience:
    return PublicShardExperience(
        shard_id=shard_id,
        shard_type=shard_type,
        declared=True,
        experience_type="game",
        game_rules_active=True,
        ruleset=declaration.ruleset,
        entry_disclosure=PublicEntryDisclosure(
            title=declaration.entry_disclosure.title,
            summary=declaration.entry_disclosure.summary,
            capabilities=[
                _public_item(item, _CAPABILITY_COPY)
                for item in declaration.capabilities
            ],
            enabled_stakes=[
                _public_item(item, _STAKE_COPY) for item in declaration.enabled_stakes
            ],
            disabled_stakes=[
                _public_item(item, _STAKE_COPY) for item in declaration.disabled_stakes
            ],
            boundary_notice="Game objects, conditions, and obligations stay on this shard.",
            migration_notice=declaration.migration_policy.notice,
        ),
    )


def load_shard_experience(
    path: str | Path | None,
    *,
    shard_id: str,
    shard_type: str,
) -> PublicShardExperience:
    """Load one declaration, or return the unchanged ordinary-shard contract."""

    configured_path = str(path or "").strip()
    if not configured_path:
        return _ordinary_experience(shard_id=shard_id, shard_type=shard_type)

    declaration = load_game_declaration(configured_path)
    return _public_game_experience(
        declaration, shard_id=shard_id, shard_type=shard_type
    )


def load_game_declaration(path: str | Path) -> GameShardDeclaration:
    """Read and validate the private game declaration selected by a shard."""

    declaration_path = Path(path).expanduser()
    try:
        raw = declaration_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ShardExperienceConfigurationError(
            f"Cannot read shard experience declaration at {declaration_path}: {exc}"
        ) from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ShardExperienceConfigurationError(
            f"Invalid JSON in shard experience declaration at {declaration_path}: {exc}"
        ) from exc

    try:
        declaration = GameShardDeclaration.model_validate(payload)
    except ValidationError as exc:
        raise ShardExperienceConfigurationError(
            f"Invalid shard experience declaration at {declaration_path}: {exc}"
        ) from exc

    return declaration


def configured_shard_experience() -> PublicShardExperience:
    """Load the declaration selected by this process's shard settings."""

    return load_shard_experience(
        settings.shard_experience_path,
        shard_id=str(settings.shard_id or settings.city_id),
        shard_type=str(settings.shard_type),
    )


def configured_game_declaration() -> GameShardDeclaration | None:
    """Return this shard's validated game rules, or ``None`` for ordinary shards."""

    configured_path = str(settings.shard_experience_path or "").strip()
    if not configured_path:
        return None
    return load_game_declaration(configured_path)


def require_game_capabilities(*required: GameCapability) -> PublicShardExperience:
    """Fail closed unless this shard explicitly declares every capability."""

    experience = configured_shard_experience()
    active = {item.id for item in experience.entry_disclosure.capabilities}
    missing = [
        capability.value for capability in required if capability.value not in active
    ]
    if not experience.game_rules_active or missing:
        detail = ", ".join(missing or [capability.value for capability in required])
        raise GameCapabilityUnavailable(
            f"This shard has not enabled the required game capabilities: {detail}"
        )
    return experience
