#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
# Normalize to a durable working directory so transient test directories cannot leak into wrapper checks.
cd "$ROOT"
CONTROL="$ROOT/python-control-plane"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/madclaude-control-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'PYTHON CONTROL-PLANE TEST FAILED: %s\n' "$*" >&2; exit 1; }
assert_file() { [[ -f "$1" ]] || fail "missing file: $1"; }

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$CONTROL/src:$CONTROL/tests"

# Start from a clean release tree; prior validation runs may have emitted caches.
find "$ROOT" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$ROOT" -type f -name '*.pyc' -delete

python3 -m unittest discover -s "$CONTROL/tests" -v

# Compile source, tests, and entrypoints without creating __pycache__.
python3 - "$CONTROL" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
files = sorted(root.rglob('*.py'))
for path in files:
    compile(path.read_text(encoding='utf-8'), str(path), 'exec')
print(f'PYTHON SOURCE COMPILE PASSED: {len(files)} files')
PY

python3 "$CONTROL/bin/madclaude.py" --version | grep -Fq '4.4.2' || fail 'version self-check'
python3 "$CONTROL/bin/madclaude.py" routes --json > "$TMP/routes.json"
python3 - "$TMP/routes.json" <<'PY'
import json, sys
routes=json.load(open(sys.argv[1], encoding='utf-8'))
assert len(routes) == 11, len(routes)
assert routes['plan']['subagents'] == ['founder-os-explorer', 'dependency-mapper']
assert 'Agent' in routes['plan']['tools']
assert routes['build']['subagents'] == []
assert 'Agent' not in routes['build']['tools']
assert routes['fix-until-green']['subagents'] == []
assert 'Agent' not in routes['fix-until-green']['tools']
assert routes['architecture-validation']['model'] == 'opus'
assert routes['architecture-validation']['effort'] == 'max'
assert routes['architecture-validation']['exact_sha'] is True
assert routes['tier1-review']['schema'] == 'review'
assert all('Skill' not in route['tools'] for route in routes.values())
PY
python3 "$CONTROL/bin/madclaude.py" export-schemas "$TMP/exported-schemas" >/dev/null
[[ "$(find "$TMP/exported-schemas" -type f -name '*.schema.json' | wc -l | tr -d ' ')" == 10 ]] || fail 'schema export count'

repo="$TMP/repo"
home="$TMP/home"
mkdir -p "$repo" "$home"
git -C "$repo" init -q
git -C "$repo" config user.email tests@example.com
git -C "$repo" config user.name 'MADCLAUDE Tests'
printf '# Test\n' > "$repo/README.md"
mkdir -p "$repo/.claude/agents"
cp "$ROOT/project/.claude/agents/founder-os-explorer.md" "$repo/.claude/agents/"
cp "$ROOT/project/.claude/agents/dependency-mapper.md" "$repo/.claude/agents/"
printf '# Test profile\n' > "$repo/.claude/PROJECT_PROFILE.md"
git -C "$repo" add .
git -C "$repo" commit -q -m initial

fake="$TMP/claude"
marker="$TMP/model-invoked"
cat > "$fake" <<'EOF_FAKE'
#!/usr/bin/env python3
import json, os, pathlib, sys
args=sys.argv[1:]
if args[:2] == ['auth', 'status']:
    print(json.dumps({
        'loggedIn': True,
        'authMethod': 'claude.ai',
        'subscriptionType': 'max',
        'apiProvider': 'firstParty',
        'email': 'test@example.com',
    }))
    raise SystemExit(0)
pathlib.Path(os.environ['MADCLAUDE_TEST_MARKER']).write_text('unexpected model invocation', encoding='utf-8')
print('model invocation is forbidden in this shell test', file=sys.stderr)
raise SystemExit(77)
EOF_FAKE
chmod 0700 "$fake"

clean_env=(
  env -i
  "PATH=$PATH"
  "HOME=$home"
  "TERM=dumb"
  "NO_COLOR=1"
  "PYTHONDONTWRITEBYTECODE=1"
  "PYTHONPATH=$CONTROL/src"
  "MADCLAUDE_TEST_MARKER=$marker"
)

"${clean_env[@]}" python3 "$CONTROL/bin/madclaude.py" auth-check \
  --repo "$repo" --claude-path "$fake" --json > "$TMP/auth.json"
python3 - "$TMP/auth.json" <<'PY'
import json, sys
payload=json.load(open(sys.argv[1], encoding='utf-8'))
assert payload['auth']['credential_lane'] == 'subscription-saved-login'
assert payload['auth']['safe'] is True
assert 'test@example.com' not in str(payload)
PY

"${clean_env[@]}" python3 "$CONTROL/bin/madclaude.py" plan 'Dry-run plan' \
  --repo "$repo" --claude-path "$fake" \
  --dry-run --json > "$TMP/dry-run.json"
[[ ! -e "$marker" ]] || fail 'dry-run invoked a model'
[[ ! -e "$repo/.claude/evidence" ]] || fail 'dry-run wrote evidence'
python3 - "$TMP/dry-run.json" <<'PY'
import json, sys
payload=json.load(open(sys.argv[1], encoding='utf-8'))
assert payload['status'] == 'dry-run'
assert payload['wouldInvokeClaude'] is False
assert payload['wouldWriteEvidence'] is False
assert payload['backend'] == 'cli'
assert payload['billingMode'] == 'subscription'
PY

set +e
"${clean_env[@]}" ANTHROPIC_API_KEY='must-never-appear' python3 "$CONTROL/bin/madclaude.py" auth-check \
  --repo "$repo" --claude-path "$fake" --json > "$TMP/conflict.out" 2>&1
status=$?
set -e
[[ $status -eq 3 ]] || fail "subscription/API conflict returned $status instead of 3"
! grep -Fq 'must-never-appear' "$TMP/conflict.out" || fail 'credential value leaked in error output'
grep -Fq 'ANTHROPIC_API_KEY' "$TMP/conflict.out" || fail 'conflict did not identify credential variable name'

# Installer must be transparent, credential-neutral, subscription-first, and network-free by default.
install_home="$TMP/install-home"
bin_dir="$TMP/bin"
install_home_ps="$TMP/install-home-ps"
bin_dir_ps="$TMP/bin-ps"
MADCLAUDE_HOME="$install_home" MADCLAUDE_BIN_DIR="$bin_dir" \
  bash "$ROOT/scripts/install-python-control-plane.sh" --dry-run > "$TMP/install-dry-run.out"
grep -Fq 'native `claude -p` subscription execution requires no Python dependencies' "$TMP/install-dry-run.out" \
  || fail 'default dry-run did not declare dependency-free native CLI execution'
grep -Fq 'would not install the optional Agent SDK' "$TMP/install-dry-run.out" \
  || fail 'default dry-run did not explicitly omit the Agent SDK'
MADCLAUDE_HOME="$install_home" MADCLAUDE_BIN_DIR="$bin_dir" \
  bash "$ROOT/scripts/install-python-control-plane.sh" --with-sdk --dry-run > "$TMP/install-sdk-dry-run.out"
grep -Fq 'would additionally install optional claude-agent-sdk==0.2.131' "$TMP/install-sdk-dry-run.out" \
  || fail 'SDK opt-in dry-run did not declare the exact optional dependency'
[[ ! -e "$install_home" ]] || fail 'installer dry-run wrote install home'
MADCLAUDE_HOME="$install_home" MADCLAUDE_BIN_DIR="$bin_dir" \
  bash "$ROOT/scripts/install-python-control-plane.sh" > "$TMP/install.out"
assert_file "$install_home/app/bin/madclaude.py"
assert_file "$install_home/venv/bin/python"
assert_file "$bin_dir/madclaude"
"$bin_dir/madclaude" --version | grep -Fq '4.4.2' || fail 'installed wrapper self-check'
"$bin_dir/madclaude" routes --json >/dev/null || fail 'installed wrapper route registry'
# Regression: the launcher must live under bin/ in every deployed layout so it
# cannot shadow the madclaude package when commands run from that directory.
# A root-level deployed madclaude.py recreates that defect and must never appear.
[[ ! -e "$install_home/app/madclaude.py" ]] || fail 'deployed root-level madclaude.py reintroduces shadow risk'
"$install_home/venv/bin/python" "$install_home/app/bin/madclaude.py" --version | grep -Fq '4.4.2' \
  || fail 'bin/madclaude.py launcher self-check'
"$install_home/venv/bin/python" "$install_home/app/bin/madclaude.py" routes --json >/dev/null \
  || fail 'bin/madclaude.py launcher route registry'
# PowerShell installer path parity (best-effort; disclose when runtime absent).
if command -v pwsh >/dev/null 2>&1 || command -v powershell >/dev/null 2>&1; then
  ps_runner="$(command -v pwsh 2>/dev/null || command -v powershell)"
  MADCLAUDE_HOME="$install_home_ps" MADCLAUDE_BIN_DIR="$bin_dir_ps" \
    "$ps_runner" -NoProfile -ExecutionPolicy Bypass \
    "$ROOT/scripts/install-python-control-plane.ps1" > "$TMP/install.ps1.out" 2>&1 \
    && assert_file "$install_home_ps/app/bin/madclaude.py" \
    && { [[ ! -e "$install_home_ps/app/madclaude.py" ]] || fail 'ps1 deployed root-level madclaude.py reintroduces shadow risk'; } \
    || fail 'PowerShell installer failed (see install.ps1.out)'
else
  echo "[MADCLAUDE] NOTE: PowerShell runtime (pwsh/powershell) unavailable on this host; Windows installer path-parity not executed. Verified by static inspection of install-python-control-plane.ps1 (bin\\madclaude.py references)."
fi
"$install_home/venv/bin/python" - <<'PY_SDK' || fail 'default install unexpectedly included Agent SDK'
from importlib.util import find_spec
raise SystemExit(0 if find_spec('claude_agent_sdk') is None else 1)
PY_SDK
if [[ "$(stat -c '%a' "$install_home" 2>/dev/null || true)" ]]; then
  [[ "$(stat -c '%a' "$install_home")" == 700 ]] || fail 'install home is not mode 700'
  [[ "$(stat -c '%a' "$install_home/app")" == 700 ]] || fail 'installed app is not mode 700'
  [[ "$(stat -c '%a' "$bin_dir/madclaude")" == 700 ]] || fail 'wrapper is not mode 700'
fi
! grep -RIlF 'must-never-appear' "$install_home" "$bin_dir" >/dev/null \
  || fail 'test credential value found in installed files' 

find "$ROOT" -type d -name '__pycache__' -print -quit | grep -q . && fail 'test created package __pycache__'
find "$ROOT" -type f -name '*.pyc' -print -quit | grep -q . && fail 'test created package .pyc'

printf 'PYTHON CONTROL-PLANE TEST PASSED\n'
