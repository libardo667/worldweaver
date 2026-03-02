"""Database seeding functionality."""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from ..models import Storylet
from ..database import SessionLocal

# Default variables applied to every new game session.
DEFAULT_SESSION_VARS: Dict[str, Any] = {
    "name": "Adventurer",
    "danger": 0,
    "has_pickaxe": True,
}


def _seed_rows(session: Session) -> None:
    """Seed the database with initial storylets if empty. Runs in the caller's transaction."""
    # If anything here raises, caller's transaction can roll back cleanly.
    if session.query(Storylet).count() > 0:
        return

    # Seed storylets at all 8 directions around (0,0) with no requirements
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
    # Add a central starting storylet at (0,0)
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


def seed_if_empty_sync(session: Session) -> None:
    """Inline, test-freindly; respsect's caller's transaction."""
    _seed_rows(session)


async def seed_if_empty(
    session: Optional[Session] = None, *, in_background: bool = False
) -> None:
    """
    Async wrapper.
    - if in_background=False: uses provided session inline (test-friendly).
    - if in_background=True: creates its own Session in a worker thread and commits (prod-friendly)
    """

    if not in_background:
        assert session is not None, "Provide a Session when running inline."
        return seed_if_empty_sync(session)

    import asyncio

    def _work():
        # Each background worker gets its own session, then commits, cleans up
        with SessionLocal() as s:
            _seed_rows(s)
            s.commit()
        SessionLocal.remove()

    await asyncio.to_thread(_work)
