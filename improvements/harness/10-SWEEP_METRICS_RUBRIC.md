# Sweep Metrics Rubric

Canonical reference for every metric emitted by the playtest harness. Use this when reading run artifacts, comparing configs, or deciding whether a result is trustworthy evidence.

All metrics live in `playtest_harness/long_run_harness.py` (per-run) and `playtest_harness/parameter_sweep.py` (aggregation + phase summaries). Field names below match exactly what appears in JSON artifacts.

---

## Vision Alignment

Every metric group in this rubric traces to one or more pillars of the [V3 product contract](../VISION.md). The three pillars are:

1. **Scene grounding** — every turn delivers a coherent immediate scene grounded in current state (not generic atmosphere).
2. **Canon safety** — world history only changes through reducer-validated commits; speculation is never promoted to canon without a player-triggered commit.
3. **Prepared frontier** — the near-future projection tree is continuously expanded so the next turn is faster and more coherent.

The V3 turn lifecycle maps to the harness observability surface as follows:

| Lifecycle step | What the harness measures |
|---|---|
| **Ack** (immediate response) | `failure_rate` — did the turn endpoint respond at all? |
| **Commit** (reducer-authoritative mutation) | not directly instrumented; `failure_rate` captures commit errors that surface as HTTP errors |
| **Narrate** (scene narrator renders from seed) | `narrator_parse_success_rate`, `exact_prefix_match_rate`, `prefix_soft_match_rate`, `motif_reuse_rate` — did the narrator produce structured, non-repetitive prose? |
| **Hint** (player narrator exposes limited signal) | not currently instrumented by the harness |
| **Weave ahead** (background planner expands frontier) | `projection_hit_rate`, `projection_waste_rate`, `projection_veto_rate`, `prefetch_wait_ms_*`, `clarity_level_distribution` — did the planner finish on time and produce usable seeds? |

The three V3 lanes map to metric groups:

| Lane | Harness observability |
|---|---|
| **World narrator (planner/referee)** | `projection_*`, `clarity_*`, `referee_decision_valid_rate`, `narrator_revise_decision_rate`, `fallback_reason_distribution` |
| **Scene narrator** | `narrator_parse_success_rate`, repetition metrics (`exact_prefix_match_rate`, `prefix_soft_match_rate`), `motif_*` |
| **Player narrator (hint filter)** | not yet instrumented |

---

## Reliability

| Field | Level | Formula / Source |
|---|---|---|
| `request_count` | run | total HTTP requests made |
| `failed_request_count` | run | requests that returned an error |
| `failure_rate` | run / phase | `failed / request_count`; 0.0 = perfect, 1.0 = total failure |
| `failure_rate` | phase | averaged across configs (`_aggregate_phase_b_metrics`) |

**Threshold:** any config with `failure_rate >= 1.0` produced no usable data. Configs with `failure_rate > 0.1` are considered unreliable baselines.

**Vision link:** Pillar 1 (Scene grounding) and Pillar 3 (Prepared frontier) — both require turns to complete successfully. `failure_rate` is the gate metric: a run with high failure rate has produced no evidence about narration quality or projection health.

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

**Composite score latency component:** `1.0 / (1.0 + latency_ms_avg / 1200.0)` — weight 0.10 (reduced from 0.15 in major 111). The 1200 ms reference point means a run averaging 1200 ms/request scores 0.5 on this component.

**Vision link:** Pillar 3 (Prepared frontier) — `prefetch_wait_ms_*` directly measures whether the "Weave ahead" step (background planner) finishes before the player's next turn. If `prefetch_wait_ms_avg` is high, the planner is the bottleneck. `harness_overhead_ms_*` measures V3's goal of "near-zero hidden harness overhead inflation" — high values indicate the harness itself is distorting sweep results.

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

**Composite score repetition component:** `1.0 - max(exact_prefix_match_rate, prefix_soft_match_rate)` — weight 0.20 (reduced from 0.25 in major 111). Higher repetition = lower score.

**Vision link:** Pillar 1 (Scene grounding) — the vision requires each turn to deliver a scene grounded in *current* state, not generic atmosphere. Repetitive scene openings are the primary symptom of a scene narrator that has drifted from the world state into template-cycling. `prefix_soft_match_rate` catches semantic repetition even when exact phrasing varies, which is the more common real-world failure mode once exact matches are trained away.

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

**Vision link:** Pillar 1 (Scene grounding) and World narrator lane — motif governance is the mechanism by which the world narrator's referee role enforces vocabulary freshness across turns. `motif_reuse_rate` above 0.5 suggests the scene narrator is operating in a vocabulary rut that the referee is not correcting. `narrator_revise_decision_rate` (Minor 114) is the direct measure of how often the referee actively intervened to break that rut.

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

**Vision link:** Pillar 3 (Prepared frontier) and World narrator lane — these metrics directly observe the "Weave ahead" lifecycle step. `projection_hit_rate` measures how often the scene narrator (Step 3 "Narrate") could consume a pre-computed seed from the background planner (Step 5 "Weave ahead"). `projection_waste_rate` measures how often the planner did work that was discarded — either because the referee vetoed the stub or because no stub was selected. `projection_veto_rate` specifically measures World narrator referee rejections: the referee saw a speculative stub but judged it implausible against the current world state, enforcing Pillar 2 (Canon safety) for the speculative tier.

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

**Vision link:** Pillar 3 (Prepared frontier) — clarity levels are the V3 vision's own vocabulary (`unknown` → `rumor` → `lead` → `prepared` → `committed`). The distribution score measures how far the background planner is actually advancing the projection frontier before each turn. A run where most turns are `unknown` or `rumor` means the "Weave ahead" step is producing no actionable seeds — the scene narrator is effectively cold-generating every turn, violating the prepared-frontier promise.

---

## Fallback reasons

| Field | Level | Meaning |
|---|---|---|
| `fallback_reason_distribution` | run / phase | dict `{reason: count}` explaining why JIT narration fell back |

Common reasons: `"projection_veto"`, `"no_stub"`, `"context_mismatch"`, `""` / `"none"` (no fallback, narration succeeded from stub).

**Vision link:** Pillar 3 (Prepared frontier) and World narrator lane — fallback reasons are the diagnostic layer for *why* the prepared frontier failed for a given turn. `"no_stub"` means the planner didn't finish in time or produced nothing; `"context_mismatch"` means the stub was structurally present but misaligned with the committed world state (a canon safety signal); `"projection_veto"` means the referee actively rejected it. Each reason points to a different failure mode in the "Weave ahead" step.

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

**Vision link:** Pillar 1 (Scene grounding) — freeform player actions are higher entropy than choice-button selections and exercise the "Commit" step more aggressively (the reducer must handle unconstrained deltas). If `freeform.failure_rate` is significantly higher than `choice.failure_rate`, it signals that reducer validation or the action interpreter is fragile under free input. Stratified projection metrics reveal whether the "Weave ahead" step degrades when the commit step was less predictable.

---

## Turn pipeline diagnostics (major 109)

Emitted per turn in `_ww_diag` (embedded in `vars` of each turn response). Not aggregated in harness summaries today but visible in per-turn JSON artifacts.

| Field | Values | Meaning |
|---|---|---|
| `turn_source` | `"initial_scene"`, `"choice_button"`, `"freeform_action"` | which endpoint / input mode produced this turn |
| `pipeline_mode` | `"jit_beat"`, `"engine_idle_fallback"`, `"storylet_selection"`, `"staged_action"`, `"direct_action"` | which narration path was taken |

`initial_scene` turns (empty vars, no choice) are the first turn from `/session/start` or a cold `/next`. These should always use `turn_source="initial_scene"` and are excluded from action-source mix percentages.

**Vision link:** Pillar 1 (Scene grounding) and all three lanes — `turn_source` is the entry classification for the V3 turn lifecycle (which step triggered this turn), and `pipeline_mode` identifies which narration path the scene narrator took in Step 3 "Narrate". These fields are the routing audit trail: if a config has unexpected `pipeline_mode` distributions, the narration architecture is not behaving as designed. `"jit_beat"` indicates the projection-seeded fast path; `"engine_idle_fallback"` indicates cold generation with no seed.

---

## Per-lane diagnostics (minor 114)

Per-run and per-phase aggregates. These metrics observe the *internal contract compliance* of each narrative lane — not just whether turns succeeded, but whether the lane's LLM calls produced structurally valid outputs.

| Field | Level | Meaning |
|---|---|---|
| `narrator_parse_attempts` | run | turns where `narrator_parse_success` was recorded (excludes `initial_scene` and heuristic-adapted turns) |
| `narrator_parse_success_rate` | run / phase | fraction of instrumented turns where the scene narrator returned a parseable JSON payload with `text` or `narrative` present |
| `referee_call_attempts` | run | turns where the world narrator referee was invoked and not skipped (`referee_decision` not `"skipped"` or `"disabled_budget"`) |
| `referee_decision_valid_rate` | run / phase | fraction of referee invocations that returned a valid `ok` or `revise` decision (vs. defaulting because the model returned garbage) |
| `narrator_revise_decision_rate` | run / phase | fraction of referee invocations that returned `revise` — the referee's active veto signal |

**Source:** `narrator_parse_success` is set in `llm_service.adapt_storylet_to_context` and propagated to `_ww_diag` via `turn_service._inject_next_diagnostics`. `referee_decision_valid` and `referee_decision` are set in `llm_service._run_motif_referee_audit` and flow through `_apply_motif_governance_to_text` → `motif_governance` dict → `turn_service` → `_ww_diag`.

**Neutral defaults:** `narrator_parse_success_rate` defaults to 1.0 when no turns have the field (e.g. a run using only heuristic adaptation). `referee_decision_valid_rate` defaults to 1.0. `narrator_revise_decision_rate` defaults to 0.0.

**Vision link:** Scene narrator lane (`narrator_parse_success_rate`) and World narrator lane (`referee_decision_valid_rate`, `narrator_revise_decision_rate`).

- `narrator_parse_success_rate` is Pillar 1 observability: did the scene narrator (Step 3 "Narrate") return a valid structured output, or did it hallucinate outside the expected schema? A rate below 1.0 means the harness was forced to fall back to raw text extraction, which degrades scene grounding quality silently in production.
- `referee_decision_valid_rate` is Pillar 2 (Canon safety) for the speculative tier: when the world narrator referee evaluates a projection stub, does it return a contract-compliant decision? A rate below 1.0 means the referee silently defaulted to `ok`, potentially allowing garbage stubs into the projection tree that will later produce incoherent scenes.
- `narrator_revise_decision_rate` is the World narrator's active enforcement signal: a rate near 0.0 with high `motif_reuse_rate` suggests the referee is failing to catch vocabulary ruts. A rate above 0.3 suggests the referee is working hard — which may reflect genuinely repetitive narrator output rather than a misconfigured system.

**Planner lane validation note:** The sweep cannot currently directly observe whether projection stubs produced by the background planner ("Weave ahead") are structurally valid — there is no `ProjectionStubContract` equivalent to the `ActionDeltaContract` used for canonical action deltas. The downstream symptoms of garbage stubs are visible as: elevated `projection_waste_rate` (referee vetoes bad stubs), `clarity_distribution_score` near zero (stubs never reach `prepared`), and elevated `narrator_revise_decision_rate` (the referee intervenes repeatedly on the rendered output). If all three are elevated simultaneously, suspect stub quality upstream of the narration step.

---

## Composite score

`score_run_metrics` combines six components into a single scalar for ranking (updated in minor 117):

```
composite_score =
    (1 - failure_rate)                                           × 0.50
  + (1 - max(exact_prefix_match_rate, prefix_soft_match_rate))  × 0.20
  + (1 - motif_reuse_rate)                                      × 0.05
  + 1 / (1 + latency_ms_avg / 1200)                            × 0.05
  + projection_component                                         × 0.10
  + clarity_distribution_score                                   × 0.10
```

where `projection_component` is derived from hit and waste rates:

```
penalty = (waste_rate × 0.60) + ((1 - hit_rate) × 0.40)
projection_component = 1.0 - penalty
```

When `projection_hit_rate` and `projection_waste_rate` are both absent (old callers), `projection_component` defaults to `0.5` (neutral).

When `clarity_distribution_score` is absent (old callers / pre-minor-115 runs), the clarity component defaults to `0.5` (neutral).

Range [0, 1]. Higher is better. Failure dominates (50% weight) — a run with 30% failure rate loses 0.15 composite points before any quality signals are considered.

**Perfect score:** a run with zero failure rate, no repetition, fully novel motifs, near-zero latency, perfect projection quality, and `clarity_distribution_score=1.0` scores `1.0`.

### Pre-minor-117 formula (historical reference)

```
composite_score =
    (1 - failure_rate)                                           × 0.50
  + (1 - max(exact_prefix_match_rate, prefix_soft_match_rate))  × 0.20
  + (1 - motif_reuse_rate)                                      × 0.05
  + 1 / (1 + latency_ms_avg / 1200)                            × 0.10
  + projection_component                                         × 0.15
```

Sweep artifacts from runs before minor 117 used this formula. Cross-sweep composite score comparisons spanning that boundary are not directly comparable.

### Pre-major-111 formula (historical reference)

```
composite_score =
    (1 - failure_rate)                                           × 0.55
  + (1 - max(exact_prefix_match_rate, prefix_soft_match_rate))  × 0.25
  + (1 - motif_reuse_rate)                                      × 0.05
  + 1 / (1 + latency_ms_avg / 1200)                            × 0.15
```

Sweep artifacts from runs before major 111 used this formula. Cross-sweep composite score comparisons spanning that boundary are not directly comparable.

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

## Projection health warnings (major 111)

Per-run records include `projection_health_warnings: list[str]` — informational only, do not disqualify configs from Phase B promotion.

A warning is raised when any of these conditions hold:
- `projection_waste_rate > 0.90` — prefetch is discarded nearly every turn (prefetch lane effectively idle)
- No turns reached `prepared` or `committed` clarity — projection system produced no scene-ready stubs
- `projection_hit_rate == 0.0` for a run with `> 10` turns — projections existed but were never used

Phase summaries include a `projection_health_summary` block:

```json
{
  "configs_with_warnings": ["a03", "a07"],
  "warning_count": 4,
  "warnings": [
    {"config_id": "a03", "warning": "projection_waste_rate=0.97 > 0.90 threshold (prefetch nearly never used)"},
    ...
  ]
}
```

A phase with `projection_health_summary.warning_count > 0` does not need to be rerun — but configs in `configs_with_warnings` should be inspected before being promoted to Phase B.

## Ranking views in phase summaries

Phase A and Phase B summaries include multiple ranked views of the same results:

| Field | Sort criterion | Use |
|---|---|---|
| `results` / `recommended_configs` | composite score (desc) | primary promotion list |
| `motif_ranked_results` / `recommended_motif_configs` | `motif_penalty_score` (asc) | find freshest-language configs |
| `projection_ranked_results` / `recommended_projection_configs` | `_projection_penalty_score` (asc) | find most efficient projection configs |
| `clarity_ranked_results` / `top_clarity_candidates` (A) / `recommended_clarity_configs` (B) | `clarity_distribution_score` (desc) | find configs where projection lane actually reached `prepared` |
| `latency_ranked_results` / `recommended_latency_configs` | failure rate then latency (asc) | find lowest-latency reliable configs |

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
