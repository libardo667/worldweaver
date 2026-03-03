"""Tests for database seeding functionality."""

from src.models import Storylet
from src.services.seed_data import (
    seed_if_empty,
    seed_legacy_storylets_if_empty_sync,
)

SEED_COUNT = 9  # 8 directions + 1 center


class TestEmptyDatabaseSeeding:

    async def test_seed_if_empty_is_noop_without_legacy_flag(self, db_session):
        assert db_session.query(Storylet).count() == 0
        inserted = await seed_if_empty(db_session)
        assert inserted == 0
        assert db_session.query(Storylet).count() == 0

    async def test_seed_if_empty_adds_expected_storylets_when_enabled(self, db_session):
        assert db_session.query(Storylet).count() == 0
        inserted = await seed_if_empty(db_session, allow_legacy_seed=True)
        assert inserted == SEED_COUNT
        assert db_session.query(Storylet).count() == SEED_COUNT

    async def test_seed_if_empty_does_not_seed_non_empty_database(self, db_session):
        db_session.add(Storylet(title="Existing", text_template="exists", requires={}, choices=[{"label": "Go", "set": {}}], weight=1.0))
        db_session.commit()
        inserted = await seed_if_empty(db_session, allow_legacy_seed=True)
        assert inserted == 0
        assert db_session.query(Storylet).count() == 1

    def test_explicit_legacy_seed_helper_keeps_previous_fixture_behavior(self, db_session):
        inserted = seed_legacy_storylets_if_empty_sync(db_session)
        assert inserted == SEED_COUNT
        titles = {s.title for s in db_session.query(Storylet).all()}
        assert "Test Center" in titles
        assert "Test North" in titles

    async def test_seed_multiple_calls_idempotent(self, db_session):
        await seed_if_empty(db_session, allow_legacy_seed=True)
        await seed_if_empty(db_session, allow_legacy_seed=True)
        await seed_if_empty(db_session, allow_legacy_seed=True)
        assert db_session.query(Storylet).count() == SEED_COUNT
