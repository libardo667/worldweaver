"""add email verification

Revision ID: a6d3f8b1c5e2
Revises: f4a7c2d9e5b1
Create Date: 2026-07-19 19:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a6d3f8b1c5e2"
down_revision: Union[str, None] = "f4a7c2d9e5b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("federation_actor_auth", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    op.add_column("federation_actor_auth", sa.Column("email_verification_token_hash", sa.String(length=128), nullable=True))
    op.add_column("federation_actor_auth", sa.Column("email_verification_expires_at", sa.DateTime(), nullable=True))
    op.add_column("federation_actor_auth", sa.Column("email_verification_sent_at", sa.DateTime(), nullable=True))
    op.add_column("players", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    op.execute("UPDATE federation_actor_auth SET email_verified_at = CURRENT_TIMESTAMP WHERE email_verified_at IS NULL")
    op.execute("UPDATE players SET email_verified_at = CURRENT_TIMESTAMP WHERE email_verified_at IS NULL")


def downgrade() -> None:
    op.drop_column("players", "email_verified_at")
    op.drop_column("federation_actor_auth", "email_verification_sent_at")
    op.drop_column("federation_actor_auth", "email_verification_expires_at")
    op.drop_column("federation_actor_auth", "email_verification_token_hash")
    op.drop_column("federation_actor_auth", "email_verified_at")
