"""Tests for src/services/game_logic.py."""

from src.services.game_logic import (
    SafeDict,
    render,
    meets_requirements,
    apply_choice_set,
    pick_storylet,
)


class TestSafeDict:

    def test_missing_key_returns_placeholder(self):
        d = SafeDict({"a": 1})
        assert d["missing"] == "{missing}"

    def test_existing_key_returns_value(self):
        d = SafeDict({"name": "Alice"})
        assert d["name"] == "Alice"


class TestRender:

    def test_substitutes_variables(self):
        assert render("Hello {name}!", {"name": "World"}) == "Hello World!"

    def test_handles_missing_keys_gracefully(self):
        assert render("{greeting} {name}", {"greeting": "Hi"}) == "Hi {name}"

    def test_empty_template(self):
        assert render("", {"a": 1}) == ""

    def test_no_placeholders(self):
        assert render("plain text", {"a": 1}) == "plain text"


class TestMeetsRequirements:

    def test_empty_requirements_always_pass(self):
        assert meets_requirements({"x": 1}, {}) is True
        assert meets_requirements({}, {}) is True

    def test_none_requirements_pass(self):
        assert meets_requirements({"x": 1}, None) is True

    def test_direct_equality(self):
        assert meets_requirements({"location": "cave"}, {"location": "cave"}) is True
        assert meets_requirements({"location": "cave"}, {"location": "forest"}) is False

    def test_boolean_requirement(self):
        assert meets_requirements({"has_key": True}, {"has_key": True}) is True
        assert meets_requirements({"has_key": True}, {"has_key": False}) is False

    def test_numeric_gte(self):
        assert meets_requirements({"gold": 10}, {"gold": {"gte": 5}}) is True
        assert meets_requirements({"gold": 3}, {"gold": {"gte": 5}}) is False
        assert meets_requirements({"gold": 5}, {"gold": {"gte": 5}}) is True

    def test_numeric_lte(self):
        assert meets_requirements({"danger": 2}, {"danger": {"lte": 3}}) is True
        assert meets_requirements({"danger": 5}, {"danger": {"lte": 3}}) is False

    def test_numeric_gt_lt(self):
        assert meets_requirements({"x": 5}, {"x": {"gt": 4}}) is True
        assert meets_requirements({"x": 4}, {"x": {"gt": 4}}) is False
        assert meets_requirements({"x": 3}, {"x": {"lt": 4}}) is True
        assert meets_requirements({"x": 4}, {"x": {"lt": 4}}) is False

    def test_eq_ne_operators(self):
        assert meets_requirements({"x": 5}, {"x": {"eq": 5}}) is True
        assert meets_requirements({"x": 5}, {"x": {"eq": 6}}) is False
        assert meets_requirements({"x": 5}, {"x": {"ne": 6}}) is True
        assert meets_requirements({"x": 5}, {"x": {"ne": 5}}) is False

    def test_missing_variable_fails(self):
        assert meets_requirements({}, {"gold": {"gte": 1}}) is False

    def test_none_value_with_comparison_fails(self):
        assert meets_requirements({"gold": None}, {"gold": {"gte": 1}}) is False


class TestApplyChoiceSet:

    def test_direct_assignment(self):
        result = apply_choice_set({"x": 1}, {"y": 2})
        assert result == {"x": 1, "y": 2}

    def test_increment(self):
        result = apply_choice_set({"ore": 5}, {"ore": {"inc": 3}})
        assert result["ore"] == 8

    def test_decrement(self):
        result = apply_choice_set({"danger": 5}, {"danger": {"dec": 2}})
        assert result["danger"] == 3

    def test_inc_from_zero(self):
        result = apply_choice_set({}, {"gold": {"inc": 10}})
        assert result["gold"] == 10

    def test_non_numeric_current_treated_as_zero(self):
        result = apply_choice_set({"x": "text"}, {"x": {"inc": 5}})
        assert result["x"] == 5

    def test_none_set_obj(self):
        result = apply_choice_set({"a": 1}, None)
        assert result == {"a": 1}

    def test_boolean_assignment(self):
        result = apply_choice_set({}, {"has_pickaxe": True})
        assert result["has_pickaxe"] is True

    def test_bad_inc_value_skipped(self):
        result = apply_choice_set({"x": 5}, {"x": {"inc": "not_a_number"}})
        assert result["x"] == 5


class TestPickStorylet:

    def test_returns_none_when_no_eligible(self, db_session):
        result = pick_storylet(db_session, {"location": "nonexistent_place_xyz"})
        assert result is None

    def test_picks_from_eligible_storylets(self, seeded_db):
        result = pick_storylet(seeded_db, {})
        assert result is not None
        assert hasattr(result, "title")

    def test_respects_requirements(self, seeded_db):
        from src.models import Storylet

        seeded_db.add(
            Storylet(
                title="Locked Door Test",
                text_template="A locked door.",
                requires={"has_secret_key_xyz": True},
                choices=[],
                weight=1.0,
            )
        )
        seeded_db.commit()

        # Without the key, this specific storylet shouldn't be picked
        # (but others may be eligible, so we can't assert None)
        for _ in range(20):
            result = pick_storylet(seeded_db, {"has_secret_key_xyz": False})
            if result and result.title == "Locked Door Test":
                raise AssertionError("Should not pick storylet with unmet requirements")
