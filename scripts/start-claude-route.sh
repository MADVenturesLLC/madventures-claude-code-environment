#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./scripts/start-claude-route.sh <profile> [claude arguments...]

Profiles:
  fanout         Haiku with no effort override for exploration/mechanical work
  everyday       Sonnet at high effort for normal coding
  deep           Opus at xhigh effort for demanding engineering
  planning       Fable at high effort in plan mode for consequential architecture
  judgment       Fable at xhigh effort for adversarial judgment/final synthesis
  max-judgment   Fable at max effort for one bounded, unusually costly decision
  best-available best at xhigh effort when Fable availability is uncertain
  advisor        Sonnet at high effort with an opt-in Opus advisor
  ultracode      best at session-only ultracode for substantive workflow orchestration
  review         Fable at xhigh with the project review-only settings profile

Run from the target repository root. Extra arguments are passed to Claude Code.
Profiles that name Fable or Advisor fail honestly when the account/provider does not expose them;
use best-available only when an explicit fallback is acceptable.
USAGE
}

[[ $# -ge 1 ]] || { usage; exit 2; }
profile="$1"
shift
command -v claude >/dev/null 2>&1 || { printf 'ERROR: claude CLI not found in PATH.\n' >&2; exit 127; }

clear_effort_env() {
  unset CLAUDE_CODE_EFFORT_LEVEL || true
}

case "$profile" in
  fanout)
    clear_effort_env
    exec claude --model haiku "$@"
    ;;
  everyday)
    clear_effort_env
    exec claude --model sonnet --effort high "$@"
    ;;
  deep)
    clear_effort_env
    exec claude --model opus --effort xhigh "$@"
    ;;
  planning)
    clear_effort_env
    exec claude --model fable --effort high --permission-mode plan "$@"
    ;;
  judgment)
    clear_effort_env
    exec claude --model fable --effort xhigh "$@"
    ;;
  max-judgment)
    clear_effort_env
    exec claude --model fable --effort max "$@"
    ;;
  best-available)
    clear_effort_env
    exec claude --model best --effort xhigh "$@"
    ;;
  advisor)
    clear_effort_env
    exec claude --model sonnet --effort high --advisor opus "$@"
    ;;
  ultracode)
    clear_effort_env
    exec claude --model best --effort ultracode "$@"
    ;;
  review)
    clear_effort_env
    settings="$PWD/.claude/profiles/review-only.settings.json"
    [[ -f "$settings" ]] || { printf 'ERROR: missing %s; install the full project environment first.\n' "$settings" >&2; exit 2; }
    exec claude --settings "$settings" --model fable --effort xhigh --permission-mode plan "$@"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    printf 'ERROR: unknown profile: %s\n\n' "$profile" >&2
    usage >&2
    exit 2
    ;;
esac
