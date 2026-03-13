"""add doula_polls table

Revision ID: a7b3c2d1e9f0
Revises: f3a1c09b8d12
Create Date: 2026-03-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a7b3c2d1e9f0"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doula_polls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("candidate_name", sa.String(200), nullable=False, index=True),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("entry_location", sa.String(200), nullable=True),
        sa.Column("entity_class", sa.String(50), nullable=False),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("voters_json", sa.JSON(), nullable=True),
        sa.Column("votes_json", sa.JSON(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("doula_polls")
