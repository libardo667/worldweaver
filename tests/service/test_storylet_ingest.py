"""Unit tests for the storylet ingest service."""

from unittest.mock import patch

from src.services.storylet_ingest import (
    assign_spatial_to_storylets,
    deduplicate_and_insert,
    postprocess_new_storylets,
)


def _storylet(title: str = "ingest-test") -> dict:
    return {
        "title": title,
        "text_template": "Some text.",
        "requires": {},
        "choices": [{"label": "Continue", "set": {}}],
        "weight": 1.0,
    }


def test_deduplicate_and_insert_inserts_valid_storylet(db_session):
    created, skipped = deduplicate_and_insert(db_session, [_storylet("ingest-valid")])
    assert len(created) == 1
    assert skipped == 0
    assert created[0]["title"] == "ingest-valid"


def test_assign_spatial_to_storylets_returns_int(seeded_db):
    from src.models import Storylet

    titles = [storylet.title for storylet in seeded_db.query(Storylet).limit(2).all()]
    updates = assign_spatial_to_storylets(seeded_db, titles)
    assert isinstance(updates, int)


@patch("src.services.embedding_service.embed_all_storylets", return_value=1)
def test_postprocess_new_storylets_returns_expected_shape(_mock_embed, db_session):
    result = postprocess_new_storylets(
        db=db_session,
        storylets=[_storylet("ingest-postprocess")],
        improvement_trigger="test-trigger",
        assign_spatial=False,
    )

    assert result["added"] == 1
    assert result["skipped"] == 0
    assert isinstance(result["storylets"], list)
    assert result["spatial_updates"] == 0
