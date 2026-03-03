# Harness Gap Decisions (WorldWeaver)

Date: `2026-03-03`

## Decision Log

### Gap 1

- gap: Root `README.md` is missing, so there is no single top-level runtime entrypoint doc yet.
- classification: `blocker_now`
- rationale: The harness adoption checklist expects a top-level entrypoint and linked harness index; without it, the command surface is not discoverable from repo root.
- owner: Runtime DX owner (minor `69`)
- due window: 2026-03-03 to 2026-03-10 (before pilot minor `67`)
- unblock condition: Root `README.md` exists and links to `improvements/harness/README.md` with canonical run/test/build commands.

### Gap 2

- gap: `run_true_tests.py` is referenced in older docs but is not present in repo root.
- classification: `blocker_now`
- rationale: Command documentation currently includes a non-existent command, which breaks execution protocol validation and causes avoidable startup/test confusion.
- owner: Docs hygiene owner (minor `70`)
- due window: 2026-03-03 to 2026-03-10 (before pilot minor `67`)
- unblock condition: Active docs no longer advertise `run_true_tests.py` as runnable; references are removed or explicitly marked historical-only.

### Gap 3

- gap: No current single-command full-stack runtime (`compose`/`make`/task wrapper).
- classification: `non_blocker_defer`
- rationale: Manual backend+client startup is currently documented and works; single-command orchestration is already tracked by major `46` and can remain deferred for this pilot.
- owner: Dev runtime owner (major `46`)
- due window: By completion of major `46` (target window: 2026-03-10 to 2026-04-15)
- unblock condition: A canonical orchestrated local stack command path exists and is documented.
- temporary waiver: Allow dual-terminal startup (`uvicorn` + `npm --prefix client run dev`) as the accepted dev runtime for pilot execution.
- expiration trigger: Waiver expires when major `46` starts implementation or on 2026-04-15, whichever comes first.

### Gap 4

- gap: Backend lint/format/type gates are not yet operationalized.
- classification: `non_blocker_defer`
- rationale: Gate 3 currently has minimum build/static coverage (`client build` + `compileall`); full lint/format gating is already tracked by minor `48`.
- owner: Code hygiene owner (minor `48`)
- due window: By completion of minor `48` (target window: 2026-03-03 to 2026-03-24)
- unblock condition: Repo has configured lint/format commands and they are part of required verification evidence for low-risk merges.
- temporary waiver: For current minors, treat Gate 3 as satisfied by `npm --prefix client run build` plus `python -m compileall src main.py`.
- expiration trigger: Waiver expires when minor `48` is completed or before the first medium-risk item after `48`, whichever comes first.
