"""Tests for functions extracted during Major 08 decomposition."""

from unittest.mock import patch

from src.config import settings
from src.models import Storylet
from src.services.storylet_ingest import (
    deduplicate_and_insert,
    assign_spatial_to_storylets,
    run_auto_improvements,
)
from src.services.game_logic import ensure_storylets, pick_storylet, auto_populate_storylets


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


class TestAssignSpatialToStorylets:

    def test_assigns_to_existing_titles(self, seeded_db):
        from src.models import Storylet as S

        titles = [s.title for s in seeded_db.query(S).limit(2).all()]
        result = assign_spatial_to_storylets(seeded_db, titles)
        assert isinstance(result, int)


class TestRunAutoImprovements:

    def test_returns_none_when_not_needed(self, db_session):
        result = run_auto_improvements(db_session, 0, "")
        assert result is None

    @patch("src.services.auto_improvement.auto_improve_storylets")
    def test_returns_none_when_trigger_is_empty(self, mock_improve, db_session):
        result = run_auto_improvements(db_session, 5, "")
        assert result is None
        mock_improve.assert_not_called()

    @patch("src.services.auto_improvement.auto_improve_storylets")
    @patch("src.services.auto_improvement.should_run_auto_improvement", return_value=True)
    def test_runs_when_triggered(self, mock_should, mock_improve, db_session, monkeypatch):
        monkeypatch.setattr(settings, "enable_story_smoothing", True)
        monkeypatch.setattr(settings, "enable_story_deepening", True)
        mock_improve.return_value = {"smoothing": {}, "deepening": {}}
        result = run_auto_improvements(db_session, 5, "test-trigger")
        assert result is not None
        mock_improve.assert_called_once_with(
            db=db_session,
            trigger="test-trigger (5 storylets)",
            run_smoothing=True,
            run_deepening=True,
        )

    @patch("src.services.auto_improvement.auto_improve_storylets")
    @patch("src.services.auto_improvement.should_run_auto_improvement", return_value=True)
    def test_skips_when_all_improvement_flags_disabled(self, mock_should, mock_improve, db_session, monkeypatch):
        monkeypatch.setattr(settings, "enable_story_smoothing", False)
        monkeypatch.setattr(settings, "enable_story_deepening", False)

        result = run_auto_improvements(db_session, 5, "test-trigger")

        assert result is None
        mock_should.assert_not_called()
        mock_improve.assert_not_called()


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

    @patch("src.services.storylet_ingest.run_auto_improvements")
    @patch("src.services.llm_service.generate_contextual_storylets")
    def test_routes_auto_improvement_through_ingest_adapter(self, mock_generate, mock_run_auto, db_session):
        mock_generate.return_value = [
            {
                "title": "Adapter Route 1",
                "text_template": "One",
                "requires": {},
                "choices": [{"label": "Go", "set": {}}],
                "weight": 1.0,
            },
            {
                "title": "Adapter Route 2",
                "text_template": "Two",
                "requires": {},
                "choices": [{"label": "Go", "set": {}}],
                "weight": 1.0,
            },
            {
                "title": "Adapter Route 3",
                "text_template": "Three",
                "requires": {},
                "choices": [{"label": "Go", "set": {}}],
                "weight": 1.0,
            },
        ]

        ensure_storylets(db_session, {"location": "adapter-route"})

        mock_run_auto.assert_called_once_with(
            db=db_session,
            storylet_count=3,
            trigger="contextual-generation",
        )


class TestAutoPopulateStorylets:

    @patch("src.services.storylet_ingest.run_auto_improvements")
    @patch("src.services.llm_service.llm_suggest_storylets")
    def test_routes_auto_improvement_through_ingest_adapter(self, mock_suggest, mock_run_auto, db_session):
        mock_suggest.return_value = [
            {
                "title": "Populate Adapter 1",
                "text_template": "One",
                "requires": {},
                "choices": [{"label": "Go", "set": {}}],
                "weight": 1.0,
            },
            {
                "title": "Populate Adapter 2",
                "text_template": "Two",
                "requires": {},
                "choices": [{"label": "Go", "set": {}}],
                "weight": 1.0,
            },
            {
                "title": "Populate Adapter 3",
                "text_template": "Three",
                "requires": {},
                "choices": [{"label": "Go", "set": {}}],
                "weight": 1.0,
            },
        ]

        added = auto_populate_storylets(db_session, target_count=3)

        assert added == 3
        mock_run_auto.assert_called_once_with(
            db=db_session,
            storylet_count=3,
            trigger="auto-populate",
        )


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
