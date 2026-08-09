"""U11: CLI visual polish (A9-06) — themed human output, zero governance effect."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from madclaude import cli, term
from madclaude.version import __version__

SRC = Path(__file__).resolve().parents[1] / "src" / "madclaude"
ESC = b"\x1b"


class TtyStream(io.StringIO):
    def isatty(self) -> bool:
        return True


class TermTests(unittest.TestCase):
    def test_non_tty_plain(self) -> None:
        for theme in ("auto", "light", "dark", "plain"):
            with self.subTest(theme=theme), mock.patch.dict(
                os.environ, {"TERM": "xterm-256color"}, clear=False
            ):
                stream = io.StringIO()  # not a tty
                self.assertFalse(term.styling_enabled(theme, stream))
                self.assertEqual(term.style("hello", "key", theme=theme, stream=stream), "hello")

    def test_tty_theme_renders_equivalent_content(self) -> None:
        with mock.patch.dict(os.environ, {"TERM": "xterm-256color"}, clear=False):
            os.environ.pop("NO_COLOR", None)
            stream = TtyStream()
            styled = term.style("status", "ok", theme="dark", stream=stream)
            self.assertIn("\x1b[", styled)
            self.assertEqual(term.strip_ansi(styled), "status")
            plain = term.style("status", "ok", theme="plain", stream=stream)
            self.assertEqual(plain, "status")

    def test_no_color_and_dumb_term_disable(self) -> None:
        stream = TtyStream()
        with mock.patch.dict(os.environ, {"TERM": "xterm", "NO_COLOR": "1"}, clear=False):
            self.assertFalse(term.styling_enabled("dark", stream))
        with mock.patch.dict(os.environ, {"TERM": "dumb"}, clear=False):
            os.environ.pop("NO_COLOR", None)
            self.assertFalse(term.styling_enabled("dark", stream))

    def test_no_ansi_in_json(self) -> None:
        stream = TtyStream()
        for theme in ("auto", "light", "dark", "plain"):
            with self.subTest(theme=theme), mock.patch.dict(
                os.environ, {"TERM": "xterm"}, clear=False
            ), mock.patch.object(sys, "stdout", stream):
                os.environ.pop("NO_COLOR", None)
                stream.seek(0)
                stream.truncate(0)
                cli._print({"status": "completed", "nested": {"a": 1}}, True, theme=theme)
                self.assertNotIn(ESC, stream.getvalue().encode())

    def test_no_ansi_in_hook_protocol(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                **os.environ,
                "PYTHONPATH": str(SRC.parent),
                "MADCLAUDE_CONTROL_PLANE_ACTIVE": "1",
                "MADCLAUDE_REPO_ROOT": temp,
                "MADCLAUDE_THEME": "dark",
                "TERM": "xterm",
                "MADCLAUDE_ALLOWED_TOOLS_JSON": '["Read"]',
                "MADCLAUDE_ALLOWED_SCOPES_JSON": "[]",
                "MADCLAUDE_ALLOWED_SUBAGENTS_JSON": "[]",
                "MADCLAUDE_MUTATES": "0",
            }
            completed = subprocess.run(
                [sys.executable, "-m", "madclaude.hook_cli"],
                input=json.dumps({"tool_name": "mcp__github__x", "tool_input": {}}).encode(),
                capture_output=True, text=False, env=env, check=False,
            )
            self.assertEqual(completed.returncode, 0)
            self.assertNotIn(ESC, completed.stdout)
            self.assertNotIn(ESC, completed.stderr)
            decision = json.loads(completed.stdout)
            self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_version_machine_readable_single_source(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "madclaude.cli", "--version"],
            capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(SRC.parent)}, check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout.strip(), f"madclaude {__version__}")
        self.assertNotIn(ESC, completed.stdout.encode())
        # The version literal must have a single source: no second literal in term.py/cli.py.
        for name in ("term.py", "cli.py"):
            text = (SRC / name).read_text(encoding="utf-8")
            self.assertNotIn(__version__, text, f"version literal duplicated in {name}")

    def test_theme_choices_no_governance_effect(self) -> None:
        # No governance module imports the cosmetic layer.
        for name in ("guard.py", "hook_cli.py", "hook_policy.py", "evidence.py", "mcp_lifecycle.py", "approval.py"):
            text = (SRC / name).read_text(encoding="utf-8")
            self.assertNotIn("import term", text, f"{name} must not depend on term")
            self.assertNotIn("from .term", text, f"{name} must not depend on term")
        # Guard outcomes are identical under every theme.
        from madclaude.guard import evaluate_tool_call

        with tempfile.TemporaryDirectory() as temp:
            outcomes = set()
            for theme in ("auto", "light", "dark", "plain"):
                with mock.patch.dict(os.environ, {"MADCLAUDE_THEME": theme}, clear=False):
                    outcomes.add(
                        evaluate_tool_call(
                            repo=Path(temp),
                            tool_name="Read",
                            tool_input={"file_path": "src/a.py"},
                            allowed_tools=("Read",),
                            mutates=False,
                        )
                    )
            self.assertEqual(len(outcomes), 1)

    def test_print_human_branch_only_styles_keys_and_status(self) -> None:
        stream = TtyStream()
        with mock.patch.dict(os.environ, {"TERM": "xterm"}, clear=False), mock.patch.object(sys, "stdout", stream):
            os.environ.pop("NO_COLOR", None)
            cli._print({"status": "completed", "note": "plain text"}, False, theme="dark")
            output = stream.getvalue()
            self.assertIn("\x1b[36mstatus\x1b[0m", output)
            self.assertIn("\x1b[32mcompleted\x1b[0m", output)
            stripped = term.strip_ansi(output)
            self.assertIn("status: completed", stripped)
            self.assertIn("note: plain text", stripped)


if __name__ == "__main__":
    unittest.main()
