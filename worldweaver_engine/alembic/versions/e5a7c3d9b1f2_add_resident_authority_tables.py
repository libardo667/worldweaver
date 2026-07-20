"""add resident authority and replay tables

Revision ID: e5a7c3d9b1f2
Revises: b8f4a2d6c9e1
Create Date: 2026-07-20 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5a7c3d9b1f2"
down_revision: Union[str, None] = "b8f4a2d6c9e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resident_authorities",
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("hearth_shard_id", sa.String(length=80), nullable=False),
        sa.Column("identity_public_key", sa.String(length=64), nullable=False),
        sa.Column("identity_key_id", sa.String(length=48), nullable=False),
        sa.Column("active_runtime_generation", sa.Integer(), nullable=True),
        sa.Column(
            "recovery_policy_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "bound_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "active_runtime_generation IS NULL OR active_runtime_generation >= 1",
            name="ck_resident_authorities_active_generation",
        ),
        sa.CheckConstraint(
            "recovery_policy_version >= 1",
            name="ck_resident_authorities_recovery_policy",
        ),
        sa.PrimaryKeyConstraint("actor_id"),
        sa.UniqueConstraint("identity_public_key"),
    )
    op.create_index(
        op.f("ix_resident_authorities_identity_key_id"),
        "resident_authorities",
        ["identity_key_id"],
        unique=True,
    )

    op.create_table(
        "resident_session_authorities",
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("runtime_generation", sa.Integer(), nullable=False),
        sa.Column(
            "bound_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "runtime_generation >= 1",
            name="ck_resident_session_authorities_generation",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["session_vars.session_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(
        op.f("ix_resident_session_authorities_actor_id"),
        "resident_session_authorities",
        ["actor_id"],
        unique=False,
    )

    op.create_table(
        "resident_request_nonces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("certificate_id", sa.String(length=128), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("runtime_generation", sa.Integer(), nullable=False),
        sa.Column("signed_at", sa.DateTime(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "runtime_generation >= 1",
            name="ck_resident_request_nonces_generation",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "certificate_id",
            "nonce",
            name="uq_resident_request_certificate_nonce",
        ),
    )
    op.create_index(
        op.f("ix_resident_request_nonces_actor_id"),
        "resident_request_nonces",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resident_request_nonces_certificate_id"),
        "resident_request_nonces",
        ["certificate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resident_request_nonces_received_at"),
        "resident_request_nonces",
        ["received_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_resident_request_nonces_received_at"),
        table_name="resident_request_nonces",
    )
    op.drop_index(
        op.f("ix_resident_request_nonces_certificate_id"),
        table_name="resident_request_nonces",
    )
    op.drop_index(
        op.f("ix_resident_request_nonces_actor_id"),
        table_name="resident_request_nonces",
    )
    op.drop_table("resident_request_nonces")
    op.drop_index(
        op.f("ix_resident_session_authorities_actor_id"),
        table_name="resident_session_authorities",
    )
    op.drop_table("resident_session_authorities")
    op.drop_index(
        op.f("ix_resident_authorities_identity_key_id"),
        table_name="resident_authorities",
    )
    op.drop_table("resident_authorities")
