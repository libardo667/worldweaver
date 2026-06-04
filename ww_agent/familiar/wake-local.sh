#!/usr/bin/env bash
# Wake the LOCAL-model familiars (Hades & Persephone) on the Windows/WSL Ollama,
# on their OWN portrait port so they never collide with the cloud stable (8777).
#
#   ./familiar/wake-local.sh                     # both (Persephone first, then Hades)
#   ./familiar/wake-local.sh hades               # just one
#   ./familiar/wake-local.sh persephone hades    # explicit order
#   PORT=8779 ./familiar/wake-local.sh hades     # pick a port
#
# Prereq: Ollama running on Windows (OLLAMA_HOST=0.0.0.0 + `ollama serve`) with the
# models pulled:  ollama pull qwen2.5:7b-instruct   ·   ollama pull qwen2.5:3b-instruct
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
cd "$HERE/.."                                   # -> ww_agent/
set -a && . <(sed 's/\r$//' .env) && set +a     # base config; we override inference below
PY="$REPO/worldweaver_engine/.venv/bin/python"
PORT="${PORT:-8778}"

# --- find the Ollama host -----------------------------------------------------
# Probe host.docker.internal, fall back to the WSL default gateway (where the
# Windows-side Ollama actually answers in NAT mode). Same heal as the embedder.
_probe() { [ "$(curl -s -m 2 -o /dev/null -w '%{http_code}' "http://$1:11434/api/tags" 2>/dev/null)" = "200" ]; }
OLLAMA_HOST="host.docker.internal"
if ! _probe "$OLLAMA_HOST"; then
  _gw="$(ip route show default 2>/dev/null | awk '/default/{print $3; exit}')"
  if [ -n "$_gw" ] && _probe "$_gw"; then
    OLLAMA_HOST="$_gw"
  else
    echo "✗ Ollama unreachable at host.docker.internal or the WSL gateway."
    echo "  On Windows:  setx OLLAMA_HOST 0.0.0.0  (then restart) and run 'ollama serve'."
    exit 1
  fi
fi

# Inference AND embedding both go to the local Ollama (this is the local-first test).
export WW_INFERENCE_URL="http://$OLLAMA_HOST:11434/v1"
export WW_INFERENCE_KEY="ollama"                       # ignored by Ollama, but must be non-empty or the daemon stubs
export WW_EMBEDDING_URL="http://$OLLAMA_HOST:11434/v1"  # drive vector via local nomic-embed-text
export WW_INFERENCE_TIMEOUT="${WW_INFERENCE_TIMEOUT:-300}"  # CPU 7B can take 60–90s/pulse
echo "· local inference + embedding → http://$OLLAMA_HOST:11434  (timeout ${WW_INFERENCE_TIMEOUT}s)"

# --- which familiars (default: every familiar marked "local": true) -----------
names=("$@")
if [ ${#names[@]} -eq 0 ]; then
  for dir in familiar/*/; do
    n="$(basename "$dir")"
    [ -d "$dir/identity" ] || continue
    [ "$("$PY" -c "import json;print('1' if json.load(open('$dir/familiar.json')).get('local') else '')" 2>/dev/null || echo '')" = "1" ] && names+=("$n")
  done
fi
[ ${#names[@]} -eq 0 ] && { echo "no local familiars found (set \"local\": true in a familiar.json, or name them explicitly)"; exit 1; }

_tags="$(curl -s -m 5 "http://$OLLAMA_HOST:11434/api/tags" 2>/dev/null || echo '')"
pids=()
for name in "${names[@]}"; do
  [ -d "familiar/$name/identity" ] || { echo "✗ no familiar at familiar/$name"; continue; }
  model="$("$PY" -c "import json;print(json.load(open('familiar/$name/familiar.json')).get('model','?'))" 2>/dev/null || echo '?')"
  if ! printf '%s' "$_tags" | grep -q "\"${model}\""; then
    echo "⚠ $name wants '$model' but it isn't pulled — run on Windows:  ollama pull $model"
  fi
  echo "· waking $name on $model"
  "$PY" scripts/familiar.py --home "familiar/$name" --tick "${TICK:-30}" >/dev/null 2>&1 &
  pids+=($!)
done
[ ${#pids[@]} -eq 0 ] && { echo "nothing to wake"; exit 1; }
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT INT TERM

cd familiar/portrait
echo "· portrait at http://localhost:$PORT   (local: ${names[*]} — Ctrl-C banks them)"
"$PY" serve.py --root .. --port "$PORT"
