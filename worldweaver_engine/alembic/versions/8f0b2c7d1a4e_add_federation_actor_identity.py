"""add federation actor identity tables and projection fields

Revision ID: 8f0b2c7d1a4e
Revises: f3a1c09b8d12
Create Date: 2026-03-15 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f0b2c7d1a4e"
down_revision: Union[str, None] = "f3a1c09b8d12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "federation_actors",
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False, server_default="human"),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("handle", sa.String(length=80), nullable=True),
        sa.Column("home_shard", sa.String(length=80), nullable=False),
        sa.Column("current_shard", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("origin", sa.String(length=20), nullable=False, server_default="migrated"),
        sa.Column("source_actor_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("actor_id"),
    )
    op.create_index(op.f("ix_federation_actors_handle"), "federation_actors", ["handle"], unique=True)
    op.create_index(op.f("ix_federation_actors_source_actor_id"), "federation_actors", ["source_actor_id"], unique=False)

    op.create_table(
        "federation_actor_auth",
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("username", sa.String(length=40), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("pass_type", sa.String(length=20), nullable=False, server_default="visitor_7day"),
        sa.Column("pass_expires_at", sa.DateTime(), nullable=True),
        sa.Column("terms_accepted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("actor_id"),
    )
    op.create_index(op.f("ix_federation_actor_auth_email"), "federation_actor_auth", ["email"], unique=True)
    op.create_index(op.f("ix_federation_actor_auth_username"), "federation_actor_auth", ["username"], unique=True)

    op.create_table(
        "federation_actor_secrets",
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("llm_api_key_enc", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("rotated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("actor_id"),
    )

    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(sa.Column("actor_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("api_key_enc", sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f("ix_players_actor_id"), ["actor_id"], unique=True)

    with op.batch_alter_table("session_vars") as batch_op:
        batch_op.add_column(sa.Column("actor_id", sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f("ix_session_vars_actor_id"), ["actor_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("session_vars") as batch_op:
        batch_op.drop_index(batch_op.f("ix_session_vars_actor_id"))
        batch_op.drop_column("actor_id")

    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_index(batch_op.f("ix_players_actor_id"))
        batch_op.drop_column("api_key_enc")
        batch_op.drop_column("actor_id")

    op.drop_table("federation_actor_secrets")
    op.drop_index(op.f("ix_federation_actor_auth_username"), table_name="federation_actor_auth")
    op.drop_index(op.f("ix_federation_actor_auth_email"), table_name="federation_actor_auth")
    op.drop_table("federation_actor_auth")
    op.drop_index(op.f("ix_federation_actors_source_actor_id"), table_name="federation_actors")
    op.drop_index(op.f("ix_federation_actors_handle"), table_name="federation_actors")
    op.drop_table("federation_actors")
