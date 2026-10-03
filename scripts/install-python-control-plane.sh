#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
SOURCE_ROOT="$ROOT/python-control-plane"
INSTALL_HOME="${MADCLAUDE_HOME:-${HOME:?HOME is required}/.madclaude}"
BIN_DIR="${MADCLAUDE_BIN_DIR:-${HOME}/.local/bin}"
PYTHON_BIN="${PYTHON:-python3}"
WITH_SDK=0
NO_DEPS_COMPAT=0
DRY_RUN=0
SDK_VERSION="0.2.131"

usage() {
  cat <<'USAGE'
Install MAD Ventures Python Claude Control Plane 4.4.2

Usage:
  ./scripts/install-python-control-plane.sh [options]

Options:
  --home PATH       install home (default: ~/.madclaude)
  --bin-dir PATH    wrapper destination (default: ~/.local/bin)
  --python PATH     Python 3.10+ interpreter (default: python3)
  --with-sdk        additionally install claude-agent-sdk==0.2.131 for the
                    explicit API-billed SDK backend
  --no-deps         deprecated compatibility no-op; the default already
                    installs no Python dependencies
  --dry-run         print operations without writing or downloading
  --help

The governed default is the dependency-free native CLI backend. Python invokes
the official `claude -p` command under the Claude Code subscription login that
is already active on this machine.

The installer never reads, copies, creates, sets, or modifies Claude credentials.
Subscription mode fails closed if ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or a
provider/gateway credential could override subscription authentication.

The optional Agent SDK is not installed unless --with-sdk is supplied. V4.4
permits that backend only with explicit API billing authorization:
  --backend sdk --billing-mode api --allow-api-billing --max-budget-usd <positive>
USAGE
}

die() { printf '[MADCLAUDE] ERROR: %s\n' "$*" >&2; exit 1; }
log() { printf '[MADCLAUDE] %s\n' "$*"; }

while (($#)); do
  case "$1" in
    --home) (($# >= 2)) || die '--home requires a path'; INSTALL_HOME="$2"; shift 2 ;;
    --bin-dir) (($# >= 2)) || die '--bin-dir requires a path'; BIN_DIR="$2"; shift 2 ;;
    --python) (($# >= 2)) || die '--python requires a path'; PYTHON_BIN="$2"; shift 2 ;;
    --with-sdk) WITH_SDK=1; shift ;;
    --no-deps) NO_DEPS_COMPAT=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ -f "$SOURCE_ROOT/bin/madclaude.py" ]] || die "control-plane source not found: $SOURCE_ROOT"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python interpreter not found: $PYTHON_BIN"
"$PYTHON_BIN" - <<'PY_VERSION' || die 'Python 3.10 or later is required.'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY_VERSION

INSTALL_HOME="$("$PYTHON_BIN" -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).expanduser().resolve())' "$INSTALL_HOME")"
BIN_DIR="$("$PYTHON_BIN" -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).expanduser().resolve())' "$BIN_DIR")"
DEST="$INSTALL_HOME/app"
VENV="$INSTALL_HOME/venv"
VENV_PYTHON="$VENV/bin/python"
WRAPPER="$BIN_DIR/madclaude"

if ((NO_DEPS_COMPAT)); then
  log 'NOTE: --no-deps is deprecated; dependency-free installation is already the default.'
fi

if ((DRY_RUN)); then
  log "DRY RUN: would create isolated Python environment at $VENV"
  log "DRY RUN: would atomically copy source to $DEST"
  log "DRY RUN: would install the package-identity manifest at $INSTALL_HOME/MANIFEST.json"
  log "DRY RUN: would install wrapper at $WRAPPER"
  log 'DRY RUN: native `claude -p` subscription execution requires no Python dependencies'
  if ((WITH_SDK)); then
    log "DRY RUN: would additionally install optional claude-agent-sdk==$SDK_VERSION for explicit API-billed SDK runs"
  else
    log 'DRY RUN: would not install the optional Agent SDK'
  fi
  log 'DRY RUN: would not modify credentials or Claude authentication settings'
  exit 0
fi

mkdir -p "$INSTALL_HOME" "$BIN_DIR"
chmod 0700 "$INSTALL_HOME" 2>/dev/null || true
if [[ ! -x "$VENV_PYTHON" ]]; then
  log "Creating isolated environment: $VENV"
  "$PYTHON_BIN" -m venv "$VENV"
fi

if ((WITH_SDK)); then
  log "Installing optional Agent SDK $SDK_VERSION for the explicit API-billed backend..."
  "$VENV_PYTHON" -m pip install --disable-pip-version-check --upgrade "claude-agent-sdk==$SDK_VERSION"
  "$VENV_PYTHON" - <<PY_VERIFY
from importlib.metadata import version
actual = version('claude-agent-sdk')
assert actual == '$SDK_VERSION', f'expected $SDK_VERSION, got {actual}'
print(f'[MADCLAUDE] Verified optional claude-agent-sdk {actual}')
PY_VERIFY
else
  log 'Dependency-free default: skipping Agent SDK installation.'
fi

STAGING="$INSTALL_HOME/.app.staging.$$"
rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -a "$SOURCE_ROOT/." "$STAGING/"
find "$STAGING" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGING" -type f -name '*.pyc' -delete 2>/dev/null || true
# The launcher ships at bin/madclaude.py in every control-plane layout (source,
# staging, and deployed ~/.madclaude/app). Keeping it under bin/ prevents the
# module-shadow defect when commands run from that directory.
if [[ -d "$DEST" ]]; then
  BACKUP="$INSTALL_HOME/app.backup.$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$DEST" "$BACKUP"
  log "Backed up existing control plane: $BACKUP"
fi
mv "$STAGING" "$DEST"
find "$DEST" -type d -exec chmod 0700 {} + 2>/dev/null || true
find "$DEST" -type d -exec chmod u-s,g-s,o-t {} + 2>/dev/null || true
find "$DEST" -type f -exec chmod 0600 {} + 2>/dev/null || true

# Package-identity manifest (R6-04): the immutable identity input hashed for
# release identity derivation. The CLI resolves exactly one explicit location
# — $MADCLAUDE_HOME/MANIFEST.json — so the installer places it deliberately.
[[ -f "$ROOT/MANIFEST.json" ]] || die "package identity manifest not found: $ROOT/MANIFEST.json"
cp "$ROOT/MANIFEST.json" "$INSTALL_HOME/MANIFEST.json"
chmod 0600 "$INSTALL_HOME/MANIFEST.json"

if [[ -e "$WRAPPER" || -L "$WRAPPER" ]]; then
  BACKUP="$WRAPPER.backup.$(date -u +%Y%m%dT%H%M%SZ)"
  cp -a "$WRAPPER" "$BACKUP"
  rm -f "$WRAPPER"
  log "Backed up existing wrapper: $BACKUP"
fi
cat > "$WRAPPER" <<EOF_WRAPPER
#!/usr/bin/env sh
exec "$VENV_PYTHON" "$DEST/bin/madclaude.py" "\$@"
EOF_WRAPPER
chmod 0700 "$WRAPPER"

"$VENV_PYTHON" "$DEST/bin/madclaude.py" --version
log "Installed source: $DEST"
log "Installed wrapper: $WRAPPER"
if ((WITH_SDK)); then
  log "Optional Agent SDK $SDK_VERSION installed; the native CLI subscription backend remains the default."
else
  log 'Installed with no third-party Python dependencies; native `claude -p` subscription execution is ready.'
fi
log 'Next: remove API/provider credential overrides from this shell, run `claude auth login`, then `madclaude auth-check --repo /path/to/repo`.'
log 'Credential preflight cannot prove model-specific entitlement, remaining allowance, or whether account-level usage credits are enabled. Python Fable routes add a separate fail-closed acknowledgement gate.'
