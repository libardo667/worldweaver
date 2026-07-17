"""carry stable travel hub ids through federation handoffs

Revision ID: 4f8a2c6d9e10
Revises: 8e2f5b0d3c71
Create Date: 2026-07-17 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4f8a2c6d9e10"
down_revision: Union[str, None] = "8e2f5b0d3c71"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("federation_travelers") as batch_op:
        batch_op.add_column(sa.Column("departure_hub_id", sa.String(80), nullable=True))
        batch_op.add_column(sa.Column("arrival_hub_id", sa.String(80), nullable=True))

    with op.batch_alter_table("shard_travel_handoffs") as batch_op:
        batch_op.add_column(sa.Column("departure_hub_id", sa.String(80), nullable=True))
        batch_op.add_column(sa.Column("arrival_hub_id", sa.String(80), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("shard_travel_handoffs") as batch_op:
        batch_op.drop_column("arrival_hub_id")
        batch_op.drop_column("departure_hub_id")

    with op.batch_alter_table("federation_travelers") as batch_op:
        batch_op.drop_column("arrival_hub_id")
        batch_op.drop_column("departure_hub_id")
