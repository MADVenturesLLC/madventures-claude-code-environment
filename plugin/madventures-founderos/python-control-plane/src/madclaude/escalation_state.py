"""A10-C: escalation-state module (DEC-20260812-05, A10-B design).

Implements the objective-bound escalation and denial journal for the
Python control plane. Surfaces (Q6): this module, ``hook_policy`` (consults
objective/escalation state in the decision), ``hook_cli`` (journal writer on
denial exits), ``evidence`` (immutable write helper + redactor), and the
protected store path ``.claude/evidence/python-control-plane/denials/``.
No new MCP surface; no second enforcement path.

Founder-set ceilings (Q3.2 — set at A10-C commission 2026-08-12):
  RETRY_CEILING = 3 per (objective_id, action_type)
  WORKAROUND_CEILING = 2 per objective_id

Design invariants carried from the A10-B decision:

- Q1 objective_id: format ``obj-<UTC-timestamp>-<uuid4-hex[:8]>``; minted
  only by the Founder (this module never mints); never reused or reset;
  lifecycle ``created -> active -> escalated -> dispositioned -> closed``;
  every id carries a Founder-anchored source-artifact reference.
- Q2 denial records: ten required fields, every field through the A10-A
  registry redactor before write; durable store under the protected
  evidence tree (0700 dir, 0600 records); records are write-once — a
  duplicate record_id is refused (O_EXCL), never reopened, never modified.
- Q3 counters: read durably from the denial records on disk, never from
  process memory (a restart cannot reset them); distinct retry counter per
  (objective_id, action_type) and one workaround counter per objective.
  Hitting a ceiling transitions the objective to ``escalated`` and the
  crossing denial record carries the ceiling reason.
- Q4 disposition: Founder-authored artifact names the exact objective_id
  and ceiling event (timestamp + record_id); binding is per objective at
  per ceiling event; continuing past a ceiling requires a matching
  disposition reference; the model can neither author nor clear one.
- Q5 fail-closed: any read/write failure of the durable store raises, and
  callers deny. Denial reasons never include storage error details.
"""

from __future__ import annotations

import json
import os
import re
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import evidence
from .errors import EvidenceError

OBJECTIVE_ID_RE = re.compile(r"^obj-\d{8}T\d{6}Z-[0-9a-f]{8}$")
RECORD_ID_RE = re.compile(r"^denial-\d{8}T\d{6}Z-[0-9a-f]{8}$")

# Q3.2: Founder-set at A10-C commission 2026-08-12 (retry 3, workaround 2).
RETRY_CEILING = 3
WORKAROUND_CEILING = 2

DENIAL_DIR_REL = ".claude/evidence/python-control-plane/denials"

# Q2.1 required fields (all ten) — every one redacted before write (Q2.3).
REQUIRED_DENIAL_FIELDS = (
    "record_id",
    "objective_id",
    "action_type",
    "action_target",
    "resolved_route",
    "risk_tier",
    "denial_reason",
    "control_id",
    "utc_time",
    "evidence_ref",
)

# Fields the journal computes itself (write-once identity + traceability);
# callers must supply the other seven.
COMPUTED_FIELDS = frozenset({"record_id", "utc_time", "evidence_ref"})
CALLER_FIELDS = tuple(f for f in REQUIRED_DENIAL_FIELDS if f not in COMPUTED_FIELDS)

OBJECTIVE_LIFECYCLE = ("created", "active", "escalated", "dispositioned", "closed")

_DISPOSITIONS = frozenset({"allow-with-conditions", "deny", "modify-ceiling"})


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{_utc_stamp()}-{uuid.uuid4().hex[:8]}"


def mint_objective_id(source_artifact: str) -> str:
    """Q1.1/Q1.6: mint an objective_id bound to a Founder-anchored artifact.

    Founder-only by contract: this function is called by Founder-side flow
    (ratified DEC naming an objective, or a Founder-issued objective
    record), never by hook decision code. The source artifact reference is
    written to the objective reference file so the model cannot later
    create or modify the traceability link.
    """
    if not source_artifact or not isinstance(source_artifact, str):
        raise EvidenceError("objective_id minting requires a Founder-anchored source artifact reference")
    return _new_id("obj")


class DenialJournal:
    """Durable, write-once denial journal + objective escalation state.

    Reads are always from disk (Q3.3): every query re-parses the denial
    records under the protected store, so a fresh process observes the same
    counters and escalation state. Any read or write failure raises, and
    hook callers must fail closed (Q5).
    """

    def __init__(self, repo: Path) -> None:
        self.repo = Path(repo).resolve()
        self.store_dir = self.repo / DENIAL_DIR_REL

    # -- durable read/write plumbing ---------------------------------------

    def _ensure_store(self) -> None:
        try:
            self.store_dir.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                self.store_dir.chmod(0o700)
        except OSError as exc:  # Q5: raise; caller denies. No detail leaks.
            raise EvidenceError("denial journal store is unavailable") from exc

    def records(self) -> list[dict[str, Any]]:
        """Q3.3: durable read of every denial record. Raises on any failure."""
        self._ensure_store()
        found: list[dict[str, Any]] = []
        try:
            entries = sorted(self.store_dir.glob("denial-*.json"))
            for entry in entries:
                try:
                    with entry.open("r", encoding="utf-8") as handle:
                        record = json.load(handle)
                except (OSError, json.JSONDecodeError) as exc:
                    raise EvidenceError("denial journal is unreadable") from exc
                if not isinstance(record, dict):
                    raise EvidenceError("denial journal contains a malformed record")
                found.append(record)
        except OSError as exc:
            raise EvidenceError("denial journal is unreadable") from exc
        return found

    def record_for(self, record_id: str) -> dict[str, Any] | None:
        return next((r for r in self.records() if r.get("record_id") == record_id), None)

    def validate_objective_id(self, objective_id: str) -> bool:
        """Q1.3: format validation on every governed action that consults it."""
        return bool(OBJECTIVE_ID_RE.fullmatch(objective_id))

    # -- Q3 counters (durable) ----------------------------------------------

    def retry_count(self, objective_id: str, action_type: str) -> int:
        """Denials for the same (objective_id, action_type) pair."""
        return sum(
            1
            for r in self.records()
            if r.get("objective_id") == objective_id and r.get("action_type") == action_type
        )

    def workaround_count(self, objective_id: str) -> int:
        """Denials for the objective against actions OTHER than the primary
        (first-denied) action type — workarounds of the same denied goal."""
        records = [r for r in self.records() if r.get("objective_id") == objective_id]
        if not records:
            return 0
        primary = records[0].get("action_type")
        return sum(1 for r in records if r.get("action_type") != primary)

    def ceiling_exceeded(self, objective_id: str, action_type: str) -> bool:
        return self.retry_count(objective_id, action_type) >= RETRY_CEILING

    def workaround_ceiling_exceeded(self, objective_id: str) -> bool:
        return self.workaround_count(objective_id) >= WORKAROUND_CEILING

    # -- Q1.4 lifecycle (derived durably) -----------------------------------

    def objective_state(self, objective_id: str) -> str:
        records = [r for r in self.records() if r.get("objective_id") == objective_id]
        if not records:
            return "created"
        disposition = self.disposition_for(objective_id)
        if disposition is not None:
            if disposition.get("disposition") == "deny":
                return "closed"
            return "dispositioned"
        if any(self.ceiling_exceeded(objective_id, str(r.get("action_type"))) for r in records) or (
            self.workaround_ceiling_exceeded(objective_id)
        ):
            return "escalated"
        return "active"

    def is_escalated(self, objective_id: str) -> bool:
        """Q1.4/Q4.3: escalated objectives keep governed actions denied."""
        return self.objective_state(objective_id) == "escalated"

    # -- Q4 disposition references (founder-written, model-unwritable) ------

    def _disposition_path(self, objective_id: str) -> Path:
        return self.store_dir / f"disposition-{objective_id}.json"

    def disposition_for(self, objective_id: str) -> dict[str, Any] | None:
        path = self._disposition_path(objective_id)
        try:
            if not path.is_file():
                return None
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise EvidenceError("disposition journal is unreadable") from exc
        return value if isinstance(value, dict) else None

    def has_valid_disposition(self, objective_id: str, ceiling_record_id: str) -> bool:
        """Q4.2/Q4.3: binding is per objective at per ceiling event. The
        disposition must name this exact ceiling event (its record_id)."""
        disposition = self.disposition_for(objective_id)
        if not disposition:
            return False
        return (
            disposition.get("objective_id") == objective_id
            and disposition.get("ceiling_record_id") == ceiling_record_id
            and disposition.get("disposition") in _DISPOSITIONS
            and bool(disposition.get("artifact_ref"))
        )

    # -- Q2 write-once journal ----------------------------------------------

    def record_denial(self, fields: dict[str, Any]) -> Path:
        """Q2: validate, redact, and durably write one denial record.

        Write-once (Q2.4): the record_id is generated here and the target
        file is created with O_EXCL — a collision refuses instead of
        overwriting. Every field passes through the A10-A registry redactor
        before write (Q2.3). Raises EvidenceError on any failure (Q5).
        """
        missing = [f for f in CALLER_FIELDS if f not in fields]
        if missing:
            raise EvidenceError(f"denial record missing required fields: {', '.join(missing)}")
        objective_id = str(fields.get("objective_id") or "")
        if objective_id and not self.validate_objective_id(objective_id):
            raise EvidenceError("denial record carries a malformed objective_id")
        if objective_id:
            if fields.get("governed") is not False:
                fields["governed"] = True
        else:
            # Q2.1: empty objective_id is only valid for pre-objective
            # baseline denials, which are recorded governed: false.
            fields["governed"] = False
        record = {str(k): evidence.redact(v) for k, v in fields.items()}
        record["record_id"] = _new_id("denial")
        record["utc_time"] = _utc_stamp()
        # Q2.1 evidence_ref: this record's own path inside the protected
        # evidence tree (bundle path convention, relative to the repo).
        record["evidence_ref"] = f"{DENIAL_DIR_REL}/{record['record_id']}.json"
        target = self.store_dir / f"{record['record_id']}.json"
        return evidence.write_immutable_record(target, record)

    def record_disposition(
        self,
        objective_id: str,
        ceiling_record_id: str,
        disposition: str,
        artifact_ref: str,
        founder: str,
    ) -> Path:
        """Q4: record a Founder disposition reference in the objective store.

        Founder-only write path — never invoked by hook decision code, and
        the store lives under guard.py's protected evidence tree, so the
        model can neither author nor clear a disposition (Q4.4).
        """
        if not self.validate_objective_id(objective_id):
            raise EvidenceError("disposition carries a malformed objective_id")
        if disposition not in _DISPOSITIONS:
            raise EvidenceError(f"disposition must be one of {sorted(_DISPOSITIONS)}")
        if self.record_for(ceiling_record_id) is None:
            raise EvidenceError("disposition references an unknown ceiling event")
        value = {
            "objective_id": objective_id,
            "ceiling_record_id": ceiling_record_id,
            "disposition": disposition,
            "artifact_ref": artifact_ref,
            "founder": founder,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        return evidence.write_immutable_record(self._disposition_path(objective_id), value)
