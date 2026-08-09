from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from madclaude.errors import PolicyViolation
from madclaude.guard import (
    enforce_scopes,
    evaluate_tool_call,
    is_protected_authority_path,
    is_sensitive_path,
    reject_sensitive_changed_paths,
    validate_scopes,
    validate_verification_command,
    within_scopes,
)


class GuardTests(unittest.TestCase):
    def test_verification_command_policy(self) -> None:
        self.assertTrue(validate_verification_command("python3 --version")[0])
        self.assertTrue(validate_verification_command("git status --short")[0])
        self.assertTrue(validate_verification_command("python3 -m unittest --help")[0])
        for command in (
            "python3 --version && rm -rf /",
            "git reset --hard",
            "git push origin main",
            "curl https://example.com",
            "npm install",
            "python3 -c 'print(1)'",
            "bash scripts/check.sh",
        ):
            with self.subTest(command=command), self.assertRaises(PolicyViolation):
                validate_verification_command(command)

    def test_scope_and_protected_path_enforcement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            scopes = validate_scopes(repo, ("src/auth", "tests/auth"))
            self.assertTrue(within_scopes("src/auth/index.ts", scopes))
            self.assertFalse(within_scopes("src/payments/index.ts", scopes))
            enforce_scopes(("src/auth/index.ts", "tests/auth/a.test.ts"), scopes)
            with self.assertRaises(PolicyViolation):
                enforce_scopes(("README.md",), scopes)
            with self.assertRaises(PolicyViolation):
                validate_scopes(repo, ("../outside",))
            with self.assertRaises(PolicyViolation):
                validate_scopes(repo, (".claude/rules",))

    def test_secret_and_authority_classification(self) -> None:
        self.assertTrue(is_sensitive_path(".env.local"))
        self.assertFalse(is_sensitive_path(".env.example"))
        self.assertTrue(is_protected_authority_path(".claude/MODEL_REGISTRY.md"))
        with self.assertRaises(PolicyViolation):
            reject_sensitive_changed_paths(("src/a.py", ".env"))

    def test_tool_policy_applies_to_main_agent_and_subagents(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "src").mkdir()
            (repo / "src" / "a.py").write_text("print('ok')\n", encoding="utf-8")
            (repo / ".env").write_text("SECRET=x\n", encoding="utf-8")
            base = dict(
                repo=repo,
                allowed_tools=("Read", "Grep", "Glob", "Write", "Agent"),
                mutates=True,
                scopes=("src",),
                allowed_subagents=("founder-os-explorer",),
            )

            self.assertFalse(evaluate_tool_call(tool_name="Read", tool_input={"file_path": ".env"}, **base)[0])
            self.assertFalse(evaluate_tool_call(tool_name="Read", tool_input={"file_path": "../outside"}, **base)[0])
            self.assertTrue(evaluate_tool_call(tool_name="Write", tool_input={"file_path": "src/new.py"}, **base)[0])
            self.assertFalse(evaluate_tool_call(tool_name="Write", tool_input={"file_path": "README.md"}, **base)[0])
            self.assertFalse(evaluate_tool_call(tool_name="Write", tool_input={"file_path": ".claude/settings.json"}, **base)[0])
            self.assertFalse(evaluate_tool_call(
                tool_name="MultiEdit",
                tool_input={"edits": [{"file_path": "src/ok.py"}, {"file_path": "README.md"}]},
                allowed_tools=(*base["allowed_tools"], "MultiEdit"),
                repo=base["repo"],
                mutates=base["mutates"],
                scopes=base["scopes"],
                allowed_subagents=base["allowed_subagents"],
            )[0])
            self.assertFalse(evaluate_tool_call(tool_name="Bash", tool_input={"command": "pwd"}, **base)[0])
            self.assertTrue(evaluate_tool_call(
                tool_name="Agent",
                tool_input={"subagent_type": "founder-os-explorer", "prompt": "explore"},
                **base,
            )[0])
            self.assertFalse(evaluate_tool_call(
                tool_name="Agent",
                tool_input={"subagent_type": "feature-builder", "prompt": "edit"},
                **base,
            )[0])
            self.assertFalse(evaluate_tool_call(tool_name="WebFetch", tool_input={"url": "https://example.com"}, **base)[0])
            self.assertFalse(evaluate_tool_call(tool_name="Grep", tool_input={"pattern": "SECRET"}, **base)[0])
            self.assertTrue(evaluate_tool_call(tool_name="Grep", tool_input={"pattern": "print", "glob": "*.py"}, **base)[0])


if __name__ == "__main__":
    unittest.main()
