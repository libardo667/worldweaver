# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""drop obsolete narrative-source id from world events

Revision ID: 6a9d3e2f1b70
Revises: 2f6c8d1e4a90
Create Date: 2026-07-14 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "6a9d3e2f1b70"
down_revision: Union[str, None] = "2f6c8d1e4a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("world_events") as batch_op:
        batch_op.drop_column("storylet_id")


def downgrade() -> None:
    with op.batch_alter_table("world_events") as batch_op:
        batch_op.add_column(sa.Column("storylet_id", sa.Integer(), nullable=True))
