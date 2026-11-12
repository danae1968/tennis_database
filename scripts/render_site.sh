#!/usr/bin/env bash
# Build (or preview) the Quarto site.
#   scripts/render_site.sh           render into _site/
#   scripts/render_site.sh preview   live preview (no browser)
#
# Normally this is just `quarto render`. On WSL, when the repository sits on a
# Windows drive (/mnt/<letter>/...), Quarto's project cache hangs on that file
# system, so the site sources are mirrored to a Linux folder, rendered there and
# _site/ is copied back. The mirror holds only the site pages and figures.
set -euo pipefail
cd "$(dirname "$0")/.."
mode="${1:-render}"

if [[ "$(pwd -P)" != /mnt/[a-z]/* ]]; then
  if [[ "$mode" == preview ]]; then exec quarto preview --no-browser; fi
  exec quarto render
fi

build="${SITE_BUILD_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/tennis_site_build}"
mkdir -p "$build"
rsync -a --delete \
  --include='/_quarto.yml' --include='/index.qmd' \
  --include='/about/***' --include='/site/***' \
  --include='/analyses/' --include='/analyses/*/' \
  --include='/analyses/*/index.qmd' --include='/analyses/*/README.md' \
  --include='/analyses/*/METHODS.md' --include='/analyses/*/figures/***' \
  --include='/.quarto/***' --include='/_site/***' \
  --exclude='*' ./ "$build/"

if [[ "$mode" == preview ]]; then
  echo "Previewing a mirror in $build (re-run after editing sources)." >&2
  cd "$build" && exec quarto preview --no-browser
fi
(cd "$build" && quarto render)
rsync -a --delete "$build/_site/" ./_site/
echo "Site written to _site/ (built in $build)."
