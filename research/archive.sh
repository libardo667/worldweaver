#!/usr/bin/env bash
# Publish the current review-bundle/ as PLAIN FILES into the PUBLIC, tracked
# research/review-bundle/<date>-<label>/, commit + push so Mr. Review can pull the
# round cold from GitHub, then CLEAR the local review-bundle/ so the next round
# starts fresh.
#
#   Usage:  ./research/archive.sh <label>
#
# Why plain files (not a tarball): the reviewer reads the round cold off GitHub and
# recomputes from the ledgers in research/runs/. A tarball in git is opaque; plain
# files are browsable. Keep heavy evidence (ledgers) in research/runs/ and point at
# it from the bundle prose — the published bundle should stay lightweight.
set -euo pipefail

label="${1:-bundle}"
root="$(cd "$(dirname "$0")/.." && pwd)"
src="$root/review-bundle"
stamp="$(date +%Y-%m-%d)"

[ -d "$src" ] || { echo "no review-bundle/ at $src — nothing to publish"; exit 1; }
if [ -z "$(find "$src" -mindepth 1 -print -quit)" ]; then
  echo "review-bundle/ is empty — nothing to publish"; exit 1
fi

dest="$root/research/review-bundle/${stamp}-${label}"
[ -e "$dest" ] && dest="$root/research/review-bundle/${stamp}-${label}-$(date +%H%M)"
mkdir -p "$dest"

# Copy the round's files as-is (preserve any subdirs the operator curated).
cp -a "$src/." "$dest/"
echo "published -> $dest"

# Publish to GitHub for the reviewer. Only the published path is staged — never a
# blanket add. .gitignore already excludes research/**/{.env,*.key,secrets*} as a
# safety net against publishing secrets.
rel="$(realpath --relative-to="$root" "$dest")"
( cd "$root" \
  && git add "$rel" \
  && git commit -m "review-round: publish $(basename "$dest") for Mr. Review" \
  && git push )
echo "pushed -> origin ($(cd "$root" && git branch --show-current))"

# Clear the local workspace so the next round starts fresh.
find "$src" -mindepth 1 -delete
echo "review-bundle cleared — next round starts fresh"
