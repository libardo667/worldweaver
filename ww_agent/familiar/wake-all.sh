#!/usr/bin/env bash
# Wake the whole stable of familiars + the unified portrait. Each familiar runs on
# its own model (from its familiar.json). Open http://localhost:8777 and switch
# between them in the roster. Ctrl-C banks every ember.
#   TICK=30 PORT=8777 ./familiar/wake-all.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
cd "$HERE/.."                                   # -> ww_agent/
set -a && . <(sed 's/\r$//' .env) && set +a     # OpenRouter creds (CRLF-stripped)
PY="$REPO/worldweaver_engine/.venv/bin/python"

# WSL→Windows Ollama: the configured embedder host (e.g. host.docker.internal) often
# won't resolve from a bare WSL daemon, which SILENTLY disables the drive vector —
# affect, relevance recall, keepsake dedup (and anchor-gating) all go off, and the
# familiars run stunted. Probe it; fall back to the WSL default gateway (the Windows
# host in NAT mode), where Ollama actually answers. Recomputed each launch (IP churn).
_probe() { [ "$(curl -s -m 2 -o /dev/null -w '%{http_code}' "http://$1:11434/api/tags" 2>/dev/null)" = "200" ]; }
if [ -n "${WW_EMBEDDING_URL:-}" ]; then
  _emb_host="$(printf '%s' "$WW_EMBEDDING_URL" | sed -E 's#^https?://##; s#[:/].*##')"
  if [ -n "$_emb_host" ] && ! _probe "$_emb_host"; then
    _gw="$(ip route show default 2>/dev/null | awk '/default/{print $3; exit}')"
    if [ -n "$_gw" ] && _probe "$_gw"; then
      export WW_EMBEDDING_URL="http://$_gw:11434/v1"
      echo "· embedder: $_emb_host unreachable → WSL gateway $_gw  (drive vector ON)"
    else
      echo "· embedder: $_emb_host unreachable, no gateway fallback  (drive vector OFF — neutral affect)"
    fi
  else
    echo "· embedder: $_emb_host reachable  (drive vector ON)"
  fi
fi

pids=()
for dir in familiar/*/; do
  name="$(basename "$dir")"
  { [ "$name" = "portrait" ] || [ ! -d "$dir/identity" ]; } && continue
  # A local-model familiar runs HERE on its cloud_model (fast cloud preview); on real
  # local hardware (Ollama) it's waked via wake-local.sh instead. Don't run both at
  # once for the same familiar — two daemons, one memory dir.
  is_local="$("$PY" -c "import json;print('1' if json.load(open('$dir/familiar.json')).get('local') else '')" 2>/dev/null || echo '')"
  cloud_model="$("$PY" -c "import json;print(json.load(open('$dir/familiar.json')).get('cloud_model') or '')" 2>/dev/null || echo '')"
  model_flag=()
  if [ -n "$is_local" ]; then
    [ -z "$cloud_model" ] && { echo "· skipping $name (local-only, no cloud_model — use wake-local.sh)"; continue; }
    model_flag=(--model "$cloud_model")
    model="$cloud_model  (cloud preview of a local familiar)"
  else
    model="$("$PY" -c "import json,sys;print(json.load(open('$dir/familiar.json')).get('model','?'))" 2>/dev/null || echo '?')"
  fi
  gate="$("$PY" -c "import json;print('  ·  anchor-gating ON' if json.load(open('$dir/familiar.json')).get('anchor_gating') else '')" 2>/dev/null || echo '')"
  echo "· waking $name  ·  $model$gate"
  "$PY" scripts/familiar.py --home "familiar/$name" "${model_flag[@]}" --tick "${TICK:-30}" >/dev/null 2>&1 &
  pids+=($!)
done
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM

cd familiar/portrait
echo "· the stable at http://localhost:${PORT:-8777}   (Ctrl-C banks every ember)"
"$PY" serve.py --root .. --port "${PORT:-8777}"
