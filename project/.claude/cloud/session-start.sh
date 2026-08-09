#!/usr/bin/env bash
# Optional cloud-only repository bootstrap. Activate through the provided
# SessionStart settings fragment; do not call directly from shared settings
# until the repository owner has reviewed the install policy.
set -euo pipefail

if [[ "${CLAUDE_CODE_REMOTE:-false}" != "true" ]]; then
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd -P)}"
cd "$ROOT"

log() { printf '[MAD-CLOUD-SESSION] %s\n' "$*"; }
fail() { log "ERROR: $*" >&2; exit 1; }

log "Repository: $(basename "$ROOT")"
log "Git head: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
log "Working tree entries: $(git status --short 2>/dev/null | wc -l | tr -d ' ')"

if [[ "${MADVENTURES_CLOUD_INSTALL_DEPS:-false}" != "true" ]]; then
  log 'Dependency bootstrap disabled. Set MADVENTURES_CLOUD_INSTALL_DEPS=true only after repository review.'
  exit 0
fi

if [[ -f pnpm-lock.yaml ]]; then
  command -v corepack >/dev/null 2>&1 || fail 'corepack is required for pnpm-lock.yaml'
  corepack enable
  pnpm install --frozen-lockfile
elif [[ -f package-lock.json ]]; then
  npm ci
elif [[ -f yarn.lock ]]; then
  command -v corepack >/dev/null 2>&1 || fail 'corepack is required for yarn.lock'
  corepack enable
  yarn install --immutable
elif [[ -f bun.lock || -f bun.lockb ]]; then
  command -v bun >/dev/null 2>&1 || fail 'bun lockfile detected but bun is unavailable'
  bun install --frozen-lockfile
elif [[ -f requirements.txt ]]; then
  python3 -m pip install --disable-pip-version-check -r requirements.txt
else
  fail 'No supported lockfile or requirements.txt found. Leave bootstrap disabled and document the repository-specific command.'
fi

log 'Repository dependency bootstrap complete.'
