#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd -P)"
cd "$ROOT"
python3 scripts/quick-validate.py
echo
echo "Fast package validation passed."
echo "Run 'python3 scripts/validate-config.py' for the exhaustive release suite."
echo
echo "Press Return to close this window."
read -r _ || true
