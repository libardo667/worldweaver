"""advertise human client URLs separately from shard APIs

Revision ID: b6e2a7d4c910
Revises: a4f7c2e9d1b6
Create Date: 2026-07-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b6e2a7d4c910"
down_revision: Union[str, None] = "a4f7c2e9d1b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "federation_shards",
        sa.Column("client_url", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "shard_travel_handoffs",
        sa.Column("destination_client_url", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shard_travel_handoffs", "destination_client_url")
    op.drop_column("federation_shards", "client_url")
