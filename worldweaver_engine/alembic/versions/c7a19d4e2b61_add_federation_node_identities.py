"""add federation node identities and replay guards

Revision ID: c7a19d4e2b61
Revises: b6e2a7d4c910
Create Date: 2026-07-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7a19d4e2b61"
down_revision: Union[str, None] = "b6e2a7d4c910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "federation_shards",
        sa.Column("public_key", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "federation_shards",
        sa.Column("identity_bound_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "federation_request_nonces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("node_id", sa.String(length=80), nullable=False),
        sa.Column("nonce", sa.String(length=80), nullable=False),
        sa.Column("signed_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("node_id", "nonce", name="uq_federation_request_node_nonce"),
    )
    op.create_index(
        op.f("ix_federation_request_nonces_node_id"),
        "federation_request_nonces",
        ["node_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_federation_request_nonces_received_at"),
        "federation_request_nonces",
        ["received_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_federation_request_nonces_received_at"),
        table_name="federation_request_nonces",
    )
    op.drop_index(
        op.f("ix_federation_request_nonces_node_id"),
        table_name="federation_request_nonces",
    )
    op.drop_table("federation_request_nonces")
    op.drop_column("federation_shards", "identity_bound_at")
    op.drop_column("federation_shards", "public_key")
