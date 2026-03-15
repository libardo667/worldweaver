"""add location_chat table

Revision ID: d9e3f1a2b4c5
Revises: a4d2b9c7e1f0
Create Date: 2026-03-10 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d9e3f1a2b4c5"
down_revision: Union[str, None] = "a4d2b9c7e1f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "location_chat",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_location_chat_location", "location_chat", ["location"])
    op.create_index("ix_location_chat_created_at", "location_chat", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_location_chat_created_at", table_name="location_chat")
    op.drop_index("ix_location_chat_location", table_name="location_chat")
    op.drop_table("location_chat")
