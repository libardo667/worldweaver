from __future__ import annotations

from src.runtime.prediction import derive_anchor_scores, derive_prediction_scores, summarize_anchor_prediction, summarize_prediction_quality


def _cast(pulse_id, ts, features, *, scope="self", half_life=120.0, confidence=0.8):
    return {
        "event_type": "afterimage_cast",
        "ts": ts,
        "payload": {"pulse_id": pulse_id, "cast_ts": ts, "scope": scope, "half_life": half_life, "confidence": confidence, "features": features},
    }


def _surprise(ts, features):
    # features: list of (scope, tag, delta)
    return {
        "event_type": "surprise_observed",
        "ts": ts,
        "payload": {"observed_ts": ts, "magnitude": max(d for _, _, d in features), "features": [{"scope": s, "tag": t, "delta": d} for s, t, d in features]},
    }


def test_miss_is_surprise_on_a_claimed_feature():
    # afterimage claims 'rain'; then 'rain' is surprised against → a MISS.
    events = [
        _cast("p1", "2026-06-03T00:00:00+00:00", {"rain": 0.7}),
        _surprise("2026-06-03T00:01:00+00:00", [("self", "rain", 0.5)]),
    ]
    [score] = derive_prediction_scores(events)
    assert score["miss"] == 0.5 and score["blindspot"] == 0.0
    assert score["clean"] is False  # it spoke and was wrong


def test_blindspot_is_surprise_on_an_unclaimed_feature():
    # afterimage claims 'rain'; but 'visitor' is what actually surprised → BLINDSPOT.
    events = [
        _cast("p1", "2026-06-03T00:00:00+00:00", {"rain": 0.7}),
        _surprise("2026-06-03T00:01:00+00:00", [("self", "visitor", 0.6)]),
    ]
    [score] = derive_prediction_scores(events)
    assert score["miss"] == 0.0 and score["blindspot"] == 0.6
    assert score["clean"] is True  # nothing it CLAIMED was violated


def test_surprise_outside_the_lifetime_window_is_not_charged():
    # half_life 60s → window is 3*60 = 180s. A surprise at 10 min is past the watch.
    events = [
        _cast("p1", "2026-06-03T00:00:00+00:00", {"rain": 0.7}, half_life=60.0),
        _surprise("2026-06-03T00:10:00+00:00", [("self", "rain", 0.9)]),
    ]
    [score] = derive_prediction_scores(events)
    assert score["miss"] == 0.0 and score["traces_in_window"] == 0


def test_summary_triad_distinguishes_dark_room_from_learning():
    # A "dark-room" afterimage claims nothing; a speaking one claims and is mostly right.
    events = [
        _cast("silent", "2026-06-03T00:00:00+00:00", {}, half_life=120.0),  # claims nothing → dropped (no features)
        _cast("p1", "2026-06-03T00:05:00+00:00", {"rain": 0.6}),
        _surprise("2026-06-03T00:06:00+00:00", [("self", "rain", 0.05)]),  # tiny → clean-ish
    ]
    summary = summarize_prediction_quality(events)
    # the empty-feature cast is not a valid afterimage; only the speaking one counts
    assert summary["afterimages"] == 1 and summary["spoke"] == 1
    assert summary["silent_fraction"] == 0.0
    assert summary["mean_claims"] == 1.0


def test_empty_ledger_summarizes_to_zero():
    assert summarize_prediction_quality([])["afterimages"] == 0


# --- drive-weighting: the price on boring (reviewer's Rung-3 correction) ---


def test_weighted_miss_counts_a_mattering_feature_for_more():
    # same raw miss on two afterimages; one claimed a feature the soul cares about
    # (weight 0.9), one claimed furniture (weight 0.1). weighted_miss separates them.
    cares = [
        _cast("p1", "2026-06-03T00:00:00+00:00", {"social_pull": 0.7}),
        _surprise("2026-06-03T00:01:00+00:00", [("self", "social_pull", 0.4)]),
    ]
    furniture = [
        _cast("p2", "2026-06-03T00:00:00+00:00", {"dust": 0.7}),
        _surprise("2026-06-03T00:01:00+00:00", [("self", "dust", 0.4)]),
    ]
    weights = {"social_pull": 0.9, "dust": 0.1}
    [c] = derive_prediction_scores(cares, weights=weights)
    [f] = derive_prediction_scores(furniture, weights=weights)
    assert c["miss"] == f["miss"] == 0.4  # identical raw miss
    assert c["weighted_miss"] > f["weighted_miss"]  # being wrong about what matters costs more


def test_claim_mattering_flags_the_dull_world_predictor():
    # a "clean" afterimage (no violations) that only ever predicted furniture
    # should read as clean-but-empty: low claim_mattering despite high clean.
    events = [
        _cast("p1", "2026-06-03T00:00:00+00:00", {"dust": 0.3, "draft": 0.2}),
        _surprise("2026-06-03T00:01:00+00:00", [("self", "dust", 0.02)]),  # below floor → clean
    ]
    weights = {"dust": 0.05, "draft": 0.08, "social_pull": 0.9}
    [s] = derive_prediction_scores(events, weights=weights)
    assert s["clean"] is True  # raw scorer is satisfied
    assert s["claim_mattering"] < 0.1  # but it predicted nothing it cares about — the dull-world tell
    summary = summarize_prediction_quality(events, weights=weights)
    assert summary["clean_fraction"] == 1.0 and summary["mean_claim_mattering"] < 0.1


def test_unweighted_path_leaves_drive_fields_none():
    events = [
        _cast("p1", "2026-06-03T00:00:00+00:00", {"rain": 0.7}),
        _surprise("2026-06-03T00:01:00+00:00", [("self", "rain", 0.5)]),
    ]
    [s] = derive_prediction_scores(events)  # no weights
    assert s["claim_mattering"] is None and s["weighted_miss"] is None


# --- the anchor lane: granular, resident-specific predictions (Major 51) ---


def _anchor_obs(ts, field):  # field: {anchor: salience}
    return {"event_type": "anchor_observed", "ts": ts, "payload": {"observed_ts": ts, "anchors": [{"anchor": k, "salience": v} for k, v in field.items()]}}


def test_anchor_prediction_hits_when_the_anchor_stays_salient():
    events = [_cast("p1", "2026-06-03T00:00:00+00:00", {"the keeper": 0.6}, scope="anchors"), _anchor_obs("2026-06-03T00:01:00+00:00", {"the keeper": 0.7})]
    [s] = derive_anchor_scores(events)
    assert s["hit_rate"] == 1.0 and s["anchor_miss"] < 0.2


def test_anchor_prediction_misses_when_anchor_absent():
    events = [_cast("p1", "2026-06-03T00:00:00+00:00", {"the keeper": 0.8}, scope="anchors"), _anchor_obs("2026-06-03T00:01:00+00:00", {"the hearth": 0.7})]
    [s] = derive_anchor_scores(events)
    assert s["hit_rate"] == 0.0 and s["anchor_miss"] >= 0.7


def test_anchor_claim_mattering_uses_soul_weights():
    events = [_cast("p1", "2026-06-03T00:00:00+00:00", {"the keeper": 0.6, "the dust": 0.6}, scope="anchors"), _anchor_obs("2026-06-03T00:01:00+00:00", {"the keeper": 0.6})]
    s = summarize_anchor_prediction(events, weights={"the keeper": 0.9, "the dust": 0.1})
    assert abs(s["mean_claim_mattering"] - 0.5) < 1e-6  # (0.9 + 0.1) / 2 — and it actually varies, unlike the flat drives


def test_only_anchor_scoped_afterimages_enter_the_anchor_lane():
    events = [
        _cast("p1", "2026-06-03T00:00:00+00:00", {"social_pull": 0.6}),  # scope "self"
        _cast("p2", "2026-06-03T00:00:00+00:00", {"the keeper": 0.6}, scope="anchors"),
        _anchor_obs("2026-06-03T00:01:00+00:00", {"the keeper": 0.6}),
    ]
    assert len(derive_anchor_scores(events)) == 1  # only the anchors-scoped one


def test_anchor_afterimage_does_not_drive_arousal_quiet_guarantee(tmp_path):
    from src.runtime.pulse import Pulse, route_pulse
    from src.runtime.salience import observe_surprise

    # cast ONLY an anchor prediction, then observe with an empty stimulus
    route_pulse(tmp_path, Pulse.from_dict({"expectations": [{"features": {"the keeper": 0.9}, "scope": "anchors", "confidence": 0.9, "half_life": 600}]}), now="2026-06-03T00:00:00+00:00")
    trace = observe_surprise(tmp_path, stimulus={}, now="2026-06-03T00:00:30+00:00")
    assert trace is None  # the anchor lane is held out of the rhythm — no phantom surprise, no arousal


def test_anchor_gating_fires_on_appearance_not_disappearance(tmp_path):
    # the gated counterpart, appearance-weighted (the disappearance-flood fix): with
    # include_anchor_scope, a cared-about anchor SHOWING UP drives surprise, but a
    # predicted anchor merely going ABSENT from the gated top-k does NOT — that absence
    # was flooding the gate (a higher mattering bar shrank the realized set, manufacturing
    # more "missing" predicted anchors). Absence is now free; only appearance wakes it.
    from src.runtime.pulse import Pulse, route_pulse
    from src.runtime.salience import observe_surprise

    route_pulse(tmp_path, Pulse.from_dict({"expectations": [{"features": {"the keeper": 0.9}, "scope": "anchors", "confidence": 0.9, "half_life": 600}]}), now="2026-06-03T00:00:00+00:00")
    # the keeper was predicted but is absent → no INSTANTANEOUS surprise (magnitude 0), but it
    # IS recorded for grief (the slow burn of confirmed loss) rather than dropped entirely.
    trace = observe_surprise(tmp_path, stimulus={"anchors": {}}, now="2026-06-03T00:00:30+00:00", include_anchor_scope=True)
    assert trace is not None and trace["magnitude"] == 0.0
    assert any(g["tag"] == "the keeper" for g in trace.get("grief_field", []))
    # an unpredicted anchor showing up → surprise (the gate still fires on appearance)
    trace = observe_surprise(tmp_path, stimulus={"anchors": {"a sudden noise": 0.9}}, now="2026-06-03T00:01:00+00:00", include_anchor_scope=True)
    assert trace is not None and trace["magnitude"] > 0.1
