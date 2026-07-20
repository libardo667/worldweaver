"""keep chat actor identity after session retirement

Revision ID: e2f6a1c9d4b7
Revises: d4a8c2f1e7b9
Create Date: 2026-07-19 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e2f6a1c9d4b7"
down_revision: Union[str, None] = "d4a8c2f1e7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("location_chat", sa.Column("actor_id", sa.String(length=36), nullable=True))
    op.execute(
        "UPDATE location_chat "
        "SET actor_id = (SELECT session_vars.actor_id FROM session_vars "
        "WHERE session_vars.session_id = location_chat.session_id) "
        "WHERE actor_id IS NULL"
    )


def downgrade() -> None:
    op.drop_column("location_chat", "actor_id")
