#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
SOURCE="$ROOT/plugin/madventures-founderos"
SCOPE="user"
PROJECT_PATH=""
FORCE=0
DRY_RUN=0
ALLOW_COEXISTENCE=0

usage() {
  cat <<'USAGE'
Install the portable MAD Ventures FounderOS plugin as a skills-directory plugin.

Usage:
  ./scripts/install-plugin.sh [options]

Options:
  --scope user|project     Default: user
  --project /path/to/repo  Required for project scope
  --force                  Replace an existing plugin after backup
  --allow-coexistence      Permit project plugin installation beside the full project environment
  --dry-run                Print the selected target without writing
  --help

For a one-session test with no installation:
  claude --plugin-dir ./plugin/madventures-founderos
USAGE
}

log() { printf '[MAD-PLUGIN] %s\n' "$*"; }
die() { printf '[MAD-PLUGIN] ERROR: %s\n' "$*" >&2; exit 1; }

while (($#)); do
  case "$1" in
    --scope) (($# >= 2)) || die "--scope requires a value"; SCOPE="$2"; shift 2 ;;
    --project) (($# >= 2)) || die "--project requires a path"; PROJECT_PATH="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --allow-coexistence) ALLOW_COEXISTENCE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ -f "$SOURCE/.claude-plugin/plugin.json" ]] || die "built plugin is missing; run python3 scripts/build-plugin.py"
case "$SCOPE" in
  user)
    [[ -n "${HOME:-}" ]] || die "HOME is required for user scope"
    TARGET="$HOME/.claude/skills/madventures-founderos"
    BACKUP_BASE="$HOME/.claude/backups"
    ;;
  project)
    [[ -n "$PROJECT_PATH" ]] || die "--project is required for project scope"
    [[ -d "$PROJECT_PATH" ]] || die "project directory does not exist: $PROJECT_PATH"
    PROJECT_PATH="$(cd "$PROJECT_PATH" && pwd -P)"
    if [[ -f "$PROJECT_PATH/.claude/FOUNDEROS.md" && $ALLOW_COEXISTENCE -ne 1 ]]; then
      die "the full project environment is already present; use it instead, or pass --allow-coexistence intentionally"
    fi
    TARGET="$PROJECT_PATH/.claude/skills/madventures-founderos"
    BACKUP_BASE="$PROJECT_PATH/.claude-backups"
    ;;
  *) die "invalid scope: $SCOPE" ;;
esac

if ((DRY_RUN)); then
  log "DRY RUN: would install plugin to $TARGET"
  exit 0
fi

if [[ -e "$TARGET" && $FORCE -ne 1 ]]; then
  die "target already exists: $TARGET (use --force after reviewing the current copy)"
fi

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if [[ -e "$TARGET" ]]; then
  mkdir -p "$BACKUP_BASE"
  BACKUP="$BACKUP_BASE/madventures-founderos-plugin-$TIMESTAMP"
  cp -a "$TARGET" "$BACKUP"
  log "Backed up existing plugin to $BACKUP"
  rm -rf "$TARGET"
fi

mkdir -p "$(dirname "$TARGET")"
cp -a "$SOURCE" "$TARGET"
log "Installed portable plugin to $TARGET"
log "Restart Claude Code or run /reload-plugins. Verify with 'claude plugin list' and invoke /madventures-founderos:founder-command."
