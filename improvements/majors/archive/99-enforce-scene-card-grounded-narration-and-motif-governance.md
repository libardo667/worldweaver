# Major 99: Enforce scene-card-grounded narration and motif governance

## Metadata

- ID: 99-enforce-scene-card-grounded-narration-and-motif-governance
- Type: major
- Owner: levi
- Status: implemented
- Risk: medium
- Target Window: 2026-03
- Depends On: 69-implement-clean-3-layer-llm-architecture

## Problem

Narration quality degrades under longer `/next`-dominant sweeps due to motif gravity (repeated sensory anchors like ozone/neon/rain), even when structural selection is healthy.

Current gaps against product vision:

- Scene-card grounding is not enforced uniformly in narrator-facing adaptation paths.
- No persistent motif ledger exists in session state to prevent short-horizon style repetition.
- No deterministic motif extraction step exists after narration commits.
- No referee-style style auditor exists to reject/revise over-repetitive drafts.
- No positive, scene-card-derived sensory palette is provided to increase grounded variety.

Net result: outputs can drift toward generic atmospheric defaults instead of reflecting on-stage constraints and immediate stakes.

## Proposed Solution

Implement a motif-governance subsystem aligned with the 3-layer architecture and scene-card discipline.

Scope:

1. Add a bounded motif ledger in session state (for example `state.recent_motifs`) with rolling retention (for example last 20-40 motifs).
2. Add deterministic post-narration motif extraction:
   - lightweight phrase extraction from narration text,
   - append extracted motifs to ledger with dedupe and cap.
3. Add scene-card palette generation per turn (smell/sound/tactile/material/object anchors) derived from:
   - `location`,
   - `cast_on_stage`,
   - `constraints_or_affordances`,
   - `immediate_stakes`.
4. Enforce narrator prompt rules:
   - avoid motifs in `motifs_recent` unless explicitly supported by scene card/recent events,
   - use at least N palette anchors (default 2) per narration when available.
5. Add referee palette-auditor lane:
   - input: scene card + motifs_recent + narrator draft,
   - output: `ok` or `revise` + overused motifs + replacement anchors,
   - on `revise`, perform one bounded re-render pass.
6. Keep route contracts unchanged and preserve deterministic reducer ownership of state mutations.

## Files Affected

- `src/services/turn_service.py`
- `src/services/llm_service.py`
- `src/services/command_interpreter.py`
- `src/services/prompt_library.py`
- `src/services/state_manager.py`
- `src/models/schemas.py` (only if internal metadata schema updates are required)
- `tests/service/test_llm_service.py`
- `tests/service/test_turn_service.py` (or nearest turn orchestration coverage)
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [x] `/next` narration receives `scene_card_now`, `goal_lens`, and `motifs_recent` in adaptation context.
- [x] Session state persists a bounded motif ledger across turns and trims to configured cap.
- [x] Deterministic motif extraction runs after narrator text commit and updates ledger.
- [x] Narrator prompts explicitly enforce motif anti-reuse and scene-card grounding rules.
- [x] Referee auditor can trigger at most one revise pass when overused motifs are detected.
- [x] No API request/response contract changes are introduced.
- [x] `python -m pytest -q` passes for touched modules and integration paths.

## Validation Commands

- `python -m pytest -q tests/service/test_llm_service.py`
- `python -m pytest -q tests/api/test_game_endpoints.py`
- `python -m pytest -q tests/integration/test_turn_progression_simulation.py`
- `python scripts/dev.py quality-strict`

## Risks & Rollback

Risks:

- Over-constraining narrator prompts may flatten voice and reduce narrative richness.
- Additional referee audit pass can increase latency if not tightly bounded.
- Weak deterministic extraction heuristics may misclassify motifs.

Rollback:

- Disable referee audit pass via feature flag (or set revise budget to zero).
- Disable motif-governance prompt clauses while preserving scene-card wiring.
- Revert motif ledger extraction/updates if quality regresses; keep existing narration path intact.
