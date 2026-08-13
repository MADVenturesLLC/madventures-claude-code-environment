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
- Q2 denial records: thirteen required fields, every field through the A10-A
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

# Q2.1 required fields (all thirteen) — every one redacted before write (Q2.3).
# A10-D (DEC-20260813-01 §1): +session_id, +repo_sha, +adaptation_outcome.
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
    "session_id",
    "repo_sha",
    "adaptation_outcome",
)

# Fields the journal computes itself (write-once identity + traceability);
# callers must supply the other nine. A10-D: adaptation_outcome is derived
# by the journal from prior records (never caller-supplied).
COMPUTED_FIELDS = frozenset({"record_id", "utc_time", "evidence_ref", "adaptation_outcome"})
CALLER_FIELDS = tuple(f for f in REQUIRED_DENIAL_FIELDS if f not in COMPUTED_FIELDS)

OBJECTIVE_LIFECYCLE = ("created", "active", "escalated", "dispositioned", "closed")

_DISPOSITIONS = frozenset({"allow-with-conditions", "deny", "modify-ceiling"})
# Q4.1: deny is a terminal ruling, never a continuation grant.
_CONTINUATION_DISPOSITIONS = frozenset({"allow-with-conditions", "modify-ceiling"})


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{_utc_stamp()}-{uuid.uuid4().hex[:8]}"


def mint_objective_id(source_artifact: str, store_root: Path | None = None) -> str:
    """Q1.1/Q1.6: mint an objective_id bound to a Founder-anchored artifact.

    Founder-only by contract: this function is called by Founder-side flow
    (ratified DEC naming an objective, or a Founder-issued objective
    record), never by hook decision code. The objective_id and its
    source-artifact reference are durably persisted to the protected store
    as ``objective-<id>.json`` (write-once via O_EXCL), so the traceability
    link is a record, not a promise, and the model cannot create or modify
    it.
    """
    if not source_artifact or not isinstance(source_artifact, str):
        raise EvidenceError("objective_id minting requires a Founder-anchored source artifact reference")
    objective_id = _new_id("obj")
    if store_root is not None:
        journal = DenialJournal(store_root)
        evidence.write_immutable_record(
            journal._objective_path(objective_id),
            {
                "objective_id": objective_id,
                "source_artifact": source_artifact,
                "minted_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    return objective_id


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

    def _adaptation_outcome(self, objective_id: str, action_type: str, action_target: str) -> str:
        """A10-D (DEC-20260813-01 §1): classify the model's behavior after
        the PRIOR denial for this objective.

        - same action_type AND same action_target as the prior denial =>
          ``retry`` (the model re-attempted the exact denied action)
        - different action_type (or different target) => ``workaround``
          (the model re-approached the same goal differently)
        - no prior denial for the objective => ``unknown`` (no evidence yet)

        ``abandoned`` is reserved for a future Stop-hook capture and is
        never derived here. The derivation is deterministic and durable:
        it reads the journal, never process memory.

        Ordering: records are compared in utc_time order (the journal's
        own timestamp), not filename order — filenames embed the same
        timestamp plus a random uuid, so same-second writes are
        inherently ambiguous at second resolution and are documented as
        such. Comparison: the journal persists the REDACTED target, so the
        incoming target is redacted before comparison — a secret-bearing
        target that was scrubbed in storage still matches itself.
        """
        prior = [r for r in self.records() if r.get("objective_id") == objective_id]
        if not prior:
            return "unknown"
        prior.sort(key=lambda r: str(r.get("utc_time") or ""))
        last = prior[-1]
        redacted_target = evidence.redact(action_target)
        if last.get("action_type") == action_type and last.get("action_target") == redacted_target:
            return "retry"
        return "workaround"

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

    def _objective_path(self, objective_id: str) -> Path:
        """Q1.6: the durable objective record carrying the Founder-anchored
        source-artifact reference. Written once at mint time (O_EXCL)."""
        return self.store_dir / f"objective-{objective_id}.json"

    def objective_record(self, objective_id: str) -> dict[str, Any] | None:
        """Q1.6 read: the persisted mint record (source artifact + minted_at)."""
        path = self._objective_path(objective_id)
        try:
            if not path.is_file():
                return None
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise EvidenceError("objective record is unreadable") from exc
        return value if isinstance(value, dict) else None

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

    def disposition_permits(self, objective_id: str, ceiling_record_id: str) -> bool:
        """Q4.1/Q4.3 (blocking fix): whether a disposition authorizes
        continuation — and only a continuation.

        A ``deny`` disposition is NEVER a continuation grant: it keeps
        governed actions denied. ``allow-with-conditions`` /
        ``modify-ceiling`` authorize continuation only when bound to the
        exact ceiling event named in the disposition (per-objective, per
        ceiling-event binding). An unbound or deny disposition permits
        nothing.
        """
        disposition = self.disposition_for(objective_id)
        if not disposition:
            return False
        if disposition.get("disposition") not in _CONTINUATION_DISPOSITIONS:
            return False
        return self.has_valid_disposition(objective_id, ceiling_record_id)

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
            # Q1.3/Q2.1: a governed denial is only meaningful against an
            # objective that exists in the durable store (Founder-minted).
            if self.objective_record(objective_id) is None:
                raise EvidenceError("denial record references an unknown objective_id")
            # A10-D (DEC-20260813-01 §1): adaptation_outcome is derived from
            # the PRIOR denial for this objective — same action+target =>
            # retry, different action => workaround, no prior => unknown.
            # (abandoned is reserved for a future Stop-hook capture.)
            fields["adaptation_outcome"] = self._adaptation_outcome(
                objective_id,
                str(fields.get("action_type") or ""),
                str(fields.get("action_target") or ""),
            )
            # Q3.4: stamp the ceiling reason when THIS denial is the
            # crossing record — the one that reaches the ceiling (count
            # after this write, not before).
            ceiling_reason: str | None = None
            action_type = str(fields.get("action_type") or "")
            if self.retry_count(objective_id, action_type) + 1 >= RETRY_CEILING:
                ceiling_reason = f"retry ceiling {RETRY_CEILING} reached for {action_type}"
            elif self.workaround_count(objective_id) + 1 >= WORKAROUND_CEILING:
                ceiling_reason = f"workaround ceiling {WORKAROUND_CEILING} reached"
            if ceiling_reason is not None:
                fields["ceiling_reason"] = ceiling_reason
        else:
            # Q2.1: empty objective_id is only valid for pre-objective
            # baseline denials, which are recorded governed: false.
            fields["governed"] = False
            # A10-D: no objective in scope => no adaptation evidence yet.
            fields["adaptation_outcome"] = "unknown"
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
