"""U10: MCP server + protocol tests (A9-05).

The dependency-free harness exercises the stdlib protocol core via a stub
transport (direct handle_jsonrpc calls). SDK-bound protocol tests are skipped
with a reason when `mcp` is not importable (it exists only in the release
venv on targets).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from madclaude import mcp_server
from madclaude.errors import PolicyViolation
from madclaude.mcp_lifecycle import enable, releases_root
from madclaude.mcp_server import (
    AUTHORITY,
    TOOL_NAMES,
    ServerContext,
    call_tool,
    handle_jsonrpc,
    tool_definitions,
)
from test_mcp_release_install import Fixture

MCP_IMPORTABLE = importlib.util.find_spec("mcp") is not None


def _context(home: Path, release: Path | None = None) -> ServerContext:
    return ServerContext(home=home, release_dir=release or home / "release")


class ToolSurfaceTests(unittest.TestCase):
    def test_tool_list_is_exactly_the_locked_surface(self) -> None:
        self.assertEqual(tuple(definition["name"] for definition in tool_definitions()), TOOL_NAMES)
        self.assertEqual(
            set(TOOL_NAMES),
            {"control_plane_status", "routes_list", "evidence_index", "evidence_read", "request_verification"},
        )

    def test_no_authority_sounding_tools_exist(self) -> None:
        forbidden = ("approve", "restore", "merge", "deploy", "enable", "disable", "remove", "rollback", "write")
        for name in TOOL_NAMES:
            for word in forbidden:
                self.assertNotIn(word, name)

    def test_every_tool_result_carries_non_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            context = _context(Path(temp))
            for name, arguments in (
                ("control_plane_status", {}),
                ("routes_list", {}),
            ):
                with self.subTest(tool=name):
                    result = call_tool(name, arguments, context)
                    self.assertEqual(result["authority"], AUTHORITY)

    def test_unknown_tool_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(PolicyViolation):
                call_tool("grant_approval", {}, _context(Path(temp)))


class StubTransportProtocolTests(unittest.TestCase):
    def _roundtrip(self, context: ServerContext) -> None:
        initialize = handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, context)
        self.assertEqual(initialize["result"]["serverInfo"]["authority"], AUTHORITY)
        listed = handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, context)
        self.assertEqual([tool["name"] for tool in listed["result"]["tools"]], list(TOOL_NAMES))
        called = handle_jsonrpc(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "control_plane_status", "arguments": {}}},
            context,
        )
        payload = called["result"]["structuredContent"]
        self.assertEqual(payload["authority"], AUTHORITY)
        self.assertFalse(called["result"]["isError"])

    def test_initialize_list_call_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            self._roundtrip(_context(Path(temp)))

    def test_malformed_frames_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            context = _context(Path(temp))
            frames = (
                "not-a-dict",
                {"id": 1},
                {"jsonrpc": "2.0", "id": 2, "method": "bogus/method"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope"}},
                {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "evidence_read", "arguments": "x"}},
            )
            for frame in frames:
                with self.subTest(frame=frame):
                    response = handle_jsonrpc(frame, context)
                    self.assertIsNotNone(response)
                    assert response is not None
                    self.assertIn("error", response)
                    self.assertNotIn("result", response)

    def test_notifications_return_none(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            context = _context(Path(temp))
            self.assertIsNone(handle_jsonrpc({"jsonrpc": "2.0", "method": "notifications/initialized"}, context))


class EvidenceToolTests(unittest.TestCase):
    def _repo_with_bundle(self, base: Path) -> Path:
        repo = base / "repo"
        bundle = repo / ".claude" / "evidence" / "python-control-plane" / "bundle-1"
        bundle.mkdir(parents=True)
        import hashlib

        content = b"verification transcript\n"
        (bundle / "VERIFICATION.md").write_bytes(content)
        manifest = {
            "status": "completed",
            "route": "verify",
            "files": [{"path": "VERIFICATION.md", "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}],
        }
        (bundle / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
        return repo

    def test_evidence_index_lists_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self._repo_with_bundle(Path(temp))
            result = call_tool("evidence_index", {"repo": str(repo)}, _context(Path(temp) / "home"))
            self.assertEqual(result["authority"], AUTHORITY)
            self.assertEqual(result["bundles"], [{"bundle": "bundle-1", "status": "completed", "route": "verify"}])

    def test_evidence_read_reports_b3_source_and_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self._repo_with_bundle(Path(temp))
            result = call_tool(
                "evidence_read",
                {"repo": str(repo), "bundle": "bundle-1", "path": "VERIFICATION.md"},
                _context(Path(temp) / "home"),
            )
            source = result["sources"][0]
            self.assertEqual(source["hash_provenance"], "computed")
            self.assertEqual(source["target_match"], "match")
            self.assertTrue(source["verified"])
            self.assertEqual(result["content"], "verification transcript\n")
            self.assertEqual(result["authority"], AUTHORITY)

    def test_evidence_read_oversized_never_streamed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = self._repo_with_bundle(Path(temp))
            bundle = repo / ".claude" / "evidence" / "python-control-plane" / "bundle-1"
            (bundle / "big.bin").write_bytes(b"x" * (mcp_server.EVIDENCE_SOURCE_CAP_BYTES + 1))
            result = call_tool(
                "evidence_read",
                {"repo": str(repo), "bundle": "bundle-1", "path": "big.bin"},
                _context(Path(temp) / "home"),
            )
            source = result["sources"][0]
            self.assertEqual(source["target_match"], "not_checked")
            self.assertIsNone(source["source_sha256"])
            self.assertNotIn("content", result)

    def test_evidence_read_outside_bundle_rejected(self) -> None:
        from madclaude.errors import MadClaudeError

        with tempfile.TemporaryDirectory() as temp:
            repo = self._repo_with_bundle(Path(temp))
            with self.assertRaises(MadClaudeError):
                call_tool(
                    "evidence_read",
                    {"repo": str(repo), "bundle": "bundle-1", "path": "../../secret"},
                    _context(Path(temp) / "home"),
                )

    def test_evidence_read_bundle_name_escape_rejected(self) -> None:
        from madclaude.errors import MadClaudeError

        with tempfile.TemporaryDirectory() as temp:
            repo = self._repo_with_bundle(Path(temp))
            for bad in ("..", "../bundle-1", "a/b", "a\\b", "", ".", "bundle-1\0"):
                with self.subTest(bundle=bad):
                    with self.assertRaises(MadClaudeError):
                        call_tool(
                            "evidence_read",
                            {"repo": str(repo), "bundle": bad, "path": "VERIFICATION.md"},
                            _context(Path(temp) / "home"),
                        )

    def test_evidence_read_symlinked_bundle_rejected(self) -> None:
        from madclaude.errors import MadClaudeError

        with tempfile.TemporaryDirectory() as temp:
            repo = self._repo_with_bundle(Path(temp))
            root = repo / ".claude" / "evidence" / "python-control-plane"
            outside = Path(temp) / "outside"
            outside.mkdir()
            (outside / "MANIFEST.json").write_text("{}", encoding="utf-8")
            os.symlink(outside, root / "link-bundle")
            with self.assertRaises(MadClaudeError):
                call_tool(
                    "evidence_read",
                    {"repo": str(repo), "bundle": "link-bundle", "path": "MANIFEST.json"},
                    _context(Path(temp) / "home"),
                )


class RequestVerificationTests(unittest.TestCase):
    def test_dangerous_command_rejected_by_guard(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            with self.assertRaises(PolicyViolation):
                call_tool(
                    "request_verification",
                    {"repo": str(repo), "commands": ["rm -rf /"]},
                    _context(Path(temp) / "home"),
                )

    def test_option_shift_bypasses_rejected_by_guard(self) -> None:
        # R6-01: the MCP tool must deny every parser-bypass shape the strict
        # guard denies — arbitrary python-* executables, interpreter option
        # shifts, and package-manager global-option smuggling.
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            for command in (
                "python-evil run_tests.py",
                "python3 -I evil.py",
                "python3 -u evil.py",
                "python3 -- evil.py",
                "npm --prefix /tmp install",
            ):
                with self.subTest(command=command):
                    with self.assertRaises(PolicyViolation):
                        call_tool(
                            "request_verification",
                            {"repo": str(repo), "commands": [command]},
                            _context(Path(temp) / "home"),
                        )

    def test_request_verification_returns_real_bundle_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()

            class Outcome:
                evidence_path = "/evidence/bundle-xyz"
                status = "completed"
                errors: list = []

            with mock.patch.object(mcp_server, "run_verify", return_value=Outcome()) as runner:
                result = call_tool(
                    "request_verification",
                    {"repo": str(repo), "goal": "Check", "commands": ["python3 --version"]},
                    _context(Path(temp) / "home"),
                )
            self.assertEqual(result["evidenceBundle"], "/evidence/bundle-xyz")
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["authority"], AUTHORITY)
            self.assertEqual(runner.call_args.args[3:], ("Check", ["python3 --version"]))

    def test_commands_must_be_nonempty_string_array(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            for bad in ([], "python3 --version", [42]):
                with self.subTest(commands=bad):
                    with self.assertRaises(PolicyViolation):
                        call_tool("request_verification", {"repo": str(repo), "commands": bad}, _context(Path(temp)))

    def test_request_verification_disabled_without_strict_allowlist(self) -> None:
        # Audit 9 remediation: the tool must refuse to run if the strict
        # executable/subcommand allowlist is ever weakened or removed.
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            with mock.patch.object(mcp_server.guard, "STRICT_VERIFICATION_ALLOWLIST", False):
                with self.assertRaises(PolicyViolation):
                    call_tool(
                        "request_verification",
                        {"repo": str(repo), "commands": ["python3 --version"]},
                        _context(Path(temp) / "home"),
                    )


class LauncherGateTests(unittest.TestCase):
    def test_launcher_self_test_and_disabled_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            launcher = release / "launcher" / "mcp-server"
            env = {**os.environ, "MADCLAUDE_HOME": str(fixture.home)}
            # Disabled state (no current): refuses.
            refused = subprocess.run(
                ["/bin/sh", str(launcher), "--self-test"], capture_output=True, text=True, check=False, env=env,
                stdin=subprocess.DEVNULL,
            )
            self.assertEqual(refused.returncode, 3)
            self.assertIn("disabled", refused.stderr)
            # Enabled: staged self-test passes.
            enable(fixture.home, release)
            accepted = subprocess.run(
                ["/bin/sh", str(launcher), "--self-test"], capture_output=True, text=True, check=False, env=env,
                stdin=subprocess.DEVNULL,
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertIn("self-test ok", accepted.stdout)

    def test_integrity_mismatch_refuses_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            enable(fixture.home, release)
            integrity_path = release / "RELEASE_INTEGRITY.json"
            doc = json.loads(integrity_path.read_text(encoding="utf-8"))
            doc["hashes"]["APP_MANIFEST.json"] = "0" * 64
            integrity_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
            env = {**os.environ, "MADCLAUDE_HOME": str(fixture.home)}
            refused = subprocess.run(
                ["/bin/sh", str(release / "launcher" / "mcp-server"), "--self-test"],
                capture_output=True, text=True, check=False, env=env, stdin=subprocess.DEVNULL,
            )
            self.assertEqual(refused.returncode, 3)
            self.assertIn("refused to start", refused.stderr)


@unittest.skipUnless(MCP_IMPORTABLE, "mcp package exists only inside the release venv on targets")
class SdkBoundProtocolTests(unittest.TestCase):
    def test_mcp_sdk_registration_matches_locked_surface(self) -> None:
        from mcp.server.mcpserver import MCPServer

        self.assertTrue(callable(MCPServer))


if __name__ == "__main__":
    unittest.main()
