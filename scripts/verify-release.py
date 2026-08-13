#!/usr/bin/env python3
"""Verify the full-environment and portable-plugin release archives end to end."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = 'MADVentures-Claude-Code-Environment-v4.4.1'
VERSION = (PACKAGE_ROOT / "VERSION").read_text(encoding="utf-8").strip()
PLUGIN_ROOT = "madventures-founderos"
EXPECTED_PLUGIN_COUNTS = {"agents": 19, "skills": 31, "workflows": 0}
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".DS_Store"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(message: str) -> None:
    raise ValueError(message)


def safe_members(archive: zipfile.ZipFile, expected_root: str) -> dict[str, bytes]:
    names = archive.namelist()
    if len(names) != len(set(names)):
        fail(f"{archive.filename}: duplicate archive entries detected")

    files: dict[str, bytes] = {}
    roots: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            fail(f"{archive.filename}: unsafe archive path: {name}")
        if not path.parts:
            continue
        roots.add(path.parts[0])
        if any(part in EXCLUDED_PARTS for part in path.parts):
            fail(f"{archive.filename}: excluded cache/metadata entry present: {name}")
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            fail(f"{archive.filename}: symlink entry present (archives ship regular files only): {name}")
        if info.is_dir():
            continue
        files[name] = archive.read(info)

    if roots != {expected_root}:
        fail(f"{archive.filename}: expected one root '{expected_root}', found {sorted(roots)}")
    return files


def parse_checksums(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line_number, raw in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", raw)
        if not match:
            fail(f"SHA256SUMS.txt:{line_number}: invalid checksum line")
        digest, rel = match.groups()
        if rel in result:
            fail(f"SHA256SUMS.txt: duplicate path: {rel}")
        result[rel] = digest
    return result


def verify_full_archive(path: Path) -> tuple[dict[str, bytes], dict[str, object]]:
    with zipfile.ZipFile(path) as archive:
        files = safe_members(archive, PACKAGE_NAME)

    prefix = f"{PACKAGE_NAME}/"
    checksum_name = prefix + "SHA256SUMS.txt"
    manifest_name = prefix + "MANIFEST.json"
    version_name = prefix + "VERSION"
    for required in (checksum_name, manifest_name, version_name):
        if required not in files:
            fail(f"{path}: missing {required}")
    for required_rel in (
        "python-control-plane/bin/madclaude.py",
        "python-control-plane/pyproject.toml",
        "python-control-plane/src/madclaude/auth.py",
        "python-control-plane/schemas/review.schema.json",
        "project/.claude/skills/python-control-plane/SKILL.md",
        "project/.claude/rules/70-python-control-plane.md",
    ):
        if prefix + required_rel not in files:
            fail(f"{path}: missing v4.4 Python asset: {required_rel}")

    if files[version_name].decode("utf-8").strip() != VERSION:
        fail(f"{path}: VERSION does not match {VERSION}")

    # Audit 9 archive membership and runtime-state validation: the release
    # contract tooling must ship, and no MCP runtime state may ever leak into
    # a published archive.
    for required_rel in (
        "scripts/mcp-wheelhouse.py",
        "scripts/audit9-target-gate.py",
        "python-control-plane/src/madclaude/safe_read.py",
        "python-control-plane/src/madclaude/mcp_lifecycle.py",
        "python-control-plane/src/madclaude/mcp_server.py",
        "python-control-plane/src/madclaude/term.py",
    ):
        if prefix + required_rel not in files:
            fail(f"{path}: missing Audit 9 release-contract member: {required_rel}")
    for member in files:
        if (
            "mcp-releases" in member
            or "mcp-installation-state.json" in member
            or ".staging." in member
            or "current.tmp." in member
            or ".trash." in member
            or member.endswith(".whl")
            or "WHEELHOUSE_MANIFEST.json" in member
        ):
            fail(f"{path}: MCP runtime state must never ship in a release archive: {member}")

    checksums = parse_checksums(files[checksum_name])
    for rel, expected in checksums.items():
        member = prefix + rel
        if member not in files:
            fail(f"{path}: checksum references missing member: {rel}")
        actual = sha256(files[member])
        if actual != expected:
            fail(f"{path}: checksum mismatch for {rel}: expected {expected}, got {actual}")

    manifest = json.loads(files[manifest_name])
    if manifest.get("package") != PACKAGE_NAME or manifest.get("version") != VERSION:
        fail(f"{path}: manifest identity/version mismatch")
    entries = manifest.get("files")
    if not isinstance(entries, list) or manifest.get("fileCount") != len(entries):
        fail(f"{path}: manifest fileCount is inconsistent")

    manifest_paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            fail(f"{path}: malformed manifest entry")
        rel = entry.get("path")
        expected_hash = entry.get("sha256")
        expected_bytes = entry.get("bytes")
        if not isinstance(rel, str) or rel in manifest_paths:
            fail(f"{path}: invalid or duplicate manifest path: {rel!r}")
        manifest_paths.add(rel)
        member = prefix + rel
        if member not in files:
            fail(f"{path}: manifest references missing member: {rel}")
        data = files[member]
        if len(data) != expected_bytes or sha256(data) != expected_hash:
            fail(f"{path}: manifest size/hash mismatch for {rel}")

    expected_members = {prefix + rel for rel in manifest_paths} | {manifest_name, checksum_name}
    actual_members = set(files)
    extra = sorted(actual_members - expected_members)
    missing = sorted(expected_members - actual_members)
    if extra or missing:
        fail(f"{path}: archive/manifest membership mismatch; extra={extra}, missing={missing}")

    if checksums.get("MANIFEST.json") != sha256(files[manifest_name]):
        fail(f"{path}: SHA256SUMS.txt does not authenticate MANIFEST.json")
    if set(checksums) != manifest_paths | {"MANIFEST.json"}:
        fail(f"{path}: checksum and manifest path sets differ")

    return files, manifest


def verify_plugin_archive(path: Path, full_files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path) as archive:
        files = safe_members(archive, PLUGIN_ROOT)

    prefix = f"{PLUGIN_ROOT}/"
    manifest_name = prefix + ".claude-plugin/plugin.json"
    if manifest_name not in files:
        fail(f"{path}: plugin manifest missing")
    manifest = json.loads(files[manifest_name])
    if manifest.get("name") != PLUGIN_ROOT or manifest.get("version") != VERSION:
        fail(f"{path}: plugin manifest identity/version mismatch")

    agents = [name for name in files if name.startswith(prefix + "agents/") and name.endswith(".md")]
    skills = [name for name in files if name.startswith(prefix + "skills/") and name.endswith("/SKILL.md")]
    workflows = [name for name in files if name.startswith(prefix + "workflows/") and name.endswith(".js")]
    actual = {"agents": len(agents), "skills": len(skills), "workflows": len(workflows)}
    if actual != EXPECTED_PLUGIN_COUNTS:
        fail(f"{path}: plugin component counts differ: expected {EXPECTED_PLUGIN_COUNTS}, got {actual}")
    if any(name.endswith("/agents/neon-reader.md") for name in agents):
        fail(f"{path}: portable plugin must not include neon-reader")
    expected_policy = {
        prefix + "python-control-plane/src/madclaude/" + name
        for name in (
            "__init__.py", "version.py", "errors.py", "safe_read.py", "guard.py", "git.py", "evidence.py",
            "artifacts.py", "hook_policy.py", "hook_cli.py",
            # A10-A: secrets_patterns is the primitive registry imported by
            # evidence.py and guard.py. A10-C: escalation_state is the denial
            # journal imported by hook_policy.py and hook_cli.py. Both are
            # part of the hook-policy dependency closure.
            "secrets_patterns.py", "escalation_state.py",
        )
    }
    actual_policy = {name for name in files if name.startswith(prefix + "python-control-plane/")}
    if actual_policy != expected_policy:
        fail(f"{path}: portable plugin must contain only the Python hook-policy dependency closure")

    full_prefix = f"{PACKAGE_NAME}/plugin/{PLUGIN_ROOT}/"
    for name, data in files.items():
        rel = name[len(prefix):]
        full_name = full_prefix + rel
        if full_name not in full_files:
            fail(f"{path}: plugin member missing from full package: {rel}")
        if full_files[full_name] != data:
            fail(f"{path}: plugin member differs from full package: {rel}")

    full_plugin_members = {
        name[len(full_prefix):]
        for name in full_files
        if name.startswith(full_prefix)
    }
    plugin_members = {name[len(prefix):] for name in files}
    if full_plugin_members != plugin_members:
        fail(f"{path}: standalone plugin and full-package plugin membership differ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("full_archive", type=Path)
    parser.add_argument("plugin_archive", type=Path)
    args = parser.parse_args()

    try:
        full_files, manifest = verify_full_archive(args.full_archive.resolve())
        verify_plugin_archive(args.plugin_archive.resolve(), full_files)
    except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        print(f"RELEASE VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 1

    print(
        "RELEASE VERIFICATION PASSED: "
        f"full package {manifest['fileCount']} manifest files; "
        f"portable plugin {EXPECTED_PLUGIN_COUNTS['agents']} agents, "
        f"{EXPECTED_PLUGIN_COUNTS['skills']} skills, "
        f"{EXPECTED_PLUGIN_COUNTS['workflows']} workflows"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
