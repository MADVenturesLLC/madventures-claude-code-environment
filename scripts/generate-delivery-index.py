#!/usr/bin/env python3
"""Generate a plain-text package index that exposes hidden-file membership."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "PACKAGE_CONTENTS.txt"
EXCLUDE = {"MANIFEST.json", "SHA256SUMS.txt", "PACKAGE_CONTENTS.txt"}
# "evidence" excludes runtime denial/approval byproducts written to ./claude/evidence
# by test runs (never package content); project/.claude has no evidence dir.
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".DS_Store", "evidence"}

files: list[Path] = []
for path in ROOT.rglob("*"):
    if not path.is_file() or path.name in EXCLUDE:
        continue
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in rel.parts):
        continue
    files.append(path)
files.sort(key=lambda p: p.relative_to(ROOT).as_posix())

agents = len(list((ROOT / "project" / ".claude" / "agents").glob("*.md")))
skills = len(list((ROOT / "project" / ".claude" / "skills").glob("*/SKILL.md")))
workflows = len(list((ROOT / "project" / ".claude" / "workflows").glob("*.js")))
hooks = len(list((ROOT / "project" / ".claude" / "hooks").glob("*.mjs")))
rules = len(list((ROOT / "project" / ".claude" / "rules").glob("*.md")))

lines = [
    "MAD VENTURES CLAUDE CODE OPERATING ENVIRONMENT — PACKAGE CONTENTS",
    "=" * 72,
    "",
    f"Version: {(ROOT / 'VERSION').read_text(encoding='utf-8').strip()}",
    f"Indexed files (excluding generated manifest/checksum/index): {len(files)}",
    f"Core project agents: {agents}",
    f"Core project skills: {skills}",
    f"Core project workflows: {workflows}",
    f"Core project hooks: {hooks}",
    f"Core project rules: {rules}",
    "",
    "IMPORTANT FOR macOS FINDER",
    "---------------------------",
    "The canonical Claude Code payload is under project/.claude. Finder hides",
    "names beginning with a period. Press Command+Shift+. to reveal hidden files,",
    "or inspect the generated VISIBLE_PROJECT_TEMPLATE directory.",
    "",
    "FILE INDEX",
    "----------",
]
for path in files:
    rel = path.relative_to(ROOT).as_posix()
    lines.append(f"{path.stat().st_size:10d}  {rel}")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Generated {OUT} with {len(files)} indexed files")
