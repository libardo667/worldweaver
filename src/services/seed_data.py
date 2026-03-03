"""Database seeding helpers.

Production startup/reset should not inject legacy "Test *" storylets by default.
Legacy seeds remain available for explicit dev/test flows.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Storylet

# Default variables applied to every new game session.
DEFAULT_SESSION_VARS: Dict[str, Any] = {
    "name": "Adventurer",
    "danger": 0,
}


def _legacy_seed_rows(session: Session) -> int:
    """Insert legacy directional test storylets when the table is empty."""
    if session.query(Storylet).count() > 0:
        return 0

    directions = [
        ("North", 0, -1),
        ("Northeast", 1, -1),
        ("East", 1, 0),
        ("Southeast", 1, 1),
        ("South", 0, 1),
        ("Southwest", -1, 1),
        ("West", -1, 0),
        ("Northwest", -1, -1),
    ]
    seeds: List[Storylet] = []
    for name, dx, dy in directions:
        seeds.append(
            Storylet(
                title=f"Test {name}",
                text_template=f"You move {name.lower()}.",
                requires={},
                choices=[{"label": f"Go {name.lower()}", "set": {}}],
                weight=1.0,
                position={"x": dx, "y": dy},
            )
        )
    seeds.append(
        Storylet(
            title="Test Center",
            text_template="You are at the center.",
            requires={},
            choices=[{"label": "Stay", "set": {}}],
            weight=1.0,
            position={"x": 0, "y": 0},
        )
    )

    session.add_all(seeds)
    session.flush()
    return len(seeds)


def seed_legacy_storylets_if_empty_sync(session: Session) -> int:
    """Explicit helper for tests/dev to seed legacy directional storylets."""
    return _legacy_seed_rows(session)


def seed_if_empty_sync(session: Session, *, allow_legacy_seed: bool = False) -> int:
    """Legacy seed wrapper used by startup/reset flows.

    Returns the number of storylets inserted.
    """
    if not allow_legacy_seed:
        return 0
    return _legacy_seed_rows(session)


async def seed_if_empty(
    session: Optional[Session] = None,
    *,
    in_background: bool = False,
    allow_legacy_seed: bool = False,
) -> int:
    """Async wrapper for optional legacy seed insertion.

    - if in_background=False: uses provided session inline (test-friendly).
    - if in_background=True: creates its own Session in a worker thread and commits.
    """
    if not allow_legacy_seed:
        return 0

    if not in_background:
        assert session is not None, "Provide a Session when running inline."
        return seed_if_empty_sync(session, allow_legacy_seed=True)

    import asyncio

    def _work() -> int:
        with SessionLocal() as s:
            count = _legacy_seed_rows(s)
            s.commit()
            return count

    return await asyncio.to_thread(_work)
