"""add guild feedback and adaptation tables

Revision ID: e4f9c2a1b6d7
Revises: b7c1d2e3f4a5
Create Date: 2026-03-20 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f9c2a1b6d7"
down_revision: Union[str, None] = "b7c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("guild_member_profiles"):
        op.create_table(
            "guild_member_profiles",
            sa.Column("actor_id", sa.String(length=36), nullable=False),
            sa.Column("member_type", sa.String(length=20), nullable=False, server_default="resident"),
            sa.Column("rank", sa.String(length=32), nullable=False, server_default="apprentice"),
            sa.Column("branches", sa.JSON(), nullable=True),
            sa.Column("mentor_actor_ids", sa.JSON(), nullable=True),
            sa.Column("quest_band", sa.String(length=32), nullable=False, server_default="foundations"),
            sa.Column("review_status", sa.JSON(), nullable=True),
            sa.Column("environment_guidance", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("actor_id"),
        )

    if not inspector.has_table("social_feedback_events"):
        op.create_table(
            "social_feedback_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("target_actor_id", sa.String(length=36), nullable=False),
            sa.Column("source_actor_id", sa.String(length=36), nullable=True),
            sa.Column("source_system", sa.String(length=80), nullable=True),
            sa.Column("feedback_mode", sa.String(length=20), nullable=False, server_default="inferred"),
            sa.Column("channel", sa.String(length=40), nullable=False, server_default="system"),
            sa.Column("dimension_scores", sa.JSON(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("evidence_refs", sa.JSON(), nullable=True),
            sa.Column("branch_hint", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        )
        op.create_index("ix_social_feedback_events_target_actor_id", "social_feedback_events", ["target_actor_id"])
        op.create_index("ix_social_feedback_events_source_actor_id", "social_feedback_events", ["source_actor_id"])
        op.create_index("ix_social_feedback_events_created_at", "social_feedback_events", ["created_at"])

    if not inspector.has_table("runtime_adaptation_states"):
        op.create_table(
            "runtime_adaptation_states",
            sa.Column("actor_id", sa.String(length=36), nullable=False),
            sa.Column("behavior_knobs", sa.JSON(), nullable=True),
            sa.Column("environment_guidance", sa.JSON(), nullable=True),
            sa.Column("source_feedback_ids", sa.JSON(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("actor_id"),
        )

    resident_columns = {column["name"] for column in inspector.get_columns("resident_identity_growth")}
    if "growth_proposals" not in resident_columns:
        op.add_column(
            "resident_identity_growth",
            sa.Column("growth_proposals", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    resident_columns = {column["name"] for column in inspector.get_columns("resident_identity_growth")}
    if "growth_proposals" in resident_columns:
        op.drop_column("resident_identity_growth", "growth_proposals")

    if inspector.has_table("runtime_adaptation_states"):
        op.drop_table("runtime_adaptation_states")

    if inspector.has_table("social_feedback_events"):
        indexes = {index["name"] for index in inspector.get_indexes("social_feedback_events")}
        for index_name in (
            "ix_social_feedback_events_created_at",
            "ix_social_feedback_events_source_actor_id",
            "ix_social_feedback_events_target_actor_id",
        ):
            if index_name in indexes:
                op.drop_index(index_name, table_name="social_feedback_events")
        op.drop_table("social_feedback_events")

    if inspector.has_table("guild_member_profiles"):
        op.drop_table("guild_member_profiles")
