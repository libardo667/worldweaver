# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""drop guild tables (Major 68: guild economy retired)

Removes the four guild reward-economy tables. The guild surface was removed
consumer-first: React client (slice 1), agent runtime reward-shaping (slice 2,
commit b42eab3), backend API + services (slice 3). This is slice 4 — the data
layer. NOTE: ``resident_identity_growth.growth_proposals`` (added by
e4f9c2a1b6d7 alongside these tables) is the LIVE identity-growth mechanism and
is intentionally untouched.

Revision ID: d7e2f9a1c4b8
Revises: c1d2e3f4a5b6
Create Date: 2026-07-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d7e2f9a1c4b8"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("guild_quests"):
        op.drop_index(op.f("ix_guild_quests_created_at"), table_name="guild_quests")
        op.drop_index(op.f("ix_guild_quests_status"), table_name="guild_quests")
        op.drop_index(op.f("ix_guild_quests_branch"), table_name="guild_quests")
        op.drop_index(
            op.f("ix_guild_quests_source_actor_id"), table_name="guild_quests"
        )
        op.drop_index(
            op.f("ix_guild_quests_target_actor_id"), table_name="guild_quests"
        )
        op.drop_table("guild_quests")

    if inspector.has_table("social_feedback_events"):
        op.drop_index(
            "ix_social_feedback_events_created_at", table_name="social_feedback_events"
        )
        op.drop_index(
            "ix_social_feedback_events_source_actor_id",
            table_name="social_feedback_events",
        )
        op.drop_index(
            "ix_social_feedback_events_target_actor_id",
            table_name="social_feedback_events",
        )
        op.drop_table("social_feedback_events")

    if inspector.has_table("runtime_adaptation_states"):
        op.drop_table("runtime_adaptation_states")

    if inspector.has_table("guild_member_profiles"):
        op.drop_table("guild_member_profiles")


def downgrade() -> None:
    # Faithful recreation of the schemas from e4f9c2a1b6d7, f2a4d9c6b7e1, and
    # a7b4e1c2d9f0 (activity_log column folded into the guild_quests create).
    op.create_table(
        "guild_member_profiles",
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column(
            "member_type",
            sa.String(length=20),
            nullable=False,
            server_default="resident",
        ),
        sa.Column(
            "rank", sa.String(length=32), nullable=False, server_default="apprentice"
        ),
        sa.Column("branches", sa.JSON(), nullable=True),
        sa.Column("mentor_actor_ids", sa.JSON(), nullable=True),
        sa.Column(
            "quest_band",
            sa.String(length=32),
            nullable=False,
            server_default="foundations",
        ),
        sa.Column("review_status", sa.JSON(), nullable=True),
        sa.Column("environment_guidance", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("actor_id"),
    )

    op.create_table(
        "social_feedback_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("target_actor_id", sa.String(length=36), nullable=False),
        sa.Column("source_actor_id", sa.String(length=36), nullable=True),
        sa.Column("source_system", sa.String(length=80), nullable=True),
        sa.Column(
            "feedback_mode",
            sa.String(length=20),
            nullable=False,
            server_default="inferred",
        ),
        sa.Column(
            "channel", sa.String(length=40), nullable=False, server_default="system"
        ),
        sa.Column("dimension_scores", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_refs", sa.JSON(), nullable=True),
        sa.Column("branch_hint", sa.String(length=80), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=True, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_social_feedback_events_target_actor_id",
        "social_feedback_events",
        ["target_actor_id"],
    )
    op.create_index(
        "ix_social_feedback_events_source_actor_id",
        "social_feedback_events",
        ["source_actor_id"],
    )
    op.create_index(
        "ix_social_feedback_events_created_at", "social_feedback_events", ["created_at"]
    )

    op.create_table(
        "runtime_adaptation_states",
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("behavior_knobs", sa.JSON(), nullable=True),
        sa.Column("environment_guidance", sa.JSON(), nullable=True),
        sa.Column("source_feedback_ids", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=True, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("actor_id"),
    )

    op.create_table(
        "guild_quests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("target_actor_id", sa.String(length=36), nullable=False),
        sa.Column("source_actor_id", sa.String(length=36), nullable=True),
        sa.Column("source_system", sa.String(length=80), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False, server_default=""),
        sa.Column("branch", sa.String(length=80), nullable=True),
        sa.Column(
            "quest_band",
            sa.String(length=32),
            nullable=False,
            server_default="foundations",
        ),
        sa.Column(
            "status", sa.String(length=24), nullable=False, server_default="assigned"
        ),
        sa.Column("progress_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("outcome_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_refs", sa.JSON(), nullable=True),
        sa.Column("assignment_context", sa.JSON(), nullable=True),
        sa.Column("review_status", sa.JSON(), nullable=True),
        sa.Column("activity_log", sa.JSON(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_guild_quests_target_actor_id"),
        "guild_quests",
        ["target_actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_guild_quests_source_actor_id"),
        "guild_quests",
        ["source_actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_guild_quests_branch"), "guild_quests", ["branch"], unique=False
    )
    op.create_index(
        op.f("ix_guild_quests_status"), "guild_quests", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_guild_quests_created_at"), "guild_quests", ["created_at"], unique=False
    )
