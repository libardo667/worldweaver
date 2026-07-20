"""formalize federation travel lifecycle

Revision ID: 7d1e4a9c2b60
Revises: 6a9d3e2f1b70
Create Date: 2026-07-17 00:00:00.000000

"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7d1e4a9c2b60"
down_revision: Union[str, None] = "6a9d3e2f1b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("federation_travelers") as batch_op:
        batch_op.add_column(sa.Column("travel_id", sa.String(64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "actor_type", sa.String(20), nullable=False, server_default="agent"
            )
        )
        batch_op.add_column(
            sa.Column(
                "status", sa.String(20), nullable=False, server_default="departing"
            )
        )
        batch_op.add_column(sa.Column("departure_hub", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("arrival_hub", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("reason", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("requested_ts", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))

    travelers = sa.table(
        "federation_travelers",
        sa.column("id", sa.Integer()),
        sa.column("travel_id", sa.String()),
        sa.column("status", sa.String()),
        sa.column("requested_ts", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
        sa.column("departed_ts", sa.DateTime()),
        sa.column("arrived_ts", sa.DateTime()),
    )
    connection = op.get_bind()
    now = datetime.now(timezone.utc)
    for row in connection.execute(
        sa.select(travelers.c.id, travelers.c.departed_ts, travelers.c.arrived_ts)
    ):
        status = (
            "arrived"
            if row.arrived_ts is not None
            else "traveling" if row.departed_ts is not None else "departing"
        )
        requested_at = row.departed_ts or now
        connection.execute(
            travelers.update()
            .where(travelers.c.id == row.id)
            .values(
                travel_id=f"legacy-{row.id}",
                status=status,
                requested_ts=requested_at,
                updated_at=now,
            )
        )

    with op.batch_alter_table("federation_travelers") as batch_op:
        batch_op.alter_column("travel_id", existing_type=sa.String(64), nullable=False)
        batch_op.alter_column(
            "requested_ts",
            existing_type=sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(),
            nullable=True,
            server_default=sa.func.now(),
        )
        batch_op.create_index(
            "ix_federation_travelers_travel_id", ["travel_id"], unique=True
        )


def downgrade() -> None:
    with op.batch_alter_table("federation_travelers") as batch_op:
        batch_op.drop_index("ix_federation_travelers_travel_id")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("requested_ts")
        batch_op.drop_column("reason")
        batch_op.drop_column("arrival_hub")
        batch_op.drop_column("departure_hub")
        batch_op.drop_column("status")
        batch_op.drop_column("actor_type")
        batch_op.drop_column("travel_id")
