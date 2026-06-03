#!/usr/bin/env bash
# Wake Cinder on the cloud model (OpenRouter creds from ww_agent/.env) and open
# her portrait. Then visit http://localhost:8777 — Ctrl-C banks the embers.
#
#   TICK=30 PORT=8777 ./familiar/wake-cinder.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"              # repo root
cd "$HERE/.."                                  # -> ww_agent/
set -a && . <(sed 's/\r$//' .env) && set +a    # cloud creds (strip Windows CRLF)
PY="$REPO/worldweaver_engine/.venv/bin/python" # absolute — survives the cd below

echo "· waking Cinder on ${WW_INFERENCE_MODEL:-?} …"
"$PY" scripts/familiar.py --tick "${TICK:-30}" &
DAEMON=$!
trap 'kill "$DAEMON" 2>/dev/null || true' EXIT INT TERM

cd familiar/portrait
echo "· portrait at http://localhost:${PORT:-8777}   (Ctrl-C to bank the embers)"
"$PY" serve.py --home ../cinder --port "${PORT:-8777}"
