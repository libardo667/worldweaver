# Refresh LLM playtest guide for reproducible agent runs

## Problem
`playtest_harness/LLM_PLAYTEST_GUIDE.md` documents legacy `harness.py` usage and does not describe the canonical `scripts/dev.py sweep` and `long_run_harness` artifact flow now used for reproducible evaluation.

## Proposed Solution
Rewrite the guide as a reproducible agent-playtest protocol.

- Document canonical commands for long-run and sweep entrypoints.
- Define required artifacts (`manifest.json`, per-run JSON/MD, phase summaries).
- Include lane-model and seed discipline requirements.
- Add a troubleshooting section for stale backends, clean reset verification, and fallback-heavy runs.

## Files Affected
- `playtest_harness/LLM_PLAYTEST_GUIDE.md`
- `README.md`

## Acceptance Criteria
- [ ] Guide no longer references obsolete primary workflow assumptions.
- [ ] Guide documents current canonical commands and artifact outputs.
- [ ] Reproducibility checklist includes seed, lane model IDs, and manifest validation.
- [ ] README links to the refreshed guide.
