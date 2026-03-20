"""add guild quests table

Revision ID: f2a4d9c6b7e1
Revises: e4f9c2a1b6d7
Create Date: 2026-03-20 18:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2a4d9c6b7e1"
down_revision = "e4f9c2a1b6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guild_quests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("target_actor_id", sa.String(length=36), nullable=False),
        sa.Column("source_actor_id", sa.String(length=36), nullable=True),
        sa.Column("source_system", sa.String(length=80), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False, server_default=""),
        sa.Column("branch", sa.String(length=80), nullable=True),
        sa.Column("quest_band", sa.String(length=32), nullable=False, server_default="foundations"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="assigned"),
        sa.Column("progress_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("outcome_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence_refs", sa.JSON(), nullable=True),
        sa.Column("assignment_context", sa.JSON(), nullable=True),
        sa.Column("review_status", sa.JSON(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_guild_quests_target_actor_id"), "guild_quests", ["target_actor_id"], unique=False)
    op.create_index(op.f("ix_guild_quests_source_actor_id"), "guild_quests", ["source_actor_id"], unique=False)
    op.create_index(op.f("ix_guild_quests_branch"), "guild_quests", ["branch"], unique=False)
    op.create_index(op.f("ix_guild_quests_status"), "guild_quests", ["status"], unique=False)
    op.create_index(op.f("ix_guild_quests_created_at"), "guild_quests", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_guild_quests_created_at"), table_name="guild_quests")
    op.drop_index(op.f("ix_guild_quests_status"), table_name="guild_quests")
    op.drop_index(op.f("ix_guild_quests_branch"), table_name="guild_quests")
    op.drop_index(op.f("ix_guild_quests_source_actor_id"), table_name="guild_quests")
    op.drop_index(op.f("ix_guild_quests_target_actor_id"), table_name="guild_quests")
    op.drop_table("guild_quests")
