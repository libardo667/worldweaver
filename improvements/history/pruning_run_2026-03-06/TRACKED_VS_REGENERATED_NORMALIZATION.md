# Tracked vs Regenerated Normalization (Wave 1)

Status: `proposed_for_current_cycle`  
Mode: additive policy artifact, no file moves

## Decision Rule
1. If deleting it changes product behavior and it is not reproducible from source/config, track it as source-of-truth.
2. If deleting it only removes generated output that can be recreated, treat it as regenerated artifact.

## Normalized Buckets
| Bucket | Track In Repo | Storage Target | Rationale |
| --- | --- | --- | --- |
| `source_runtime_tooling` / `source_tests` / `source_frontend` / `source_harness_tooling` / `repo_meta_docs` / `data_asset` | yes | `worldweaver/worldweaver` | Authored behavior + contracts |
| `planning_active_docs` | yes | `worldweaver/worldweaver` | Active governance/source process docs |
| `planning_archive_history` | yes (archive) | `worldweaver/worldweaver` archive paths | Historical context retained but out of active path |
| `generated_dependency_vendor_local` | no (generated) | keep local in-place | Toolchain compatibility (`client/node_modules`) |
| `generated_build_output_local` | no (generated) | local generated output | Build artifact (`client/dist`) |
| `generated_cache_local` | no (generated) | local generated output | Fast local iteration caches |
| `generated_playtest_artifact_relocate` / `generated_log_artifact_relocate` / `report_output_artifact_relocate` / `local_db_artifact_relocate` | no (generated) | parent workspace artifact area (`.../worldweaver/`) | Keep core repo focused on source-of-truth |

## Operational Convention
- Generated artifacts may exist locally during runs but are not source-of-truth.
- For reproducibility and cleanup, prefer writing heavy outputs to parent workspace artifact directories.
- Keep compatibility-required generated trees (`node_modules`, caches, build output) local/in-place unless tooling workflow is redesigned.

## Follow-On (Not Executed Here)
- Align scripts/harness defaults to artifact target paths.
- Add CI/process checks to prevent accidental re-introduction of bulky generated output into source-of-truth scope.
