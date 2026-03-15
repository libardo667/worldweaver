"""add federation tables

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-03-14 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "federation_shards",
        sa.Column("shard_id", sa.String(80), primary_key=True),
        sa.Column("shard_url", sa.String(255), nullable=False),
        sa.Column("shard_type", sa.String(20), nullable=False, server_default="city"),
        sa.Column("city_id", sa.String(80), nullable=True),
        sa.Column("last_pulse_ts", sa.DateTime(), nullable=True),
        sa.Column("last_pulse_seq", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("registered_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "federation_residents",
        sa.Column("resident_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, index=True),
        sa.Column("home_shard", sa.String(80), nullable=False),
        sa.Column("current_shard", sa.String(80), nullable=False),
        sa.Column("last_location", sa.String(200), nullable=True),
        sa.Column("last_act_ts", sa.DateTime(), nullable=True),
        sa.Column("resident_type", sa.String(20), nullable=False, server_default="agent"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "federation_travelers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("resident_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("from_shard", sa.String(80), nullable=False),
        sa.Column("to_shard", sa.String(80), nullable=False),
        sa.Column("departed_ts", sa.DateTime(), nullable=True),
        sa.Column("arrived_ts", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "federation_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("from_resident_id", sa.String(36), nullable=False),
        sa.Column("from_shard", sa.String(80), nullable=False),
        sa.Column("to_resident_id", sa.String(36), nullable=False, index=True),
        sa.Column("to_shard", sa.String(80), nullable=False, index=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("federation_messages")
    op.drop_table("federation_travelers")
    op.drop_table("federation_residents")
    op.drop_table("federation_shards")
