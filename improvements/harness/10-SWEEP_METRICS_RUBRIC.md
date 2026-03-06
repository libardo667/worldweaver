# Sweep Metrics Rubric

Canonical reference for every metric emitted by the playtest harness. Use this when reading run artifacts, comparing configs, or deciding whether a result is trustworthy evidence.

All metrics live in `playtest_harness/long_run_harness.py` (per-run) and `playtest_harness/parameter_sweep.py` (aggregation + phase summaries). Field names below match exactly what appears in JSON artifacts.

---

## Reliability

| Field | Level | Formula / Source |
|---|---|---|
| `request_count` | run | total HTTP requests made |
| `failed_request_count` | run | requests that returned an error |
| `failure_rate` | run / phase | `failed / request_count`; 0.0 = perfect, 1.0 = total failure |
| `failure_rate` | phase | averaged across configs (`_aggregate_phase_b_metrics`) |

**Threshold:** any config with `failure_rate >= 1.0` produced no usable data. Configs with `failure_rate > 0.1` are considered unreliable baselines.

---

## Latency

| Field | Level | Meaning |
|---|---|---|
| `latency_ms_avg` | run / phase | mean request round-trip duration |
| `latency_ms_p95` | run / phase | 95th-percentile request duration |
| `request_latency_ms_avg` | run | alias for `latency_ms_avg` (explicit name) |
| `request_latency_ms_p95` | run | alias for `latency_ms_p95` |
| `turn_wallclock_ms_avg` | run | per-turn wall time including prefetch wait |
| `turn_wallclock_ms_p95` | run | 95th-percentile turn wall time |
| `prefetch_wait_ms_total` | run | cumulative time spent waiting for prefetch |
| `prefetch_wait_ms_avg` | run | average prefetch wait per turn |
| `prefetch_wait_ms_p95` | run | 95th-percentile prefetch wait |
| `harness_overhead_ms_total` | run | elapsed time not accounted for by requests |
| `harness_overhead_ms_avg_per_request` | run | overhead per request |
| `non_setup_non_prefetch_overhead_ms_total` | run | overhead after subtracting setup and prefetch wait |
| `setup_total_ms` | run | bootstrap + model switch + clean reset total |
| `bootstrap_ms` | run | time to run `/session/bootstrap` |
| `hard_reset_ms` | run | time to purge + reboot backend between configs |
| `switch_model_ms` | run | time to switch model if `switch_model=True` |

**Composite score latency component:** `1.0 / (1.0 + latency_ms_avg / 1200.0)` — weight 0.15. The 1200 ms reference point means a run averaging 1200 ms/request scores 0.5 on this component.

---

## Repetition

### Hard prefix repetition
| Field | Level | Meaning |
|---|---|---|
| `exact_prefix_match_rate` | run / phase | fraction of turns whose first N chars exactly matched a prior turn |
| `prefix_chars` | run | prefix window width (default 80 chars) |
| `prefix_non_empty_turns` | run | turns with non-empty narrative (denominator) |
| `prefix_unique_count` | run | number of unique prefixes seen |
| `prefix_duplicate_count` | run | number of exact-duplicate prefix occurrences |
| `exact_prefix_matches` | run | count of exact matches |

### Soft prefix repetition (embedding similarity)
| Field | Level | Meaning |
|---|---|---|
| `prefix_soft_match_rate` | run / phase | fraction of turns with cosine similarity to prior turn above threshold |
| `prefix_soft_match_threshold` | run | similarity threshold used (default 0.2) |
| `prefix_soft_matches` | run | count of soft-match occurrences |
| `prefix_similarity_avg` | run / phase | mean cosine similarity across consecutive turn pairs |
| `prefix_similarity_p95` | run / phase | 95th-percentile cosine similarity |
| `prefix_max_similarity` | run | highest single-pair similarity observed |
| `prefix_top_reused` | run | up to 5 most-repeated prefix strings |

**Composite score repetition component:** `1.0 - max(exact_prefix_match_rate, prefix_soft_match_rate)` — weight 0.25. Higher repetition = lower score.

---

## Motif coherence

Motif tokens are significant content words extracted from each turn's narrative. High reuse means the narrator is cycling the same vocabulary; high novelty means each turn introduces fresh language.

| Field | Level | Meaning |
|---|---|---|
| `motif_turns_with_tokens` | run | turns from which at least one motif token was extracted |
| `motif_total_tokens` | run | sum of all motif tokens across turns |
| `motif_unique_tokens` | run | number of distinct tokens seen |
| `motif_overlap_count` | run | token occurrences that appeared in a prior turn |
| `motif_reused_tokens` | run | distinct tokens that were reused at least once |
| `motif_novelty_rate` | run / phase | `unique_tokens / total_tokens` |
| `motif_reuse_rate` | run / phase | `reused_tokens / unique_tokens` |
| `motif_turn_overlap_rate_avg` | run / phase | mean per-turn fraction of tokens already seen |
| `motif_top_reused` | run | up to 10 most-frequently reused tokens |

**`motif_penalty_score`** (composite):
```
(0.6 × motif_reuse_rate) + (0.4 × motif_turn_overlap_rate_avg)
```
Lower is better. 0.0 = perfectly fresh language; 1.0 = total repetition.

**Composite score motif component:** `1.0 - motif_reuse_rate` — weight 0.05.

---

## Projection lane

Projection stubs are pre-computed scene seeds generated speculatively. A "hit" means the narrator used the stub instead of cold-generating.

| Field | Level | Meaning |
|---|---|---|
| `projection_stub_count` | run | turns where a stub was available |
| `projection_hit_rate` | run / phase | fraction of stub opportunities where the stub was used |
| `projection_waste_rate` | run / phase | fraction of stubs generated but not used |
| `projection_veto_rate` | run / phase | fraction of opportunities where a stub was discarded by the referee |

**`_projection_penalty_score`** (used for projection-efficiency ranking):
```
(waste_rate × 0.45) + (veto_rate × 0.35) + ((1 - hit_rate) × 0.20)
```
Lower is better.

---

## Clarity distribution

Clarity levels measure how far the projection system advanced a session's next-turn seed. The five levels in ascending order: `unknown` → `rumor` → `lead` → `prepared` → `committed`. `prepared` means a scene-ready seed exists for the next turn.

| Field | Level | Meaning |
|---|---|---|
| `clarity_level_distribution` | run / phase | dict `{level: count}` for all five levels |
| `clarity_distribution_score` | run | weighted scalar in [0, 1] (see formula below) |
| `clarity_distribution_score_avg` | phase aggregate | averaged across runs per config |
| `clarity_distribution_score_avg` | phase summary | averaged across all configs in the phase |
| `clarity_health_warning` | run | non-empty string if distribution is degenerate; `""` means healthy |
| `clarity_health_flags` | phase summary | list of `{"config_id": "...", "warning": "..."}` for flagged configs |

**`clarity_distribution_score` formula:**
```
weights = {unknown: 0.0, rumor: 0.25, lead: 0.5, prepared: 1.0, committed: 1.0}
score   = sum(weight × count) / total_turns
```
Returns 0.0 if no turns are recorded.

**`clarity_health_check` triggers a warning when:**
- All turns are at `unknown` (zero non-unknown turns), or
- `clarity_distribution_score < 0.05` (fewer than ~5% of turns reached `prepared` or above)

**Minimum acceptable threshold:** `clarity_distribution_score_avg >= 0.05` for a run to be considered valid projection-lane evidence. Runs below this threshold show the projection system is effectively not functioning for that config.

---

## Fallback reasons

| Field | Level | Meaning |
|---|---|---|
| `fallback_reason_distribution` | run / phase | dict `{reason: count}` explaining why JIT narration fell back |

Common reasons: `"projection_veto"`, `"no_stub"`, `"context_mismatch"`, `""` / `"none"` (no fallback, narration succeeded from stub).

---

## Action-source mix (minor 112)

Tracks what fraction of turns were driven by choice buttons vs. freeform actions (diversity injections from the harness).

| Field | Level | Meaning |
|---|---|---|
| `choice_turns` | run | turns where `action_source == "choice_button"` |
| `freeform_turns` | run | turns where `action_source` starts with `"diversity"` |
| `diversity_turns` | run | alias for `freeform_turns` |
| `choice_turn_pct` | run | `choice_turns / (choice_turns + freeform_turns)` |
| `freeform_turn_pct` | run | `freeform_turns / (choice_turns + freeform_turns)` |

### Per-source metric slices (`stratified_metrics`)

Both the per-run summary and the phase aggregate include `stratified_metrics: {choice: {...}, freeform: {...}}` where each sub-dict contains:

| Sub-field | Meaning |
|---|---|
| `turn_count` | number of turns in this source group |
| `latency_ms_avg` | mean request latency for this source |
| `failure_rate` | fraction of this source's turns that errored |
| `projection_hit_rate` | projection hit rate for this source |
| `projection_waste_rate` | projection waste rate for this source |
| `projection_veto_rate` | projection veto rate for this source |
| `clarity_level_distribution` | per-level counts for this source |

**Interpretation:** if `freeform_turn_pct == 0.0`, all projection and clarity evidence comes from the choice-button path only. Compare `choice.projection_hit_rate` vs `freeform.projection_hit_rate` to diagnose whether the projection lane is selectively beneficial.

---

## Turn pipeline diagnostics (major 109)

Emitted per turn in `_ww_diag` (embedded in `vars` of each turn response). Not aggregated in harness summaries today but visible in per-turn JSON artifacts.

| Field | Values | Meaning |
|---|---|---|
| `turn_source` | `"initial_scene"`, `"choice_button"`, `"freeform_action"` | which endpoint / input mode produced this turn |
| `pipeline_mode` | `"jit_beat"`, `"engine_idle_fallback"`, `"storylet_selection"`, `"staged_action"`, `"direct_action"` | which narration path was taken |

`initial_scene` turns (empty vars, no choice) are the first turn from `/session/start` or a cold `/next`. These should always use `turn_source="initial_scene"` and are excluded from action-source mix percentages.

---

## Composite score

`score_run_metrics` combines four components into a single scalar for ranking:

```
composite_score =
    (1 - failure_rate)                                           × 0.55
  + (1 - max(exact_prefix_match_rate, prefix_soft_match_rate))  × 0.25
  + (1 - motif_reuse_rate)                                      × 0.05
  + 1 / (1 + latency_ms_avg / 1200)                            × 0.15
```

Range [0, 1]. Higher is better. Failure dominates (55% weight) — a run with 30% failure rate loses 0.165 composite points before any quality signals are considered.

**Note:** the composite score does not yet incorporate clarity or projection quality. Major 111 will rebalance weights to include `clarity_distribution_score` and a projection efficiency term.

---

## Phase summary quality gate outcomes

Every phase A and phase B summary includes a `quality_gate_outcomes` block:

| Field | Meaning |
|---|---|
| `shared_seed_schedule_validated` | all configs in this phase used the same seed sequence |
| `projection_quality_metrics_present` | at least one run reported projection stub metrics |
| `clarity_distribution_score_avg` | mean clarity score across all configs in this phase |
| `clarity_health_flags` | list of `{config_id, warning}` for configs with degenerate clarity |

`clarity_health_flags: []` means all configs passed the clarity gate. Non-empty means at least one config ran an effectively blind projection system.

---

## Bootstrap and setup

| Field | Level | Meaning |
|---|---|---|
| `bootstrap_state` | run | `"completed"` or error string from `/session/bootstrap` |
| `bootstrap_storylets_created` | run | number of storylets seeded during bootstrap |
| `bootstrap_sample_titles` | run | first 3 storylet titles (spot-check readability) |
| `bootstrap_embeddings_computed` | run | whether embeddings were computed during bootstrap |
| `bootstrap_gate_failed` | run | `True` if bootstrap did not return `"completed"` state |
| `clean_reset_verification_enabled` | run | whether inter-run state isolation was verified |
| `clean_reset_verification_passed` | run | whether all counters were zero after hard reset |
| `clean_reset_snapshot` | run | variable values observed at reset checkpoint |

---

## Reading a run artifact

When skimming a JSON run report, check in this order:

1. `bootstrap_gate_failed` — if `True`, the run produced no valid data.
2. `failure_rate` — above 0.1 means unreliable; above 0.5 means discard.
3. `clarity_health_warning` — non-empty means the projection system was blind for this run.
4. `clarity_distribution_score` — below 0.05 confirms the warning; above 0.3 suggests healthy projection.
5. `projection_hit_rate` vs `projection_waste_rate` — are stubs being used or thrown away?
6. `motif_penalty_score` — above 0.5 suggests the narrator is in a vocabulary rut.
7. `prefix_soft_match_rate` — above 0.3 suggests semantic repetition even if exact matches are low.
8. `stratified_metrics` — if `freeform_turn_pct > 0`, check whether quality differs between sources.
9. `composite_score` (phase aggregate) — for final ranking.
