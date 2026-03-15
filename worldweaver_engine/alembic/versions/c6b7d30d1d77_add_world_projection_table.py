"""add world_projection table

Revision ID: c6b7d30d1d77
Revises: 9c7a6d5b4e31
Create Date: 2026-03-02 10:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c6b7d30d1d77"
down_revision: Union[str, None] = "9c7a6d5b4e31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "world_projection",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_event_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["source_event_id"], ["world_events.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path", name="uq_world_projection_path"),
    )
    op.create_index("ix_world_projection_path", "world_projection", ["path"])
    op.create_index("ix_world_projection_source_event", "world_projection", ["source_event_id"])


def downgrade() -> None:
    op.drop_index("ix_world_projection_source_event", table_name="world_projection")
    op.drop_index("ix_world_projection_path", table_name="world_projection")
    op.drop_table("world_projection")
