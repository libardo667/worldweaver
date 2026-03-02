"""baseline schema

Revision ID: b189ebeca4b5
Revises:
Create Date: 2026-03-01 19:57:16.348788

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b189ebeca4b5'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "storylets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(200), nullable=False, unique=True),
        sa.Column("text_template", sa.Text, nullable=False),
        sa.Column("requires", sa.JSON, server_default="{}"),
        sa.Column("choices", sa.JSON, server_default="[]"),
        sa.Column("weight", sa.Float, server_default="1.0"),
        sa.Column("position", sa.JSON, server_default='{"x": 0, "y": 0}'),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
    )

    op.create_table(
        "session_vars",
        sa.Column("session_id", sa.String(64), primary_key=True),
        sa.Column("vars", sa.JSON, server_default="{}"),
        sa.Column(
            "updated_at",
            sa.DateTime,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
    )


def downgrade() -> None:
    op.drop_table("session_vars")
    op.drop_table("storylets")
