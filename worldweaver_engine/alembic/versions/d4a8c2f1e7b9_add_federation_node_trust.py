"""add explicit federation node admission and trust history

Revision ID: d4a8c2f1e7b9
Revises: c7a19d4e2b61
Create Date: 2026-07-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a8c2f1e7b9"
down_revision: Union[str, None] = "c7a19d4e2b61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "federation_shards",
        sa.Column(
            "admission_state",
            sa.String(length=20),
            server_default="approved",
            nullable=False,
        ),
    )
    op.add_column(
        "federation_shards", sa.Column("admitted_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "federation_shards", sa.Column("revoked_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "federation_shards",
        sa.Column("revocation_reason", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "federation_shards", sa.Column("key_recovered_at", sa.DateTime(), nullable=True)
    )
    op.execute(
        "UPDATE federation_shards SET admitted_at = COALESCE(identity_bound_at, registered_at, CURRENT_TIMESTAMP)"
    )
    op.create_table(
        "federation_node_trust_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("node_id", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("previous_public_key", sa.String(length=80), nullable=True),
        sa.Column("public_key", sa.String(length=80), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_federation_node_trust_events_node_id"),
        "federation_node_trust_events",
        ["node_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_federation_node_trust_events_created_at"),
        "federation_node_trust_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_federation_node_trust_events_created_at"),
        table_name="federation_node_trust_events",
    )
    op.drop_index(
        op.f("ix_federation_node_trust_events_node_id"),
        table_name="federation_node_trust_events",
    )
    op.drop_table("federation_node_trust_events")
    op.drop_column("federation_shards", "key_recovered_at")
    op.drop_column("federation_shards", "revocation_reason")
    op.drop_column("federation_shards", "revoked_at")
    op.drop_column("federation_shards", "admitted_at")
    op.drop_column("federation_shards", "admission_state")
