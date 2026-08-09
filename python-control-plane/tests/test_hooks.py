from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from madclaude.backend import AgentResponse
from madclaude.config import get_route
from madclaude.workflows import RuntimeOptions, run_verify
from support import clean_env, fake_claude, make_git_repo


class HookCliTests(unittest.TestCase):
    def _run(self, repo: Path, profile: str, payload: dict[str, object] | str) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["MADCLAUDE_REPO_ROOT"] = str(repo)
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(
            [sys.executable, "-m", "madclaude.hook_cli", "--profile", profile],
            input=raw,
            capture_output=True,
            text=True,
            env=environment,
            cwd=repo,
            check=False,
        )

    def test_baseline_blocks_shell_bypasses_and_protected_tool_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            blocked = (
                {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "cat .env"}},
                {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git -C . reset --hard HEAD"}},
                {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": ".claude/hooks/hook-adapter.mjs"}},
                {"hook_event_name": "PreToolUse", "tool_name": "Write", "tool_input": {"file_path": ".claude/rules/40-governance-authority.md"}},
                {"hook_event_name": "PreToolUse", "tool_name": "Glob", "tool_input": {"path": ".", "pattern": "**/.env*"}},
            )
            for payload in blocked:
                with self.subTest(payload=payload):
                    result = self._run(repo, "baseline", payload)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_baseline_hook_fails_closed_on_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            result = self._run(repo, "baseline", "{")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_completion_blocks_a_dirty_tree_without_current_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            (repo / "README.md").write_text("changed\n", encoding="utf-8")
            result = self._run(repo, "completion", {"hook_event_name": "Stop", "stop_hook_active": False})
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("verification", result.stderr.lower())

    def test_completion_allows_reentrant_stop_to_prevent_a_block_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            (repo / "README.md").write_text("changed\n", encoding="utf-8")
            result = self._run(repo, "completion", {"hook_event_name": "Stop", "stop_hook_active": True})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_completion_allows_clean_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            result = self._run(repo, "completion", {"hook_event_name": "Stop", "stop_hook_active": False})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_completion_blocks_stale_or_tampered_verification(self) -> None:
        class ReadOnlyBackend:
            def run(self, request):
                return AgentResponse(success=True, structured_output={"status": "passed"})

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = make_git_repo(root / "repo")
            (repo / "README.md").write_text("verified change\n", encoding="utf-8")
            cli = fake_claude(root / "claude", {"status": "passed"})
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
                "madclaude.workflows.backend_for", return_value=ReadOnlyBackend()
            ):
                outcome = run_verify(get_route("verify"), options, repo, "Verify change", ["git status --short"])
            self.assertEqual(outcome.status, "completed", outcome.errors)

            # Manifest bound to the current head; a new change makes it stale.
            allowed = self._run(repo, "completion", {"hook_event_name": "Stop", "stop_hook_active": False})
            self.assertEqual(allowed.returncode, 0, allowed.stdout + allowed.stderr)

            (repo / "README.md").write_text("new unverified change\n", encoding="utf-8")
            stale = self._run(repo, "completion", {"hook_event_name": "Stop", "stop_hook_active": False})
            self.assertEqual(stale.returncode, 2, stale.stdout + stale.stderr)

            # Tampered artifact must also fail.
            (repo / "README.md").write_text("verified change\n", encoding="utf-8")
            artifact = Path(outcome.evidence_path) / "VERIFICATION.md"
            artifact.write_text(artifact.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            tampered = self._run(repo, "completion", {"hook_event_name": "Stop", "stop_hook_active": False})
            self.assertEqual(tampered.returncode, 2, tampered.stdout + tampered.stderr)


if __name__ == "__main__":
    unittest.main()
