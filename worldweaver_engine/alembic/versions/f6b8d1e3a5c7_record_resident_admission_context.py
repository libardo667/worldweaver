"""record resident admission context

Revision ID: f6b8d1e3a5c7
Revises: e5a7c3d9b1f2
Create Date: 2026-07-20 17:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6b8d1e3a5c7"
down_revision: Union[str, None] = "e5a7c3d9b1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("resident_authorities") as batch_op:
        batch_op.add_column(
            sa.Column(
                "admission_reason",
                sa.String(length=500),
                server_default="",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "admitted_by",
                sa.String(length=80),
                server_default="internal",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("resident_authorities") as batch_op:
        batch_op.drop_column("admitted_by")
        batch_op.drop_column("admission_reason")
