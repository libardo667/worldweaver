# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""drop storylets table (Major 69: storylet engine removed)

The storylet engine (selection, prefetch, JIT beats, seeding) was removed in
Major 69 slices 1-2 — /api/next had no production callers (client and agent
both act through /api/action + chat/move), and world content now comes from
the city-pack world graph. WorldEvent.storylet_id remains as a plain nullable
column (immutable event-history schema; new events write NULL).

Revision ID: e8b3a6d2f1c9
Revises: d7e2f9a1c4b8
Create Date: 2026-07-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8b3a6d2f1c9"
down_revision: Union[str, None] = "d7e2f9a1c4b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("storylets"):
        op.drop_table("storylets")


def downgrade() -> None:
    # Faithful recreation of the storylets schema (baseline b189ebeca4b5 plus the
    # effects/embedding/provenance columns added by a4d2b9c7e1f0, e10d9c78240b,
    # and f3a1c09b8d12).
    op.create_table(
        "storylets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False, unique=True),
        sa.Column("text_template", sa.Text(), nullable=False),
        sa.Column("requires", sa.JSON(), nullable=True),
        sa.Column("choices", sa.JSON(), nullable=True),
        sa.Column("effects", sa.JSON(), nullable=True),
        sa.Column("weight", sa.Float(), nullable=True),
        sa.Column("position", sa.JSON(), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="authored"),
        sa.Column("seed_event_ids", sa.JSON(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
