"""add auth player table and player_id on session_vars

Revision ID: a1b2c3d4e5f6
Revises: f3a1c09b8d12
Create Date: 2026-03-12 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "d9e3f1a2b4c5"
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

    # Use direct ADD COLUMN — SQLite supports this natively and avoids
    # the full table-rebuild that batch_alter_table does (which hangs on
    # Windows Docker bind mounts due to WAL file-lock semantics).
    op.add_column("session_vars", sa.Column("player_id", sa.String(36), nullable=True))


def downgrade() -> None:
    # SQLite doesn't support DROP COLUMN directly in older versions,
    # but alembic's batch_alter_table is fine for downgrade (less critical path).
    with op.batch_alter_table("session_vars") as batch_op:
        batch_op.drop_column("player_id")
    op.drop_index("ix_players_username", "players")
    op.drop_index("ix_players_email", "players")
    op.drop_table("players")
