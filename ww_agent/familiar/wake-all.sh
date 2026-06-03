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

pids=()
for dir in familiar/*/; do
  name="$(basename "$dir")"
  { [ "$name" = "portrait" ] || [ ! -d "$dir/identity" ]; } && continue
  model="$("$PY" -c "import json,sys;print(json.load(open('$dir/familiar.json')).get('model','?'))" 2>/dev/null || echo '?')"
  echo "· waking $name  ·  $model"
  "$PY" scripts/familiar.py --home "familiar/$name" --tick "${TICK:-30}" >/dev/null 2>&1 &
  pids+=($!)
done
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM

cd familiar/portrait
echo "· the stable at http://localhost:${PORT:-8777}   (Ctrl-C banks every ember)"
"$PY" serve.py --root .. --port "${PORT:-8777}"
