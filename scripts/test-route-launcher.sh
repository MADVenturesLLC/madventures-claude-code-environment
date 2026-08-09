#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/bin" "$TMP/project/.claude/profiles"
cp "$ROOT/project/profiles/review-only.settings.json" "$TMP/project/.claude/profiles/"

cat > "$TMP/bin/claude" <<'FAKE'
#!/usr/bin/env bash
set -euo pipefail
{
  printf 'EFFORT=%s\n' "${CLAUDE_CODE_EFFORT_LEVEL-<unset>}"
  printf 'ARG='; printf '%q ' "$@"; printf '\n'
} > "${CLAUDE_TEST_OUTPUT:?}"
FAKE
chmod +x "$TMP/bin/claude"
export PATH="$TMP/bin:$PATH"

run_profile() {
  local profile="$1"
  local output="$TMP/${profile}.out"
  shift
  (
    cd "$TMP/project"
    CLAUDE_TEST_OUTPUT="$output" bash "$ROOT/scripts/start-claude-route.sh" "$profile" "$@"
  )
  [[ -s "$output" ]] || { printf 'No route output for %s\n' "$profile" >&2; exit 1; }
}

run_profile fanout --name fanout-test
run_profile everyday --name everyday-test
run_profile deep --name deep-test
run_profile planning --name planning-test
run_profile judgment --name judgment-test
run_profile max-judgment --name max-test
run_profile best-available --name fallback-test
run_profile advisor --name advisor-test
run_profile ultracode --name ultracode-test
run_profile review --name review-test

for output in "$TMP"/*.out; do
  grep -Fq 'EFFORT=<unset>' "$output"
done
grep -Fq -- '--model haiku' "$TMP/fanout.out"
grep -Fq -- '--model sonnet --effort high' "$TMP/everyday.out"
grep -Fq -- '--model opus --effort xhigh' "$TMP/deep.out"
grep -Fq -- '--model fable --effort high --permission-mode plan' "$TMP/planning.out"
grep -Fq -- '--model fable --effort xhigh' "$TMP/judgment.out"
grep -Fq -- '--model fable --effort max' "$TMP/max-judgment.out"
grep -Fq -- '--model best --effort xhigh' "$TMP/best-available.out"
grep -Fq -- '--model sonnet --effort high --advisor opus' "$TMP/advisor.out"
grep -Fq -- '--model best --effort ultracode' "$TMP/ultracode.out"
grep -Fq -- '--settings ' "$TMP/review.out"
grep -Fq -- '.claude/profiles/review-only.settings.json' "$TMP/review.out"
grep -Fq -- '--model fable --effort xhigh --permission-mode plan' "$TMP/review.out"

if (
  cd "$TMP/project"
  CLAUDE_TEST_OUTPUT="$TMP/invalid.out" bash "$ROOT/scripts/start-claude-route.sh" invalid >/dev/null 2>&1
); then
  printf 'Invalid route unexpectedly succeeded.\n' >&2
  exit 1
fi

printf 'MODEL ROUTE LAUNCHER TEST PASSED\n'
