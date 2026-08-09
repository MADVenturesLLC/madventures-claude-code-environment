from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from . import safe_read
from .errors import PolicyViolation
from .evidence import sha256_file
from .guard import validate_scopes


def load_json_rooted(root_fd: int, relpath: str) -> dict[str, Any]:
    try:
        value = json.loads(safe_read.read_text(root_fd, relpath))
    except json.JSONDecodeError as exc:
        raise PolicyViolation(f"Could not read JSON file {relpath}: {exc}") from exc
    if not isinstance(value, dict):
        raise PolicyViolation(f"Expected a JSON object in {relpath}.")
    return value


def _governed_anchor(root: Path, path: Path) -> tuple[Path, str]:
    """Pick the trusted anchor for a governed read: the supplied root when the
    file lives inside it, otherwise the file's own parent directory (a
    founder-supplied location). The descriptor open rejects symlinks below the
    anchor either way."""
    relative = os.path.relpath(str(path), str(root))
    if relative == ".." or relative.startswith(f"..{os.sep}"):
        return path.parent, path.name
    return root, relative


def load_json_at(root: Path, path: Path) -> dict[str, Any]:
    """Load a governance JSON file through a descriptor anchored at the trusted root."""
    anchor, relpath = _governed_anchor(root, path)
    root_fd = safe_read.open_root(anchor)
    try:
        return load_json_rooted(root_fd, relpath)
    finally:
        os.close(root_fd)


def _sha256_at(root: Path, path: Path) -> str:
    anchor, relpath = _governed_anchor(root, path)
    root_fd = safe_read.open_root(anchor)
    try:
        return hashlib.sha256(safe_read.read_bytes(root_fd, relpath)).hexdigest()
    finally:
        os.close(root_fd)


def load_json(path: Path) -> dict[str, Any]:
    root_fd = safe_read.open_root(path.parent)
    try:
        return load_json_rooted(root_fd, path.name)
    finally:
        os.close(root_fd)


def approval_template(plan_file: Path, goal: str) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "founderApproved": False,
        "approvedBy": "",
        "approvedAt": "",
        "approvalReference": "",
        "evidenceSource": "local_evidence",
        "goal": goal,
        "planFile": str(plan_file),
        "planSha256": sha256_file(plan_file),
        "allowedScope": [],
        "acceptanceCriteria": [],
        "verificationCommands": [],
        "notes": "Set founderApproved=true only after the Founder approves this exact plan and scope.",
    }


def validate_approval(repo: Path, plan_file: Path, approval_file: Path, goal: str) -> tuple[dict[str, Any], tuple[str, ...], list[str], list[str]]:
    approval = load_json_at(repo, approval_file)
    expected_hash = _sha256_at(repo, plan_file)
    if approval.get("founderApproved") is not True:
        raise PolicyViolation("Founder approval file must contain `founderApproved: true`.")
    for field in ("approvedBy", "approvedAt", "approvalReference"):
        if not isinstance(approval.get(field), str) or not approval[field].strip():
            raise PolicyViolation(f"Founder approval file requires a non-empty {field!r}.")
    source = approval.get("evidenceSource")
    if source not in {"local_evidence", "remote_verified_evidence"}:
        raise PolicyViolation(
            "Founder approval evidenceSource must be local_evidence or remote_verified_evidence; "
            f"{source or 'missing'} cannot establish approval authority."
        )
    if approval.get("goal") != goal:
        raise PolicyViolation("Build goal does not exactly match the Founder-approved goal.")
    if approval.get("planSha256") != expected_hash:
        raise PolicyViolation(
            "Founder approval is not bound to the supplied plan file. The plan SHA-256 changed or is missing."
        )
    raw_scopes = approval.get("allowedScope")
    acceptance = approval.get("acceptanceCriteria")
    verification = approval.get("verificationCommands")
    if not isinstance(raw_scopes, list) or not all(isinstance(item, str) for item in raw_scopes):
        raise PolicyViolation("allowedScope must be a non-empty string array.")
    if not isinstance(acceptance, list) or not acceptance or not all(isinstance(item, str) for item in acceptance):
        raise PolicyViolation("acceptanceCriteria must be a non-empty string array.")
    if not isinstance(verification, list) or not verification or not all(isinstance(item, str) for item in verification):
        raise PolicyViolation("verificationCommands must be a non-empty string array.")
    scopes = validate_scopes(repo, tuple(raw_scopes))
    return approval, scopes, acceptance, verification
