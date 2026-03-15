"""merge federation schema heads

Revision ID: 9f4c2b7a1d6e
Revises: 8f0b2c7d1a4e, c3d4e5f6a7b8
Create Date: 2026-03-15 12:35:00.000000

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "9f4c2b7a1d6e"
down_revision: Union[str, Sequence[str], None] = ("8f0b2c7d1a4e", "c3d4e5f6a7b8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
