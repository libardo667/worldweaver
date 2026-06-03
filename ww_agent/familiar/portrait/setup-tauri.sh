#!/usr/bin/env bash
# One-time setup to build Cinder's native window on Debian/Ubuntu (incl. WSL2).
# Installs the Tauri v2 Linux system deps, Rust (if missing), and the Tauri CLI.
# Needs sudo for the apt step. On Windows 11 WSL2, WSLg provides the display, so
# the window appears on your desktop; on macOS/Windows native, skip the apt step.
set -euo pipefail

echo "· Tauri v2 Linux system deps (sudo apt)…"
sudo apt-get update
sudo apt-get install -y \
  libwebkit2gtk-4.1-dev build-essential curl wget file \
  libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev

if ! command -v cargo >/dev/null 2>&1; then
  echo "· installing Rust (rustup)…"
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  # shellcheck disable=SC1091
  . "$HOME/.cargo/env"
fi

echo "· Tauri CLI (cargo install, may take a few minutes)…"
cargo install tauri-cli --version "^2.0" --locked

echo
echo "✓ setup done. Now, in two terminals from ww_agent/:"
echo "    1)  set -a && . <(sed 's/\\r\$//' .env) && set +a && ../worldweaver_engine/.venv/bin/python scripts/familiar.py --tick 30"
echo "    2)  cd familiar/portrait && cargo tauri dev"
