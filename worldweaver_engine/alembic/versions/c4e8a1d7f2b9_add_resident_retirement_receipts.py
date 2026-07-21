"""add resident session retirement receipts

Revision ID: c4e8a1d7f2b9
Revises: a9f4c2e7d1b6
Create Date: 2026-07-21 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8a1d7f2b9"
down_revision: Union[str, None] = "a9f4c2e7d1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resident_session_retirement_receipts",
        sa.Column("transition_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("runtime_generation", sa.Integer(), nullable=False),
        sa.Column("deleted_sessions", sa.Integer(), nullable=False),
        sa.Column("committed_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "deleted_sessions >= 0",
            name="ck_resident_retirement_receipts_deleted_sessions",
        ),
        sa.CheckConstraint(
            "runtime_generation >= 1",
            name="ck_resident_retirement_receipts_generation",
        ),
        sa.PrimaryKeyConstraint("transition_id"),
    )
    op.create_index(
        op.f("ix_resident_session_retirement_receipts_actor_id"),
        "resident_session_retirement_receipts",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resident_session_retirement_receipts_session_id"),
        "resident_session_retirement_receipts",
        ["session_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_resident_session_retirement_receipts_session_id"),
        table_name="resident_session_retirement_receipts",
    )
    op.drop_index(
        op.f("ix_resident_session_retirement_receipts_actor_id"),
        table_name="resident_session_retirement_receipts",
    )
    op.drop_table("resident_session_retirement_receipts")
