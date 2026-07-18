# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""add durable objects and append-only consequence receipts

Revision ID: 5c1e7a9b3d20
Revises: 4f8a2c6d9e10
Create Date: 2026-07-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5c1e7a9b3d20"
down_revision: Union[str, None] = "4f8a2c6d9e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "durable_objects",
        sa.Column("object_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("object_kind", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("custodian_actor_id", sa.String(length=36), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("origin_shard_id", sa.String(length=80), nullable=False),
        sa.Column("created_by_actor_id", sa.String(length=36), nullable=False),
        sa.Column("provenance_kind", sa.String(length=40), nullable=False),
        sa.Column("provenance_ref", sa.String(length=120), nullable=True),
        sa.Column("provenance_event_id", sa.Integer(), nullable=True),
        sa.Column("properties_json", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(custodian_actor_id IS NOT NULL AND location IS NULL) OR " "(custodian_actor_id IS NULL AND location IS NOT NULL)",
            name="ck_durable_objects_one_attachment",
        ),
        sa.ForeignKeyConstraint(["provenance_event_id"], ["world_events.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("object_id"),
    )
    op.create_index("ix_durable_objects_provenance_event_id", "durable_objects", ["provenance_event_id"])
    op.create_index("ix_durable_objects_custodian_status", "durable_objects", ["custodian_actor_id", "status"])
    op.create_index("ix_durable_objects_location_status", "durable_objects", ["location", "status"])

    op.create_table(
        "consequence_receipts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("receipt_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("object_id", sa.String(length=36), nullable=False),
        sa.Column("world_event_id", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["object_id"], ["durable_objects.object_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["world_event_id"], ["world_events.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor_id", "idempotency_key", name="uq_consequence_receipts_actor_idempotency"),
        sa.UniqueConstraint("receipt_id"),
        sa.UniqueConstraint("world_event_id"),
    )
    op.create_index("ix_consequence_receipts_actor_id", "consequence_receipts", ["actor_id"])
    op.create_index("ix_consequence_receipts_object_created", "consequence_receipts", ["object_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_consequence_receipts_object_created", table_name="consequence_receipts")
    op.drop_index("ix_consequence_receipts_actor_id", table_name="consequence_receipts")
    op.drop_table("consequence_receipts")

    op.drop_index("ix_durable_objects_location_status", table_name="durable_objects")
    op.drop_index("ix_durable_objects_custodian_status", table_name="durable_objects")
    op.drop_index("ix_durable_objects_provenance_event_id", table_name="durable_objects")
    op.drop_table("durable_objects")
