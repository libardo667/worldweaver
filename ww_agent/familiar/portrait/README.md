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

**2b. The real desktop window — Tauri** (a frameless, always-on-top window that
floats on your desktop). One-time setup (installs Rust + the Tauri CLI + Linux
system deps; on Win11 WSL2, WSLg shows the window):

```bash
./setup-tauri.sh
```

Then run the daemon (terminal 1, from `ww_agent/`) and the window (terminal 2):

```bash
# terminal 1 — wake her (writes state.json)
set -a && . <(sed 's/\r$//' .env) && set +a
../worldweaver_engine/.venv/bin/python scripts/familiar.py --tick 30

# terminal 2 — the native window
cd familiar/portrait && npx tauri dev
```

The native shell reads/writes the same two files via Rust commands (no web
server), so the daemon must be running. Point it at a different familiar with
`WW_FAMILIAR_HOME=/abs/path/to/familiar/somebody`.

### Notes
- For a full bundled app (`npx tauri build`), generate the icon set once:
  `npx tauri icon src-tauri/icons/icon.png`.
- Memory-capped WSL? The first `npx tauri dev` compiles the Rust app once; it's
  capped to 4 jobs in `src-tauri/.cargo/config.toml` (lower to 2 if it still
  struggles). Make sure you ran `wsl --shutdown` from Windows after `.wslconfig`
  changed, so the larger memory + swap took effect.
- If the window shows opaque/square on your platform, set `"transparent": false`
  in `src-tauri/tauri.conf.json` — it degrades gracefully (the UI is dark either way).
- No GUI in WSL? You need Windows 11 (WSLg). Otherwise build the window natively
  on Windows/macOS, or just use the browser preview (2a) — same portrait.
