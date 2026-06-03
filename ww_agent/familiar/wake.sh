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
[ -d "familiar/$NAME/identity" ] || { echo "no familiar at familiar/$NAME (need identity/SOUL.canonical.md)"; exit 1; }

echo "· waking $NAME on ${WW_INFERENCE_MODEL:-?} …"
"$PY" scripts/familiar.py --home "familiar/$NAME" --tick "${TICK:-30}" &
DAEMON=$!
trap 'kill "$DAEMON" 2>/dev/null || true' EXIT INT TERM
cd familiar/portrait
echo "· $NAME's portrait at http://localhost:$PORT   (Ctrl-C to bank the embers)"
"$PY" serve.py --home "../$NAME" --port "$PORT"
