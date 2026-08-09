from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from madclaude.approval import approval_template, validate_approval
from madclaude.errors import PolicyViolation
from support import make_git_repo


class ApprovalTests(unittest.TestCase):
    def test_approval_binds_goal_plan_and_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            plan = root / "plan.json"
            plan.write_text('{"status":"ready"}\n', encoding="utf-8")
            approval = approval_template(plan, "Build feature")
            approval.update({
                "founderApproved": True,
                "approvedBy": "Michael Daley",
                "approvedAt": "2026-08-06T20:00:00-04:00",
                "approvalReference": "Founder approval test reference",
                "allowedScope": ["src", "tests"],
                "acceptanceCriteria": ["Behavior is correct"],
                "verificationCommands": ["python3 --version"],
            })
            approval_path = root / "approval.json"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            loaded, scopes, acceptance, commands = validate_approval(repo, plan, approval_path, "Build feature")
            self.assertTrue(loaded["founderApproved"])
            self.assertEqual(loaded["evidenceSource"], "local_evidence")
            self.assertEqual(scopes, ("src", "tests"))
            self.assertEqual(commands, ["python3 --version"])
            plan.write_text('{"status":"changed"}\n', encoding="utf-8")
            with self.assertRaises(PolicyViolation):
                validate_approval(repo, plan, approval_path, "Build feature")

    def test_approval_rejects_cached_evidence_as_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            plan = root / "plan.json"
            plan.write_text('{"status":"ready"}\n', encoding="utf-8")
            approval = approval_template(plan, "Build feature")
            approval.update({
                "founderApproved": True,
                "approvedBy": "Michael Daley",
                "approvedAt": "2026-08-06T20:00:00-04:00",
                "approvalReference": "Founder approval test reference",
                "evidenceSource": "cached_evidence",
                "allowedScope": ["src"],
                "acceptanceCriteria": ["Behavior is correct"],
                "verificationCommands": ["python3 --version"],
            })
            approval_path = root / "approval.json"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "cached_evidence"):
                validate_approval(repo, plan, approval_path, "Build feature")


if __name__ == "__main__":
    unittest.main()
