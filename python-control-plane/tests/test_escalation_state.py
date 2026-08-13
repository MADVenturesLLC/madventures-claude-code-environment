"""A10-C tests (DEC-20260812-05): escalation-state journal, counters,
write-once immutability, fail-closed behavior, and hook integration.

Coverage required by the A10-B decision acceptance criteria:
- session-reset test: counters and escalation state are durable (Q3.3) —
  a fresh DenialJournal instance (new process equivalent) reads the same
  state from disk.
- secret-exclusion test: every journal field passes through the A10-A
  registry redactor before write (Q2.3) — a denial_reason / target that
  contains an audit-confirmed secret shape is stored redacted.
- fail-closed test: an unwritable store raises, and consult_escalation
  denies without leaking storage details (Q5).
- write-once test: a duplicate record_id is refused (Q2.4).
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from madclaude import escalation_state as es
from madclaude.errors import EvidenceError
from madclaude.hook_policy import consult_escalation, evaluate_baseline

RETRY_CEILING = es.RETRY_CEILING  # 3
WORKAROUND_CEILING = es.WORKAROUND_CEILING  # 2


def make_repo() -> Path:
    return Path(tempfile.mkdtemp(prefix="a10c-test-"))


def make_journal(repo: Path) -> es.DenialJournal:
    return es.DenialJournal(repo)


def mint(repo: Path, artifact: str = "DEC-20260812-05@d5adae5") -> str:
    """Mint a Founder objective_id persisted in this repo's store (Q1.6)."""
    return es.mint_objective_id(artifact, store_root=repo)


def denial_fields(objective_id: str = "", action_type: str = "Bash", reason: str = "blocked") -> dict:
    return {
        "objective_id": objective_id,
        "action_type": action_type,
        "action_target": "/tmp/x",
        "resolved_route": "baseline",
        "risk_tier": "medium",
        "denial_reason": reason,
        "control_id": "matrix-cell-1",
    }


def mint_and_seed(repo: Path, objective_id: str, primary_type: str = "Bash") -> es.DenialJournal:
    journal = make_journal(repo)
    journal.record_denial(denial_fields(objective_id, primary_type, "first"))
    return journal


class ObjectiveLifecycleTests(unittest.TestCase):
    def test_objective_id_format_and_validation(self):
        journal = make_journal(make_repo())
        self.assertTrue(journal.validate_objective_id("obj-20260812T120000Z-1a2b3c4d"))
        self.assertFalse(journal.validate_objective_id("obj-nope"))
        self.assertFalse(journal.validate_objective_id(""))
        self.assertFalse(journal.validate_objective_id("20260812T120000Z-1a2b3c4d"))

    def test_minted_id_is_wellformed(self):
        repo = make_repo()
        objective_id = mint(repo)
        self.assertTrue(es.OBJECTIVE_ID_RE.fullmatch(objective_id))
        # Q1.6: the mint record is durably persisted with the source ref.
        record = make_journal(repo).objective_record(objective_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["source_artifact"], "DEC-20260812-05@d5adae5")
        self.assertEqual(record["objective_id"], objective_id)

    def test_mint_requires_source_artifact(self):
        # Q1.6: traceability requires a Founder-anchored source reference.
        with self.assertRaises(EvidenceError):
            es.mint_objective_id("")

    def test_lifecycle_derives_durably(self):
        repo = make_repo()
        objective_id = mint(repo)
        journal = make_journal(repo)
        self.assertEqual(journal.objective_state(objective_id), "created")
        journal.record_denial(denial_fields(objective_id, "Bash"))
        self.assertEqual(journal.objective_state(objective_id), "active")
        # Retry ceiling reached on the same action type -> escalated (Q1.4).
        for _ in range(RETRY_CEILING - 1):
            journal.record_denial(denial_fields(objective_id, "Bash"))
        self.assertEqual(journal.objective_state(objective_id), "escalated")
        self.assertTrue(journal.is_escalated(objective_id))


class DurableCounterTests(unittest.TestCase):
    def test_retry_counter_counts_same_action_type(self):
        repo = make_repo()
        objective_id = mint(repo)
        journal = make_journal(repo)
        journal.record_denial(denial_fields(objective_id, "Bash"))
        journal.record_denial(denial_fields(objective_id, "Bash"))
        journal.record_denial(denial_fields(objective_id, "Read"))
        self.assertEqual(journal.retry_count(objective_id, "Bash"), 2)
        self.assertEqual(journal.retry_count(objective_id, "Read"), 1)

    def test_workaround_counter_distinct_per_objective(self):
        repo = make_repo()
        objective_id = mint(repo)
        journal = make_journal(repo)
        journal.record_denial(denial_fields(objective_id, "Bash"))
        self.assertEqual(journal.workaround_count(objective_id), 0)  # primary action
        journal.record_denial(denial_fields(objective_id, "Read"))
        journal.record_denial(denial_fields(objective_id, "Write"))
        self.assertEqual(journal.workaround_count(objective_id), 2)  # both differ from primary
        self.assertTrue(journal.workaround_ceiling_exceeded(objective_id))

    def test_session_reset_durability(self):
        # Q3.3 acceptance: counters and escalation state survive a "restart"
        # — a fresh DenialJournal instance reads the same durable state.
        repo = make_repo()
        objective_id = mint(repo)
        make_journal(repo).record_denial(denial_fields(objective_id, "Bash"))
        make_journal(repo).record_denial(denial_fields(objective_id, "Bash"))
        fresh = make_journal(repo)  # new instance == new process equivalent
        self.assertEqual(fresh.retry_count(objective_id, "Bash"), 2)
        self.assertEqual(fresh.objective_state(objective_id), "active")

    def test_ceiling_event_escalates_and_records_reason(self):
        repo = make_repo()
        objective_id = mint(repo)
        journal = make_journal(repo)
        for _ in range(RETRY_CEILING):
            journal.record_denial(denial_fields(objective_id, "Bash", "blocked"))
        self.assertEqual(journal.objective_state(objective_id), "escalated")
        records = journal.records()
        self.assertEqual(len(records), RETRY_CEILING)
        self.assertTrue(all(r.get("action_type") == "Bash" for r in records))
        # Q3.4: the crossing record stamps the ceiling reason durably.
        # (records are filename-sorted, so search, don't index.)
        stamped = [r for r in records if r.get("ceiling_reason")]
        self.assertEqual(len(stamped), 1)
        self.assertIn(f"retry ceiling {RETRY_CEILING} reached for Bash", stamped[0]["ceiling_reason"])


class WriteOnceTests(unittest.TestCase):
    def test_record_ids_unique(self):
        repo = make_repo()
        journal = make_journal(repo)
        journal.record_denial(denial_fields())
        journal.record_denial(denial_fields())
        ids = [r["record_id"] for r in journal.records()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(es.RECORD_ID_RE.fullmatch(i) for i in ids))

    def test_duplicate_target_refused(self):
        # Q2.4: write-once — a second write to the same record_id refuses.
        repo = make_repo()
        journal = make_journal(repo)
        journal.record_denial(denial_fields())
        target = repo / journal.records()[0]["evidence_ref"]
        journal.record_denial(denial_fields())  # new id -> fine
        # Direct overwrite attempt must fail too (O_EXCL on the same path).
        with self.assertRaises(EvidenceError):
            from madclaude import evidence as ev

            ev.write_immutable_record(target, {"boom": True})

    def test_required_fields_enforced(self):
        repo = make_repo()
        journal = make_journal(repo)
        with self.assertRaises(EvidenceError):
            journal.record_denial({"action_type": "Bash"})  # missing six fields
        with self.assertRaises(EvidenceError):
            journal.record_denial(denial_fields("bad-objective"))

    def test_store_permissions(self):
        repo = make_repo()
        journal = make_journal(repo)
        journal.record_denial(denial_fields())
        record = journal.records()[0]
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(journal.store_dir.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((repo / record["evidence_ref"]).stat().st_mode), 0o600)


class SecretExclusionTests(unittest.TestCase):
    def test_denial_reason_redacted_before_write(self):
        # Q2.3: the A10-A registry redactor runs on every field — a secret
        # shape inside denial_reason must not reach disk.
        repo = make_repo()
        journal = make_journal(repo)
        journal.record_denial(
            denial_fields(reason="blocked: token ghp_12345678901234567890 leaked")
        )
        stored = journal.records()[0]
        self.assertNotIn("ghp_12345678901234567890", stored["denial_reason"])
        self.assertIn("[REDACTED]", stored["denial_reason"])
        self.assertNotIn("ghp_", stored["denial_reason"])

    def test_action_target_redacted_before_write(self):
        repo = make_repo()
        journal = make_journal(repo)
        fields = denial_fields()
        fields["action_target"] = "https://user:sekrit@example.com/x"
        journal.record_denial(fields)
        stored = journal.records()[0]
        self.assertNotIn("sekrit", stored["action_target"])
        self.assertIn("[REDACTED]", stored["action_target"])


class FailClosedTests(unittest.TestCase):
    def test_unwritable_store_raises(self):
        # Q5: a store that cannot be created must raise. Simulate by making
        # the store path a regular file — mkdir then fails. (chmod 0500 is
        # not a reliable blocker: the journal restores 0700 before writing.)
        repo = make_repo()
        store = repo / es.DENIAL_DIR_REL
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text("blocking file", encoding="utf-8")
        journal = make_journal(repo)
        with self.assertRaises(EvidenceError):
            journal.record_denial(denial_fields())

    def test_consult_escalation_denies_on_store_failure_without_leak(self):
        # Q5: consult fails closed and never exposes storage details.
        repo = make_repo()
        objective_id = "obj-20260812T120000Z-1a2b3c4d"
        store = repo / es.DENIAL_DIR_REL
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text("blocking file", encoding="utf-8")
        allowed, reason = consult_escalation(repo, {"objective_id": objective_id})
        self.assertFalse(allowed)
        self.assertNotIn("PermissionError", reason)
        self.assertNotIn(store.as_posix(), reason)
        self.assertNotIn("blocking file", reason)

    def test_no_objective_is_allowed(self):
        repo = make_repo()
        allowed, _ = consult_escalation(repo, {})
        self.assertTrue(allowed)
        allowed, _ = consult_escalation(repo, {"objective_id": ""})
        self.assertTrue(allowed)

    def test_malformed_objective_denied(self):
        repo = make_repo()
        allowed, _ = consult_escalation(repo, {"objective_id": "obj-nope"})
        self.assertFalse(allowed)

    def test_unknown_objective_denied(self):
        # Q1.1/Q1.3: well-formed but never Founder-minted -> deny.
        repo = make_repo()
        allowed, reason = consult_escalation(
            repo, {"objective_id": "obj-20260812T120000Z-1a2b3c4d"}
        )
        self.assertFalse(allowed)
        self.assertIn("unknown objective_id", reason)


class DispositionTests(unittest.TestCase):
    def _escalated(self, repo: Path, objective_id: str) -> es.DenialJournal:
        journal = make_journal(repo)
        for _ in range(RETRY_CEILING):
            journal.record_denial(denial_fields(objective_id, "Bash"))
        return journal

    def test_deny_disposition_is_terminal(self):
        # Q4.1 blocking fix: a deny disposition is NOT a continuation grant.
        # Consult must keep governed actions denied even with the exact
        # ceiling record_id supplied.
        repo = make_repo()
        objective_id = mint(repo)
        journal = self._escalated(repo, objective_id)
        ceiling = journal.records()[-1]["record_id"]
        journal.record_disposition(
            objective_id, ceiling, "deny", "DEC-20260812-05@d5adae5", "michael",
        )
        self.assertEqual(journal.objective_state(objective_id), "closed")
        # Direct consult with the exact ceiling event still denies.
        allowed, reason = consult_escalation(
            repo, {"objective_id": objective_id, "ceiling_record_id": ceiling}
        )
        self.assertFalse(allowed)
        self.assertIn("deny disposition", reason)
        # And with no ceiling event at all.
        allowed, _ = consult_escalation(repo, {"objective_id": objective_id})
        self.assertFalse(allowed)

    def test_continuation_requires_exact_ceiling_binding(self):
        # Q4.2/Q4.3: allow-with-conditions is a continuation grant ONLY when
        # bound to the exact ceiling event.
        repo = make_repo()
        objective_id = mint(repo)
        journal = self._escalated(repo, objective_id)
        records = journal.records()
        ceiling = records[-1]["record_id"]
        other_ceiling = records[-2]["record_id"]
        self.assertTrue(journal.is_escalated(objective_id))
        # Escalated, no disposition -> consult denies.
        allowed, _ = consult_escalation(
            repo, {"objective_id": objective_id, "ceiling_record_id": ceiling}
        )
        self.assertFalse(allowed)
        # Founder allow-with-conditions for the exact ceiling event.
        journal.record_disposition(
            objective_id, ceiling, "allow-with-conditions",
            "DEC-20260812-05@d5adae5", "michael",
        )
        self.assertTrue(journal.disposition_permits(objective_id, ceiling))
        # Consult allows continuation for THAT ceiling event...
        allowed, reason = consult_escalation(
            repo, {"objective_id": objective_id, "ceiling_record_id": ceiling}
        )
        self.assertTrue(allowed)
        self.assertIn("authorizes continuation", reason)
        # ...but denies a DIFFERENT ceiling event (per-event binding).
        allowed, _ = consult_escalation(
            repo, {"objective_id": objective_id, "ceiling_record_id": other_ceiling}
        )
        self.assertFalse(allowed)
        # And denies with no ceiling event at all.
        allowed, _ = consult_escalation(repo, {"objective_id": objective_id})
        self.assertFalse(allowed)

    def test_disposition_unknown_ceiling_refused(self):
        repo = make_repo()
        objective_id = mint(repo)
        journal = make_journal(repo)
        with self.assertRaises(EvidenceError):
            journal.record_disposition(
                objective_id, "denial-20260812T120000Z-deadbeef",
                "deny", "DEC-x@sha", "michael",
            )

    def test_non_self_clearing(self):
        # Q4.4: the model cannot author or clear a disposition — the only
        # write path is record_disposition, and there is no clear/delete
        # surface on the journal.
        repo = make_repo()
        journal = make_journal(repo)
        self.assertFalse(hasattr(journal, "clear_disposition"))
        self.assertFalse(hasattr(journal, "delete_disposition"))


class HookIntegrationTests(unittest.TestCase):
    def test_baseline_hook_consults_escalation(self):
        # A10-C integration: evaluate_baseline with an escalated objective
        # denies before the tool is evaluated.
        repo = make_repo()
        objective_id = mint(repo)
        journal = make_journal(repo)
        for _ in range(RETRY_CEILING):
            journal.record_denial(denial_fields(objective_id, "Bash"))
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
            "objective_id": objective_id,
        }
        allowed, reason = evaluate_baseline(repo, payload)
        self.assertFalse(allowed)
        self.assertIn("escalation", reason.lower())

    def test_baseline_hook_ignores_escalation_without_objective(self):
        repo = make_repo()
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
        }
        allowed, _ = evaluate_baseline(repo, payload)
        self.assertTrue(allowed)

    def test_hook_cli_journal_denial(self):
        # Q2 integration: hook_cli writes a durable denial record on a
        # baseline deny exit.
        from madclaude import hook_cli

        repo = make_repo()
        payload = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "echo hi"},
        }
        reason = "Destructive shell command blocked."
        with mock.patch.dict(
            os.environ, {"MADCLAUDE_REPO_ROOT": str(repo)}, clear=False
        ):
            hook_cli._journal_denial(payload, reason)
        records = make_journal(repo).records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["denial_reason"], reason)
        self.assertEqual(records[0]["governed"], False)  # no objective -> un-governed


if __name__ == "__main__":
    unittest.main()
