from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from madclaude.backend import AgentRequest, AgentResponse, CliBackend, SdkBackend, make_pre_tool_policy_hook
from madclaude.errors import AgentRunError
from madclaude.schemas import schema_for
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
    "governance_references": [],
    "unknowns": [],
    "status": "ready",
    "summary": "ok",
    "repository_findings": [],
    "plan_steps": [{"step": "one", "files": [], "rationale": "why", "acceptance": []}],
    "acceptance_mapping": [],
    "verification_plan": [],
    "risks": [],
    "stop_conditions": [],
    "founder_decisions_required": [],
    "confidence": "high",
}


def request(repo: Path, cli: Path, **overrides) -> AgentRequest:
    values = dict(
        route_name="plan",
        prompt="plan",
        cwd=repo,
        claude_path=str(cli),
        environment=clean_env(),
        model="fable",
        effort="high",
        max_turns=10,
        permission_mode="dontAsk",
        tools=("Read", "Grep", "Glob", "Agent"),
        schema=schema_for("plan"),
        timeout_seconds=30,
        mutates=False,
        allowed_scopes=(),
        max_budget_usd=None,
        setting_sources=("project",),
        system_append="test",
        backend="cli",
        billing_mode="subscription",
        subagents=("founder-os-explorer", "dependency-mapper"),
    )
    values.update(overrides)
    return AgentRequest(**values)


class BackendTests(unittest.TestCase):
    def _fake_sdk(self, captured: dict[str, object], *, cost: float = 0.0):
        class FakeOptions:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        class FakeHookMatcher:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeResultMessage:
            def __init__(self):
                self.subtype = "success"
                self.is_error = False
                self.errors = None
                self.structured_output = PLAN
                self.session_id = "sdk-session"
                self.total_cost_usd = cost
                self.num_turns = 2
                self.terminal_reason = "completed"
                self.stop_reason = "end_turn"
                self.result = ""

        async def fake_query(*, prompt, options):
            self.assertEqual(prompt, "plan")
            self.assertIsInstance(options, FakeOptions)
            yield FakeResultMessage()

        module = types.ModuleType("claude_agent_sdk")
        module.ClaudeAgentOptions = FakeOptions
        module.HookMatcher = FakeHookMatcher
        module.ResultMessage = FakeResultMessage
        module.query = fake_query
        return module

    def test_cli_subscription_is_default_and_uses_ephemeral_hard_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            capture = root / "capture.json"
            cli = fake_claude(root / "claude", PLAN, capture_path=capture)
            response = CliBackend().run(request(repo, cli))

            self.assertTrue(response.success, response.errors)
            self.assertEqual(request(repo, cli).backend, "cli")
            self.assertIn("-p", response.command)
            self.assertIn("--strict-mcp-config", response.command)
            self.assertIn("[EPHEMERAL POLICY SETTINGS]", response.command)
            self.assertIn("[PROMPT REDACTED FROM COMMAND EVIDENCE]", response.command)
            self.assertNotIn("--max-budget-usd", response.command)
            joined = " ".join(response.command)
            self.assertIn("Agent(founder-os-explorer)", joined)
            self.assertIn("Agent(dependency-mapper)", joined)

            captured = json.loads(capture.read_text(encoding="utf-8"))
            hook = captured["settings"]["hooks"]["PreToolUse"][0]["hooks"][0]
            self.assertIn("madclaude.hook_cli", hook["command"])
            self.assertEqual(captured["env"]["MADCLAUDE_CONTROL_PLANE_ACTIVE"], "1")
            self.assertEqual(captured["env"]["MADCLAUDE_MUTATES"], "0")
            self.assertEqual(
                json.loads(captured["env"]["MADCLAUDE_ALLOWED_SUBAGENTS_JSON"]),
                ["founder-os-explorer", "dependency-mapper"],
            )

    def test_cli_supports_founder_scoped_mutating_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            (repo / "src").mkdir()
            cli = fake_claude(root / "claude", PLAN)
            response = CliBackend().run(
                request(
                    repo,
                    cli,
                    route_name="build",
                    mutates=True,
                    tools=("Read", "Grep", "Glob", "Edit", "Write"),
                    permission_mode="acceptEdits",
                    allowed_scopes=("src",),
                    subagents=(),
                )
            )
            self.assertTrue(response.success, response.errors)
            joined = " ".join(response.command)
            self.assertIn("acceptEdits", joined)
            self.assertIn("Edit,Write", joined)
            self.assertNotIn("Agent(", joined)

    def test_cli_rejects_mutation_without_approved_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN)
            with self.assertRaisesRegex(AgentRunError, "Founder-approved scope"):
                CliBackend().run(
                    request(
                        repo,
                        cli,
                        route_name="build",
                        mutates=True,
                        tools=("Read", "Edit", "Write"),
                        permission_mode="acceptEdits",
                        subagents=(),
                    )
                )

    def test_cli_api_estimated_cost_ceiling_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN, total_cost_usd=2.0)
            response = CliBackend().run(
                request(
                    repo,
                    cli,
                    billing_mode="api",
                    max_budget_usd=1.0,
                    tools=("Read", "Grep", "Glob"),
                    subagents=(),
                )
            )
            self.assertFalse(response.success)
            self.assertIn("--max-budget-usd", response.command)
            self.assertTrue(any("exceeded" in error for error in response.errors))

    def test_sdk_rejects_subscription_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN)
            with self.assertRaisesRegex(AgentRunError, "API-billed"):
                SdkBackend().run(request(repo, cli, backend="sdk"))

    def test_sdk_api_lane_applies_hard_controls_and_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN)
            captured: dict[str, object] = {}
            fake_sdk = self._fake_sdk(captured, cost=2.0)
            with patch.dict(sys.modules, {"claude_agent_sdk": fake_sdk}):
                response = SdkBackend().run(
                    request(
                        repo,
                        cli,
                        backend="sdk",
                        billing_mode="api",
                        max_budget_usd=1.0,
                    )
                )
            self.assertFalse(response.success)
            self.assertEqual(captured["setting_sources"], ["project"])
            self.assertEqual(captured["mcp_servers"], {})
            self.assertEqual(captured["skills"], [])
            self.assertEqual(captured["plugins"], [])
            self.assertTrue(captured["strict_mcp_config"])
            self.assertEqual(captured["system_prompt"]["preset"], "claude_code")
            self.assertEqual(captured["max_budget_usd"], 1.0)
            self.assertIn("PreToolUse", captured["hooks"])
            self.assertIn("Agent", captured["tools"])
            self.assertIn("Agent(founder-os-explorer)", captured["allowed_tools"])
            self.assertNotIn("Agent", captured["disallowed_tools"])
            self.assertIn("Task", captured["disallowed_tools"])
            self.assertTrue(any("exceeded" in error for error in response.errors))

    def test_pretool_hook_enforces_scope_subagent_registry_and_no_nesting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN)
            hook = make_pre_tool_policy_hook(
                request(
                    repo,
                    cli,
                    route_name="build",
                    mutates=True,
                    tools=("Read", "Edit", "Write", "Agent"),
                    allowed_scopes=("src",),
                    subagents=("founder-os-explorer",),
                )
            )
            denied = asyncio.run(
                hook({"tool_name": "Write", "tool_input": {"file_path": "README.md"}}, None, {})
            )
            self.assertEqual(denied["hookSpecificOutput"]["permissionDecision"], "deny")
            allowed = asyncio.run(
                hook({"tool_name": "Write", "tool_input": {"file_path": "src/new.py"}}, None, {})
            )
            self.assertEqual(allowed, {})
            agent_allowed = asyncio.run(
                hook(
                    {"tool_name": "Agent", "tool_input": {"subagent_type": "founder-os-explorer"}},
                    None,
                    {},
                )
            )
            self.assertEqual(agent_allowed, {})
            agent_denied = asyncio.run(
                hook(
                    {"tool_name": "Agent", "tool_input": {"subagent_type": "feature-builder"}},
                    None,
                    {},
                )
            )
            self.assertEqual(agent_denied["hookSpecificOutput"]["permissionDecision"], "deny")
            nested = asyncio.run(
                hook(
                    {
                        "tool_name": "Agent",
                        "agent_id": "child-1",
                        "agent_type": "founder-os-explorer",
                        "tool_input": {"subagent_type": "founder-os-explorer"},
                    },
                    None,
                    {},
                )
            )
            self.assertIn("Nested", nested["hookSpecificOutput"]["permissionDecisionReason"])


class BackendFailurePathTests(unittest.TestCase):
    """A9-03: malformed and failure-path handling must fail closed."""

    def _setup(self, root: Path, structured_output=None, **fake_kwargs):
        repo = make_git_repo(root / "repo")
        cli = fake_claude(root / "claude", structured_output if structured_output is not None else PLAN, **fake_kwargs)
        return repo, cli

    def test_malformed_json_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, cli = self._setup(Path(temp), stdout="this is not json{{{")
            response = CliBackend().run(request(repo, cli))
            self.assertFalse(response.success)
            self.assertIsNone(response.structured_output)
            self.assertTrue(any("not valid JSON" in error for error in response.errors))

    def test_empty_output_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, cli = self._setup(Path(temp), stdout="")
            response = CliBackend().run(request(repo, cli))
            self.assertFalse(response.success)
            self.assertIsNone(response.structured_output)
            self.assertTrue(response.errors)

    def test_nonzero_exit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, cli = self._setup(Path(temp), exit_code=3)
            response = CliBackend().run(request(repo, cli))
            self.assertFalse(response.success)
            self.assertTrue(any("exited 3" in error for error in response.errors))

    def test_timeout_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, cli = self._setup(Path(temp), sleep_seconds=10)
            with self.assertRaisesRegex(AgentRunError, "exceeded 1 seconds"):
                CliBackend().run(request(repo, cli, timeout_seconds=1))

    def test_missing_structured_output_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            payload = json.dumps({"type": "result", "subtype": "success", "result": "plain text, not json"})
            repo, cli = self._setup(Path(temp), stdout=payload)
            response = CliBackend().run(request(repo, cli))
            self.assertFalse(response.success)
            self.assertIsNone(response.structured_output)
            self.assertTrue(any("structured_output" in error for error in response.errors))

    def test_invalid_structured_output_vs_schema_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, cli = self._setup(Path(temp), structured_output={"bogus": True})
            response = CliBackend().run(request(repo, cli))
            self.assertFalse(response.success)
            self.assertTrue(response.errors)

    def test_oversized_output_not_silently_truncated_at_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            large = "x" * 300_000
            payload = json.dumps(
                {"type": "result", "subtype": "success", "result": large, "structured_output": PLAN}
            )
            repo, cli = self._setup(Path(temp), stdout=payload)
            response = CliBackend().run(request(repo, cli))
            self.assertTrue(response.success, response.errors)
            self.assertEqual(response.result_text, large)
            self.assertGreaterEqual(len(response.stdout), 300_000)

    def test_sdk_absent_import_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, cli = self._setup(Path(temp))
            with patch.dict(sys.modules, {"claude_agent_sdk": None}):
                with self.assertRaisesRegex(AgentRunError, "--with-sdk"):
                    SdkBackend().run(request(repo, cli, backend="sdk", billing_mode="api"))

    def test_sdk_subscription_combination_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo, cli = self._setup(Path(temp))
            for billing_mode in ("subscription",):
                with self.subTest(billing_mode=billing_mode):
                    with self.assertRaisesRegex(AgentRunError, "API-billed"):
                        SdkBackend().run(request(repo, cli, backend="sdk", billing_mode=billing_mode))

    def test_diff_evidence_truncation_poisons_approval(self) -> None:
        from madclaude.git import diff_text

        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            base = _head_sha(repo)
            (repo / "README.md").write_text("# Changed with a much longer line of content\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "change"], check=True)
            head = _head_sha(repo)
            text, truncated = diff_text(repo, base, head, max_chars=100)
            self.assertTrue(truncated)
            self.assertTrue(text.endswith("[DIFF TRUNCATED BY CONTROL PLANE]\n"))
            full, truncated_full = diff_text(repo, base, head)
            self.assertFalse(truncated_full)
            self.assertIn("Changed with a much longer line", full)

    def test_agent_run_failure_never_writes_success_evidence(self) -> None:
        import os

        from madclaude.config import get_route
        from madclaude.workflows import RuntimeOptions, run_verify

        class FailingBackend:
            def run(self, request):
                return AgentResponse(success=False, structured_output=None, errors=["backend exploded"])

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            cli = fake_claude(root / "claude", PLAN)
            options = RuntimeOptions(
                backend="cli",
                billing_mode="subscription",
                allow_api_billing=False,
                allow_usage_credits=False,
                claude_path=str(cli),
                timeout_seconds=30,
                verification_timeout_seconds=30,
                max_budget_usd=None,
                evidence_dir=repo / ".claude" / "evidence" / "python-control-plane",
            )
            with patch.dict(os.environ, clean_env(), clear=True), patch(
                "madclaude.workflows.backend_for", return_value=FailingBackend()
            ):
                outcome = run_verify(get_route("verify"), options, repo, "Verify", ["python3 --version"])
            self.assertEqual(outcome.status, "failed")
            self.assertIn("backend exploded", outcome.errors)
            manifest = json.loads((Path(outcome.evidence_path) / "MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "failed")


def _head_sha(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


if __name__ == "__main__":
    unittest.main()
