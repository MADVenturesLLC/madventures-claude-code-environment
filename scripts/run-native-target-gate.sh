#!/usr/bin/env bash
# run-native-target-gate.sh — canonical native target-gate runner (one host per architecture).
#
# Runs scripts/audit9-target-gate.py on THIS host for the requested architecture and
# writes the per-machine evidence JSON. The gate records platform.machine() of the
# RUNNING interpreter and the release standard forbids architecture simulation
# (no Rosetta, no cross-arch runners, no caller-supplied arch strings), so this
# runner refuses to start on the wrong hardware.
#
# Usage:
#   bash scripts/run-native-target-gate.sh --arch arm64|x86_64 --release-dir releases/<name> [options]
#
# Options:
#   --arch ARCH         Required: arm64 | x86_64. Must match this host exactly.
#   --release-dir DIR   Required, e.g. releases/v4.4.2-20261003.
#   --branch BRANCH     Fetch and switch to origin/BRANCH first (self-fetching
#                       runner; never hard-resets work). Default: stay on the
#                       current branch.
#   --constraints FILE  Default: <release-dir>/evidence/wheelhouse-constraints-cp314-macos.txt
#   --artifact FILE     Default: <release-dir>/artifacts/MADVentures-Claude-Code-Environment-v<VERSION>.zip
#   --home DIR          Default: $HOME/.hermes/cache/scratch/audit<VERSIONCODE>-<ARCH>-home
#   --output FILE       Default: <release-dir>/evidence/audit<VERSIONCODE>-target-gate-<ARCH>.json
#   --commit-and-push   Commit and push the evidence JSON to the branch.
#   --dry-run           Guards + resolution only; print the plan and exit.
#   --allow-dirty       Skip the clean-clone guard (not recommended).
#
# Exit codes: 2 = wrong hardware/Rosetta; 3 = dirty clone; 4 = missing
# prerequisite; 5 = usage error.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd -P)"
cd "$REPO"

usage() {
  echo "usage: bash scripts/run-native-target-gate.sh --arch arm64|x86_64 --release-dir releases/<name> [--branch BRANCH] [--constraints FILE] [--artifact FILE] [--home DIR] [--output FILE] [--commit-and-push] [--dry-run] [--allow-dirty]" >&2
  exit 5
}

ARCH="" ; RELEASE_DIR="" ; BRANCH="" ; CONSTRAINTS="" ; ARTIFACT="" ; GATE_HOME="" ; OUT=""
COMMIT_AND_PUSH=0 ; DRY_RUN=0 ; ALLOW_DIRTY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --arch)            [ $# -ge 2 ] || usage; ARCH="$2"; shift 2 ;;
    --release-dir)     [ $# -ge 2 ] || usage; RELEASE_DIR="$2"; shift 2 ;;
    --branch)          [ $# -ge 2 ] || usage; BRANCH="$2"; shift 2 ;;
    --constraints)     [ $# -ge 2 ] || usage; CONSTRAINTS="$2"; shift 2 ;;
    --artifact)        [ $# -ge 2 ] || usage; ARTIFACT="$2"; shift 2 ;;
    --home)            [ $# -ge 2 ] || usage; GATE_HOME="$2"; shift 2 ;;
    --output)          [ $# -ge 2 ] || usage; OUT="$2"; shift 2 ;;
    --commit-and-push) COMMIT_AND_PUSH=1; shift ;;
    --dry-run)         DRY_RUN=1; shift ;;
    --allow-dirty)     ALLOW_DIRTY=1; shift ;;
    -h|--help)         usage ;;
    *) echo "unknown argument: $1" >&2; usage ;;
  esac
done

[ -n "$ARCH" ] || { echo "error: --arch is required (arm64|x86_64)" >&2; usage; }
[ -n "$RELEASE_DIR" ] || { echo "error: --release-dir is required" >&2; usage; }
case "$ARCH" in arm64|x86_64) ;; *) echo "error: --arch must be arm64 or x86_64" >&2; usage ;; esac

VERSION="$(tr -d '[:space:]' < VERSION)"
VERSION_CODE="$(printf '%s' "$VERSION" | tr -d '.')"
[ -n "$CONSTRAINTS" ] || CONSTRAINTS="$RELEASE_DIR/evidence/wheelhouse-constraints-cp314-macos.txt"
[ -n "$ARTIFACT" ] || ARTIFACT="$RELEASE_DIR/artifacts/MADVentures-Claude-Code-Environment-v${VERSION}.zip"
[ -n "$GATE_HOME" ] || GATE_HOME="$HOME/.hermes/cache/scratch/audit${VERSION_CODE}-${ARCH}-home"
[ -n "$OUT" ] || OUT="$RELEASE_DIR/evidence/audit${VERSION_CODE}-target-gate-${ARCH}.json"

# --- Guard 1: native hardware only (no emulation) -------------------------------
HOST_ARCH="$(python3 -c 'import platform; print(platform.machine())')"
TRANSLATED="$(sysctl -n sysctl.proc_translated 2>/dev/null || echo 0)"
if [ "$HOST_ARCH" != "$ARCH" ] || [ "$TRANSLATED" = "1" ]; then
  echo "REFUSING TO RUN: requested --arch $ARCH, but this host reports arch=$HOST_ARCH (rosetta_translated=$TRANSLATED)."
  echo "The release standard forbids architecture simulation: run the $ARCH gate on native $ARCH hardware."
  exit 2
fi

# --- Guard 2: never touch a clone with uncommitted changes ----------------------
if [ "$ALLOW_DIRTY" = "0" ] && [ -n "$(git status --porcelain)" ]; then
  echo "REFUSING TO RUN: this clone has uncommitted changes:"
  git status --short
  echo "Commit, stash, or discard them deliberately, then rerun (or pass --allow-dirty)."
  exit 3
fi

# --- Prerequisites --------------------------------------------------------------
[ -d "$RELEASE_DIR" ]       || { echo "error: missing release dir: $RELEASE_DIR" >&2; exit 4; }
[ -f "$CONSTRAINTS" ]       || { echo "error: missing constraints file: $CONSTRAINTS" >&2; exit 4; }
[ -f "$ARTIFACT" ]          || { echo "error: missing artifact: $ARTIFACT" >&2; exit 4; }
grep -q '==' "$CONSTRAINTS" || { echo "error: constraints file has no pinned requirements: $CONSTRAINTS" >&2; exit 4; }

if [ "$DRY_RUN" = "1" ]; then
  echo "DRY RUN — guards passed; nothing executed."
  echo "  host arch:       $HOST_ARCH (rosetta_translated=$TRANSLATED)"
  echo "  requested arch:  $ARCH"
  echo "  release dir:     $RELEASE_DIR"
  echo "  version:         $VERSION"
  echo "  constraints:     $CONSTRAINTS ($(grep -c '==' "$CONSTRAINTS") pins)"
  echo "  artifact:        $ARTIFACT"
  echo "  gate home:       $GATE_HOME"
  echo "  evidence output: $OUT"
  if [ -n "$BRANCH" ]; then
    echo "  branch:          $BRANCH (will fetch + switch)"
  else
    echo "  branch:          current ($(git branch --show-current))"
  fi
  echo "Command that would run:"
  echo "  PIP_CONSTRAINT=$CONSTRAINTS python3 scripts/audit9-target-gate.py --home $GATE_HOME --output $OUT --artifact $ARTIFACT"
  exit 0
fi

# --- Optional self-fetch (never a hard reset) -----------------------------------
if [ -n "$BRANCH" ]; then
  git fetch origin "$BRANCH"
  git checkout -B "$BRANCH" "origin/$BRANCH"
fi

rm -rf "$GATE_HOME" "$OUT"
mkdir -p "$GATE_HOME" "$(dirname "$OUT")"

echo "=== constraints in effect (first 5 pins) ==="
grep '==' "$CONSTRAINTS" | head -n 5

PIP_CONSTRAINT="$CONSTRAINTS" python3 scripts/audit9-target-gate.py \
  --home "$GATE_HOME" \
  --output "$OUT" \
  --artifact "$ARTIFACT"

echo
echo "=== $ARCH gate evidence written: $OUT ==="
shasum -a 256 "$OUT"
python3 - "$OUT" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1])
d = json.loads(p.read_text())
print("machine:", d["machine"], "| platformMachine:", d["platformMachine"])
print("evidenceClass:", d["evidenceClass"], "| releaseEvidence:", d["releaseEvidence"])
print("artifactSha256:", d["artifactSha256"])
failed = [s["step"] for s in d["steps"] if s["exitCode"] != 0]
print("failed steps:", failed or "NONE")
print("installed mcp:", d.get("installedInventory", {}).get("mcp"))
PY

echo
if [ "$COMMIT_AND_PUSH" = "1" ]; then
  if [ -z "$BRANCH" ]; then
    BRANCH="$(git branch --show-current)"
  fi
  git add "$OUT"
  git commit -m "release: ${ARCH} native target gate evidence (${VERSION})" \
    --trailer "Role-Id: builder" \
    --trailer "Actor-Id: session:founder/native-gate-runner" \
    --trailer "Execution-Surface: hermes-local-code"
  git push origin "$BRANCH"
  echo "DONE — evidence committed and pushed on $BRANCH."
else
  echo "Evidence NOT committed or pushed. Re-run with --commit-and-push, or commit manually:"
  echo "  git add $OUT && git commit && git push"
fi
