from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from . import safe_read
from .config import RouteConfig
from .errors import PolicyViolation, SafeReadError


def load_execution_record(path: Path) -> dict[str, Any]:
    root_fd = safe_read.open_root(path.parent)
    try:
        try:
            # One open per file: the record is parsed and hashed from the same
            # single read buffer, so the manifest binding cannot be
            # desynchronized by a content swap between opens.
            record_bytes, _ = safe_read.open_verified_leaf(root_fd, path.name)
            record = json.loads(record_bytes.decode("utf-8"))
            expected_hash = hashlib.sha256(record_bytes).hexdigest()
            manifest = json.loads(safe_read.read_text(root_fd, "MANIFEST.json"))
        except (SafeReadError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PolicyViolation(f"Execution record requires a readable Python evidence manifest: {exc}") from exc
    finally:
        os.close(root_fd)
    entries = manifest.get("files") if isinstance(manifest, dict) else None
    expected = next(
        (item.get("sha256") for item in entries or [] if isinstance(item, dict) and item.get("path") == path.name),
        None,
    )
    if not isinstance(record, dict) or expected != expected_hash:
        raise PolicyViolation("Execution record is not bound to its Python evidence manifest.")
    if record.get("evidenceSource") != "local_evidence" or manifest.get("evidenceSource") != "local_evidence":
        raise PolicyViolation("Execution record must be classified as local_evidence.")
    if record.get("artifacts", {}).get("evidenceBundle") != str(path.parent):
        raise PolicyViolation("Execution record evidence-bundle path does not match its manifest location.")
    return record


def select_builder(
    route: RouteConfig,
    plan: dict[str, Any],
    requested_model: str | None = None,
) -> RouteConfig:
    recommended = plan.get("recommended_builder")
    fallbacks = plan.get("eligible_fallbacks")
    if not isinstance(recommended, str) or not recommended.strip():
        raise PolicyViolation("Approved plan requires a non-empty recommended_builder.")
    if not isinstance(fallbacks, list) or not all(isinstance(item, str) and item.strip() for item in fallbacks):
        raise PolicyViolation("Approved plan requires eligible_fallbacks as a string array.")
    plan_models = [recommended.strip(), *(item.strip() for item in fallbacks)]
    invalid = [model for model in plan_models if model not in route.eligible_models]
    if invalid:
        raise PolicyViolation(
            f"Plan-selected builder {invalid[0]!r} is not eligible for route {route.name!r}."
        )
    selected = requested_model or recommended.strip()
    if selected not in plan_models:
        raise PolicyViolation(f"Requested builder {selected!r} is outside the approved plan envelope.")
    return replace(route, model=selected)


def select_independent_reviewer(route: RouteConfig, record: dict[str, Any]) -> RouteConfig:
    participants = record.get("participants")
    if not isinstance(participants, list) or not participants:
        raise PolicyViolation("Tier-2 requires a non-empty execution record with prior participants.")
    used: set[str] = set()
    for participant in participants:
        if not isinstance(participant, dict) or any(
            not isinstance(participant.get(field), str) or not participant[field].strip()
            for field in ("role", "model", "stage")
        ):
            raise PolicyViolation("Each execution-record participant requires non-empty role, model, and stage fields.")
        used.add(participant["model"].strip().lower())
    roles = {participant["role"].strip() for participant in participants}
    required = {"planner", "builder", "verifier", "tier1-reviewer"}
    if missing := sorted(required - roles):
        raise PolicyViolation(f"Tier-2 execution record is missing required roles: {', '.join(missing)}")
    for candidate in route.eligible_models:
        if candidate.lower() not in used:
            return replace(route, model=candidate, independence_verified=True)
    raise PolicyViolation("No eligible independent reviewer remains after excluding all prior participants.")


def execution_record(
    *,
    route: RouteConfig,
    repository: Path,
    starting_sha: str,
    final_sha: str,
    status: str,
    evidence_path: Path,
) -> dict[str, Any]:
    roles = {
        "plan": "planner",
        "build": "builder",
        "verify": "verifier",
        "review": "tier2-reviewer",
        "tier1-review": "tier1-reviewer",
        "release-readiness": "release-assessor",
        "fix-until-green": "builder",
    }
    return {
        "schemaVersion": 1,
        "workflowId": evidence_path.name,
        "repository": str(repository),
        "startingSha": starting_sha,
        "finalSha": final_sha,
        "participants": [{"role": roles.get(route.name, "auditor"), "model": route.model, "stage": route.name}],
        "artifacts": {"evidenceBundle": str(evidence_path)},
        "evidenceSource": "local_evidence",
        "finalStatus": status,
        "recordedAt": datetime.now(timezone.utc).isoformat(),
    }
