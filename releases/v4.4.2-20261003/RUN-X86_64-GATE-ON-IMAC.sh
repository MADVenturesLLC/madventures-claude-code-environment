#!/usr/bin/env bash
# 4.4.2 x86_64 NATIVE TARGET GATE — run this in Terminal.app on Michaels-iMac.local
#
# Why on the iMac: scripts/audit9-target-gate.py records platform.machine() of
# the RUNNING interpreter and the release standard forbids architecture
# simulation. The Audit 9 x86_64 evidence was produced natively on this iMac
# (evidence JSON: machine=Michaels-iMac.local, platformMachine=x86_64).
#
# PINNED RUN: cryptography is pinned to 48.0.1 via a constraints file because
# the newest release (50.0.2) ships an arm64-only macOS wheel — there is no
# x86_64 build, so an unpinned Intel run would diverge and the deterministic
# wheelhouse merge would fail closed. All other pins freeze the exact set the
# arm64 gate resolved on 2026-10-03.
#
# Requirements on the iMac: macOS (Intel), CPython 3.14.x, PyPI reachable,
# and this repository at the path below. The script hard-resets ONLY its own
# clone's release/4.4.2-gates branch — never run it in a clone holding your
# work.

set -euo pipefail
REPO="$HOME/MADVenturesOPs/madventures-claude-code-environment"
HOME_DIR="$HOME/.hermes/cache/scratch/audit442-x86-home"
OUT="$REPO/releases/v4.4.2-20261003/evidence/audit442-target-gate-x86_64.json"
CONSTRAINTS="$REPO/releases/v4.4.2-20261003/evidence/wheelhouse-constraints-cp314-macos.txt"

if [ ! -d "$REPO/.git" ]; then
  echo "Repository not found at $REPO — clone it first:"
  echo "  mkdir -p \"$(dirname "$REPO")\""
  echo "  git clone https://github.com/MADVenturesLLC/madventures-claude-code-environment.git \"$REPO\""
  exit 1
fi

cd "$REPO"
git fetch origin release/4.4.2-gates
git checkout -B release/4.4.2-gates origin/release/4.4.2-gates

rm -rf "$HOME_DIR" "$OUT"
mkdir -p "$HOME_DIR"

echo "=== constraints in effect: ==="
grep -E '^cryptography==' "$CONSTRAINTS" || { echo "constraints file missing cryptography pin"; exit 1; }

PIP_CONSTRAINT="$CONSTRAINTS" python3 scripts/audit9-target-gate.py \
  --home "$HOME_DIR" \
  --output "$OUT" \
  --artifact "$REPO/releases/v4.4.2-20261003/artifacts/MADVentures-Claude-Code-Environment-v4.4.2.zip"

echo
echo "=== x86_64 gate evidence written: $OUT ==="
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
echo "=== commit + push the evidence back so the record can absorb it ==="
git add "releases/v4.4.2-20261003/evidence/audit442-target-gate-x86_64.json"
git commit -m "release: x86_64 native target gate evidence (4.4.2)" \
  --trailer "Role-Id: builder" \
  --trailer "Actor-Id: session:founder/imac-x86-gate" \
  --trailer "Execution-Surface: hermes-local-code"
git push origin release/4.4.2-gates
echo "DONE — evidence committed and pushed."
