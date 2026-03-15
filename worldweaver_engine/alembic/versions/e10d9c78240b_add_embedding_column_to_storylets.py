"""add embedding column to storylets

Revision ID: e10d9c78240b
Revises: b189ebeca4b5
Create Date: 2026-03-01 20:10:03.522627

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e10d9c78240b'
down_revision: Union[str, None] = 'b189ebeca4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("storylets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("embedding", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("storylets", schema=None) as batch_op:
        batch_op.drop_column("embedding")
