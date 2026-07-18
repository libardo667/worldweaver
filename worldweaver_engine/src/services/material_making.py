# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Replenishing non-essential materials and atomic recipe-based making."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import DurableObject, MaterialPool
from .consequence_objects import (
    ConsequenceDomainError,
    ConsequenceResult,
    _actor_context,
    _complete_consequence,
    _existing_receipt,
    _idempotency_key,
    _recover_duplicate,
    _require_capabilities,
    _result_from_receipt,
)
from .federation_identity import current_shard_id
from .shard_experience import (
    GameCapability,
    GameShardDeclaration,
    MaterialSourceDeclaration,
    RecipeDeclaration,
    configured_game_declaration,
)


def _utc_naive(value: datetime | None = None) -> datetime:
    resolved = value or datetime.now(timezone.utc)
    if resolved.tzinfo is not None:
        return resolved.astimezone(timezone.utc).replace(tzinfo=None)
    return resolved


def _active_declaration(*capabilities: GameCapability) -> GameShardDeclaration:
    _require_capabilities(*capabilities)
    declaration = configured_game_declaration()
    if declaration is None:
        raise ConsequenceDomainError("game_rules_unavailable", "No game ruleset is active on this shard.", status_code=403)
    return declaration


def _material_configuration(material: MaterialSourceDeclaration) -> dict[str, int | str]:
    return {
        "title": material.title,
        "capacity_units": material.capacity_units,
        "starting_units": material.starting_units,
        "replenish_units": material.replenish_units,
        "replenish_every_seconds": material.replenish_every_seconds,
    }


def initialize_material_pools(db: Session, *, now: datetime | None = None) -> list[MaterialPool]:
    """Idempotently found the pools named by the active versioned ruleset."""

    declaration = _active_declaration(GameCapability.REPLENISHING_MATERIALS)
    ruleset = declaration.ruleset
    initialized_at = _utc_naive(now)
    rows: list[MaterialPool] = []
    try:
        for material in declaration.materials:
            expected = _material_configuration(material)
            for location in material.available_at:
                row = (
                    db.query(MaterialPool)
                    .filter(
                        MaterialPool.ruleset_id == ruleset.id,
                        MaterialPool.ruleset_version == ruleset.version,
                        MaterialPool.material_id == material.id,
                        MaterialPool.location == location,
                    )
                    .one_or_none()
                )
                if row is None:
                    row = MaterialPool(
                        ruleset_id=ruleset.id,
                        ruleset_version=ruleset.version,
                        material_id=material.id,
                        title=material.title,
                        location=location,
                        capacity_units=material.capacity_units,
                        starting_units=material.starting_units,
                        available_units=material.starting_units,
                        replenish_units=material.replenish_units,
                        replenish_every_seconds=material.replenish_every_seconds,
                        last_replenished_at=initialized_at,
                    )
                    db.add(row)
                    db.flush()
                else:
                    actual = {
                        "title": str(row.title),
                        "capacity_units": int(row.capacity_units),
                        "starting_units": int(row.starting_units),
                        "replenish_units": int(row.replenish_units),
                        "replenish_every_seconds": int(row.replenish_every_seconds),
                    }
                    if actual != expected:
                        raise ConsequenceDomainError(
                            "ruleset_migration_required",
                            f"Material {material.id} at {location} changed without a new ruleset version.",
                        )
                rows.append(row)
        db.commit()
        for row in rows:
            db.refresh(row)
        return rows
    except Exception:
        db.rollback()
        raise


def _effective_pool_state(row: MaterialPool, *, now: datetime) -> tuple[int, datetime]:
    last = _utc_naive(row.last_replenished_at)
    elapsed_seconds = max(0.0, (now - last).total_seconds())
    periods = int(elapsed_seconds // int(row.replenish_every_seconds))
    if periods <= 0:
        return int(row.available_units), last
    available = min(
        int(row.capacity_units),
        int(row.available_units) + periods * int(row.replenish_units),
    )
    advanced = last + timedelta(seconds=periods * int(row.replenish_every_seconds))
    return available, advanced


def _material_payload(
    row: MaterialPool,
    declaration: MaterialSourceDeclaration,
    *,
    now: datetime,
) -> dict[str, Any]:
    available, _ = _effective_pool_state(row, now=now)
    return {
        "material_id": str(row.material_id),
        "title": declaration.title,
        "description": declaration.description,
        "location": str(row.location),
        "available_units": available,
        "capacity_units": int(row.capacity_units),
        "replenishes": True,
        "replenish_units": int(row.replenish_units),
        "replenish_every_seconds": int(row.replenish_every_seconds),
        "essential": False,
        "used_for_resident_need": False,
    }


def _ruleset_pools(
    db: Session,
    declaration: GameShardDeclaration,
    *,
    location: str,
    lock: bool = False,
) -> dict[str, MaterialPool]:
    query = db.query(MaterialPool).filter(
        MaterialPool.ruleset_id == declaration.ruleset.id,
        MaterialPool.ruleset_version == declaration.ruleset.version,
        MaterialPool.location == location,
    )
    if lock:
        query = query.order_by(MaterialPool.material_id.asc()).with_for_update()
    rows = query.all()
    return {str(row.material_id): row for row in rows}


def _recipe_at_location(
    declaration: GameShardDeclaration,
    *,
    recipe_id: str,
    location: str,
) -> RecipeDeclaration:
    normalized = str(recipe_id or "").strip()
    recipe = next((item for item in declaration.recipes if item.id == normalized), None)
    if recipe is None:
        raise ConsequenceDomainError("recipe_not_found", "Recipe not found.", status_code=404)
    if location not in recipe.available_at:
        raise ConsequenceDomainError("recipe_not_available_here", "That recipe is not available at this exact location.")
    return recipe


def making_catalog(db: Session, *, session_id: str, now: datetime | None = None) -> dict[str, Any]:
    """Return elective local recipes and current effective material availability."""

    declaration = _active_declaration(
        GameCapability.DURABLE_OBJECTS,
        GameCapability.CUSTODY,
        GameCapability.REPLENISHING_MATERIALS,
        GameCapability.MAKING,
    )
    context = _actor_context(db, session_id)
    initialize_material_pools(db, now=now)
    checked_at = _utc_naive(now)
    material_by_id = {material.id: material for material in declaration.materials}
    pools = _ruleset_pools(db, declaration, location=context.location)
    materials = [_material_payload(pool, material_by_id[material_id], now=checked_at) for material_id, pool in sorted(pools.items()) if material_id in material_by_id]
    availability = {item["material_id"]: int(item["available_units"]) for item in materials}
    recipes = []
    for recipe in declaration.recipes:
        if context.location not in recipe.available_at:
            continue
        missing = {material_id: max(0, units - availability.get(material_id, 0)) for material_id, units in recipe.inputs.items()}
        missing = {material_id: units for material_id, units in missing.items() if units > 0}
        recipes.append(
            {
                "recipe_id": recipe.id,
                "title": recipe.title,
                "description": recipe.description,
                "inputs": dict(recipe.inputs),
                "output": recipe.output.model_dump(mode="json"),
                "can_make": not missing,
                "missing_units": missing,
            }
        )
    return {
        "ruleset": declaration.ruleset.model_dump(mode="json"),
        "location": context.location,
        "materials": materials,
        "recipes": recipes,
    }


def make_durable_object(
    db: Session,
    *,
    session_id: str,
    recipe_id: str,
    idempotency_key: str,
    now: datetime | None = None,
) -> ConsequenceResult:
    """Consume replenishing materials and create one object in one transaction."""

    declaration = _active_declaration(
        GameCapability.DURABLE_OBJECTS,
        GameCapability.CUSTODY,
        GameCapability.REPLENISHING_MATERIALS,
        GameCapability.MAKING,
    )
    context = _actor_context(db, session_id)
    key = _idempotency_key(idempotency_key)
    existing = _existing_receipt(
        db,
        actor_id=context.actor_id,
        idempotency_key=key,
        operation="object_made",
    )
    if existing is not None:
        return _result_from_receipt(existing, replayed=True)
    recipe = _recipe_at_location(declaration, recipe_id=recipe_id, location=context.location)
    initialize_material_pools(db, now=now)
    made_at = _utc_naive(now)

    try:
        pools = _ruleset_pools(db, declaration, location=context.location, lock=True)
        existing = _existing_receipt(
            db,
            actor_id=context.actor_id,
            idempotency_key=key,
            operation="object_made",
        )
        if existing is not None:
            return _result_from_receipt(existing, replayed=True)

        material_changes: dict[str, dict[str, int]] = {}
        for material_id, units in recipe.inputs.items():
            pool = pools.get(material_id)
            if pool is None:
                raise ConsequenceDomainError("material_pool_missing", f"Material pool {material_id} is not initialized here.")
            effective, advanced_at = _effective_pool_state(pool, now=made_at)
            if effective < units:
                raise ConsequenceDomainError(
                    "insufficient_materials",
                    f"Recipe {recipe.id} needs {units} units of {material_id}, but only {effective} are available.",
                )
            pool.available_units = effective - units
            pool.last_replenished_at = advanced_at
            material_changes[material_id] = {
                "before_units": effective,
                "consumed_units": int(units),
                "after_units": effective - int(units),
            }

        output = recipe.output
        object_row = DurableObject(
            name=output.name,
            description=output.description,
            object_kind=output.object_kind,
            status="active",
            custodian_actor_id=context.actor_id,
            location=None,
            origin_shard_id=current_shard_id(),
            created_by_actor_id=context.actor_id,
            provenance_kind="recipe",
            provenance_ref=f"{declaration.ruleset.id}@{declaration.ruleset.version}:{recipe.id}",
            properties_json=dict(output.properties),
            revision=1,
        )
        db.add(object_row)
        return _complete_consequence(
            db,
            context=context,
            idempotency_key=key,
            operation="object_made",
            object_row=object_row,
            before=None,
            summary=f"{output.name} is made at {context.location}.",
            details={
                "recipe_id": recipe.id,
                "ruleset_id": declaration.ruleset.id,
                "ruleset_version": declaration.ruleset.version,
                "location": context.location,
                "materials": material_changes,
            },
            provenance_event=True,
        )
    except IntegrityError:
        return _recover_duplicate(
            db,
            context=context,
            idempotency_key=key,
            operation="object_made",
        )
    except Exception:
        db.rollback()
        raise
