"""add account profile completion

Revision ID: f4a7c2d9e5b1
Revises: e2f6a1c9d4b7
Create Date: 2026-07-19 18:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f4a7c2d9e5b1"
down_revision: Union[str, None] = "e2f6a1c9d4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("federation_actor_auth", sa.Column("profile_completed_at", sa.DateTime(), nullable=True))
    op.add_column("players", sa.Column("profile_completed_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE federation_actor_auth SET profile_completed_at = CURRENT_TIMESTAMP WHERE profile_completed_at IS NULL")
    op.execute("UPDATE players SET profile_completed_at = CURRENT_TIMESTAMP WHERE profile_completed_at IS NULL")


def downgrade() -> None:
    op.drop_column("players", "profile_completed_at")
    op.drop_column("federation_actor_auth", "profile_completed_at")
