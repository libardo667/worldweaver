"""add runtime storylet provenance fields

Revision ID: f3a1c09b8d12
Revises: c6b7d30d1d77
Create Date: 2026-03-02 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3a1c09b8d12"
down_revision: Union[str, None] = "c6b7d30d1d77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("storylets") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source",
                sa.String(length=50),
                nullable=False,
                server_default="authored",
            )
        )
        batch_op.add_column(
            sa.Column("seed_event_ids", sa.JSON(), nullable=True)
        )
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("storylets") as batch_op:
        batch_op.drop_column("expires_at")
        batch_op.drop_column("seed_event_ids")
        batch_op.drop_column("source")
