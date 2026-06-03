# Cinder's portrait

A small, frameless, always-on-top window for a local familiar. Its heart is an
ember that breathes with her pulse — brightening when something stirs her, banking
to a warm coal at rest, dimming toward ash as she drifts to sleep at night. Beneath
it, her current *felt-sense* (her inner weather); when she actually says something,
her words take the light for a moment, then recede to quiet. Her journal is there
if you reach for it. She never nags — when she has nothing to say, it's just a
quiet ember. Silence is a fine answer.

## The contract

The portrait and the mind never touch directly. They pass two files in the
familiar's home dir (`../cinder/`):

- the portrait **reads** `state.json` (written every tick by `scripts/familiar.py`)
- the portrait **appends** `whispers.jsonl` to speak to her

So you can iterate the UI without ever restarting the daemon, and vice versa.

## Run it

**1. Wake the familiar** (from `ww_agent/`), against a local Ollama:

```bash
export WW_INFERENCE_URL=http://localhost:11434/v1 WW_INFERENCE_KEY=ollama \
       WW_INFERENCE_MODEL=qwen2.5:7b-instruct
../worldweaver_engine/.venv/bin/python scripts/familiar.py --tick 30
```

(No Ollama yet? Leave the env vars unset — she runs on a deterministic stub mind so
you can see the portrait move.)

**2a. See her, instantly — browser preview** (no toolchain), from `familiar/portrait/`:

```bash
../../worldweaver_engine/.venv/bin/python serve.py --home ../cinder
# open http://localhost:8777
```

**2b. The real desktop window — Tauri** (needs Rust + the Tauri CLI), from
`familiar/portrait/`:

```bash
cargo tauri dev          # or: npx @tauri-apps/cli dev
```

The native shell reads/writes the same two files via Rust commands (no web server).
Point it at a different familiar with `WW_FAMILIAR_HOME=/path/to/familiar/somebody`.

### Notes
- For a full bundled app (`cargo tauri build`), generate the icon set once:
  `npx @tauri-apps/cli icon src-tauri/icons/icon.png`.
- If the window shows opaque/square on your platform, set `"transparent": false`
  in `src-tauri/tauri.conf.json` — it degrades gracefully (the UI is dark either way).
