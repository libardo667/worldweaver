# Multi-Agent Pruning Prompts

Use these prompt patterns when you want multiple agents pruning the same
codebase without creating incoherent diffs.

## Intent

Drive targeted, coherent reduction:

- remove duplication
- demote fragile optional subsystems
- simplify runtime paths
- preserve behavior and contracts unless explicitly approved

## Pruning Orchestrator Prompt (Plan First, Docs-Only)

```text
Read:
- improvements/VISION.md
- improvements/ROADMAP.md
- improvements/harness/07-PRUNING_PLAYBOOK.md
- improvements/harness/03-AGENT_EXECUTION_PROTOCOL.md
- improvements/majors/MAJOR_SCHEMA.md
- improvements/minors/MINOR_SCHEMA.md

Task (docs-only):
1) Produce improvements/PRUNING_COORDINATION_PLAN.md with:
   - top 8 pruning candidates
   - candidate score (user value, reliability, complexity cost, risk)
   - recommended action per candidate (delete, merge, demote, isolate)
2) Partition work into 2-4 agent lanes with non-overlapping file boundaries.
3) Define interface contracts between lanes (shared types, API shape, event payloads).
4) Define integration order and required validation commands per lane.
5) Do not change application code.
```

## Lane Assignment Prompt (Agent-Specific)

```text
Read:
- improvements/PRUNING_COORDINATION_PLAN.md
- improvements/harness/03-AGENT_EXECUTION_PROTOCOL.md
- improvements/harness/04-QUALITY_GATES.md

You are Lane <N>.

Scope:
- Allowed files: <explicit list or glob>
- Forbidden files: all others
- Contract dependencies: <shared interfaces you must preserve>

Task:
1) Implement only the lane scope.
2) Keep API and payload contracts stable unless lane plan explicitly allows changes.
3) Produce improvements/PRUNING_LANE_<N>_EVIDENCE.md with:
   - files changed
   - validations run and results
   - unresolved risks
   - handoff notes for integration
```

## Lane Execution Prompt (Targeted Prune Change)

```text
Execute pruning lane <N> as defined in improvements/PRUNING_COORDINATION_PLAN.md.

Rules:
- No drive-by refactors.
- No edits outside allowed file boundary.
- Prefer delete/merge over new abstraction.
- If blocked by cross-lane dependency, stop and write a blocker note in:
  improvements/PRUNING_LANE_<N>_EVIDENCE.md

Validation:
- Run lane-specific commands listed in the plan.
- Record exact pass/fail results in lane evidence doc.
```

## Integration Prompt (Lead Agent)

```text
Read:
- improvements/PRUNING_COORDINATION_PLAN.md
- improvements/PRUNING_LANE_1_EVIDENCE.md
- improvements/PRUNING_LANE_2_EVIDENCE.md
- improvements/PRUNING_LANE_3_EVIDENCE.md (if present)
- improvements/harness/templates/PR_EVIDENCE_TEMPLATE.md

Task:
1) Integrate lane outputs in the planned order.
2) Resolve conflicts by preserving declared contracts first, lane preferences second.
3) Run full validation gates required for this risk level.
4) Produce improvements/PRUNING_INTEGRATION_EVIDENCE.md including:
   - merge/conflict decisions
   - validations and results
   - regressions found/fixed
   - follow-up items needed
```

## Conflict Resolution Prompt (When Lanes Collide)

```text
Given conflicting lane outputs, decide using this priority:
1) Contract stability
2) Correctness
3) Simplicity (fewer branches, fewer duplicated paths)
4) Performance
5) Stylistic preference

Output:
- winning approach
- rejected approach and reason
- concrete merge edits required
- any required follow-up minor item
```

## Post-Prune Retrospective Prompt

```text
Read:
- improvements/PRUNING_INTEGRATION_EVIDENCE.md
- improvements/harness/templates/RETROSPECTIVE_TEMPLATE.md

Task (docs-only):
1) Create improvements/PRUNING_RETROSPECTIVE_<date>.md
2) Capture:
   - what was successfully deleted/merged/demoted
   - where coordination failed
   - changes to lane boundaries for next cycle
   - top 3 next pruning candidates
```

## Coherence Guardrails for Multi-Agent Pruning

Use these in every pruning prompt:

1. "No edits outside explicit lane file boundary."
2. "Preserve public contract shape unless explicitly approved."
3. "If blocked, write a blocker note instead of improvising across boundaries."
4. "Record validation outputs in evidence doc, not only chat output."
5. "Prefer deletion and consolidation over abstraction growth."

