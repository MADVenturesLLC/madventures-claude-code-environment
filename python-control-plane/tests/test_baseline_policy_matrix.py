"""A10-A: supported-tool policy matrix at the baseline hook.

The baseline previously fell through to allow for every non-file,
non-shell tool (hook_policy.py:99-100). After the A10-A flip, every
family has an explicit disposition and unknown tools fail closed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import make_git_repo


class BaselinePolicyMatrixTests(unittest.TestCase):
    def _run(self, repo: Path, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["MADCLAUDE_REPO_ROOT"] = str(repo)
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        return subprocess.run(
            [sys.executable, "-m", "madclaude.hook_cli", "--profile", "baseline"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=environment,
            cwd=repo,
            check=False,
        )

    def test_unknown_tool_denied_at_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            for tool in ("TotallyUnknownTool", "FutureTool", "weird_tool"):
                with self.subTest(tool=tool):
                    result = self._run(repo, {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {}})
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("denied at baseline", result.stderr)

    def test_web_tools_denied_at_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            for tool in ("WebFetch", "WebSearch"):
                with self.subTest(tool=tool):
                    result = self._run(
                        repo,
                        {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"url": "https://example.com"}},
                    )
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                    self.assertIn("not supported at baseline", result.stderr)

    def test_mcp_denied_at_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            for tool in ("mcp__github__create_issue", "MCP__figma__get_file"):
                with self.subTest(tool=tool):
                    result = self._run(repo, {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {}})
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_meta_tools_allowed_at_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            for tool in ("TodoWrite", "ExitPlanMode", "TaskCreate", "TaskUpdate"):
                with self.subTest(tool=tool):
                    result = self._run(repo, {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {}})
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_skill_allowed_at_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            result = self._run(repo, {"hook_event_name": "PreToolUse", "tool_name": "Skill", "tool_input": {}})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_agent_denied_outside_governed_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            environment = dict(os.environ)
            environment["MADCLAUDE_REPO_ROOT"] = str(repo)
            environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            environment.pop("MADCLAUDE_CONTROL_PLANE_ACTIVE", None)
            result = subprocess.run(
                [sys.executable, "-m", "madclaude.hook_cli", "--profile", "baseline"],
                input=json.dumps(
                    {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {"subagent_type": "founder-os-explorer"}}
                ),
                capture_output=True,
                text=True,
                env=environment,
                cwd=repo,
                check=False,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("governed control-plane routes", result.stderr)

    def test_agent_deferred_inside_governed_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            environment = dict(os.environ)
            environment["MADCLAUDE_REPO_ROOT"] = str(repo)
            environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            environment["MADCLAUDE_CONTROL_PLANE_ACTIVE"] = "1"
            result = subprocess.run(
                [sys.executable, "-m", "madclaude.hook_cli", "--profile", "baseline"],
                input=json.dumps(
                    {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {"subagent_type": "founder-os-explorer"}}
                ),
                capture_output=True,
                text=True,
                env=environment,
                cwd=repo,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
