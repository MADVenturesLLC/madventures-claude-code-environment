#!/usr/bin/env python3
"""Fast install-time integrity and delivery-layout validation."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
PACKAGE_NAME = f"MADVentures-Claude-Code-Environment-v{VERSION}"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(message: str) -> None:
    print(f"QUICK VALIDATION FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)

required = [
    "README_FIRST.txt",
    "OPEN_ME_FIRST.md",
    "INSTALL_MAC.command",
    "INSTALL_WINDOWS.ps1",
    "VERIFY_PACKAGE.command",
    "PACKAGE_CONTENTS.txt",
    "project/.claude/settings.json",
    "project/.claude/FOUNDEROS.md",
    "python-control-plane/bin/madclaude.py",
    "scripts/install.sh",
    "scripts/install.ps1",
    "scripts/environment-lifecycle.py",
    "scripts/test-release-archives.py",
    "managed/20-madventures-baseline.json",
    "workspace/.claude/MADVENTURES_WORKSPACE.md",
    "VISIBLE_PROJECT_TEMPLATE/README_FIRST.txt",
]
for rel in required:
    if not (ROOT / rel).is_file():
        fail(f"missing required file: {rel}")

# PACKAGE_CONTENTS.txt must be an EXACT index of the generator-eligible
# source set (same membership and count as scripts/generate-delivery-index.py
# would produce now); a stale index fails closed.
_contents_exclude = {"MANIFEST.json", "SHA256SUMS.txt", "PACKAGE_CONTENTS.txt"}
_contents_excluded_parts = {"__pycache__", ".pytest_cache", ".DS_Store", "evidence", ".git"}
eligible: set[str] = set()
for path in ROOT.rglob("*"):
    if not path.is_file() or path.name in _contents_exclude:
        continue
    relative = path.relative_to(ROOT)
    if any(part in _contents_excluded_parts for part in relative.parts):
        continue
    eligible.add(relative.as_posix())
declared_count = None
indexed: set[str] = set()
in_index = False
for line in (ROOT / "PACKAGE_CONTENTS.txt").read_text(encoding="utf-8").splitlines():
    if line.startswith("Indexed files"):
        count_match = re.search(r":\s*(\d+)", line)
        declared_count = int(count_match.group(1)) if count_match else None
    if line == "FILE INDEX":
        in_index = True
    elif in_index and len(line) > 12 and line[:10].strip().isdigit() and line[10:12] == "  ":
        indexed.add(line[12:])
if declared_count is None:
    fail("PACKAGE_CONTENTS.txt lacks an indexed-count line")
if indexed != eligible or declared_count != len(eligible):
    missing = sorted(eligible - indexed)[:10]
    unexpected = sorted(indexed - eligible)[:10]
    fail(
        "PACKAGE_CONTENTS.txt is stale (regenerate with scripts/generate-delivery-index.py): "
        f"declared {declared_count}, indexed {len(indexed)}, eligible {len(eligible)}; "
        f"missing {missing}; unexpected {unexpected}"
    )

expected_counts = {
    "agents": (ROOT / "project/.claude/agents", "*.md", 20),
    "skills": (ROOT / "project/.claude/skills", "*/SKILL.md", 31),
    "workflows": (ROOT / "project/.claude/workflows", "*.js", 0),
    "hooks": (ROOT / "project/.claude/hooks", "*.mjs", 2),
    "rules": (ROOT / "project/.claude/rules", "*.md", 8),
}
for name, (base, pattern, expected) in expected_counts.items():
    actual = len(list(base.glob(pattern)))
    if actual != expected:
        fail(f"{name} count expected {expected}, found {actual}")

source = ROOT / "project/.claude"
mirror = ROOT / "VISIBLE_PROJECT_TEMPLATE/CLAUDE_FOLDER_CONTENTS"
source_files = sorted(p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file())
mirror_files = sorted(p.relative_to(mirror).as_posix() for p in mirror.rglob("*") if p.is_file())
if source_files != mirror_files:
    fail("visible project template membership differs from canonical project/.claude")
for rel in source_files:
    if digest(source / rel) != digest(mirror / rel):
        fail(f"visible project template differs from canonical source: {rel}")

for path in ROOT.rglob("*.json"):
    if path.name == "MANIFEST.json":
        continue
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid JSON {path.relative_to(ROOT)}: {exc}")

manifest_path = ROOT / "MANIFEST.json"
checksums_path = ROOT / "SHA256SUMS.txt"
if manifest_path.exists() != checksums_path.exists():
    fail("MANIFEST.json and SHA256SUMS.txt must both be present or both be absent")
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("package") != PACKAGE_NAME or manifest.get("version") != VERSION:
        fail("manifest package identity/version mismatch")
    entries = manifest.get("files")
    if not isinstance(entries, list) or manifest.get("fileCount") != len(entries):
        fail("manifest fileCount mismatch")
    manifest_paths: set[str] = set()
    for entry in entries:
        rel = entry.get("path")
        if not isinstance(rel, str) or rel in manifest_paths:
            fail(f"invalid or duplicate manifest path: {rel!r}")
        manifest_paths.add(rel)
        path = ROOT / rel
        if not path.is_file():
            fail(f"manifest references missing file: {rel}")
        if path.stat().st_size != entry.get("bytes") or digest(path) != entry.get("sha256"):
            fail(f"manifest mismatch: {rel}")
    checksum_paths: set[str] = set()
    for number, line in enumerate(checksums_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            fail(f"malformed checksum line {number}")
        expected, rel = match.groups()
        if rel in checksum_paths:
            fail(f"duplicate checksum path: {rel}")
        checksum_paths.add(rel)
        path = ROOT / rel
        if not path.is_file() or digest(path) != expected:
            fail(f"checksum mismatch: {rel}")
    if checksum_paths != manifest_paths | {"MANIFEST.json"}:
        fail("checksum and manifest path sets differ")

print(
    "QUICK VALIDATION PASSED: "
    f"v{VERSION}; 20 agents; 31 skills; 0 executable JS workflows; "
    "hidden payload and visible inspection mirror match"
)
