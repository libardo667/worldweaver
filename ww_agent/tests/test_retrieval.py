from __future__ import annotations

import asyncio

from src.runtime.drive import DeterministicEmbedder
from src.runtime.retrieval import anchor_generalization_backtest, anchor_retrieval_backtest, anchor_snapshots, transition_learnability, transition_learnability_semantic


def test_retrieval_foresees_an_alternation_that_persistence_cannot():
    # a world that flips a <-> b every step. persistence always predicts "more of
    # the same" and catches none of the flips; retrieval recalls past a-states,
    # sees they were followed by b, and predicts the flip.
    snaps = [{"the keeper"}, {"the bench"}] * 8
    r = asyncio.run(anchor_retrieval_backtest(DeterministicEmbedder(), snaps, k=3, top_n=2, min_history=2))
    assert r["steps"] >= 4
    assert r["new_anchor_recall"]["retrieval"] is not None and r["new_anchor_recall"]["retrieval"] > 0.5
    assert (r["new_anchor_recall"]["persistence"] or 0.0) == 0.0  # structurally blind to change


def test_persistence_wins_on_a_perfectly_stable_world():
    # nothing ever changes → there are no new anchors to foresee; both methods just
    # echo the steady set, and retrieval's recall matches persistence.
    snaps = [{"the red thread", "the frame"}] * 8
    r = asyncio.run(anchor_retrieval_backtest(DeterministicEmbedder(), snaps, k=3, top_n=3, min_history=2))
    assert r["new_anchor_recall"]["retrieval"] is None  # no changes occurred at all
    assert r["retrieval"]["recall"] == 1.0 and r["persistence"]["recall"] == 1.0


def test_anchor_snapshots_reads_observed_events_in_order():
    events = [
        {"event_type": "anchor_observed", "payload": {"observed_ts": "2026-06-03T00:00:00+00:00", "anchors": [{"anchor": "the keeper", "salience": 1.0}, {"anchor": "dust", "salience": 0.2}]}},
        {"event_type": "felt_sense_logged", "payload": {"felt_sense": "noise"}},
        {"event_type": "anchor_observed", "payload": {"observed_ts": "2026-06-03T00:01:00+00:00", "anchors": [{"anchor": "the hearth", "salience": 0.8}]}},
    ]
    snaps = anchor_snapshots(events)
    assert snaps == [{"the keeper", "dust"}, {"the hearth"}]
    # salience floor drops the faint ones
    assert anchor_snapshots(events, salience_floor=0.5) == [{"the keeper"}, {"the hearth"}]


def test_concept_space_recurrence_catches_a_rephrase_that_strings_miss():
    # "red thread" seen, then "red thread now" appears — a different STRING but the
    # same concept. String space calls it first-time; concept space calls it recurring.
    snaps = [{"red thread"}, {"frame"}, {"red thread now"}]
    string_lr = transition_learnability(snaps)
    concept_lr = asyncio.run(transition_learnability_semantic(DeterministicEmbedder(), snaps, threshold=0.7))
    assert string_lr["first_time"] >= 2  # "frame" and "red thread now" both novel as strings
    assert concept_lr["first_time"] < string_lr["first_time"]  # the rephrase collapses into recurring


def test_empty_or_too_short_history_yields_no_steps():
    r = asyncio.run(anchor_retrieval_backtest(DeterministicEmbedder(), [{"a"}], k=3))
    assert r["steps"] == 0


def test_semantic_recall_is_at_least_exact_recall():
    # semantic matching is a relaxation of exact matching (exact hit => cosine 1.0 =>
    # semantic hit at any threshold <= 1), so semantic recall can never be lower.
    snaps = [{"the keeper"}, {"the bench"}] * 6 + [{"the keeper"}, {"keeper waits"}]
    r = asyncio.run(anchor_generalization_backtest(DeterministicEmbedder(), snaps, k=3, top_n=3, sim_threshold=0.2, min_history=2))
    se = r["new_anchor_recall_semantic"]["retrieval"]
    ex = r["new_anchor_recall_exact"]["retrieval"]
    assert se is not None and ex is not None and se >= ex


def test_transition_learnability_separates_recurring_from_first_time():
    # keeper recurs (appears, leaves, reappears = 1 recurring); hearth & dust each
    # appear once for the first time = 2 first-time.
    snaps = [{"keeper"}, {"hearth"}, {"keeper"}, {"dust"}]
    lr = transition_learnability(snaps)
    assert lr["recurring"] == 1 and lr["first_time"] == 2
    assert lr["appeared"] == 3 and lr["learnable_ceiling"] == round(1 / 3, 3)
