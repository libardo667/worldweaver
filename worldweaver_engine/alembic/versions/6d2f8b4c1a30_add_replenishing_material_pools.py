# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""add replenishing material pools

Revision ID: 6d2f8b4c1a30
Revises: 5c1e7a9b3d20
Create Date: 2026-07-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "6d2f8b4c1a30"
down_revision: Union[str, None] = "5c1e7a9b3d20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "material_pools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ruleset_id", sa.String(length=80), nullable=False),
        sa.Column("ruleset_version", sa.String(length=40), nullable=False),
        sa.Column("material_id", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("capacity_units", sa.Integer(), nullable=False),
        sa.Column("starting_units", sa.Integer(), nullable=False),
        sa.Column("available_units", sa.Integer(), nullable=False),
        sa.Column("replenish_units", sa.Integer(), nullable=False),
        sa.Column("replenish_every_seconds", sa.Integer(), nullable=False),
        sa.Column("last_replenished_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("capacity_units > 0", name="ck_material_pools_positive_capacity"),
        sa.CheckConstraint(
            "available_units >= 0 AND available_units <= capacity_units",
            name="ck_material_pools_bounded_available",
        ),
        sa.CheckConstraint(
            "replenish_units > 0 AND replenish_every_seconds > 0",
            name="ck_material_pools_positive_replenishment",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ruleset_id",
            "ruleset_version",
            "material_id",
            "location",
            name="uq_material_pools_ruleset_material_location",
        ),
    )
    op.create_index(
        "ix_material_pools_ruleset_location",
        "material_pools",
        ["ruleset_id", "ruleset_version", "location"],
    )


def downgrade() -> None:
    op.drop_index("ix_material_pools_ruleset_location", table_name="material_pools")
    op.drop_table("material_pools")
