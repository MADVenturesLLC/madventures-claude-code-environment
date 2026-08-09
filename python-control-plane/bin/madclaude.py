#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# Locate the importable package directory (python-control-plane/src) by walking
# upward from this launcher file until src/madclaude/__init__.py is found. This
# keeps the launcher functional whether it lives at
# python-control-plane/bin/madclaude.py (source) or at the deployed
# ~/.madclaude/app/madclaude.py (offline install), and prevents it from
# shadowing the madclaude package when `python -m madclaude.hook_cli` runs from
# the python-control-plane directory.
HERE = Path(__file__).resolve().parent
SRC = None
for candidate in (HERE, *HERE.parents):
    if (candidate / "src" / "madclaude" / "__init__.py").is_file():
        SRC = str(candidate / "src")
        break
if SRC is None:
    sys.stderr.write("madclaude launcher could not locate the src/madclaude package.\n")
    raise SystemExit(1)
try:
    sys.path.remove(SRC)
except ValueError:
    pass
sys.path.insert(0, SRC)

from madclaude.cli import main  # noqa: E402

raise SystemExit(main())
