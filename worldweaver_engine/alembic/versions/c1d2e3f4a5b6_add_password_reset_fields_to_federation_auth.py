"""add password reset fields to federation auth

Revision ID: c1d2e3f4a5b6
Revises: a7b4e1c2d9f0
Create Date: 2026-03-20 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "a7b4e1c2d9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("federation_actor_auth")}
    if "password_reset_token_hash" not in columns:
        op.add_column(
            "federation_actor_auth",
            sa.Column("password_reset_token_hash", sa.String(length=128), nullable=True),
        )
    if "password_reset_expires_at" not in columns:
        op.add_column(
            "federation_actor_auth",
            sa.Column("password_reset_expires_at", sa.DateTime(), nullable=True),
        )
    if "password_reset_requested_at" not in columns:
        op.add_column(
            "federation_actor_auth",
            sa.Column("password_reset_requested_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("federation_actor_auth")}
    if "password_reset_requested_at" in columns:
        op.drop_column("federation_actor_auth", "password_reset_requested_at")
    if "password_reset_expires_at" in columns:
        op.drop_column("federation_actor_auth", "password_reset_expires_at")
    if "password_reset_token_hash" in columns:
        op.drop_column("federation_actor_auth", "password_reset_token_hash")
