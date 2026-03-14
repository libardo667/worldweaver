"""add direct_messages table

Revision ID: b1c2d3e4f5a6
Revises: a7b3c2d1e9f0
Create Date: 2026-03-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a7b3c2d1e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "direct_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("from_name", sa.String(60), nullable=False),
        sa.Column("from_session_id", sa.String(64), nullable=True, index=True),
        sa.Column("to_name", sa.String(64), nullable=False, index=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), server_default=sa.func.now(), index=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("direct_messages")
