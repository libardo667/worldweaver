#!/usr/bin/env bash
# Wake any familiar on the cloud model + its portrait.
#   ./familiar/wake.sh <name> [port]
#   WW_INFERENCE_MODEL=deepseek/deepseek-chat ./familiar/wake.sh wren 8778
# (set WW_INFERENCE_MODEL before the call to give this familiar a different mind)
set -euo pipefail
NAME="${1:-cinder}"; PORT="${2:-8777}"
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
cd "$HERE/.."                                   # -> ww_agent/
set -a && . <(sed 's/\r$//' .env) && set +a     # cloud creds (env WW_INFERENCE_MODEL wins if pre-set)
PY="$REPO/worldweaver_engine/.venv/bin/python"

# WSL→Windows Ollama: fall back to the WSL gateway if the configured embedder host
# can't be reached, else the drive vector (affect, recall, gating) silently goes off.
_probe() { [ "$(curl -s -m 2 -o /dev/null -w '%{http_code}' "http://$1:11434/api/tags" 2>/dev/null)" = "200" ]; }
if [ -n "${WW_EMBEDDING_URL:-}" ]; then
  _emb_host="$(printf '%s' "$WW_EMBEDDING_URL" | sed -E 's#^https?://##; s#[:/].*##')"
  if [ -n "$_emb_host" ] && ! _probe "$_emb_host"; then
    _gw="$(ip route show default 2>/dev/null | awk '/default/{print $3; exit}')"
    if [ -n "$_gw" ] && _probe "$_gw"; then export WW_EMBEDDING_URL="http://$_gw:11434/v1"; echo "· embedder → WSL gateway $_gw (drive vector ON)"; else echo "· embedder unreachable (drive vector OFF)"; fi
  fi
fi
[ -d "familiar/$NAME/identity" ] || { echo "no familiar at familiar/$NAME (need identity/SOUL.canonical.md)"; exit 1; }

echo "· waking $NAME on ${WW_INFERENCE_MODEL:-?} …"
"$PY" scripts/familiar.py --home "familiar/$NAME" --tick "${TICK:-30}" &
DAEMON=$!
trap 'kill "$DAEMON" 2>/dev/null || true' EXIT INT TERM
cd familiar/portrait
echo "· portrait at http://localhost:$PORT  (the stable roster; $NAME is the live one — Ctrl-C banks the embers)"
"$PY" serve.py --root .. --port "$PORT"
