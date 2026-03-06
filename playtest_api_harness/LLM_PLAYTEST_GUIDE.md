# LLM Playtest Guide (API-First, File-Driven)

This guide defines a reproducible workflow for external LLM agents that play by:

1. reading turn JSON from disk,
2. writing a strict decision JSON file,
3. advancing one turn through `/api/next` or `/api/action`.

This harness is separate from `playtest_harness` on purpose. It is designed for
explicit endpoint control and turn-by-turn artifact visibility.

## Script

Use:

```bash
python playtest_api_harness/api_first_llm_playtest.py <command> ...
```

Supported commands:

- `init`: create run dir, optionally spawn backend, hard reset, bootstrap, fetch `turn_1.json`
- `status`: show latest turn and expected next decision file
- `emit-prompt`: build a prompt file the external LLM can consume
- `step`: consume one decision JSON and advance one turn
- `finalize`: render transcript + summary
- `stop`: stop spawned backend process for this run

## Agent-Selected World Config

Before `init`, the agent should define a coherent world config unless a human
already provided these values:

- `scenario`
- `theme`
- `role`
- `description`
- `key-elements` (comma-separated)
- `tone`
- `storylet-count`
- `seed`

The agent is allowed to choose these creatively, but should keep them
internally consistent and aligned to a single narrative direction.

Example:

```bash
python playtest_api_harness/api_first_llm_playtest.py init --scenario mystery --theme "cathedral conspiracy thriller" --role "forensic translator of unwritten scripture" --description "A city where redacted liturgies alter civic law whenever spoken aloud." --key-elements "sealed archives,fractured lexicon,clerical spies,memory debt,choir codes" --tone "investigative, tense, ritualistic" --storylet-count 8 --seed 20260305
```

## Decision Contract

Each step consumes a strict JSON object with this schema:

```json
{
  "mode": "choice or freeform",
  "choice_label": "required when mode=choice",
  "action_text": "required when mode=freeform",
  "rationale": "optional short reason"
}
```

Notes:

- For `mode="choice"`, the harness matches `choice_label` against the latest turn's choices.
- If no label matches, it falls back to the first available choice and records `fallback_used=true`.
- For `mode="freeform"`, the harness calls `/api/action`.

## Agent Operator Prompt (Reusable)

Use this as the top-level instruction for an external agent:

```text
You are running a file-driven API playtest for WorldWeaver.

Primary guide:
- playtest_api_harness/LLM_PLAYTEST_GUIDE.md

Primary script:
- playtest_api_harness/api_first_llm_playtest.py

First, define run world config (unless user already provided values):
- scenario
- theme
- role
- description
- key-elements (comma-separated)
- tone
- storylet-count
- seed

You may choose these creatively, but keep them coherent and internally consistent.

Workflow:
1. Initialize run with `init`, passing your chosen world config values.
2. Generate prompt with `emit-prompt`.
3. Write strict decision JSON to `inbox/decision_<N>.json`:
   - mode: "choice" or "freeform"
   - choice_label: required when mode="choice"
   - action_text: required when mode="freeform"
   - rationale: short reason
4. Advance exactly one turn with `step`.
5. Repeat steps 2-4 until target turns reached.
6. Run `finalize`.
7. Run `stop` to shut down spawned backend.

Constraints:
- Use only this harness workflow for /api/next and /api/action.
- Prefer exact choice labels when mode is choice.
- Keep freeform actions concrete, one sentence, and state-aware.
- Keep decisions aligned with selected theme/role and evolving story state.
```

## Canonical Workflow

### 1) Initialize a run

Spawn-managed (recommended):

```bash
python playtest_api_harness/api_first_llm_playtest.py init --scenario mystery --theme "thriller mystery" --role "translator of an unwritten language" --description "A city of sealed archives and disappearances where meaning itself is dangerous; every translated fragment changes power." --key-elements "unwritten glyphs,missing lexicon,sealed vaults,rival translators,unreliable witnesses" --storylet-count 8 --spawn-port 8013
```

Reuse existing backend:

```bash
python playtest_api_harness/api_first_llm_playtest.py init --reuse-backend --base-url http://127.0.0.1:8000/api --scenario mystery
```

### 2) Generate a prompt for the external LLM

```bash
python playtest_api_harness/api_first_llm_playtest.py emit-prompt --run-dir playtests/agent_runs/api_first/<RUN_ID>
```

This writes:

- `inbox/prompt_turn_<N>.md`

### 3) External LLM writes decision JSON

Write to:

- `inbox/decision_<N>.json`

Where `<N>` is the latest turn number currently present in `turns/`.

### 4) Advance one turn

```bash
python playtest_api_harness/api_first_llm_playtest.py step --run-dir playtests/agent_runs/api_first/<RUN_ID>
```

This writes:

- `decisions/decision_<N>.json` (normalized, with fallback metadata)
- `turns/turn_<N+1>.json` (API response payload)

Repeat steps 2-4 for as many turns as needed.

### 5) Finalize artifacts

```bash
python playtest_api_harness/api_first_llm_playtest.py finalize --run-dir playtests/agent_runs/api_first/<RUN_ID>
```

This writes:

- `transcript.md`
- `summary.json`

### 6) Stop spawned backend

```bash
python playtest_api_harness/api_first_llm_playtest.py stop --run-dir playtests/agent_runs/api_first/<RUN_ID>
```

## Artifact Layout

Each run directory contains:

- `manifest.json`
- `session.txt`
- `bootstrap.json`
- `turns/turn_*.json`
- `decisions/decision_*.json`
- `inbox/prompt_turn_*.md`
- `inbox/decision_*.json` (agent-produced input)
- `transcript.md` (after finalize)
- `summary.json` (after finalize)
- `backend.out.log`, `backend.err.log`, `backend.pid` (spawn mode)

## Troubleshooting

- If `init` fails on readiness, increase `--startup-timeout-seconds`.
- If you see stale world bleed, use spawn mode instead of reuse mode.
- If `/api/action` responses look empty, inspect `narrative` in turn payload (some responses use `narrative` instead of `text`).
- If `step` fails due missing decision file, run `status` to confirm the expected `decision_<N>.json` target.
