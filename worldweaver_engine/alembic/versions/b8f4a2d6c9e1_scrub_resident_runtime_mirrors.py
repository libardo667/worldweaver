"""scrub resident runtime mirrors from city sessions

Revision ID: b8f4a2d6c9e1
Revises: a6d3f8b1c5e2
Create Date: 2026-07-20 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8f4a2d6c9e1"
down_revision: Union[str, None] = "a6d3f8b1c5e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PRIVATE_RUNTIME_KEYS = {
    "_resident_runtime_projection",
    "_resident_subjective_projection",
    "_resident_memory_projection",
    "_resident_subjective_facts",
    "_resident_cognitive_projection",
    "_resident_ledger_event_count",
    "_resident_runtime_synced_at",
    "_resident_rest",
}


def _without_private_runtime_fields(payload: object) -> tuple[object, bool]:
    if not isinstance(payload, dict):
        return payload, False

    cleaned = dict(payload)
    changed = False
    for key in _PRIVATE_RUNTIME_KEYS:
        if key in cleaned:
            cleaned.pop(key, None)
            changed = True

    variables = cleaned.get("variables")
    if cleaned.get("_v") == 2 and isinstance(variables, dict):
        clean_variables = dict(variables)
        for key in _PRIVATE_RUNTIME_KEYS:
            if key in clean_variables:
                clean_variables.pop(key, None)
                changed = True
        if changed:
            cleaned["variables"] = clean_variables

    return cleaned, changed


def upgrade() -> None:
    session_vars = sa.table(
        "session_vars",
        sa.column("session_id", sa.String(length=64)),
        sa.column("vars", sa.JSON()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(session_vars.c.session_id, session_vars.c.vars)
    ).mappings()
    for row in rows:
        cleaned, changed = _without_private_runtime_fields(row["vars"])
        if not changed:
            continue
        connection.execute(
            session_vars.update()
            .where(session_vars.c.session_id == row["session_id"])
            .values(vars=cleaned)
        )


def downgrade() -> None:
    # Deleted private copies cannot and should not be reconstructed.
    pass
