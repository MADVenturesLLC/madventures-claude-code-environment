#!/usr/bin/env bash
# run-native-target-gate.sh — canonical native target-gate runner (one host per architecture).
#
# Runs scripts/audit9-target-gate.py on THIS host for the requested architecture and
# writes the per-machine evidence JSON. The gate records platform.machine() of the
# RUNNING interpreter and the release standard forbids architecture simulation
# (no Rosetta, no cross-arch runners, no caller-supplied arch strings), so this
# runner refuses to start on the wrong hardware or OS, or on an interpreter other
# than the CPython 3.14 that the cp314-macos wheel contract requires.
#
# Usage:
#   bash scripts/run-native-target-gate.sh --arch arm64|x86_64 --release-dir releases/<name> [options]
#
# Options:
#   --arch ARCH         Required: arm64 | x86_64. Must match this host exactly.
#   --release-dir DIR   Required, e.g. releases/v4.4.2-20261003.
#   --branch BRANCH     Fetch and switch to origin/BRANCH first. The fetch runs BEFORE
#                       prerequisite checks, so the runner can bootstrap a gate branch
#                       that does not exist locally yet. Refuses a local branch
#                       carrying unpushed commits; never a hard reset.
#   --constraints FILE  Default: <release-dir>/evidence/wheelhouse-constraints-cp314-macos.txt
#   --artifact FILE     Default: <release-dir>/artifacts/MADVentures-Claude-Code-Environment-v<VERSION>.zip
#   --home DIR          Default: $HOME/.hermes/cache/scratch/audit<VERSIONCODE>-<ARCH>-home
#                       (must stay under $HOME/.hermes/cache/scratch; this directory is
#                       recreated by the run, so unsafe targets are refused)
#   --output FILE       Default: <release-dir>/evidence/audit<VERSIONCODE>-target-gate-<ARCH>.json
#                       (must be a .json path inside the repository)
#   --commit-and-push   Commit and push the evidence JSON to the branch.
#   --dry-run           Guards + resolution only; print the plan and exit.
#   --allow-dirty       Skip the clean-clone guard (not recommended).
#
# Exit codes: 2 = wrong hardware/OS/Rosetta; 3 = dirty clone or unsafe local branch;
#             4 = missing prerequisite; 5 = usage error;
#             6 = safety/contract refusal (interpreter or unsafe --home/--output target).

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
command -v python3 >/dev/null 2>&1 || { echo "error: python3 not found on PATH" >&2; exit 4; }

# --- Guard 1: native hardware and OS only (no emulation) ------------------------
# The gate contract produces macOS (cp314-macos) wheels for a specific
# architecture; both the OS and the hardware must be native, so an x86_64 Linux
# host cannot pass the x86_64 request and emit mislabeled evidence.
HOST_OS="$(uname -s)"
HOST_ARCH="$(python3 -c 'import platform; print(platform.machine())')"
TRANSLATED="$(sysctl -n sysctl.proc_translated 2>/dev/null || echo 0)"
if [ "$HOST_ARCH" != "$ARCH" ] || [ "$TRANSLATED" = "1" ]; then
  echo "REFUSING TO RUN: requested --arch $ARCH, but this host reports arch=$HOST_ARCH (rosetta_translated=$TRANSLATED)."
  echo "The release standard forbids architecture simulation: run the $ARCH gate on native $ARCH hardware."
  exit 2
fi
if [ "$HOST_OS" != "Darwin" ]; then
  echo "REFUSING TO RUN: the native target gate contract is macOS (cp314-macos wheels); this host reports OS=$HOST_OS."
  echo "Run the $ARCH gate on the native macOS $ARCH host."
  exit 2
fi

# --- Guard 2: never touch a clone with uncommitted changes ----------------------
if [ "$ALLOW_DIRTY" = "0" ] && [ -n "$(git status --porcelain)" ]; then
  echo "REFUSING TO RUN: this clone has uncommitted changes:"
  git status --short
  echo "Commit, stash, or discard them deliberately, then rerun (or pass --allow-dirty)."
  exit 3
fi

# --- Optional self-fetch (runs BEFORE prerequisites so --branch can bootstrap) --
# Never a hard reset: a local branch carrying commits that are not on
# origin/$BRANCH is refused instead of being force-moved (checkout -B would drop
# them from the tip).
if [ -n "$BRANCH" ] && [ "$DRY_RUN" = "0" ]; then
  git fetch origin "$BRANCH" || { echo "error: cannot fetch origin/$BRANCH" >&2; exit 4; }
  if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    if ! AHEAD_COUNT="$(git rev-list --count "origin/$BRANCH..refs/heads/$BRANCH" 2>/dev/null)"; then
      echo "REFUSING TO RUN: cannot compute divergence of local branch '$BRANCH' vs origin/$BRANCH; refusing to move it." >&2
      exit 3
    fi
    if [ "$AHEAD_COUNT" != "0" ]; then
      echo "REFUSING TO RUN: local branch '$BRANCH' has $AHEAD_COUNT commit(s) not present on origin/$BRANCH;"
      echo "moving it to origin would drop them from the tip. Push or delete the local branch deliberately first."
      exit 3
    fi
  fi
  git checkout -B "$BRANCH" "origin/$BRANCH"
fi

# --- Resolve version + defaults (after the checkout, so VERSION is the branch's) --
VERSION="$(tr -d '[:space:]' < VERSION)"
VERSION_CODE="$(printf '%s' "$VERSION" | tr -d '.')"
[ -n "$CONSTRAINTS" ] || CONSTRAINTS="$RELEASE_DIR/evidence/wheelhouse-constraints-cp314-macos.txt"
[ -n "$ARTIFACT" ] || ARTIFACT="$RELEASE_DIR/artifacts/MADVentures-Claude-Code-Environment-v${VERSION}.zip"
[ -n "$GATE_HOME" ] || GATE_HOME="$HOME/.hermes/cache/scratch/audit${VERSION_CODE}-${ARCH}-home"
[ -n "$OUT" ] || OUT="$RELEASE_DIR/evidence/audit${VERSION_CODE}-target-gate-${ARCH}.json"

# Normalize the paths this script deletes/recreates, so the guards below can
# reason about absolute shapes.
case "$OUT" in /*) ;; *) OUT="$REPO/$OUT" ;; esac
case "$GATE_HOME" in /*) ;; *) GATE_HOME="$REPO/$GATE_HOME" ;; esac

# --- Guard 3: interpreter contract (cp314-macos) --------------------------------
PY_IMPL_VER="$(python3 -c 'import platform, sys; print(platform.python_implementation() + " " + ("%d.%d" % sys.version_info[:2]))')"
if [ "$PY_IMPL_VER" != "CPython 3.14" ]; then
  echo "REFUSING TO RUN: the cp314-macos contract requires CPython 3.14 for the gate; python3 reports $PY_IMPL_VER ($(command -v python3))."
  exit 6
fi

# --- Guard 4: constrain the deletion/recreation targets -------------------------
# --home is recreated (rm -rf) and --output is overwritten; refuse shapes that
# are not the expected safe targets so a typo such as `--home "$HOME"` cannot
# recursively delete a home directory or the checkout.
case "$GATE_HOME" in
  "$HOME/.hermes/cache/scratch/"*) ;;
  *) echo "REFUSING TO RUN: --home must be under \$HOME/.hermes/cache/scratch (got: $GATE_HOME)." >&2; exit 6 ;;
esac
if [ "$GATE_HOME" = "$HOME/.hermes/cache/scratch" ] || [ "$GATE_HOME" = "$HOME/.hermes/cache/scratch/" ]; then
  echo "REFUSING TO RUN: --home must not be the scratch root itself." >&2; exit 6
fi
# The prefix checks above are lexical; reject '..' traversal in either target.
case "$GATE_HOME" in *..*) echo "REFUSING TO RUN: --home must not contain '..' path components." >&2; exit 6 ;; esac
case "$OUT" in *..*) echo "REFUSING TO RUN: --output must not contain '..' path components." >&2; exit 6 ;; esac
case "$OUT" in
  "$REPO"/*.json) ;;
  *) echo "REFUSING TO RUN: --output must be a .json file inside the repository (got: $OUT)." >&2; exit 6 ;;
esac
# --- Prerequisites (after the fetch) --------------------------------------------
MISSING=0
[ -d "$RELEASE_DIR" ] || { echo "missing: release dir $RELEASE_DIR"; MISSING=1; }
[ -f "$CONSTRAINTS" ] || { echo "missing: constraints file $CONSTRAINTS"; MISSING=1; }
[ -f "$ARTIFACT" ]    || { echo "missing: artifact $ARTIFACT"; MISSING=1; }
if [ "$MISSING" = "1" ]; then
  if [ "$DRY_RUN" = "1" ] && [ -n "$BRANCH" ]; then
    echo "DRY RUN: the missing paths resolve after fetching '$BRANCH'; continuing with the plan."
  else
    echo "error: prerequisites missing (exit 4)." >&2
    exit 4
  fi
fi
if [ -f "$CONSTRAINTS" ]; then
  grep -q '==' "$CONSTRAINTS" || { echo "error: constraints file has no pinned requirements: $CONSTRAINTS" >&2; exit 4; }
fi

if [ "$DRY_RUN" = "1" ]; then
  echo "DRY RUN — guards passed; nothing executed."
  echo "  host:            $HOST_OS $HOST_ARCH (rosetta_translated=$TRANSLATED), $PY_IMPL_VER"
  echo "  requested arch:  $ARCH"
  echo "  release dir:     $RELEASE_DIR"
  echo "  version:         $VERSION"
  PIN_COUNT=0
  if [ -f "$CONSTRAINTS" ]; then PIN_COUNT="$(grep -c '==' "$CONSTRAINTS" || true)"; fi
  echo "  constraints:     $CONSTRAINTS ($PIN_COUNT pins)"
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

rm -rf "$GATE_HOME"
rm -f "$OUT"
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
