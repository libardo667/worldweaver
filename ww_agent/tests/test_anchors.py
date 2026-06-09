from __future__ import annotations

from src.runtime.anchors import extract_anchors


def test_pulls_article_headed_concrete_phrases():
    texts = ["The keeper's voice is a warmth against the cooling room.", "the tea in my cup is a dark eye."]
    got = {a["anchor"] for a in extract_anchors(texts)}
    assert "keeper's voice" in got
    assert "cooling room" in got
    assert "tea" in got  # "the tea in my cup" trims at the preposition → "tea"


def test_cuts_at_internal_verbs_and_prepositions():
    # "the house has settled into its bones" should yield "house", not "house has settled"
    got = {a["anchor"] for a in extract_anchors(["the house has settled into its bones"])}
    assert "house" in got
    assert not any("settled" in a for a in got)


def test_filters_abstract_function_nouns():
    got = {a["anchor"] for a in extract_anchors(["the moment passed", "a kind of feeling", "the way of things"])}
    assert got == set()  # moment / feeling / way / things are all abstract → nothing concrete


def test_salience_is_recurrence_normalized_to_peak():
    texts = ["the house is quiet", "the house hums", "the house holds", "a copper button"]
    anchors = {a["anchor"]: a["salience"] for a in extract_anchors(texts)}
    assert anchors["house"] == 1.0  # most recurrent → peak
    assert 0.0 < anchors["copper button"] < 1.0


def test_structured_entities_count_double_and_get_normalized():
    # a named resident present in the scene is an unambiguous anchor, weighted up
    anchors = {a["anchor"]: a["salience"] for a in extract_anchors([], structured=["Sun_Li"])}
    assert "sun li" in anchors and anchors["sun li"] == 1.0


def test_empty_in_empty_out():
    assert extract_anchors([]) == []
    assert extract_anchors(["", "   "]) == []
