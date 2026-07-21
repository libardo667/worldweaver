"""add actor-addressed correspondence

Revision ID: a9f4c2e7d1b6
Revises: f6b8d1e3a5c7
Create Date: 2026-07-20 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9f4c2e7d1b6"
down_revision: Union[str, None] = "f6b8d1e3a5c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "direct_messages",
        sa.Column("sender_actor_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "direct_messages",
        sa.Column("recipient_actor_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "direct_messages",
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        op.f("ix_direct_messages_sender_actor_id"),
        "direct_messages",
        ["sender_actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_direct_messages_recipient_actor_id"),
        "direct_messages",
        ["recipient_actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_direct_messages_acknowledged_at"),
        "direct_messages",
        ["acknowledged_at"],
        unique=False,
    )
    op.execute(
        "UPDATE direct_messages "
        "SET sender_actor_id = (SELECT session_vars.actor_id FROM session_vars "
        "WHERE session_vars.session_id = direct_messages.from_session_id) "
        "WHERE sender_actor_id IS NULL AND from_session_id IS NOT NULL"
    )
    op.execute(
        "UPDATE direct_messages "
        "SET recipient_actor_id = (SELECT session_vars.actor_id FROM session_vars "
        "WHERE session_vars.session_id = direct_messages.to_name) "
        "WHERE recipient_actor_id IS NULL"
    )
    op.execute(
        "UPDATE direct_messages SET acknowledged_at = read_at "
        "WHERE acknowledged_at IS NULL AND read_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_direct_messages_acknowledged_at"), table_name="direct_messages"
    )
    op.drop_index(
        op.f("ix_direct_messages_recipient_actor_id"), table_name="direct_messages"
    )
    op.drop_index(
        op.f("ix_direct_messages_sender_actor_id"), table_name="direct_messages"
    )
    op.drop_column("direct_messages", "acknowledged_at")
    op.drop_column("direct_messages", "recipient_actor_id")
    op.drop_column("direct_messages", "sender_actor_id")
