# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""add accepted object exchanges

Revision ID: 8b5d0f3a2c71
Revises: 7a4c9e2d1f60
Create Date: 2026-07-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8b5d0f3a2c71"
down_revision: Union[str, None] = "7a4c9e2d1f60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "object_exchanges",
        sa.Column("exchange_id", sa.String(length=36), nullable=False),
        sa.Column("proposer_actor_id", sa.String(length=36), nullable=False),
        sa.Column("recipient_actor_id", sa.String(length=36), nullable=False),
        sa.Column("offered_object_id", sa.String(length=36), nullable=False),
        sa.Column("requested_object_id", sa.String(length=36), nullable=False),
        sa.Column("offered_object_revision", sa.Integer(), nullable=False),
        sa.Column("requested_object_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("offered_at_location", sa.String(length=200), nullable=False),
        sa.Column("completed_at_location", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'completed', 'declined', 'cancelled')",
            name="ck_object_exchanges_known_status",
        ),
        sa.CheckConstraint(
            "proposer_actor_id <> recipient_actor_id",
            name="ck_object_exchanges_distinct_actors",
        ),
        sa.CheckConstraint(
            "offered_object_id <> requested_object_id",
            name="ck_object_exchanges_distinct_objects",
        ),
        sa.ForeignKeyConstraint(
            ["offered_object_id"],
            ["durable_objects.object_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_object_id"],
            ["durable_objects.object_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("exchange_id"),
    )
    op.create_index(
        "ix_object_exchanges_proposer_status",
        "object_exchanges",
        ["proposer_actor_id", "status"],
    )
    op.create_index(
        "ix_object_exchanges_recipient_status",
        "object_exchanges",
        ["recipient_actor_id", "status"],
    )

    op.create_table(
        "exchange_receipts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("receipt_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("exchange_id", sa.String(length=36), nullable=False),
        sa.Column("world_event_id", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["exchange_id"],
            ["object_exchanges.exchange_id"],
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
            name="uq_exchange_receipts_actor_idempotency",
        ),
    )
    op.create_index(
        "ix_exchange_receipts_actor_id",
        "exchange_receipts",
        ["actor_id"],
    )
    op.create_index(
        "ix_exchange_receipts_exchange_created",
        "exchange_receipts",
        ["exchange_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_exchange_receipts_exchange_created", table_name="exchange_receipts")
    op.drop_index("ix_exchange_receipts_actor_id", table_name="exchange_receipts")
    op.drop_table("exchange_receipts")
    op.drop_index("ix_object_exchanges_recipient_status", table_name="object_exchanges")
    op.drop_index("ix_object_exchanges_proposer_status", table_name="object_exchanges")
    op.drop_table("object_exchanges")
