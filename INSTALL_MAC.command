#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd -P)"
LOG="$ROOT/install-v4.4.2.log"

pause_on_exit() {
  status=$?
  echo
  if [[ $status -eq 0 ]]; then
    echo "Installation workflow finished successfully."
  else
    echo "Installation stopped with status $status. Review: $LOG"
  fi
  echo "Press Return to close this window."
  read -r _ || true
  exit "$status"
}
trap pause_on_exit EXIT

exec > >(tee -a "$LOG") 2>&1
clear || true
cat <<'BANNER'
============================================================
 MAD Ventures Claude Code Operating Environment V4.4.2
 Finder-visible guided installer for macOS
============================================================

This installer backs up managed Claude configuration before writing.
It installs the subscription-first Python control plane without the
optional API SDK.
BANNER

command -v python3 >/dev/null 2>&1 || {
  echo "Python 3.10+ is required. Install Python, then run this installer again."
  exit 1
}

python3 "$ROOT/scripts/quick-validate.py"

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  if command -v osascript >/dev/null 2>&1; then
    set +e
    TARGET="$(osascript -e 'POSIX path of (choose folder with prompt "Choose the Git repository that should receive the MAD Ventures Claude Code environment")' 2>/dev/null)"
    choice_status=$?
    set -e
    if [[ $choice_status -ne 0 || -z "$TARGET" ]]; then
      echo "No repository was selected. Nothing was changed."
      exit 2
    fi
  else
    read -r -p "Absolute path to the target repository: " TARGET
  fi
fi
TARGET="${TARGET%/}"
[[ -d "$TARGET" ]] || { echo "Target is not a directory: $TARGET"; exit 1; }

PROFILE="auto"
echo
read -r -p "Profile [auto/generic/doctrine/runtime/console] (default: auto): " entered_profile || true
if [[ -n "${entered_profile:-}" ]]; then PROFILE="$entered_profile"; fi
case "$PROFILE" in auto|generic|doctrine|runtime|console) ;; *) echo "Invalid profile: $PROFILE"; exit 1 ;; esac

echo
echo "Target:  $TARGET"
echo "Profile: $PROFILE"
echo "A timestamped backup will be created inside the repository."
read -r -p "Install now? [Y/n]: " confirm || true
case "${confirm:-Y}" in n|N|no|NO) echo "Cancelled. Nothing was changed."; exit 2 ;; esac

bash "$ROOT/scripts/install.sh" "$TARGET" \
  --profile "$PROFILE" \
  --install-python-control-plane

echo
printf '%s\n' "Installed environment:" "$TARGET/.claude"
printf '%s\n' "Next commands:" \
  "  cd \"$TARGET\"" \
  "  claude doctor" \
  "  python3 .claude/control-plane/madclaude.py auth-check --repo ."

if [[ "$(uname -s)" == "Darwin" ]] && command -v open >/dev/null 2>&1; then
  open "$TARGET/.claude" || true
fi
