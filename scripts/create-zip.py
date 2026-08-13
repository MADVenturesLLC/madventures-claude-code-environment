#!/usr/bin/env python3
"""Create a deterministic-enough distributable ZIP containing the package root."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = 'MADVentures-Claude-Code-Environment-v4.4.1'
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".DS_Store", "releases", ".git", "evidence"}

parser = argparse.ArgumentParser()
parser.add_argument("output", nargs="?", default=str(ROOT.parent / f"{PACKAGE_NAME}.zip"))
args = parser.parse_args()
output = Path(args.output).resolve()
output.parent.mkdir(parents=True, exist_ok=True)

files = []
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        continue
    if path.resolve() == output:
        continue
    files.append(path)

with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(files, key=lambda p: p.relative_to(ROOT).as_posix()):
        arcname = (Path(PACKAGE_NAME) / path.relative_to(ROOT)).as_posix()
        archive.write(path, arcname)

print(f"Created {output} with {len(files)} files")
