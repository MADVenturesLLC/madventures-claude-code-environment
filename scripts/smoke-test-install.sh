#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
PACKAGE_VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
PACKAGE_SERIES="v${PACKAGE_VERSION%.*}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/mad-ccoe-smoke.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'SMOKE TEST FAILED: %s\n' "$*" >&2; exit 1; }
assert_file() { [[ -f "$1" ]] || fail "missing file: $1"; }
assert_dir() { [[ -d "$1" ]] || fail "missing directory: $1"; }
assert_eq() { [[ "$1" == "$2" ]] || fail "expected '$2', got '$1' ($3)"; }

# Package validation is run separately by the release pipeline; this script exercises installation only.

# Fresh generic repository.
repo1="$TMP/generic-repo"
mkdir -p "$repo1"
git -C "$repo1" init -q
MADVENTURES_LIFECYCLE_TEST_FAST=1 bash "$ROOT/scripts/install.sh" "$repo1" --profile generic --skip-validation >/dev/null
assert_file "$repo1/.claude/FOUNDEROS.md"
assert_file "$repo1/.claude/MODEL_REGISTRY.md"
assert_file "$repo1/.claude/CLAUDE.md"
assert_file "$repo1/.claude/PROJECT_PROFILE.md"
assert_file "$repo1/.claude/settings.json"
assert_file "$repo1/.mcp.example.json"
assert_file "$repo1/.claude/INSTALLATION_RECORD.md"
assert_file "$repo1/.claude/cloud/session-start.sh"
assert_file "$repo1/.claude/profiles/cloud-session-start.settings.fragment.json"
assert_file "$repo1/.claude/profiles/advisor-opus.settings.fragment.json"
assert_file "$repo1/.claude/control-plane/bin/madclaude.py"
assert_file "$repo1/.claude/control-plane/src/madclaude/auth.py"
assert_file "$repo1/.claude/control-plane/schemas/review.schema.json"
python3 - "$repo1/.mcp.example.json" <<'PYJSON'
import json, sys
cfg=json.load(open(sys.argv[1], encoding='utf-8'))['mcpServers']['github-readonly']
assert cfg['url'] == 'https://api.githubcopilot.com/mcp/'
assert cfg['headers']['X-MCP-Readonly'] == 'true'
assert 'repos' in cfg['headers']['X-MCP-Toolsets']
PYJSON
python3 - "$repo1/.claude/settings.json" "$repo1/.claude/profiles/advisor-opus.settings.fragment.json" <<'PYJSON'
import json, sys
base=json.load(open(sys.argv[1], encoding='utf-8'))
advisor=json.load(open(sys.argv[2], encoding='utf-8'))
assert 'SessionStart' not in base.get('hooks', {}), 'cloud dependency bootstrap must remain opt-in'
assert 'advisorModel' not in base, 'advisor must remain opt-in'
assert advisor.get('advisorModel') == 'opus', 'advisor profile must route to opus'
PYJSON
assert_eq "$(find "$repo1/.claude/agents" -type f -name '*.md' | wc -l | tr -d ' ')" "20" "agent count"
assert_eq "$(find "$repo1/.claude/skills" -type f -name 'SKILL.md' | wc -l | tr -d ' ')" "31" "skill count"
assert_eq "$(find "$repo1/.claude/workflows" -type f -name '*.js' | wc -l | tr -d ' ')" "0" "executable workflow count"
assert_eq "$(find "$repo1/.claude/rules" -type f -name '*.md' | wc -l | tr -d ' ')" "8" "rule count"
python3 "$repo1/.claude/control-plane/bin/madclaude.py" --version | grep -Fq '4.4.2' || fail "installed control-plane version"
python3 "$repo1/.claude/control-plane/bin/madclaude.py" routes --json >/dev/null || fail "installed control-plane route registry"
# The canonical control-plane suite runs immediately before this installer smoke test in build-release.sh.
# Here we prove the installed copy starts and exposes the expected registry without rerunning the full suite.
assert_eq "$(grep -Ec '^[[:space:]]*@FOUNDEROS\.md[[:space:]]*$' "$repo1/.claude/CLAUDE.md")" "1" "FOUNDEROS import count"
assert_eq "$(grep -Fc '# >>> MAD Ventures Claude Code Environment >>>' "$repo1/.gitignore")" "1" "gitignore marker count"

# Reinstall must remain idempotent for imports/markers.
bash "$ROOT/scripts/install.sh" "$repo1" --profile generic --skip-validation >/dev/null
assert_eq "$(grep -Ec '^[[:space:]]*@FOUNDEROS\.md[[:space:]]*$' "$repo1/.claude/CLAUDE.md")" "1" "FOUNDEROS import after reinstall"
assert_eq "$(grep -Fc '# >>> MAD Ventures Claude Code Environment >>>' "$repo1/.gitignore")" "1" "gitignore marker after reinstall"
assert_file "$repo1/.claude/settings.founderos-${PACKAGE_SERIES}.example.json"

# Existing settings and profile must be preserved by default.
repo2="$TMP/existing-config"
mkdir -p "$repo2/.claude"
git -C "$repo2" init -q
printf '{"model":"haiku"}\n' > "$repo2/.claude/settings.json"
printf '# Custom project profile\nKEEP_ME\n' > "$repo2/.claude/PROJECT_PROFILE.md"
printf '# Existing repository rules\n' > "$repo2/.claude/CLAUDE.md"
MADVENTURES_LIFECYCLE_TEST_FAST=1 bash "$ROOT/scripts/install.sh" "$repo2" --skip-validation >/dev/null
assert_eq "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["model"])' "$repo2/.claude/settings.json")" "haiku" "existing settings preserved"
grep -Fq 'KEEP_ME' "$repo2/.claude/PROJECT_PROFILE.md" || fail "existing project profile was overwritten"
assert_file "$repo2/.claude/settings.founderos-${PACKAGE_SERIES}.example.json"
assert_eq "$(grep -Ec '^[[:space:]]*@FOUNDEROS\.md[[:space:]]*$' "$repo2/.claude/CLAUDE.md")" "1" "import appended to existing CLAUDE.md"

# Force settings replacement after backup.
MADVENTURES_LIFECYCLE_TEST_FAST=1 bash "$ROOT/scripts/install.sh" "$repo2" --force-settings --skip-validation >/dev/null
assert_eq "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["model"])' "$repo2/.claude/settings.json")" "sonnet" "forced shared settings"
find "$repo2/.claude-backups" -type f -path '*/.claude/settings.json' -print -quit | grep -q . || fail "settings backup not found"

# Auto-detect doctrine profile.
repo3="$TMP/FounderOS"
mkdir -p "$repo3/04-agents" "$repo3/00-system/scripts"
touch "$repo3/04-agents/role-registry.md" "$repo3/00-system/scripts/path-audit.sh"
git -C "$repo3" init -q
MADVENTURES_LIFECYCLE_TEST_FAST=1 bash "$ROOT/scripts/install.sh" "$repo3" --profile auto --skip-validation >/dev/null
grep -Fq 'MADVenturesLLC/FounderOS doctrine repository' "$repo3/.claude/PROJECT_PROFILE.md" || fail "doctrine profile not auto-detected"

# Dry run must not write.
repo4="$TMP/dry-run"
mkdir -p "$repo4"
bash "$ROOT/scripts/install.sh" "$repo4" --dry-run --skip-validation >/dev/null
[[ ! -e "$repo4/.claude" ]] || fail "dry run wrote .claude"

# Optional global install in an isolated HOME.
repo5="$TMP/global-test-repo"
home5="$TMP/home"
mkdir -p "$repo5" "$home5"
HOME="$home5" MADVENTURES_LIFECYCLE_TEST_FAST=1 bash "$ROOT/scripts/install.sh" "$repo5" --install-global --skip-validation >/dev/null
HOME="$home5" bash "$ROOT/scripts/install-python-control-plane.sh" >/dev/null
assert_file "$home5/.claude/MADVENTURES.md"
assert_file "$home5/.claude/madventures-statusline.mjs"
assert_file "$home5/.claude/examples/madventures-${PACKAGE_SERIES}/settings.json.fragment"
assert_eq "$(grep -Ec '^[[:space:]]*@MADVENTURES\.md[[:space:]]*$' "$home5/.claude/CLAUDE.md")" "1" "global doctrine import"
assert_file "$home5/.madclaude/app/bin/madclaude.py"
# The launcher must stay under bin/ in the deployed global layout; a root-level
# deployed madclaude.py would reintroduce the module-shadow defect.
[[ ! -e "$home5/.madclaude/app/madclaude.py" ]] || fail "global deploy must not ship root-level madclaude.py"
assert_file "$home5/.local/bin/madclaude"
assert_file "$home5/.madclaude/venv/bin/python"
"$home5/.madclaude/venv/bin/python" - <<'PY_SDK' || fail "default global install unexpectedly included Agent SDK"
from importlib.util import find_spec
raise SystemExit(0 if find_spec('claude_agent_sdk') is None else 1)
PY_SDK
HOME="$home5" "$home5/.local/bin/madclaude" routes --json >/dev/null || fail "global madclaude wrapper"

# Portable plugin user-scope install and forced replacement.
home6="$TMP/plugin-home"
mkdir -p "$home6"
HOME="$home6" bash "$ROOT/scripts/install-plugin.sh" --scope user >/dev/null
plugin6="$home6/.claude/skills/madventures-founderos"
assert_file "$plugin6/.claude-plugin/plugin.json"
assert_eq "$(find "$plugin6/agents" -type f -name '*.md' | wc -l | tr -d ' ')" "19" "plugin agent count"
assert_eq "$(find "$plugin6/skills" -type f -name 'SKILL.md' | wc -l | tr -d ' ')" "31" "plugin skill count"
assert_eq "$(find "$plugin6/workflows" -type f -name '*.js' | wc -l | tr -d ' ')" "0" "plugin executable workflow count"
[[ ! -e "$plugin6/agents/neon-reader.md" ]] || fail "portable plugin must exclude neon-reader"
HOME="$home6" bash "$ROOT/scripts/install-plugin.sh" --scope user --force >/dev/null
find "$home6/.claude/backups" -maxdepth 1 -type d -name 'madventures-founderos-plugin-*' -print -quit | grep -q . || fail "plugin backup not found"

# Project-scope plugin refuses coexistence with the full project environment by default.
if HOME="$home6" bash "$ROOT/scripts/install-plugin.sh" --scope project --project "$repo1" >/dev/null 2>&1; then
  fail "plugin installer allowed unintentional coexistence with full project environment"
fi

printf 'INSTALLATION SMOKE TEST PASSED\n'
