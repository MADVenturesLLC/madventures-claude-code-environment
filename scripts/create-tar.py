#!/usr/bin/env python3
"""Create a macOS/Linux-friendly TAR.GZ preserving executable permissions and dotfiles."""
from __future__ import annotations

import argparse
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
PACKAGE_NAME = f"MADVentures-Claude-Code-Environment-v{VERSION}"
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".DS_Store"}

parser = argparse.ArgumentParser()
parser.add_argument("output", nargs="?", default=str(ROOT.parent / f"{PACKAGE_NAME}.tar.gz"))
args = parser.parse_args()
output = Path(args.output).resolve()
output.parent.mkdir(parents=True, exist_ok=True)

files: list[Path] = []
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        continue
    if path.resolve() == output:
        continue
    files.append(path)

with tarfile.open(output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
    for path in sorted(files, key=lambda p: p.relative_to(ROOT).as_posix()):
        arcname = (Path(PACKAGE_NAME) / path.relative_to(ROOT)).as_posix()
        archive.add(path, arcname=arcname, recursive=False)

print(f"Created {output} with {len(files)} files")
