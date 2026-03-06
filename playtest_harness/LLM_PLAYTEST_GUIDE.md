# LLM Playtest Guide (Managed Agent Runs)

For API-first, file-driven endpoint control in a separate sibling harness, use:

- `playtest_api_harness/LLM_PLAYTEST_GUIDE.md`
- `playtest_api_harness/api_first_llm_playtest.py`

This guide is for generating coherent, reproducible LLM-authored playthroughs.

Primary path: `python scripts/dev.py llm-playtest ...`

This path is sweep-style managed:

- backend spawn (or reuse),
- hard reset,
- bootstrap,
- turn loop,
- artifact write,
- backend teardown (spawn mode).

## Why this guide changed

The old direct `harness.py` mode depended on manual backend lifecycle handling and
is no longer the recommended primary workflow for agentic runs.

## Prerequisites

1. Run from repository root.
2. `.env` has valid API credentials.
3. Lane models are pinned for reproducibility.

Example lane pinning (PowerShell):

```powershell
$env:LLM_MODEL="google/gemini-3-flash-preview"
$env:LLM_NARRATOR_MODEL="google/gemini-3-flash-preview"
$env:LLM_REFEREE_MODEL="google/gemini-3-flash-preview"
```

## Canonical Command (Golden Run)

```bash
python scripts/dev.py llm-playtest --turns 12 --seed 20260305 --scenario mystery --theme "thriller mystery" --role "translator of an unwritten language" --description "A city of sealed archives and disappearances where meaning itself is dangerous; every translated fragment changes power." --key-elements "unwritten glyphs,missing lexicon,sealed vaults,rival translators,unreliable witnesses" --storylet-count 8 --spawn-port 8010 --out-dir playtests/agent_runs
```

What this does:

- boots a managed backend process,
- resets and bootstraps a fresh world,
- uses an LLM to decide each turn (choice or freeform),
- writes run artifacts,
- tears down the backend process on completion.

## Artifacts

Each run writes to `playtests/agent_runs/<timestamp>/`:

- `manifest.json`: run config, scenario, model settings, bootstrap result
- `backend.log`: spawned backend logs (spawn mode)
- `turns/turn_N.json`: per-turn API payloads
- `decisions/decision_N.json`: per-turn LLM action decisions
- `transcript.md`: readable transcript

## Reproducibility Checklist

1. Keep lane model IDs fixed per run.
2. Keep seed fixed when comparing behavior.
3. Keep scenario/theme/role/description fixed when comparing behavior.
4. Use managed spawn mode for per-run isolation.
5. Preserve `manifest.json` with each shared transcript.

## Optional: Existing Backend Mode

If you already have a backend running and want to reuse it:

```bash
python scripts/dev.py llm-playtest --reuse-backend --base-url http://127.0.0.1:8000/api --turns 12 --scenario mystery
```

Note: in reuse mode, backend env overrides are not applied by the harness.

## Legacy Fallback (Not Primary)

`playtest_harness/harness.py` remains available for low-level manual loops, but
it is no longer the recommended primary flow for managed agent runs.

## Troubleshooting

- If outputs look like stale-world bleed, ensure managed spawn mode is used.
- If turns degrade into fallback text, inspect `backend.log` and run manifest.
- If run hangs on readiness, increase `--startup-timeout`.
- If per-turn latency is high, keep bounded prefetch behavior in comparative
  sweeps (`--prefetch-wait-policy bounded --prefetch-wait-timeout-seconds 3`).
