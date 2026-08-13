#!/usr/bin/env python3
"""Generate a deterministic package manifest and SHA-256 checksum file."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = 'MADVentures-Claude-Code-Environment-v4.4.1'
EXCLUDED_NAMES = {"MANIFEST.json", "SHA256SUMS.txt"}
# "evidence" excludes runtime denial/approval byproducts written to ./claude/evidence
# by test runs (never package content); project/.claude has no evidence dir.
# ".git" excludes repository history; "releases" excludes historical release
# records (Audit 9 artifacts + wheelhouse) — evidence in the repo, never shipped.
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".DS_Store", "evidence", ".git", "releases"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def included_files() -> list[Path]:
    result: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if path.name in EXCLUDED_NAMES or any(part in EXCLUDED_PARTS for part in rel.parts):
            continue
        result.append(path)
    return sorted(result, key=lambda p: p.relative_to(ROOT).as_posix())


files = included_files()
entries = []
for path in files:
    rel = path.relative_to(ROOT).as_posix()
    entries.append({"path": rel, "bytes": path.stat().st_size, "sha256": digest(path)})

version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
manifest = {
    "package": PACKAGE_NAME,
    "version": version,
    "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "algorithm": "SHA-256",
    "fileCount": len(entries),
    "files": entries,
}
(ROOT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

checksum_paths = files + [ROOT / "MANIFEST.json"]
lines = [f"{digest(path)}  {path.relative_to(ROOT).as_posix()}" for path in checksum_paths]
(ROOT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Generated MANIFEST.json ({len(entries)} files) and SHA256SUMS.txt")
