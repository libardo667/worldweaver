#!/usr/bin/env bash
# One-time setup to build Cinder's native window on Debian/Ubuntu (incl. WSL2).
# Tuned to stay within a memory-capped WSL: the Tauri CLI comes prebuilt via npm
# (no heavy cargo-install compile), and the app build is capped to 4 parallel
# jobs by src-tauri/.cargo/config.toml. On Win11 WSL2, WSLg shows the window.
#
# If WSL still runs low: lower `jobs` in src-tauri/.cargo/config.toml to 2, and
# make sure you ran `wsl --shutdown` from Windows after .wslconfig was updated.
set -euo pipefail
cd "$(dirname "$0")"

echo "· Tauri v2 Linux system deps (sudo apt)…"
sudo apt-get update
sudo apt-get install -y \
  libwebkit2gtk-4.1-dev build-essential curl wget file \
  libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev

if ! command -v cargo >/dev/null 2>&1; then
  echo "· installing Rust (rustup; prebuilt, light)…"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  # shellcheck disable=SC1091
  . "$HOME/.cargo/env"
fi

echo "· Tauri CLI (prebuilt binary via npm — no source compile)…"
npm install

echo
echo "✓ setup done. Then, in two terminals from ww_agent/:"
echo "    1)  set -a && . <(sed 's/\\r\$//' .env) && set +a && ../worldweaver_engine/.venv/bin/python scripts/familiar.py --tick 30"
echo "    2)  cd familiar/portrait && npx tauri dev"
echo
echo "The FIRST 'npx tauri dev' compiles the Rust app once (a few minutes, capped"
echo "to 4 jobs so it fits memory). After that it is fast."
