# Decision Criteria Matrix (Approved, Additive)

Status: `approved_for_current_cycle`  
This matrix is approved for current-cycle scoring and batch planning.

## Purpose
Create consistent, auditable criteria to classify files and subsystems as:
- keep
- simplify
- merge
- demote
- archive
- delete candidate

## Scoring Dimensions (1-5)
- user_value: how directly this path supports current user-visible product behavior.
- reliability: test stability and runtime predictability.
- complexity_cost: maintenance burden, branching, indirection, duplicate paths.
- operational_risk: blast radius if changed/removed.
- observability_quality: ability to detect regressions quickly.

## Decision Heuristics
- Delete candidate:
  - user_value <= 2
  - reliability <= 3
  - complexity_cost >= 4
  - operational_risk <= 2
- Archive candidate:
  - low runtime value but historical/reference value present.
- Demote candidate:
  - value >= 3 but reliability <= 3 and not required on critical path.
- Merge candidate:
  - two or more paths solve the same job with inconsistent behavior.
- Simplify candidate:
  - single path has high complexity with no corresponding user value gain.
- Keep:
  - critical path, high value, and acceptable complexity/risk profile.

## Bucket-Level Defaults
- `source_runtime_tooling`: default `keep/simplify`, never mass-delete.
- `source_tests`: default `keep/simplify`, prune only dead/duplicate tests with coverage evidence.
- `source_frontend`: default `keep/simplify`, separate from dependency/vendor bulk.
- `source_harness_tooling`: default `keep/demote`, depending on active workflow use.
- `planning_active_docs`: default `keep/archive` based on roadmap relevance.
- `planning_archive_history`: default `archive`.
- `generated_dependency_vendor_local`: generated and non-source-of-truth; keep in-place for tool compatibility.
- `generated_playtest_artifact_relocate`: default `archive/externalize` to parent workspace artifacts.
- `generated_cache_local` / `generated_log_artifact_relocate` / `generated_build_output_local`: generated-only buckets.
- `local_db_artifact_relocate` / `local_secret_env_local`: local-only, exclude from source-of-truth.
- `repo_meta_docs`: default `keep`.
- `unclassified_review`: mandatory manual classification.

## Gate Rules Before Any Non-Trivial Prune
1. Baseline command set must be recorded and reproducible.
2. Critical-path map must identify whether target is in mutation spine.
3. If operational_risk >= 3, require bounded rollout/rollback note.
4. If contract-adjacent, require additive-only or explicit approval.

## Decision Quality Checklist
- Evidence linked in `DECISION_LOG.md`.
- Change type strategy assigned (`delete`, `merge`, `demote`, `isolate`).
- Risk and rollback explicitly documented.
- Validation command set attached before marking done.

## Sign-Off Outcome
- Criteria approved for execution planning.
- Playtest/generated artifacts remain non-source-of-truth and are planned for isolate/delete handling by wave.
- Harness/docs remain in-scope with conservative `demote`/`keep` default strategies.
