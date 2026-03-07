# Add per-lane harness diagnostics: narrator JSON parse rate and referee contract validity rate

## Problem

The sweep harness currently reports aggregate metrics (motif novelty, latency, failure rate, projection hit rate) but cannot attribute quality problems to a specific lane. When a run produces low motif novelty or high latency, there is no way to determine from the harness artifacts whether the issue originated in:

- The scene narrator (adaptation call producing poor JSON, repeating motifs, or timing out)
- The referee (motif audit producing erroneous decisions or failing to parse)
- The projection planner (producing invalid stubs that are vetoed or wasted)

This means that when comparing model configurations in the sweep, a config with a fast but low-quality narrator looks identical in aggregate metrics to one with a slow but high-quality narrator paired with a referee that is failing silently.

The v3 vision's three-lane model is only operationally validated if each lane is independently observable.

## Proposed Solution

1. In `src/services/llm_service.py`, extend the existing runtime metrics emission (via `runtime_metrics`) to record per-call-category outcomes. Specifically, at minimum:
   - **Narrator parse success rate**: after `_extract_json_object` is called on narrator responses, emit a metric indicating whether the parse succeeded or fell back to empty/default. Track separately for `adapt_storylet_to_context` and `_rewrite_text_with_motif_guidance`.
   - **Referee contract validity rate**: after the motif audit call, emit a metric for whether the referee returned a valid `decision` field (`ok`|`revise`) or fell through to the default `ok` due to parse failure or missing field.

2. In `playtest_harness/long_run_harness.py`, collect these per-turn lane diagnostics from the turn response metadata (they should already be present in governance metadata if emitted correctly) and aggregate them into per-run metrics:
   - `narrator_parse_success_rate`: fraction of narrator calls where JSON was valid and non-empty
   - `referee_decision_valid_rate`: fraction of referee audit calls where decision field was `ok` or `revise` (not defaulted)
   - `narrator_revise_decision_rate`: fraction of turns where the referee requested a revise (not just ok-defaulted)

3. Include these aggregated fields in the per-run metrics dict written to phase summary JSON, alongside existing fields. They are additive — existing fields are not changed.

4. Surface the new fields in the `latency_ranked_results` and `motif_ranked_results` views so they appear in summary review artifacts.

## Files Affected

- `src/services/llm_service.py` — emit per-call-category parse/validity metrics
- `playtest_harness/long_run_harness.py` — aggregate lane diagnostic metrics per run
- `tests/integration/test_long_run_harness_helpers.py` — verify new fields present in per-run metrics

## Acceptance Criteria

- [ ] Per-run harness metrics include `narrator_parse_success_rate`, `referee_decision_valid_rate`, and `narrator_revise_decision_rate`.
- [ ] These fields are present in phase A and phase B summary JSON artifacts.
- [ ] When narrator JSON parse fails, `narrator_parse_success_rate` is less than 1.0 for that run.
- [ ] When referee decision field is missing/invalid, `referee_decision_valid_rate` is less than 1.0.
- [ ] Adding these metrics does not change any existing metric field values (additive only).
- [ ] `python scripts/dev.py quality-strict` passes.
