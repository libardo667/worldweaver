"""The server-side concordance gate (src/services/growth_service.py).

The cure for the March field-journal disease: a theme becomes soul only when it
*recurs across separate days*, never from a single runaway session.
"""

from src.models import ResidentIdentityGrowth
from src.services.growth_service import append_growth_proposals, promote_growth

# A deterministic bag-of-words embedder: bodies sharing words cluster; different
# themes don't. Stands in for the server embedding service in unit tests.
_VOCAB = ["sill", "stay", "window", "river", "hum", "current", "quiet", "belong"]


def _embed(text: str) -> list[float]:
    t = str(text).lower()
    return [float(t.count(w)) for w in _VOCAB]


def _zero_embed(text: str) -> list[float]:
    return [0.0] * len(_VOCAB)  # AI disabled → fallback zero vectors


def _row() -> ResidentIdentityGrowth:
    return ResidentIdentityGrowth(actor_id="r1", growth_text="", growth_metadata={}, growth_proposals=[])


def _prop(body: str, pulse_id: str, day: int) -> dict:
    return {"body": body, "pulse_id": pulse_id, "ts": f"2026-06-{day:02d}T12:00:00+00:00"}


# --- the gate promotes a recurring theme ---

def test_promotes_a_theme_recurring_across_days():
    row = _row()
    row.growth_proposals = [
        _prop("I stay on the sill", "p1", 1),
        _prop("staying on the sill", "p2", 2),
        _prop("the sill, where I stay", "p3", 2),
    ]
    res = promote_growth(row, embed_fn=_embed)
    assert res["promoted"] == 1
    assert "sill" in row.growth_text
    assert set(row.growth_metadata["promoted_pulse_ids"]) == {"p1", "p2", "p3"}


# --- the cure: a single-session burst CANNOT rewrite the soul ---

def test_does_not_promote_a_single_day_burst():
    row = _row()
    row.growth_proposals = [
        _prop("I stay on the sill", "p1", 1),
        _prop("staying on the sill", "p2", 1),
        _prop("the sill, where I stay", "p3", 1),  # all the same day
    ]
    res = promote_growth(row, embed_fn=_embed)
    assert res["promoted"] == 0
    assert res["status"] == "none_mature"
    assert row.growth_text == ""  # the March disease, designed out


def test_does_not_promote_below_concordance():
    row = _row()
    row.growth_proposals = [_prop("I stay on the sill", "p1", 1), _prop("staying on the sill", "p2", 2)]
    res = promote_growth(row, embed_fn=_embed)
    assert res["promoted"] == 0
    assert res["status"] == "below_concordance"


def test_does_not_promote_scattered_singletons():
    row = _row()
    row.growth_proposals = [
        _prop("the sill", "p1", 1),
        _prop("the river hum", "p2", 2),
        _prop("the quiet current", "p3", 3),
    ]
    res = promote_growth(row, embed_fn=_embed)
    assert res["promoted"] == 0
    assert res["status"] == "none_mature"  # 3 candidates, but no theme recurs


# --- it doesn't re-promote, and dedups against what's already soul ---

def test_does_not_re_promote_the_same_proposals():
    row = _row()
    row.growth_proposals = [_prop("I stay on the sill", "p1", 1), _prop("staying on the sill", "p2", 2), _prop("the sill where I stay", "p3", 2)]
    promote_growth(row, embed_fn=_embed)
    text_after_first = row.growth_text
    res2 = promote_growth(row, embed_fn=_embed)
    assert res2["promoted"] == 0
    assert row.growth_text == text_after_first  # promoted ids are remembered


def test_dedups_against_existing_growth():
    row = _row()
    row.growth_text = "I stay on the sill\n"  # already part of the soul
    row.growth_proposals = [_prop("I stay on the sill", "p1", 1), _prop("I stay on the sill", "p2", 2), _prop("I stay on the sill", "p3", 2)]
    res = promote_growth(row, embed_fn=_embed)
    assert res["promoted"] == 0
    assert res["status"] == "all_deduped"
    assert row.growth_text == "I stay on the sill\n"  # not duplicated
    assert set(row.growth_metadata["promoted_pulse_ids"]) == {"p1", "p2", "p3"}  # but consumed


# --- the feed + the fail-closed guarantee ---

def test_append_growth_proposals_dedups_by_pulse_id():
    row = _row()
    n1 = append_growth_proposals(row, [_prop("a", "p1", 1), _prop("b", "p2", 1)])
    n2 = append_growth_proposals(row, [_prop("b again", "p2", 1), _prop("c", "p3", 2)])  # p2 already stored
    assert n1 == 2
    assert n2 == 1
    assert len(row.growth_proposals) == 3


def test_fails_closed_without_embeddings():
    row = _row()
    row.growth_proposals = [_prop("I stay on the sill", "p1", 1), _prop("staying on the sill", "p2", 2), _prop("the sill where I stay", "p3", 2)]
    res = promote_growth(row, embed_fn=_zero_embed)  # embeddings unavailable
    assert res["promoted"] == 0  # nothing clusters → the gate fails closed
    assert row.growth_text == ""


# --- Major 61: provenance — what is allowed to become soul ---
# Three law-safe rules layered on concordance: no social-strategy, dischargeable goals
# only, and differential persistence past the population (the world-event null hypothesis).

_VOCAB2 = ["storm", "drains", "drainage", "dahlia", "bloom", "flower", "radio", "mend", "fix", "respond", "notice", "alone"]


def _embed2(text: str) -> list[float]:
    t = str(text).lower()
    return [float(t.count(w)) for w in _VOCAB2]


def _gprop(body: str, pulse_id: str, day: int, kind: str = "soul_edit") -> dict:
    return {"body": body, "pulse_id": pulse_id, "ts": f"2026-06-{day:02d}T12:00:00+00:00", "kind": kind}


# Rule 3 — a social-strategy self-delta is never promoted, however much it recurs.

def test_rule3_never_promotes_a_social_strategy_self_delta():
    row = _row()
    row.growth_proposals = [
        _gprop("I post in the square so that people will respond to me", "s1", 1),
        _gprop("I should speak up more so the others notice me", "s2", 2),
        _gprop("posting so that people will respond to me again", "s3", 3),
    ]
    res = promote_growth(row, embed_fn=_embed2)
    assert res["promoted"] == 0
    assert res["rejected"] == 3  # all three rejected as social instrumentality
    assert row.growth_text == ""
    assert set(row.growth_metadata["rejected_pulse_ids"]) == {"s1", "s2", "s3"}


# Rule 2 — a goal the world affords no finite action to complete never becomes soul.

def test_rule2_never_promotes_an_undischargeable_goal():
    row = _row()
    row.growth_proposals = [
        _gprop("I will end all the loneliness in the whole city", "g1", 1, kind="goal_update"),
        _gprop("I vow to end all loneliness, always", "g2", 2, kind="goal_update"),
        _gprop("I will make everyone in the city feel less alone", "g3", 3, kind="goal_update"),
    ]
    res = promote_growth(row, embed_fn=_embed2)
    assert res["promoted"] == 0
    assert res["rejected"] == 3  # absolute/totalizing vows → reverie-only, never soul
    assert row.growth_text == ""


def test_rule2_promotes_a_dischargeable_goal_that_recurs():
    row = _row()
    row.growth_proposals = [
        _gprop("I will mend the broken radio, fix it", "g1", 1, kind="goal_update"),
        _gprop("I mean to mend that radio and fix it", "g2", 2, kind="goal_update"),
        _gprop("I want to fix and mend the radio", "g3", 2, kind="goal_update"),
    ]
    res = promote_growth(row, embed_fn=_embed2)
    assert res["promoted"] == 1  # a concrete, completable goal can become soul
    assert "radio" in row.growth_text


# Rule 1 — differential persistence: the population is the world-event null hypothesis.

def test_rule1_defers_a_theme_the_population_is_still_on():
    row = _row()
    row.growth_proposals = [
        _gprop("the storm drains and the drainage keep backing up", "d1", 1),
        _gprop("storm drains, the drainage again", "d2", 2),
        _gprop("storm drains and drainage still on my mind", "d3", 2),
    ]
    # The whole population is STILL on storm drainage as of day 2 (concurrent with this mind).
    pop = [{"body": "storm drains drainage", "last_day": "2026-06-02"}]
    res = promote_growth(row, embed_fn=_embed2, population_themes=pop)
    assert res["promoted"] == 0
    assert res["deferred"] == 1  # world-sourced, not yet self-differentiated
    assert row.growth_text == ""
    assert "d1" not in set(row.growth_metadata.get("promoted_pulse_ids") or [])  # not consumed — can promote later


def test_rule1_promotes_when_this_mind_outlasts_the_population():
    row = _row()
    row.growth_proposals = [
        _gprop("the storm drains and the drainage keep backing up", "d1", 4),
        _gprop("storm drains, the drainage again", "d2", 5),
        _gprop("storm drains and drainage still on my mind", "d3", 5),
    ]
    # The population moved on after day 2; this mind kept the theme into day 5 — it grew.
    pop = [{"body": "storm drains drainage", "last_day": "2026-06-02"}]
    res = promote_growth(row, embed_fn=_embed2, population_themes=pop)
    assert res["promoted"] == 1
    assert "drain" in row.growth_text.lower()


def test_rule1_promotes_a_self_sourced_theme_despite_a_population_baseline():
    row = _row()
    row.growth_proposals = [
        _gprop("the dahlia blooms in the flower bed", "f1", 1),
        _gprop("more dahlia blooms, the flower opening", "f2", 2),
        _gprop("the dahlia bloom keeps on, a flower", "f3", 2),
    ]
    # The population is on drainage; this mind's flowers don't match it → self-sourced.
    pop = [{"body": "storm drains drainage", "last_day": "2026-06-09"}]
    res = promote_growth(row, embed_fn=_embed2, population_themes=pop)
    assert res["promoted"] == 1
    assert "dahlia" in row.growth_text or "bloom" in row.growth_text
