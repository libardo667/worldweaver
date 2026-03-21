"""add guild quest activity log

Revision ID: a7b4e1c2d9f0
Revises: f2a4d9c6b7e1
Create Date: 2026-03-20 10:34:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7b4e1c2d9f0"
down_revision = "f2a4d9c6b7e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_quests",
        sa.Column("activity_log", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guild_quests", "activity_log")
