# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""add reclaimable object placement

Revision ID: a4f7c2e9d1b6
Revises: 9c6e1a4b3d82
Create Date: 2026-07-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a4f7c2e9d1b6"
down_revision: Union[str, None] = "9c6e1a4b3d82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "durable_objects",
        sa.Column("placed_by_actor_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_durable_objects_placed_by_status",
        "durable_objects",
        ["placed_by_actor_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_durable_objects_placed_by_status", table_name="durable_objects")
    op.drop_column("durable_objects", "placed_by_actor_id")
