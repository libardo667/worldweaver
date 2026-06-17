#!/usr/bin/env bash
# check-public.sh — leak-sweep for the in-place public worldweaver repo.
#
# Unlike the program's other repos, worldweaver has no sanitizing export lane
# (see ../export-public.sh — "worldweaver ... stands as it is, public already").
# This guards the TRACKED tree directly: it fails if any git-tracked file carries a
# hardcoded personal path or a secret-shaped token. It scans ONLY tracked files on
# purpose — the local gitignored runtime (shards/, residents, .env) legitimately
# contains personal paths and secrets and is never published.
#
# Usage:  scripts/check-public.sh     # exit 0 = clean, exit 2 = leak
set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 2

leak=0
say() { printf '\n\033[1m· %s\033[0m\n' "$*"; }

say "tracked files — hardcoded personal paths"
if git grep -nIE "/home/levibanks|/mnt/c/Users/levib" -- ':!scripts/check-public.sh'; then
  echo "!! hardcoded personal path(s) above"; leak=1
else
  echo "  clean"
fi

say "tracked files — secret/token-shaped strings"
if git grep -nIE "sk-[A-Za-z0-9]{20}|or-v1-[A-Za-z0-9]{20}|gh[pousr]_[A-Za-z0-9]{20}" -- ':!scripts/check-public.sh'; then
  echo "!! secret/token-shaped string(s) above"; leak=1
else
  echo "  clean"
fi

if [[ "$leak" -ne 0 ]]; then
  echo; echo "LEAK — tracked files contain personal data. Fix before pushing."; exit 2
fi
echo; echo "clean — no personal paths or token-shaped secrets in tracked files."
