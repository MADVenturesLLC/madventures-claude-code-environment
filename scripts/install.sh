#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
LIFECYCLE="$SCRIPT_DIR/environment-lifecycle.py"

# Fast validation remains the default; --full-validation selects validate-config.py.
# Legacy usage remains valid: install.sh /repo --profile auto --dry-run
case "${1:-}" in
  install|update|status|doctor|uninstall|restore)
    action="$1"
    shift
    exec python3 "$LIFECYCLE" "$action" "$@"
    ;;
  *)
    exec python3 "$LIFECYCLE" install "$@"
    ;;
esac
