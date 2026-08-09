from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import safe_read
from .evidence import EvidenceBundle, redact, sha256_text
from .errors import EvidenceError, SafeReadError


CANONICAL_ARTIFACTS = {
    "PLAN",
    "HANDOFF",
    "VERIFICATION",
    "REVIEW",
    "TIER2_REVIEW",
    "ACCEPTANCE",
    "DECISION_PROPOSAL",
}
REQUIRED_METADATA = {
    "artifact_type",
    "schema_version",
    "workflow_id",
    "task_id",
    "repository",
    "route",
    "stage",
    "base_sha",
    "head_sha",
    "status",
    "evidence_source",
    "generated_at",
    "payload_sha256",
}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _scalar(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def render_canonical_artifact(
    artifact_type: str,
    payload: Any,
    *,
    workflow_id: str,
    repository: str,
    route: str,
    base_sha: str,
    head_sha: str,
    status: str,
    task_id: str | None = None,
) -> str:
    name = artifact_type.strip().upper()
    if name not in CANONICAL_ARTIFACTS:
        raise EvidenceError(f"Unsupported canonical artifact type: {artifact_type}")
    safe_payload = redact(payload)
    payload_json = json.dumps(safe_payload, indent=2, sort_keys=True, ensure_ascii=False)
    metadata = {
        "artifact_type": name,
        "schema_version": "1",
        "workflow_id": workflow_id,
        "task_id": task_id or workflow_id,
        "repository": repository,
        "route": route,
        "stage": route,
        "base_sha": base_sha.lower(),
        "head_sha": head_sha.lower(),
        "status": status,
        "evidence_source": "local_evidence",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": sha256_text(payload_json),
    }
    frontmatter = "\n".join(f"{key}: {_scalar(value)}" for key, value in metadata.items())
    return f"---\n{frontmatter}\n---\n\n# {name}\n\n```json\n{payload_json}\n```\n"


def write_canonical_artifact(
    bundle: EvidenceBundle,
    artifact_type: str,
    payload: Any,
    *,
    repository: Path,
    base_sha: str,
    head_sha: str,
    status: str,
) -> Path:
    task_id = payload.get("task_id") if isinstance(payload, dict) and isinstance(payload.get("task_id"), str) else None
    return bundle.write_text(
        f"{artifact_type.upper()}.md",
        render_canonical_artifact(
            artifact_type,
            payload,
            workflow_id=bundle.path.name,
            task_id=task_id,
            repository=str(repository),
            route=bundle.route,
            base_sha=base_sha,
            head_sha=head_sha,
            status=status,
        ),
    )


def read_canonical_artifact(path: Path) -> tuple[dict[str, str], Any]:
    root_fd = safe_read.open_root(path.parent)
    try:
        text = safe_read.read_text(root_fd, path.name)
    except SafeReadError as exc:
        raise EvidenceError(f"Canonical artifact is unreadable: {path}: {exc}") from exc
    finally:
        os.close(root_fd)
    match = re.fullmatch(r"---\n([\s\S]*?)\n---\n\n# ([A-Z0-9_]+)\n\n```json\n([\s\S]*?)\n```\n", text)
    if not match:
        raise EvidenceError(f"Canonical artifact has an invalid envelope: {path}")
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            raise EvidenceError(f"Canonical artifact metadata is malformed: {path}")
        key, value = line.split(":", 1)
        key = key.strip()
        if key in metadata:
            raise EvidenceError(f"Canonical artifact metadata contains duplicate key {key!r}: {path}")
        metadata[key] = value.strip()
    missing = sorted(REQUIRED_METADATA - metadata.keys())
    if missing:
        raise EvidenceError(f"Canonical artifact is missing metadata {missing}: {path}")
    if metadata["artifact_type"] != match.group(2) or metadata["artifact_type"] not in CANONICAL_ARTIFACTS:
        raise EvidenceError(f"Canonical artifact type mismatch: {path}")
    if metadata["schema_version"] != "1" or metadata["evidence_source"] != "local_evidence":
        raise EvidenceError(f"Canonical artifact classification is invalid: {path}")
    required_values = {"workflow_id", "task_id", "repository", "route", "stage", "status", "generated_at"}
    if any(not metadata[key] for key in required_values) or metadata["stage"] != metadata["route"]:
        raise EvidenceError(f"Canonical artifact identity or stage metadata is invalid: {path}")
    try:
        generated_at = datetime.fromisoformat(metadata["generated_at"])
    except ValueError as exc:
        raise EvidenceError(f"Canonical artifact timestamp is invalid: {path}") from exc
    if generated_at.tzinfo is None:
        raise EvidenceError(f"Canonical artifact timestamp must include a timezone: {path}")
    if not FULL_SHA.fullmatch(metadata["base_sha"]) or not FULL_SHA.fullmatch(metadata["head_sha"]):
        raise EvidenceError(f"Canonical artifact requires literal full Git SHAs: {path}")
    payload_text = match.group(3)
    if sha256_text(payload_text) != metadata["payload_sha256"]:
        raise EvidenceError(f"Canonical artifact payload hash mismatch: {path}")
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"Canonical artifact payload is invalid JSON: {path}: {exc}") from exc
    return metadata, payload
