#!/usr/bin/env bash
# 4.4.2 x86_64 NATIVE TARGET GATE — run this in Terminal on Michaels-iMac.local
#
# Why on the iMac: scripts/audit9-target-gate.py records platform.machine() of
# the RUNNING interpreter and the release standard forbids architecture
# simulation. The Audit 9 x86_64 evidence was produced natively on this iMac
# (evidence JSON: machine=Michaels-iMac.local, platformMachine=x86_64).
#
# Requirements on the iMac: macOS, CPython 3.14.x, network access to PyPI,
# and this repository cloned at the path below.
#
# Copy this block into Terminal.app on the iMac. It performs, in order:
#   1. fetch + checkout the frozen release tree (4fdc5bd)
#   2. run the native target gate (wheelhouse download + offline install +
#      staged self-test + atomic enable + protocol roundtrip + real mcp SDK
#      stdio roundtrip + disable/re-enable/status cycle)
#   3. print the evidence file path and its SHA-256

set -euo pipefail
REPO="$HOME/MADVenturesOPs/madventures-claude-code-environment"
HOME_DIR="$HOME/.hermes/cache/scratch/audit442-x86-home"
OUT="$REPO/releases/v4.4.2-20261003/evidence/audit442-target-gate-x86_64.json"

if [ ! -d "$REPO/.git" ]; then
  echo "Repository not found at $REPO — clone it first:"
  echo "  git clone https://github.com/MADVenturesLLC/madventures-claude-code-environment.git \"$REPO\""
  exit 1
fi

cd "$REPO"
git fetch origin release/4.4.2-prep
git checkout release/4.4.2-prep
git reset --hard 4fdc5bd01ed2654bad9405338133e582a452f231

rm -rf "$HOME_DIR" "$OUT"
mkdir -p "$HOME_DIR"

python3 scripts/audit9-target-gate.py \
  --home "$HOME_DIR" \
  --output "$OUT" \
  --artifact "$REPO/releases/v4.4.2-20261003/artifacts/MADVentures-Claude-Code-Environment-v4.4.2.zip"

echo
echo "=== x86_64 gate evidence written: $OUT ==="
shasum -a 256 "$OUT"
python3 - <<'PY'
import json, pathlib
p = pathlib.Path.home() / "MADVenturesOPs/madventures-claude-code-environment/releases/v4.4.2-20261003/evidence/audit442-target-gate-x86_64.json"
d = json.loads(p.read_text())
print("platformMachine:", d["platformMachine"])
print("evidenceClass:", d["evidenceClass"], "| releaseEvidence:", d["releaseEvidence"])
print("artifactSha256:", d["artifactSha256"])
failed = [s["step"] for s in d["steps"] if s["exitCode"] != 0]
print("failed steps:", failed or "NONE")
PY
