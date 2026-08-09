#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
PACKAGE_NAME="MADVentures-Claude-Code-Environment-v${VERSION}"
MAIN_OUTPUT="${1:-$(dirname "$ROOT")/${PACKAGE_NAME}.zip}"
PLUGIN_OUTPUT="${2:-$(dirname "$ROOT")/MADVentures-FounderOS-Claude-Code-Plugin-v${VERSION}.zip}"
TAR_OUTPUT="${3:-$(dirname "$ROOT")/${PACKAGE_NAME}.tar.gz}"

checksum_file() {
  python3 - "$1" <<'PY'
import hashlib, pathlib, sys
path = pathlib.Path(sys.argv[1])
digest = hashlib.sha256(path.read_bytes()).hexdigest()
print(f"{digest}  {path.name}")
PY
}

# Rebuild generated delivery and portability assets first so validation always sees canonical output.
python3 "$ROOT/scripts/sync-visible-template.py"
python3 "$ROOT/scripts/build-plugin.py"
python3 "$ROOT/scripts/generate-delivery-index.py"
python3 "$ROOT/scripts/generate-manifest.py"
bash "$ROOT/scripts/test-python-control-plane.sh"
python3 "$ROOT/scripts/validate-config.py" --report "$ROOT/docs/VALIDATION_REPORT.md" --skip-python-integration
if command -v claude >/dev/null 2>&1; then
  claude plugin validate "$ROOT/plugin/madventures-founderos" --strict
else
  printf 'WARNING: claude CLI not found; skipped official plugin validation.\n' >&2
fi
node "$ROOT/scripts/validate-workflows.mjs"
node "$ROOT/scripts/test-hooks.mjs"
bash "$ROOT/scripts/smoke-test-install.sh"
bash "$ROOT/scripts/test-route-launcher.sh"
bash "$ROOT/scripts/test-cloud-session.sh"

# Keep generated package contents clean before hashing.
find "$ROOT" -type d \( -name '__pycache__' -o -name '.pytest_cache' \) -prune -exec rm -rf {} +
find "$ROOT" -type f -name '.DS_Store' -delete
python3 "$ROOT/scripts/generate-delivery-index.py"

python3 "$ROOT/scripts/generate-manifest.py"
python3 "$ROOT/scripts/quick-validate.py"
# Revalidate after manifest generation without rewriting the report timestamp.
python3 "$ROOT/scripts/validate-config.py" --no-report --skip-python-integration
node "$ROOT/scripts/validate-workflows.mjs"

# quick-validate.py above already fails closed on every manifest/checksum mismatch.

python3 "$ROOT/scripts/create-zip.py" "$MAIN_OUTPUT"
python3 "$ROOT/scripts/create-tar.py" "$TAR_OUTPUT"
python3 "$ROOT/scripts/create-plugin-zip.py" "$PLUGIN_OUTPUT"
python3 "$ROOT/scripts/test-release-archives.py" "$MAIN_OUTPUT" "$TAR_OUTPUT"
python3 "$ROOT/scripts/verify-release.py" "$MAIN_OUTPUT" "$PLUGIN_OUTPUT"

checksum_file "$MAIN_OUTPUT" > "$MAIN_OUTPUT.sha256"
checksum_file "$PLUGIN_OUTPUT" > "$PLUGIN_OUTPUT.sha256"
checksum_file "$TAR_OUTPUT" > "$TAR_OUTPUT.sha256"

printf 'Release built and verified:\n  Full ZIP: %s\n  Full TAR.GZ: %s\n  Portable plugin: %s\n' "$MAIN_OUTPUT" "$TAR_OUTPUT" "$PLUGIN_OUTPUT"
