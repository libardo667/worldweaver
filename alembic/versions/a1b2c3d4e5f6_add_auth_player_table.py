"""add auth player table and player_id on session_vars

Revision ID: a1b2c3d4e5f6
Revises: f3a1c09b8d12
Create Date: 2026-03-12 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f3a1c09b8d12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "players",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("username", sa.String(40), nullable=False, unique=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("pass_type", sa.String(20), nullable=False, server_default="visitor_7day"),
        sa.Column("pass_expires_at", sa.DateTime, nullable=True),
        sa.Column("terms_accepted_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_players_email", "players", ["email"])
    op.create_index("ix_players_username", "players", ["username"])

    with op.batch_alter_table("session_vars") as batch_op:
        batch_op.add_column(
            sa.Column("player_id", sa.String(36), sa.ForeignKey("players.id"), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("session_vars") as batch_op:
        batch_op.drop_column("player_id")
    op.drop_index("ix_players_username", "players")
    op.drop_index("ix_players_email", "players")
    op.drop_table("players")
