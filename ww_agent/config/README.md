# Runtime configuration

Configuration comes from environment variables (or a local `.env` loaded at startup). Copy
`env.example` to `.env`; real environment variables take precedence.

| Variable | Purpose |
|---|---|
| `WW_INFERENCE_KEY` | Required model-provider credential |
| `WW_SERVER_URL` | WorldWeaver base URL, without an `/api` suffix |
| `WW_INFERENCE_URL` | OpenAI-compatible inference base URL |
| `WW_INFERENCE_MODEL` | Default model identifier |
| `WW_RESIDENTS_DIR` | Resident directory root |
| `WW_LOG_LEVEL` | Process logging level |
| `WW_PROMPT_TRACE` | Private append-only exact prompt/completion evidence; default `1`, set `0` to disable |
| `WW_DOULA` / `WW_DOULA_MODEL` | Optional world-watching resident proposal process |

Additional narrowly scoped runtime flags live beside their consumer and are documented in
`env.example` when intended for operators. Avoid adding a second config-file system.
