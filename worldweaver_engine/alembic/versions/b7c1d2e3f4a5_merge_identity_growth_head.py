"""merge identity growth head

Revision ID: b7c1d2e3f4a5
Revises: 4d2a9b6c1f7e, 9f4c2b7a1d6e
Create Date: 2026-03-18 20:20:00.000000

"""
from typing import Sequence, Union


revision: str = "b7c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = ("4d2a9b6c1f7e", "9f4c2b7a1d6e")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
