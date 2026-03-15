"""add storylet effects column

Revision ID: a4d2b9c7e1f0
Revises: f3a1c09b8d12
Create Date: 2026-03-05 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4d2b9c7e1f0"
down_revision: Union[str, None] = "f3a1c09b8d12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("storylets") as batch_op:
        batch_op.add_column(sa.Column("effects", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("storylets") as batch_op:
        batch_op.drop_column("effects")
