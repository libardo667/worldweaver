# Pruning Decision Log

Track every keep/merge/archive/delete decision with evidence.

## Fields
- Date (UTC)
- Path
- Decision (`keep`, `simplify`, `merge`, `demote`, `archive`, `delete`)
- Rationale
- Risk (`low`, `medium`, `high`)
- Evidence (test output, reachability proof, usage grep, metric delta)
- Rollback note
- Owner

## Entries
| Date (UTC) | Path | Decision | Rationale | Risk | Evidence | Rollback Note | Owner |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-03-06 | improvements/pruning/FILE_INVENTORY.csv | keep | Baseline census artifact for full assessment | low | Generated from recursive repository scan | Regenerate from filesystem census command | codex |
| 2026-03-06 | improvements/pruning/ASSESSMENT_CHARTER.md | keep | Defines scope, constraints, and staged process | low | Reviewed against pruning playbook | Revert doc if process changes | codex |
| 2026-03-06 | improvements/pruning/INVENTORY_SUMMARY.md | keep | Captures initial census statistics and hotspots | low | Derived from inventory CSV counts | Recompute from CSV if stale | codex |
| 2026-03-06 | improvements/pruning/CRITICAL_PATH_MAP.md | keep | Captures endpoint-to-service mutation spine before pruning | low | Mapped from current API/service modules and route definitions | Recompute from source if runtime paths change | codex |
| 2026-03-06 | improvements/pruning/BASELINE_FREEZE.md | keep | Freezes current quality/test evidence for before/after pruning comparison | low | Captured command outputs and statuses | Re-run baseline commands and refresh results | codex |
| 2026-03-06 | improvements/pruning/BUCKET_INVENTORY.csv | keep | Adds source-of-truth vs generated/dependency bucket tagging for all inventoried files | low | Derived via explicit path-based bucket rules | Regenerate with bucket script command | codex |
| 2026-03-06 | improvements/pruning/BUCKET_SUMMARY.csv | keep | Aggregated count/size view by inventory bucket | low | Computed from BUCKET_INVENTORY.csv | Regenerate from bucketed inventory | codex |
| 2026-03-06 | improvements/pruning/DECISION_CRITERIA_MATRIX.md | keep | Draft scoring/threshold matrix for pruning policy sign-off | low | Based on pruning playbook and current repo census | Update after user sign-off on criteria | codex |
| 2026-03-06 | improvements/pruning/CANDIDATE_SHORTLIST.md | keep | First-pass candidate queue by bucket with no destructive actions | low | Based on BUCKET_SUMMARY + critical-path map | Reprioritize after criteria sign-off | codex |
| 2026-03-06 | improvements/pruning/SOURCE_OF_TRUTH_POLICY.md | keep | Locks boundary policy for source-of-truth vs generated artifacts, including node_modules handling | low | Based on explicit user direction and bucket evidence | Update policy by explicit review if tooling constraints change | codex |
| 2026-03-06 | improvements/pruning/UNCLASSIFIED_RESOLUTION.md | keep | Documents closure of unclassified bucket and mapping decisions | low | Derived from bucket refresh comparison | Recompute if new unclassified files appear | codex |
| 2026-03-06 | improvements/pruning/SCORING_WORKSHEET.csv | keep | Seeds structured scoring workflow for threshold sign-off before pruning | low | Draft worksheet generated from current bucket model | Revise rows/columns after criteria sign-off | codex |
