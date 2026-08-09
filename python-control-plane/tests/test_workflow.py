from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from madclaude.backend import AgentResponse
from madclaude.config import get_route
from madclaude.errors import AgentRunError, PolicyViolation
from madclaude.execution import load_execution_record, select_builder, select_independent_reviewer
from madclaude.prompts import audit_prompt
from madclaude.workflows import RuntimeOptions, dry_run_preview, run_build, run_exact_sha, run_fix_until_green, run_plan, run_verify
from support import clean_env, fake_claude, make_git_repo

PLAN = {
    "task_id": "TASK-TEST-1",
    "repository": "test/repo",
    "base_sha": "0" * 40,
    "risk_class": "medium",
    "recommended_builder": "sonnet",
    "builder_justification": "Bounded ordinary implementation",
    "eligible_fallbacks": ["opus"],
    "founder_gate_required": True,
    "governance_references": ["rules/70-python-control-plane.md"],
    "unknowns": [],
    "status": "ready",
    "summary": "ok",
    "repository_findings": [],
    "plan_steps": [{"step": "one", "files": ["README.md"], "rationale": "why", "acceptance": ["done"]}],
    "acceptance_mapping": [],
    "verification_plan": ["python3 --version"],
    "risks": [],
    "stop_conditions": [],
    "founder_decisions_required": [],
    "confidence": "high",
}


class WorkflowTests(unittest.TestCase):
    def _options(self, repo: Path, cli: Path, *, backend: str = "cli", billing_mode: str = "subscription") -> RuntimeOptions:
        return RuntimeOptions(
            backend=backend,
            billing_mode=billing_mode,
            allow_api_billing=billing_mode == "api",
            allow_usage_credits=False,
            claude_path=str(cli),
            timeout_seconds=30,
            verification_timeout_seconds=30,
            max_budget_usd=1.0 if billing_mode == "api" else None,
            evidence_dir=repo / ".claude" / "evidence" / "python-control-plane",
        )

    def test_plan_writes_complete_subscription_cli_evidence_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            (repo / ".claude" / "PROJECT_PROFILE.md").write_text("# Profile\n", encoding="utf-8")
            cli = fake_claude(root / "claude", PLAN)
            options = self._options(repo, cli)
            with patch.dict(os.environ, clean_env(), clear=True):
                outcome = run_plan(get_route("plan"), options, repo, "Plan the test feature")
            self.assertEqual(outcome.status, "completed", outcome.errors)
            evidence = Path(outcome.evidence_path)
            self.assertTrue((evidence / "MANIFEST.json").is_file())
            self.assertTrue((evidence / "structured-output.json").is_file())
            self.assertTrue((evidence / "PLAN.json").is_file())
            self.assertTrue((evidence / "PLAN.md").is_file())
            self.assertTrue((evidence / "auth.json").is_file())
            bundle_data = json.loads((evidence / "bundle.json").read_text(encoding="utf-8"))
            self.assertEqual(bundle_data["evidenceSource"], "local_evidence")
            execution = json.loads((evidence / "EXECUTION_RECORD.json").read_text(encoding="utf-8"))
            self.assertEqual(execution["participants"][0]["model"], "fable")
            self.assertEqual(execution["finalStatus"], "completed")
            self.assertEqual(load_execution_record(evidence / "EXECUTION_RECORD.json")["finalStatus"], "completed")
            request_data = json.loads((evidence / "request.json").read_text(encoding="utf-8"))
            self.assertEqual(request_data["backend"], "cli")
            self.assertEqual(request_data["billingMode"], "subscription")
            self.assertFalse(request_data["usageCreditsAcknowledged"])
            self.assertEqual(request_data["allowedSubagents"], ["founder-os-explorer", "dependency-mapper"])

    def test_dry_run_validates_without_writes_or_agent_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN)
            options = self._options(repo, cli)
            evidence_root = options.evidence_dir
            with patch.dict(os.environ, clean_env(), clear=True):
                preview = dry_run_preview(
                    route=get_route("plan"), options=options, repo=repo, goal="Plan dry run"
                )
            self.assertEqual(preview["status"], "dry-run")
            self.assertFalse(preview["wouldInvokeClaude"])
            self.assertFalse(evidence_root.exists())
            self.assertEqual(preview["backend"], "cli")
            self.assertEqual(preview["billingMode"], "subscription")
            self.assertEqual(preview["route"]["subagents"], ["founder-os-explorer", "dependency-mapper"])

    def test_agent_run_constructs_subscription_cli_request_with_read_only_fanout(self) -> None:
        class FakeBackend:
            def __init__(self) -> None:
                self.request = None

            def run(self, request):
                self.request = request
                return AgentResponse(success=True, structured_output=PLAN, subtype="success")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            (repo / ".claude" / "PROJECT_PROFILE.md").write_text("# Profile\n", encoding="utf-8")
            cli = fake_claude(root / "claude", PLAN)
            options = self._options(repo, cli)
            fake_backend = FakeBackend()
            with patch.dict(os.environ, clean_env(), clear=True), patch(
                "madclaude.workflows.backend_for", return_value=fake_backend
            ):
                outcome = run_plan(get_route("plan"), options, repo, "Plan through governed CLI")
            self.assertEqual(outcome.status, "completed", outcome.errors)
            self.assertIsNotNone(fake_backend.request)
            self.assertEqual(fake_backend.request.backend, "cli")
            self.assertEqual(fake_backend.request.billing_mode, "subscription")
            self.assertEqual(
                fake_backend.request.subagents,
                ("founder-os-explorer", "dependency-mapper"),
            )
            self.assertIn("Agent", fake_backend.request.tools)

    def test_sdk_backend_cannot_be_used_with_subscription_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN)
            with self.assertRaisesRegex(AgentRunError, "API-billed"):
                dry_run_preview(
                    route=get_route("plan"),
                    options=self._options(repo, cli, backend="sdk"),
                    repo=repo,
                    goal="Should fail before model invocation",
                )

    def test_route_model_override_must_stay_inside_governed_envelope(self) -> None:
        self.assertEqual(get_route("build", model="opus").model, "opus")
        with self.assertRaisesRegex(ValueError, "not eligible"):
            get_route("build", model="fable")

    def test_builder_selection_is_plan_recommended_and_python_validated(self) -> None:
        self.assertEqual(select_builder(get_route("build"), PLAN).model, "sonnet")
        invalid = {**PLAN, "recommended_builder": "fable"}
        with self.assertRaisesRegex(PolicyViolation, "not eligible"):
            select_builder(get_route("build"), invalid)

    def test_architecture_validation_is_exact_sha_read_only_opus_max(self) -> None:
        route = get_route("architecture-validation")
        self.assertTrue(route.exact_sha)
        self.assertFalse(route.mutates)
        self.assertEqual((route.model, route.effort), ("opus", "max"))

    def test_tier1_is_a_distinct_exact_sha_review_route(self) -> None:
        route = get_route("tier1-review")
        self.assertTrue(route.exact_sha)
        self.assertFalse(route.independence_verified)
        self.assertEqual(route.schema, "review")

    def test_fix_recovery_ceiling_is_three_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN)
            with self.assertRaisesRegex(PolicyViolation, "between 1 and 3"):
                run_fix_until_green(
                    get_route("fix-until-green"),
                    self._options(repo, cli),
                    repo,
                    "Repair",
                    ("src",),
                    ["python3 --version"],
                    4,
                )

    def test_successful_fix_writes_handoff_and_acceptance_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN)
            with patch.dict(os.environ, clean_env(), clear=True):
                outcome = run_fix_until_green(
                    get_route("fix-until-green"),
                    self._options(repo, cli),
                    repo,
                    "Confirm green state",
                    ("src",),
                    ["python3 --version"],
                    1,
                )
            evidence = Path(outcome.evidence_path)
            self.assertEqual(outcome.status, "completed")
            for name in ("HANDOFF.json", "HANDOFF.md", "ACCEPTANCE.json", "ACCEPTANCE.md", "VERIFICATION.md"):
                self.assertTrue((evidence / name).is_file(), name)

    def test_failed_fix_writes_recovery_handoff(self) -> None:
        class NoProgressBackend:
            def run(self, request):
                return AgentResponse(success=True, structured_output={"status": "partial"})

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            (repo / "tests").mkdir()
            (repo / "tests" / "check.py").write_text(
                "from pathlib import Path\nraise SystemExit(0 if Path('src/ok').exists() else 1)\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "-C", str(repo), "add", "tests/check.py"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "add check"], check=True)
            cli = fake_claude(root / "claude", PLAN)
            with patch.dict(os.environ, clean_env(), clear=True), patch(
                "madclaude.workflows.backend_for", return_value=NoProgressBackend()
            ):
                outcome = run_fix_until_green(
                    get_route("fix-until-green"),
                    self._options(repo, cli),
                    repo,
                    "Repair",
                    ("src",),
                    ["python3 tests/check.py"],
                    1,
                )
            self.assertEqual(outcome.status, "failed")
            handoff = json.loads((Path(outcome.evidence_path) / "HANDOFF.json").read_text(encoding="utf-8"))
            self.assertEqual(handoff["nextAction"], "architecture-validation-or-founder-escalation")

    def test_tier2_reviewer_excludes_all_prior_participants(self) -> None:
        record = {
            "participants": [
                {"role": "planner", "model": "fable", "stage": "plan"},
                {"role": "builder", "model": "sonnet", "stage": "build"},
                {"role": "verifier", "model": "opus", "stage": "verify"},
                {"role": "tier1-reviewer", "model": "codex", "stage": "tier1-review"},
            ]
        }
        selected = select_independent_reviewer(get_route("review"), record)
        self.assertEqual(selected.model, "haiku")
        self.assertTrue(selected.independence_verified)
        record["participants"].append({"role": "tier1", "model": "haiku", "stage": "review"})
        with self.assertRaisesRegex(PolicyViolation, "No eligible independent reviewer"):
            select_independent_reviewer(get_route("review"), record)
        with self.assertRaisesRegex(PolicyViolation, "missing required roles"):
            select_independent_reviewer(
                get_route("review"),
                {"participants": [{"role": "planner", "model": "fable", "stage": "plan"}]},
            )

    def test_unmanifested_execution_record_cannot_establish_participation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "EXECUTION_RECORD.json"
            path.write_text(json.dumps({"participants": []}), encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "manifest"):
                load_execution_record(path)

    def test_merged_audit_profile_preserves_specialized_contract(self) -> None:
        prompt = audit_prompt("Find drift", "repo-audit", {}, "", "docs-drift")
        self.assertIn("documentation claims against executable source", prompt)

    def test_build_and_verify_write_canonical_deterministic_artifacts(self) -> None:
        class BuildBackend:
            def __init__(self, repo: Path) -> None:
                self.repo = repo

            def run(self, request):
                target = self.repo / "src" / "result.txt"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("implemented\n", encoding="utf-8")
                return AgentResponse(success=True, structured_output={"status": "implemented"})

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN)
            plan = root / "plan.json"
            plan.write_text(json.dumps(PLAN), encoding="utf-8")
            from madclaude.approval import approval_template

            approval = approval_template(plan, "Build feature")
            approval.update({
                "founderApproved": True,
                "approvedBy": "Michael Daley",
                "approvedAt": "2026-08-07T12:00:00-04:00",
                "approvalReference": "Founder approval test",
                "allowedScope": ["src"],
                "acceptanceCriteria": ["Result exists"],
                "verificationCommands": ["git status --short"],
            })
            approval_path = root / "approval.json"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            with patch.dict(os.environ, clean_env(), clear=True), patch(
                "madclaude.workflows.backend_for", return_value=BuildBackend(repo)
            ):
                outcome = run_build(get_route("build"), self._options(repo, cli), repo, "Build feature", plan, approval_path)
            evidence = Path(outcome.evidence_path)
            self.assertEqual(outcome.status, "completed", outcome.errors)
            self.assertTrue((evidence / "HANDOFF.json").is_file())
            self.assertTrue((evidence / "ACCEPTANCE.json").is_file())
            self.assertTrue((evidence / "VERIFICATION.json").is_file())
            self.assertTrue((evidence / "PLAN.md").is_file())
            self.assertTrue((evidence / "HANDOFF.md").is_file())
            self.assertTrue((evidence / "ACCEPTANCE.md").is_file())
            self.assertTrue((evidence / "VERIFICATION.md").is_file())

    def test_verify_and_tier2_require_python_evidence_and_independence(self) -> None:
        class ReadOnlyBackend:
            def run(self, request):
                return AgentResponse(success=True, structured_output={"status": "passed"})

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN)
            options = self._options(repo, cli)
            with patch.dict(os.environ, clean_env(), clear=True), patch(
                "madclaude.workflows.backend_for", return_value=ReadOnlyBackend()
            ):
                verified = run_verify(get_route("verify"), options, repo, "Verify", ["python3 --version"])
            self.assertTrue((Path(verified.evidence_path) / "VERIFICATION.json").is_file())

            base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            (repo / "README.md").write_text("# Changed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "change"], check=True)
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            with self.assertRaisesRegex(PolicyViolation, "participant exclusion"):
                run_exact_sha(get_route("review"), options, repo, "Review", base, head, [])


if __name__ == "__main__":
    unittest.main()
