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
  model="$("$PY" -c "import json,sys;print(json.load(open('$dir/familiar.json')).get('model','?'))" 2>/dev/null || echo '?')"
  gate="$("$PY" -c "import json;print('  ·  anchor-gating ON' if json.load(open('$dir/familiar.json')).get('anchor_gating') else '')" 2>/dev/null || echo '')"
  echo "· waking $name  ·  $model$gate"
  "$PY" scripts/familiar.py --home "familiar/$name" --tick "${TICK:-30}" >/dev/null 2>&1 &
  pids+=($!)
done
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM

cd familiar/portrait
echo "· the stable at http://localhost:${PORT:-8777}   (Ctrl-C banks every ember)"
"$PY" serve.py --root .. --port "${PORT:-8777}"
