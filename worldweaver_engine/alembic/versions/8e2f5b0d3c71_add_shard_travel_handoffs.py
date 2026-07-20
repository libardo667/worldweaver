"""add node-local travel handoff recovery

Revision ID: 8e2f5b0d3c71
Revises: 7d1e4a9c2b60
Create Date: 2026-07-17 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8e2f5b0d3c71"
down_revision: Union[str, None] = "7d1e4a9c2b60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shard_travel_handoffs",
        sa.Column("travel_id", sa.String(64), primary_key=True),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("owner_player_id", sa.String(36), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("source_shard", sa.String(80), nullable=False),
        sa.Column("destination_shard", sa.String(80), nullable=False),
        sa.Column("destination_url", sa.String(255), nullable=True),
        sa.Column("route_id", sa.String(80), nullable=True),
        sa.Column("departure_hub", sa.String(200), nullable=True),
        sa.Column("arrival_hub", sa.String(200), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="prepared"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_shard_travel_handoffs_actor_id", "shard_travel_handoffs", ["actor_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shard_travel_handoffs_actor_id", table_name="shard_travel_handoffs"
    )
    op.drop_table("shard_travel_handoffs")
