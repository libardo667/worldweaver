"""Smoke test for StorySmoother using SQLAlchemy session.

Creates a temporary DB in the workspace (DW_DB_PATH) with a few storylets,
runs the smoother (non-dry-run) and prints the result summary.
"""

import os

os.environ.setdefault("DW_DB_PATH", "test_smoother.db")

from src.database import create_tables, SessionLocal
from src.models import Storylet
from src.services.story_smoother import StorySmoother


def seed():
    create_tables()
    db = SessionLocal()
    try:
        # Clean slate
        db.query(Storylet).delete()
        db.commit()

        # Seed minimal data
        db.add_all(
            [
                Storylet(
                    title="A",
                    text_template="A text",
                    requires={},
                    choices=[],
                    weight=1.0,
                ),
                Storylet(
                    title="B",
                    text_template="B text",
                    requires={},
                    choices=[],
                    weight=1.0,
                ),
                Storylet(
                    title="C",
                    text_template="C text",
                    requires={"location": "Clan Hall"},
                    choices=[{"label": "Descend", "set": {"location": "Neon Caverns"}}],
                    weight=1.0,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


def main():
    seed()
    smoother = StorySmoother()
    result = smoother.smooth_story(dry_run=False)
    print("\nRESULT:", result)


if __name__ == "__main__":
    main()

