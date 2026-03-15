"""add world graph tables

Revision ID: 9c7a6d5b4e31
Revises: 6e4df98f7250
Create Date: 2026-03-02 08:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c7a6d5b4e31"
down_revision: Union[str, None] = "6e4df98f7250"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "world_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("node_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "node_type", "normalized_name", name="uq_world_nodes_type_name"
        ),
    )

    op.create_table(
        "world_edges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_node_id", sa.Integer(), nullable=False),
        sa.Column("target_node_id", sa.Integer(), nullable=False),
        sa.Column("edge_type", sa.String(length=80), nullable=False),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_event_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["source_event_id"], ["world_events.id"]),
        sa.ForeignKeyConstraint(["source_node_id"], ["world_nodes.id"]),
        sa.ForeignKeyConstraint(["target_node_id"], ["world_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_node_id",
            "target_node_id",
            "edge_type",
            name="uq_world_edges_source_target_type",
        ),
    )

    op.create_table(
        "world_facts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("subject_node_id", sa.Integer(), nullable=False),
        sa.Column("location_node_id", sa.Integer(), nullable=True),
        sa.Column("predicate", sa.String(length=120), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column(
            "valid_from",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column("valid_to", sa.DateTime(), nullable=True),
        sa.Column("source_event_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["location_node_id"], ["world_nodes.id"]),
        sa.ForeignKeyConstraint(["source_event_id"], ["world_events.id"]),
        sa.ForeignKeyConstraint(["subject_node_id"], ["world_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_world_facts_session_id", "world_facts", ["session_id"])
    op.create_index("ix_world_facts_predicate", "world_facts", ["predicate"])
    op.create_index("ix_world_facts_subject", "world_facts", ["subject_node_id"])
    op.create_index("ix_world_facts_location", "world_facts", ["location_node_id"])


def downgrade() -> None:
    op.drop_index("ix_world_facts_location", table_name="world_facts")
    op.drop_index("ix_world_facts_subject", table_name="world_facts")
    op.drop_index("ix_world_facts_predicate", table_name="world_facts")
    op.drop_index("ix_world_facts_session_id", table_name="world_facts")
    op.drop_table("world_facts")
    op.drop_table("world_edges")
    op.drop_table("world_nodes")
