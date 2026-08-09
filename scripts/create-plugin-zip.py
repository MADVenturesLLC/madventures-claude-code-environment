#!/usr/bin/env python3
"""Create a distributable ZIP containing the generated portable plugin root."""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin" / "madventures-founderos"
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".DS_Store"}

parser = argparse.ArgumentParser()
parser.add_argument(
    "output",
    nargs="?",
    default=str(ROOT.parent / f"MADVentures-FounderOS-Claude-Code-Plugin-v{(ROOT / 'VERSION').read_text().strip()}.zip"),
)
args = parser.parse_args()
output = Path(args.output).resolve()
output.parent.mkdir(parents=True, exist_ok=True)

if not PLUGIN.is_dir():
    raise SystemExit(f"Portable plugin is missing: {PLUGIN}. Run scripts/build-plugin.py first.")

files: list[Path] = []
for path in PLUGIN.rglob("*"):
    if not path.is_file():
        continue
    rel = path.relative_to(PLUGIN)
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        continue
    if path.resolve() == output:
        continue
    files.append(path)

with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(files, key=lambda p: p.relative_to(PLUGIN).as_posix()):
        arcname = (Path(PLUGIN.name) / path.relative_to(PLUGIN)).as_posix()
        archive.write(path, arcname)

print(f"Created {output} with {len(files)} files")
