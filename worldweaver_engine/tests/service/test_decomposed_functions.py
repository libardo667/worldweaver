"""Tests for functions extracted during Major 08 decomposition."""

from src.models import Storylet
from src.services.storylet_ingest import deduplicate_and_insert
from src.services.game_logic import ensure_storylets, pick_storylet


class TestDeduplicateAndInsert:

    def _storylet(self, title="Test", **overrides):
        base = {
            "title": title,
            "text_template": "Some text.",
            "requires": {},
            "choices": [{"label": "Go", "set": {}}],
            "weight": 1.0,
        }
        base.update(overrides)
        return base

    def test_inserts_valid_storylet(self, db_session):
        created, skipped = deduplicate_and_insert(db_session, [self._storylet()])
        assert len(created) == 1
        assert skipped == 0
        assert created[0]["title"] == "Test"

    def test_skips_missing_keys(self, db_session):
        bad = {"title": "Incomplete"}  # missing text_template, requires, etc.
        created, skipped = deduplicate_and_insert(db_session, [bad])
        assert len(created) == 0
        assert skipped == 1

    def test_skips_duplicate_title(self, db_session):
        db_session.add(
            Storylet(
                title="Existing",
                text_template="Already here.",
                requires={},
                choices=[],
                weight=1.0,
            )
        )
        db_session.commit()

        created, skipped = deduplicate_and_insert(db_session, [self._storylet(title="Existing")])
        assert len(created) == 0
        assert skipped == 1

    def test_multiple_storylets(self, db_session):
        storylets = [self._storylet(f"Story {i}") for i in range(3)]
        created, skipped = deduplicate_and_insert(db_session, storylets)
        assert len(created) == 3
        assert skipped == 0


class TestEnsureStorylets:

    def test_does_nothing_when_enough_eligible(self, seeded_db):
        """With 9 seed storylets (all requiring {}), ensure_storylets is a no-op."""
        count_before = seeded_db.query(Storylet).count()
        ensure_storylets(seeded_db, {})
        count_after = seeded_db.query(Storylet).count()
        assert count_after == count_before

    def test_generates_when_few_eligible(self, db_session):
        """When no storylets match, ensure_storylets tries to generate (fallback)."""
        ensure_storylets(db_session, {"location": "nonexistent_xyz"})
        # Under PYTEST_CURRENT_TEST, the LLM falls back to _FALLBACK_STORYLETS
        count = db_session.query(Storylet).count()
        assert count >= 1


class TestPickStoryletPure:

    def test_no_side_effects(self, seeded_db):
        """pick_storylet should NOT generate new storylets."""
        count_before = seeded_db.query(Storylet).count()
        pick_storylet(seeded_db, {"location": "nonexistent_xyz_123"})
        count_after = seeded_db.query(Storylet).count()
        assert count_after == count_before

    def test_returns_eligible(self, seeded_db):
        result = pick_storylet(seeded_db, {})
        assert result is not None
