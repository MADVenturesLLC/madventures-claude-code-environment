#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
HOOK="$ROOT/project/.claude/cloud/session-start.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/mad-cloud-session.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'CLOUD SESSION TEST FAILED: %s\n' "$*" >&2; exit 1; }
repo="$TMP/repo"
mkdir -p "$repo"
git -C "$repo" init -q

# Local execution is a no-op.
CLAUDE_PROJECT_DIR="$repo" bash "$HOOK" >/dev/null

# Remote execution with dependency bootstrap disabled is observational only.
out="$(CLAUDE_CODE_REMOTE=true MADVENTURES_CLOUD_INSTALL_DEPS=false CLAUDE_PROJECT_DIR="$repo" bash "$HOOK")"
grep -Fq 'Dependency bootstrap disabled' <<<"$out" || fail 'disabled remote path did not report its state'

# Enabling bootstrap without a recognized dependency contract must fail safely.
if CLAUDE_CODE_REMOTE=true MADVENTURES_CLOUD_INSTALL_DEPS=true CLAUDE_PROJECT_DIR="$repo" bash "$HOOK" >/dev/null 2>&1; then
  fail 'bootstrap unexpectedly succeeded without a recognized lockfile'
fi

# A recognized lockfile uses the immutable command. Mock npm to avoid network access.
mkdir -p "$TMP/bin"
cat > "$TMP/bin/npm" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$*" > "${MAD_TEST_NPM_RECORD:?}"
MOCK
chmod +x "$TMP/bin/npm"
printf '{}\n' > "$repo/package-lock.json"
record="$TMP/npm.record"
PATH="$TMP/bin:$PATH" MAD_TEST_NPM_RECORD="$record" CLAUDE_CODE_REMOTE=true \
  MADVENTURES_CLOUD_INSTALL_DEPS=true CLAUDE_PROJECT_DIR="$repo" bash "$HOOK" >/dev/null
[[ "$(cat "$record")" == 'ci' ]] || fail "expected npm ci, got '$(cat "$record")'"

printf 'CLOUD SESSION TEST PASSED\n'
