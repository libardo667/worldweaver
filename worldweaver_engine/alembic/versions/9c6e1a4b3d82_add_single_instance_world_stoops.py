# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""add single instance world stoops

Revision ID: 9c6e1a4b3d82
Revises: 8b5d0f3a2c71
Create Date: 2026-07-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9c6e1a4b3d82"
down_revision: Union[str, None] = "8b5d0f3a2c71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "world_stoops",
        sa.Column("stoop_id", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("prompt", sa.String(length=500), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "capacity > 0 AND capacity <= 50",
            name="ck_world_stoops_bounded_capacity",
        ),
        sa.PrimaryKeyConstraint("stoop_id"),
    )
    op.create_index("ix_world_stoops_location", "world_stoops", ["location"])

    op.create_table(
        "stoop_object_entries",
        sa.Column("entry_id", sa.String(length=36), nullable=False),
        sa.Column("stoop_id", sa.String(length=80), nullable=False),
        sa.Column("object_id", sa.String(length=36), nullable=False),
        sa.Column("left_by_actor_id", sa.String(length=36), nullable=False),
        sa.Column("taken_by_actor_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("object_revision_at_leave", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'taken', 'withdrawn')",
            name="ck_stoop_object_entries_known_status",
        ),
        sa.ForeignKeyConstraint(
            ["object_id"],
            ["durable_objects.object_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["stoop_id"],
            ["world_stoops.stoop_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("entry_id"),
    )
    op.create_index(
        "ix_stoop_object_entries_object_status",
        "stoop_object_entries",
        ["object_id", "status"],
    )
    op.create_index(
        "ix_stoop_object_entries_stoop_status",
        "stoop_object_entries",
        ["stoop_id", "status"],
    )

    op.create_table(
        "stoop_receipts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("receipt_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("entry_id", sa.String(length=36), nullable=False),
        sa.Column("world_event_id", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["entry_id"],
            ["stoop_object_entries.entry_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["world_event_id"],
            ["world_events.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_id"),
        sa.UniqueConstraint("world_event_id"),
        sa.UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_stoop_receipts_actor_idempotency",
        ),
    )
    op.create_index("ix_stoop_receipts_actor_id", "stoop_receipts", ["actor_id"])
    op.create_index(
        "ix_stoop_receipts_entry_created",
        "stoop_receipts",
        ["entry_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_stoop_receipts_entry_created", table_name="stoop_receipts")
    op.drop_index("ix_stoop_receipts_actor_id", table_name="stoop_receipts")
    op.drop_table("stoop_receipts")
    op.drop_index("ix_stoop_object_entries_stoop_status", table_name="stoop_object_entries")
    op.drop_index("ix_stoop_object_entries_object_status", table_name="stoop_object_entries")
    op.drop_table("stoop_object_entries")
    op.drop_index("ix_world_stoops_location", table_name="world_stoops")
    op.drop_table("world_stoops")
