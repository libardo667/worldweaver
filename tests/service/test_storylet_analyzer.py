"""Tests for src/services/storylet_analyzer.py."""

from src.models import Storylet
from src.services.storylet_analyzer import (
    _identify_successful_patterns,
    analyze_storylet_gaps,
    generate_gap_recommendations,
    get_ai_learning_context,
)


class TestAnalyzeStoryletGaps:

    def test_empty_database(self, db_session):
        result = analyze_storylet_gaps(db_session)
        assert result["total_storylets"] == 0
        assert result["connectivity_score"] == 0

    def test_tracks_variables_required(self, db_session):
        db_session.add(
            Storylet(
                title="Locked Gate",
                text_template="A locked gate.",
                requires={"has_key": True},
                choices=[{"label": "Wait", "set": {}}],
                weight=1.0,
            )
        )
        db_session.commit()
        result = analyze_storylet_gaps(db_session)
        assert "has_key" in result["variables_required"]

    def test_tracks_variables_set(self, db_session):
        db_session.add(
            Storylet(
                title="Find Key",
                text_template="You find a key.",
                requires={},
                choices=[{"label": "Take it", "set": {"has_key": True}}],
                weight=1.0,
            )
        )
        db_session.commit()
        result = analyze_storylet_gaps(db_session)
        assert "has_key" in result["variables_set"]

    def test_missing_setters_detected(self, db_session):
        db_session.add(
            Storylet(
                title="Needs Gold",
                text_template="Pay gold.",
                requires={"gold": {"gte": 10}},
                choices=[{"label": "Pay", "set": {}}],
                weight=1.0,
            )
        )
        db_session.commit()
        result = analyze_storylet_gaps(db_session)
        assert "gold" in result["missing_setters"]

    def test_unused_setters_detected(self, db_session):
        db_session.add(
            Storylet(
                title="Get Gems",
                text_template="Shiny gems.",
                requires={},
                choices=[{"label": "Collect", "set": {"gems": 5}}],
                weight=1.0,
            )
        )
        db_session.commit()
        result = analyze_storylet_gaps(db_session)
        assert "gems" in result["unused_setters"]

    def test_connectivity_score_with_seeded_data(self, seeded_db):
        result = analyze_storylet_gaps(seeded_db)
        assert result["total_storylets"] >= 9
        assert 0 <= result["connectivity_score"] <= 1

    def test_location_flow_tracked(self, db_session):
        db_session.add(
            Storylet(
                title="Forest Path",
                text_template="A path through the forest.",
                requires={"location": "forest"},
                choices=[{"label": "Go to cave", "set": {"location": "cave"}}],
                weight=1.0,
            )
        )
        db_session.commit()
        result = analyze_storylet_gaps(db_session)
        assert "forest" in result["location_flow"]
        assert "cave" in result["location_flow"]

    def test_danger_distribution(self, db_session):
        db_session.add(
            Storylet(
                title="Safe Area",
                text_template="Safe.",
                requires={"danger": {"lte": 1}},
                choices=[{"label": "Rest", "set": {}}],
                weight=1.0,
            )
        )
        db_session.commit()
        result = analyze_storylet_gaps(db_session)
        assert result["danger_distribution"]["low"] >= 1


class TestGenerateGapRecommendations:

    def test_recommends_for_missing_has_key(self):
        recs = generate_gap_recommendations({"has_key"}, set(), {}, {})
        assert any(r["variable"] == "has_key" for r in recs)

    def test_recommends_for_unused_gold(self):
        recs = generate_gap_recommendations(set(), {"gold"}, {}, {})
        assert any(r["variable"] == "gold" for r in recs)

    def test_empty_gaps_returns_empty(self):
        assert generate_gap_recommendations(set(), set(), {}, {}) == []

    def test_location_connectivity_recommendation(self):
        flow = {
            "cave": {"required_by": ["A", "B", "C", "D", "E"], "transitions_to": ["X"]},
        }
        recs = generate_gap_recommendations(set(), set(), flow, {})
        assert any(r["type"] == "location_connectivity" for r in recs)


class TestGetAILearningContext:

    def test_returns_expected_keys(self, seeded_db):
        ctx = get_ai_learning_context(seeded_db)
        assert "world_state_analysis" in ctx
        assert "variable_ecosystem" in ctx
        assert "location_network" in ctx
        assert "narrative_balance" in ctx
        assert "improvement_priorities" in ctx
        assert "successful_patterns" in ctx


class TestIdentifySuccessfulPatterns:

    def test_connected_variables_pattern(self):
        analysis = {
            "variables_set": {"location": [], "gold": []},
            "variables_required": {"location": [], "danger": []},
            "danger_distribution": {"low": 0, "medium": 0, "high": 0},
            "location_flow": {},
        }
        patterns = _identify_successful_patterns(analysis)
        assert any("location" in p for p in patterns)

    def test_empty_analysis(self):
        analysis = {
            "variables_set": {},
            "variables_required": {},
            "danger_distribution": {"low": 0, "medium": 0, "high": 0},
            "location_flow": {},
        }
        patterns = _identify_successful_patterns(analysis)
        assert isinstance(patterns, list)
