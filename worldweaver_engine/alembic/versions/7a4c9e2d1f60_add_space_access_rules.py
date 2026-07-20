# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""add ordinary space access rules

Revision ID: 7a4c9e2d1f60
Revises: 6d2f8b4c1a30
Create Date: 2026-07-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7a4c9e2d1f60"
down_revision: Union[str, None] = "6d2f8b4c1a30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "space_access_policies",
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("controller_actor_id", sa.String(length=36), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "mode IN ('public', 'requestable', 'private', 'closed')",
            name="ck_space_access_policies_known_mode",
        ),
        sa.PrimaryKeyConstraint("location"),
    )
    op.create_index(
        "ix_space_access_policies_controller_actor_id",
        "space_access_policies",
        ["controller_actor_id"],
    )

    op.create_table(
        "space_access_grants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("granted_by_actor_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["location"], ["space_access_policies.location"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "location", "actor_id", name="uq_space_access_grants_location_actor"
        ),
    )
    op.create_index(
        "ix_space_access_grants_actor_active",
        "space_access_grants",
        ["actor_id", "active"],
    )

    op.create_table(
        "space_access_requests",
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("requester_actor_id", sa.String(length=36), nullable=False),
        sa.Column("requester_session_id", sa.String(length=64), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("resolved_by_actor_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'admitted', 'denied', 'withdrawn')",
            name="ck_space_access_requests_known_status",
        ),
        sa.ForeignKeyConstraint(
            ["location"], ["space_access_policies.location"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("request_id"),
    )
    op.create_index(
        "ix_space_access_requests_location_status",
        "space_access_requests",
        ["location", "status"],
    )
    op.create_index(
        "ix_space_access_requests_requester_actor_id",
        "space_access_requests",
        ["requester_actor_id"],
    )

    op.create_table(
        "space_access_receipts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("receipt_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("world_event_id", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["world_event_id"], ["world_events.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_id"),
        sa.UniqueConstraint("world_event_id"),
        sa.UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_space_access_receipts_actor_idempotency",
        ),
    )
    op.create_index(
        "ix_space_access_receipts_actor_id",
        "space_access_receipts",
        ["actor_id"],
    )
    op.create_index(
        "ix_space_access_receipts_location_created",
        "space_access_receipts",
        ["location", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_space_access_receipts_location_created", table_name="space_access_receipts"
    )
    op.drop_index(
        "ix_space_access_receipts_actor_id", table_name="space_access_receipts"
    )
    op.drop_table("space_access_receipts")
    op.drop_index(
        "ix_space_access_requests_requester_actor_id",
        table_name="space_access_requests",
    )
    op.drop_index(
        "ix_space_access_requests_location_status", table_name="space_access_requests"
    )
    op.drop_table("space_access_requests")
    op.drop_index(
        "ix_space_access_grants_actor_active", table_name="space_access_grants"
    )
    op.drop_table("space_access_grants")
    op.drop_index(
        "ix_space_access_policies_controller_actor_id",
        table_name="space_access_policies",
    )
    op.drop_table("space_access_policies")
