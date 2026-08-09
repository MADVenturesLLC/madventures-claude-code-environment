#!/usr/bin/env python3
"""Generate a Finder/Explorer-visible inspection mirror of the hidden project template."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "project" / ".claude"
DEST_ROOT = ROOT / "VISIBLE_PROJECT_TEMPLATE"
DEST = DEST_ROOT / "CLAUDE_FOLDER_CONTENTS"
ROOT_FILES = DEST_ROOT / "REPOSITORY_ROOT_FILES"


def main() -> None:
    if not SOURCE.is_dir():
        raise SystemExit(f"Missing canonical project template: {SOURCE}")
    if DEST_ROOT.exists():
        shutil.rmtree(DEST_ROOT)
    shutil.copytree(SOURCE, DEST)
    ROOT_FILES.mkdir(parents=True)
    shutil.copy2(ROOT / "project" / ".mcp.example.json", ROOT_FILES / "mcp.example.json")
    shutil.copy2(ROOT / "project" / ".gitignore.fragment", ROOT_FILES / "gitignore.fragment.txt")
    shutil.copy2(ROOT / "project" / "settings.local.example.json", ROOT_FILES / "settings.local.example.json")
    text = (
        "VISIBLE PROJECT TEMPLATE — INSPECTION COPY\n\n"
        "The actual installer source is project/.claude, which macOS Finder hides because its name begins with a period.\n"
        "This directory is a generated, visible mirror so every agent, skill, workflow, hook, rule, and setting can be inspected normally.\n\n"
        "Mapping during installation:\n"
        "  VISIBLE_PROJECT_TEMPLATE/CLAUDE_FOLDER_CONTENTS  ->  <repository>/.claude\n"
        "  REPOSITORY_ROOT_FILES/mcp.example.json          ->  <repository>/.mcp.example.json\n"
        "  REPOSITORY_ROOT_FILES/gitignore.fragment.txt    ->  appended to <repository>/.gitignore\n\n"
        "Do not manually install from this mirror. Use INSTALL_MAC.command, INSTALL_WINDOWS.ps1, or scripts/install.*.\n"
        "The release validator verifies this mirror against the canonical hidden source before packaging.\n"
    )
    (DEST_ROOT / "README_FIRST.txt").write_text(text, encoding="utf-8")
    print(f"Generated visible project-template mirror: {DEST_ROOT}")


if __name__ == "__main__":
    main()
