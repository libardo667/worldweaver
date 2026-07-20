# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""add the local expiring world-trace store

Revision ID: 2f6c8d1e4a90
Revises: e8b3a6d2f1c9
Create Date: 2026-07-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "2f6c8d1e4a90"
down_revision: Union[str, None] = "e8b3a6d2f1c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "world_traces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("author_name", sa.String(length=200), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("target", sa.String(length=200), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_world_traces_session_id", "world_traces", ["session_id"])
    op.create_index("ix_world_traces_location", "world_traces", ["location"])
    op.create_index("ix_world_traces_expires_at", "world_traces", ["expires_at"])
    op.create_index(
        "ix_world_traces_location_expires_at",
        "world_traces",
        ["location", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_world_traces_location_expires_at", table_name="world_traces")
    op.drop_index("ix_world_traces_expires_at", table_name="world_traces")
    op.drop_index("ix_world_traces_location", table_name="world_traces")
    op.drop_index("ix_world_traces_session_id", table_name="world_traces")
    op.drop_table("world_traces")
