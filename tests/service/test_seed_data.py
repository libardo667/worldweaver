"""Tests for database seeding functionality."""

import pytest
from src.models import Storylet
from src.services.seed_data import seed_if_empty

SEED_COUNT = 9  # 8 directions + 1 center


class TestEmptyDatabaseSeeding:

    async def test_seed_if_empty_adds_expected_storylets(self, db_session):
        assert db_session.query(Storylet).count() == 0
        await seed_if_empty(db_session)
        assert db_session.query(Storylet).count() == SEED_COUNT

    async def test_seed_if_empty_does_not_seed_non_empty_database(self, db_session):
        db_session.add(Storylet(title="Existing", text_template="exists", requires={}, choices=[{"label": "Go", "set": {}}], weight=1.0))
        db_session.commit()
        await seed_if_empty(db_session)
        assert db_session.query(Storylet).count() == 1

    async def test_seeded_storylets_have_correct_structure(self, db_session):
        await seed_if_empty(db_session)
        for s in db_session.query(Storylet).all():
            assert s.title and s.text_template
            assert s.requires is not None and s.choices is not None

    async def test_seeded_storylets_specific_content(self, db_session):
        await seed_if_empty(db_session)
        titles = {s.title for s in db_session.query(Storylet).all()}
        assert "Test Center" in titles
        assert "Test North" in titles

    async def test_seeded_storylets_requirements_and_choices(self, db_session):
        await seed_if_empty(db_session)
        center = db_session.query(Storylet).filter_by(title="Test Center").first()
        assert center is not None
        assert isinstance(center.requires, dict)
        assert isinstance(center.choices, list) and len(center.choices) >= 1

    async def test_seed_multiple_calls_idempotent(self, db_session):
        await seed_if_empty(db_session)
        await seed_if_empty(db_session)
        await seed_if_empty(db_session)
        assert db_session.query(Storylet).count() == SEED_COUNT

    async def test_seeded_storylets_database_persistence(self, db_session):
        await seed_if_empty(db_session)
        db_session.commit()
        assert db_session.query(Storylet).count() == SEED_COUNT

    async def test_seed_with_transaction_rollback(self, db_session):
        db_session.begin_nested()
        await seed_if_empty(db_session)
        assert db_session.query(Storylet).count() == SEED_COUNT
        db_session.rollback()
        assert db_session.query(Storylet).count() == 0

    async def test_storylet_choice_format_consistency(self, db_session):
        await seed_if_empty(db_session)
        for s in db_session.query(Storylet).all():
            assert isinstance(s.choices, list) and len(s.choices) > 0
            for c in s.choices:
                assert isinstance(c, dict)
                assert "label" in c or "text" in c
                assert "set" in c or "set_vars" in c
