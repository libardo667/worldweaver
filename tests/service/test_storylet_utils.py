"""Tests for storylet helper normalization and location lookup."""

from sqlalchemy import text

from src.models import Storylet
from src.services.storylet_utils import (
    find_storylet_by_location,
    normalize_choice,
    normalize_requires,
    storylet_location,
)


class TestNormalizeRequires:

    def test_returns_dict_as_is(self):
        requires = {"location": "cave", "danger": 2}
        result = normalize_requires(requires)
        assert result == requires

    def test_parses_json_string(self):
        result = normalize_requires('{"location":"bridge","torch":true}')
        assert result == {"location": "bridge", "torch": True}

    def test_none_returns_empty_dict(self):
        assert normalize_requires(None) == {}

    def test_malformed_json_returns_empty_dict(self):
        assert normalize_requires("{bad json") == {}

    def test_non_dict_json_returns_empty_dict(self):
        assert normalize_requires('["not", "a", "dict"]') == {}


class TestNormalizeChoice:

    def test_prefers_label_and_set(self):
        choice = {
            "label": "Step Forward",
            "text": "Ignored",
            "set": {"location": "hall"},
            "set_vars": {"location": "cellar"},
        }
        assert normalize_choice(choice) == {
            "label": "Step Forward",
            "set": {"location": "hall"},
        }

    def test_falls_back_to_text_and_set_vars(self):
        choice = {"text": "Continue On", "set_vars": {"gold": 5}}
        assert normalize_choice(choice) == {
            "label": "Continue On",
            "set": {"gold": 5},
        }

    def test_defaults_when_missing(self):
        assert normalize_choice({}) == {"label": "Continue", "set": {}}


class TestStoryletLocationAndLookup:

    def test_storylet_location_handles_dict_json_and_invalid(self):
        from_dict = Storylet(
            title="dict-loc",
            text_template="x",
            requires={"location": "forge"},
            choices=[],
            weight=1.0,
        )
        from_json = Storylet(
            title="json-loc",
            text_template="x",
            requires='{"location":"bridge"}',
            choices=[],
            weight=1.0,
        )
        invalid = Storylet(
            title="bad-loc",
            text_template="x",
            requires="{bad",
            choices=[],
            weight=1.0,
        )
        assert storylet_location(from_dict) == "forge"
        assert storylet_location(from_json) == "bridge"
        assert storylet_location(invalid) is None

    def test_find_storylet_by_location_supports_legacy_json_requires(self, db_session):
        db_session.add(
            Storylet(
                title="legacy-json-location",
                text_template="Legacy location storylet.",
                requires='{"location":"start"}',
                choices=[{"label": "Continue", "set": {}}],
                weight=1.0,
                position={"x": 0, "y": 0},
            )
        )
        db_session.commit()

        found = find_storylet_by_location(db_session, "start")
        assert found is not None
        assert found.title == "legacy-json-location"

    def test_find_storylet_by_location_ignores_malformed_requires(self, db_session):
        db_session.add(
            Storylet(
                title="bad-json-location",
                text_template="Bad location storylet.",
                requires="{bad",
                choices=[{"label": "Continue", "set": {}}],
                weight=1.0,
                position={"x": 0, "y": 0},
            )
        )
        db_session.commit()

        assert find_storylet_by_location(db_session, "start") is None

    def test_find_storylet_by_location_survives_invalid_json_column_payloads(self, db_session):
        db_session.add(
            Storylet(
                title="raw-invalid-json-location",
                text_template="Raw JSON payload gets corrupted.",
                requires={"location": "start"},
                choices=[{"label": "Continue", "set": {}}],
                weight=1.0,
                position={"x": 0, "y": 0},
            )
        )
        db_session.commit()
        db_session.execute(text("UPDATE storylets SET choices = '' WHERE title = :title"), {"title": "raw-invalid-json-location"})
        db_session.commit()

        found = find_storylet_by_location(db_session, "start")
        assert found is not None
        assert found.title == "raw-invalid-json-location"
