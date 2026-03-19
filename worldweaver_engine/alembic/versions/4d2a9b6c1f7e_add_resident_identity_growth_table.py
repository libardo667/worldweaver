"""add resident identity growth table

Revision ID: 4d2a9b6c1f7e
Revises: f3a1c09b8d12
Create Date: 2026-03-18 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d2a9b6c1f7e"
down_revision: Union[str, None] = "f3a1c09b8d12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("resident_identity_growth"):
        return
    op.create_table(
        "resident_identity_growth",
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("growth_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("growth_metadata", sa.JSON(), nullable=True),
        sa.Column("note_records", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("actor_id"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("resident_identity_growth"):
        return
    op.drop_table("resident_identity_growth")
