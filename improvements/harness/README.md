# Agentic Harness Kit

This folder is a reusable operating kit for "generative sculpting" development:

1. Build fast.
2. Lock behavior.
3. Prune aggressively.
4. Repeat.

It is designed to be portable to other repositories with minimal edits.

## What this kit gives you

- A shared operating model for human + agent collaboration.
- A standard work item system (major, minor, patch, incident, spike).
- Execution protocols that keep diffs bounded and reversible.
- Merge/release quality gates with evidence requirements.
- A pruning playbook so deletion is first-class, not ad hoc.
- Templates you can copy into any codebase.

## File map

- `00-ADOPTION_GUIDE.md`: how to install this harness in a new repo.
- `01-OPERATING_MODEL.md`: cadence, risk budgets, and development phases.
- `02-WORK_ITEM_SYSTEM.md`: work item taxonomy and lifecycle.
- `03-AGENT_EXECUTION_PROTOCOL.md`: task-by-task execution rules.
- `04-QUALITY_GATES.md`: test, contract, perf, and rollout gates.
- `05-GIT_PR_RELEASE_POLICY.md`: branch, PR, and release rules.
- `06-OBSERVABILITY_AND_BOTTLENECKS.md`: instrumentation and bottleneck triage.
- `07-PRUNING_PLAYBOOK.md`: systematic deletion and simplification.
- `08-PORTABILITY_PLAYBOOK.md`: porting matrix for different repo types.
- `templates/*`: copy/paste templates for implementation.

## Relationship to this repo

This kit does not replace `improvements/VISION.md`, `improvements/ROADMAP.md`,
or the current major/minor schema files. It layers on top of them and makes
execution with AI agents explicit and repeatable.

