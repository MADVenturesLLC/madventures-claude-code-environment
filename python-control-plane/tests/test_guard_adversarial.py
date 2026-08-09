"""A9-01: bounded adversarial regression corpus for guard behavior.

Fixed enumerated corpus (no fuzzing). Every negative case asserts denial or a
typed PolicyViolation; every positive case asserts the allow path still works.
The Audit 9 remediation resolved the five suspected guard gaps; they live in
ResolvedGuardGaps at the bottom as ordinary passing regression tests.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from madclaude.errors import PolicyViolation
from madclaude.guard import (
    evaluate_tool_call,
    is_sensitive_path,
    normalize_scope,
    validate_verification_command,
    within_scopes,
)
from madclaude.hook_cli import evaluate_input

ALL_TOOLS = ("Read", "Edit", "Write", "NotebookEdit", "MultiEdit", "Grep", "Glob", "Agent")


class CorpusBase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.repo = Path(self._temp.name).resolve()

    def tearDown(self) -> None:
        self._temp.cleanup()

    def call(self, tool, tool_input=None, *, allowed=ALL_TOOLS, mutates=True, scopes=("src",), subs=("Explore",)):
        return evaluate_tool_call(
            repo=self.repo,
            tool_name=tool,
            tool_input=tool_input or {},
            allowed_tools=allowed,
            mutates=mutates,
            scopes=scopes,
            allowed_subagents=subs,
        )

    def assertDenied(self, tool, tool_input=None, **kwargs) -> None:
        allowed, reason = self.call(tool, tool_input, **kwargs)
        self.assertFalse(allowed, f"expected denial, got allowed: {reason}")

    def assertAllowed(self, tool, tool_input=None, **kwargs) -> None:
        allowed, reason = self.call(tool, tool_input, **kwargs)
        self.assertTrue(allowed, f"expected allow, got denied: {reason}")

    def assertCommandDenied(self, command: str) -> None:
        with self.assertRaises(PolicyViolation, msg=f"expected denial: {command!r}"):
            validate_verification_command(command)

    def assertCommandAllowed(self, command: str) -> None:
        argv = validate_verification_command(command)
        self.assertTrue(argv and argv[0], f"expected allow: {command!r}")


class TraversalCorpus(CorpusBase):
    DENIED_PATHS = (
        "../outside.txt",
        "src/../../outside.txt",
        "src/../../../etc/passwd",
        "..",
        "/etc/passwd",
        "/tmp",
        "~/secrets.txt",
        "~",
        "src/../../repo2/x",
        "a/../../../b",
    )

    def test_traversal_denied_for_read_and_write(self) -> None:
        for path in self.DENIED_PATHS:
            with self.subTest(path=path):
                self.assertDenied("Read", {"file_path": path})
                self.assertDenied("Write", {"file_path": path})
                self.assertDenied("NotebookEdit", {"notebook_path": path})
                self.assertDenied("MultiEdit", {"edits": [{"file_path": path, "old_string": "a", "new_string": "b"}]})

    def test_dot_chains_inside_repo_allowed(self) -> None:
        for path in ("./src/a.py", "src/./a.py", "src/sub/../a.py"):
            with self.subTest(path=path):
                self.assertAllowed("Read", {"file_path": path})

    def test_backslash_is_posix_filename_not_separator(self) -> None:
        # On POSIX a backslash is a legal filename character; the path stays
        # lexically inside the repo, so current behavior is allow.
        self.assertAllowed("Read", {"file_path": "src\\..\\..\\etc"})

    def test_absolute_repo_internal_path_allowed(self) -> None:
        self.assertAllowed("Read", {"file_path": str(self.repo / "src" / "a.py")})


class ScopeEscapeCorpus(CorpusBase):
    def test_scope_boundary_cases(self) -> None:
        denied = ("src2/x.py", "src/../secret/x.py", "secret", "srcx", "SRC/x.py", "src/../../src/x.py")
        for path in denied:
            with self.subTest(path=path):
                self.assertDenied("Write", {"file_path": path}, scopes=("src",))
        allowed = ("src", "src/x.py", "src/deep/nested/file.py")
        for path in allowed:
            with self.subTest(path=path):
                self.assertAllowed("Write", {"file_path": path}, scopes=("src",))

    def test_within_scopes_semantics(self) -> None:
        cases = [
            ("src", ("src",), True),
            ("src/x", ("src",), True),
            ("src2/x", ("src",), False),
            ("src", ("src/sub",), False),
            ("src/sub/x", ("src/sub",), True),
            ("a/b", ("",), True),  # empty scope means repository root
        ]
        for path, scopes, expected in cases:
            with self.subTest(path=path, scopes=scopes):
                self.assertEqual(within_scopes(path, scopes), expected)

    def test_normalize_scope_rejects_escape(self) -> None:
        for scope in ("../x", "/abs", "a/../../b", ".."):
            with self.subTest(scope=scope):
                with self.assertRaises(PolicyViolation):
                    normalize_scope(scope)
        self.assertEqual(normalize_scope("a/./b"), "a/b")
        self.assertEqual(normalize_scope("src\\auth"), "src/auth")
        self.assertEqual(normalize_scope(""), "")
        self.assertEqual(normalize_scope("."), "")


class SensitivePathCorpus(CorpusBase):
    SENSITIVE = (
        ".env",
        ".env.prod",
        ".env.local",
        ".ENV",
        "sub/.env",
        "sub/.env.staging",
        "id_rsa",
        "id_ed25519.pub",
        "sub/id_ecdsa",
        "server.pem",
        "store.p12",
        "cert.pfx",
        "app.key",
        "keys.keystore",
        "trust.jks",
        "vault.kdbx",
        ".npmrc",
        ".netrc",
        ".pypirc",
        ".aws/credentials",
        ".config/gcloud/application_default_credentials.json",
        "credentials.json",
        "nested/credentials.json",
        "service-account.json",
        "service_account.prod.json",
        "secrets.json",
        "secrets.yaml",
        "secrets.toml",
        "sub/dir/secrets.yml",
    )

    def test_sensitive_paths_classified(self) -> None:
        for path in self.SENSITIVE:
            with self.subTest(path=path):
                self.assertTrue(is_sensitive_path(path), path)

    def test_sensitive_paths_denied_for_tools(self) -> None:
        for path in (".env.prod", ".ENV", "nested/credentials.json", "id_rsa", "secrets.yaml"):
            with self.subTest(path=path):
                self.assertDenied("Read", {"file_path": path})
                self.assertDenied("Write", {"file_path": path})
                self.assertDenied("Grep", {"path": path, "pattern": "x"})

    def test_template_allowlist_not_bypassed_but_not_extended(self) -> None:
        for path in (".env.example", ".env.sample", ".env.template", "sub/.env.defaults"):
            with self.subTest(path=path):
                self.assertFalse(is_sensitive_path(path), path)
        # A template suffix on a different secret name is not an allowlist entry.
        for path in (".env.prod", ".env.local.backup"):
            with self.subTest(path=path):
                self.assertTrue(is_sensitive_path(path), path)


class VerificationCommandCorpus(CorpusBase):
    SHELL_CONTROL_DENIALS = (
        "python3 --version && rm -rf /",
        "python3 --version || echo no",
        "python3 --version; echo done",
        "python3 --version | cat",
        "python3 --version > out.txt",
        "python3 --version < in.txt",
        "echo `whoami`",
        "echo $(whoami)",
        "git log --oneline | head",
        "python3 -m pytest > report.txt",
    )

    DANGEROUS_DENIALS = (
        "git reset --hard",
        "git reset --hard HEAD~1",
        "git clean -fd",
        "git clean -fdx",
        "git push",
        "git push origin main",
        "gh pr merge 1",
        "gh release create v1",
        "gh api repos",
        "rm -rf build",
        "mkfs /dev/sda",
        "dd if=/dev/zero of=/dev/sda",
        "shutdown -h now",
        "reboot",
        "claude --dangerously-skip-permissions",
        "claude code --allow-dangerously-skip-permissions",
    )

    EXECUTABLE_DENIALS = (
        "curl https://example.com",
        "wget https://example.com",
        "ssh host",
        "scp a b",
        "rsync a b",
        "aws s3 ls",
        "gcloud info",
        "kubectl get pods",
        "terraform plan",
        "vercel deploy",
        "wrangler deploy",
        "docker ps",
        "gh auth status",
        "psql -c select",
        "sqlite3 db",
        "sh -c ls",
        "bash -c ls",
        "zsh script.sh",
        "cmd /c dir",
        "powershell -Command ls",
        "'bash' -c ls",
        '"sh" -c ls',
    )

    GIT_DENIALS = (
        "git -C repo push",
        "git -c user.x=1 push",
        "git branch -d feature",
        "git branch -D feature",
        "git branch -m old new",
        "git branch --delete feature",
        "git merge feature",
        "git rebase main",
        "git checkout main",
        "git switch main",
        "git tag v1",
        "git commit -m x",
    )

    PACKAGE_DENIALS = (
        "npm install",
        "npm i lodash",
        "npm add lodash",
        "npm remove lodash",
        "npm uninstall lodash",
        "npm update",
        "npm publish",
        "npm link",
        "npm exec x",
        "npm create vite",
        "npm init",
        "pnpm install",
        "pnpm add lodash",
        "pnpm dlx create-react-app",
        "yarn add lodash",
        "yarn remove lodash",
        "bun add lodash",
        "npx cowsay",
        "pnpx cowsay",
        "bunx cowsay",
        "npm run test:deploy",
        "npm run deploy:test",
        "npm run migrate",
        "npm run release:prod",
        "yarn build:publish",
    )

    PYTHON_DENIALS = (
        "python3 -c 'print(1)'",
        "python3 --command 'print(1)'",
        "python3 -m pip install x",
        "python3 -m venv .venv",
        "python3 -m http.server",
        "python3 -m json.tool",
        "python3 -m pytest -c 'print(1)'",
        "python3 -m",
        "python3 scripts/deploy.py",
        "python3 manage.py migrate",
        "python3 -m pytest --ignore=x -c y",
        "py -c 'print(1)'",
    )

    NODE_DENIALS = (
        "node script.js",
        "node -e 'console.log(1)'",
        "node --eval 'console.log(1)'",
        "node",
    )

    def test_shell_control_denied(self) -> None:
        for command in self.SHELL_CONTROL_DENIALS:
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_dangerous_denied(self) -> None:
        for command in self.DANGEROUS_DENIALS:
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_executable_denied(self) -> None:
        for command in self.EXECUTABLE_DENIALS:
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_git_mutation_denied(self) -> None:
        for command in self.GIT_DENIALS:
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_package_mutation_denied(self) -> None:
        for command in self.PACKAGE_DENIALS:
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_python_evasion_denied(self) -> None:
        for command in self.PYTHON_DENIALS:
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_node_evasion_denied(self) -> None:
        for command in self.NODE_DENIALS:
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_quoting_and_empty_denied(self) -> None:
        for command in ("", "   ", "python3 --version '", "python3 --version \""):
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_representative_allowed_commands(self) -> None:
        for command in (
            "python3 --version",
            "python3 -m pytest",
            "python3 -m unittest discover",
            "python3 -m mypy src",
            "python3 run_tests.py",
            "python3 scripts/verify_release.py",
            "python3 -m ruff check",
            "git status --short",
            "git diff HEAD",
            "git log --oneline",
            "git show HEAD",
            "git branch",
            "git rev-parse HEAD",
        ):
            with self.subTest(command=command):
                self.assertCommandAllowed(command)

    @unittest.skipUnless(shutil.which("npm"), "npm not on PATH")
    def test_npm_readonly_script_allowed(self) -> None:
        self.assertCommandAllowed("npm run test")
        self.assertCommandAllowed("npm test")

    @unittest.skipUnless(shutil.which("node"), "node not on PATH")
    def test_node_check_allowed(self) -> None:
        self.assertCommandAllowed("node --check script.js")

    def test_newline_is_argv_whitespace_not_shell(self) -> None:
        # List-argv execution has no shell, so a newline is token whitespace.
        self.assertCommandAllowed("python3 --version\n--help")


class McpAndSubagentCorpus(CorpusBase):
    def test_mcp_prefix_denied(self) -> None:
        for name in ("mcp__github__create_issue", "mcp__figma__get_file", "mcp__x"):
            with self.subTest(tool=name):
                allowed, reason = self.call(name, {}, allowed=ALL_TOOLS + (name,))
                self.assertFalse(allowed)
                self.assertIn("MCP tools are disabled", reason)

    def test_mcp_uppercase_caught_by_prefix(self) -> None:
        # The mcp__ denial is case-insensitive and fires before the allowlist.
        allowed, reason = self.call("MCP__github__x", {})
        self.assertFalse(allowed)
        self.assertIn("MCP tools are disabled", reason)

    def test_unlisted_tool_denied(self) -> None:
        self.assertDenied("Read", {"file_path": "src/a.py"}, allowed=("Grep",))
        self.assertDenied("Bash", {"command": "ls"})
        self.assertDenied("WebFetch", {"url": "https://example.com"})
        self.assertDenied("WebSearch", {"query": "x"})

    def test_subagent_spoofing_denied(self) -> None:
        denied_inputs = (
            {},
            {"subagent_type": ""},
            {"subagent_type": "Evil"},
            {"agent_type": "Evil"},
            {"name": "Evil"},
            {"subagent_type": "explore"},
        )
        for tool_input in denied_inputs:
            with self.subTest(tool_input=tool_input):
                self.assertDenied("Agent", tool_input)

    def test_subagent_name_is_stripped_before_match(self) -> None:
        # The guard strips surrounding whitespace before matching.
        self.assertAllowed("Agent", {"subagent_type": " Explore "})

    def test_subagent_alias_and_approval(self) -> None:
        self.assertAllowed("Agent", {"subagent_type": "Explore"})
        self.assertAllowed("Task", {"subagent_type": "Explore"})  # alias of Agent
        self.assertDenied("Agent", {"subagent_type": "Explore"}, subs=())

    def test_readonly_route_blocks_mutation(self) -> None:
        for tool, tool_input in (
            ("Edit", {"file_path": "src/a.py"}),
            ("Write", {"file_path": "src/a.py"}),
            ("NotebookEdit", {"notebook_path": "src/a.ipynb"}),
            ("MultiEdit", {"edits": [{"file_path": "src/a.py", "old_string": "a", "new_string": "b"}]}),
        ):
            with self.subTest(tool=tool):
                self.assertDenied(tool, tool_input, mutates=False)
        self.assertAllowed("Read", {"file_path": "src/a.py"}, mutates=False)

    def test_authority_paths_denied_for_mutation(self) -> None:
        for path in (
            ".claude/settings.json",
            ".claude/rules/x.md",
            ".claude/hooks/hook.py",
            ".claude/evidence/x/MANIFEST.json",
            ".git/config",
            "CLAUDE.md",
            "01-constitution/charter.md",
            "evidence/bundle.json",
        ):
            with self.subTest(path=path):
                self.assertDenied("Write", {"file_path": path}, scopes=(".",))
                self.assertDenied("MultiEdit", {"edits": [{"file_path": path, "old_string": "a", "new_string": "b"}]}, scopes=(".",))

    def test_glob_secret_targeting_denied(self) -> None:
        for pattern in ("**/*.env*", "*.pem", "**/id_rsa", "**/credentials*", "secret*"):
            with self.subTest(pattern=pattern):
                self.assertDenied("Glob", {"pattern": pattern})
        self.assertAllowed("Glob", {"pattern": "src/**/*.py"})


class HookCliCorpus(CorpusBase):
    ENV = {
        "MADCLAUDE_CONTROL_PLANE_ACTIVE": "1",
        "MADCLAUDE_MUTATES": "1",
        "MADCLAUDE_ALLOWED_SUBAGENTS_JSON": json.dumps(["Explore"]),
        "MADCLAUDE_ALLOWED_TOOLS_JSON": json.dumps(list(ALL_TOOLS)),
        "MADCLAUDE_ALLOWED_SCOPES_JSON": json.dumps(["src"]),
    }

    def _env(self) -> dict[str, str]:
        return {**self.ENV, "MADCLAUDE_REPO_ROOT": str(self.repo)}

    def _denied(self, payload: dict) -> bool:
        with mock.patch.dict(os.environ, self._env(), clear=False):
            result = evaluate_input(payload)
        decision = result.get("hookSpecificOutput", {}).get("permissionDecision")
        return decision == "deny"

    def test_inactive_control_plane_ignores_payload(self) -> None:
        with mock.patch.dict(os.environ, {"MADCLAUDE_CONTROL_PLANE_ACTIVE": "0"}, clear=False):
            self.assertEqual(evaluate_input({"tool_name": "Bash"}), {})

    def test_missing_repo_root_denied(self) -> None:
        env = {k: v for k, v in self._env().items() if k != "MADCLAUDE_REPO_ROOT"}
        with mock.patch.dict(os.environ, env, clear=False):
            result = evaluate_input({"tool_name": "Read", "tool_input": {"file_path": "src/a.py"}})
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_subagent_spoofing_denied_at_hook(self) -> None:
        payloads = (
            {"agent_id": "agent-1", "agent_type": "Evil", "tool_name": "Read", "tool_input": {"file_path": "src/a.py"}},
            {"agent_id": "agent-1", "tool_name": "Read", "tool_input": {"file_path": "src/a.py"}},
            {"agent_id": "agent-1", "agent_type": "Explore", "tool_name": "Agent", "tool_input": {"subagent_type": "Explore"}},
            {"agent_id": "agent-1", "agent_type": "Explore", "tool_name": "Task", "tool_input": {"subagent_type": "Explore"}},
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assertTrue(self._denied(payload))

    def test_malformed_policy_env_fails_closed(self) -> None:
        env = {**self._env(), "MADCLAUDE_ALLOWED_TOOLS_JSON": "not-json"}
        with mock.patch.dict(os.environ, env, clear=False):
            result = evaluate_input({"tool_name": "Read", "tool_input": {"file_path": "src/a.py"}})
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_approved_main_agent_read_allowed(self) -> None:
        with mock.patch.dict(os.environ, self._env(), clear=False):
            result = evaluate_input({"tool_name": "Read", "tool_input": {"file_path": "src/a.py"}})
        self.assertEqual(result, {})

    def test_hook_denies_sensitive_and_mcp(self) -> None:
        self.assertTrue(self._denied({"tool_name": "Read", "tool_input": {"file_path": ".env"}}))
        self.assertTrue(self._denied({"tool_name": "mcp__github__x", "tool_input": {}}))


class ResolvedGuardGaps(CorpusBase):
    """Former suspected gaps, resolved by the Audit 9 remediation guard fixes
    (strict executable allowlist, substring risky-script matching,
    case-insensitive mcp__ denial, NUL rejection). These are ordinary passing
    regression tests; a regression here fails the suite."""

    def test_launcher_prefixed_shell_evasion(self) -> None:
        # env/nice/xargs/time prefixes are outside the strict executable
        # allowlist, so they cannot smuggle a shell interpreter through.
        for command in ("env bash", "nice bash", "xargs bash", "time bash"):
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_deploy_substring_script_name(self) -> None:
        # Risky-script matching is substring-based, so "deployment" is caught.
        self.assertCommandDenied("npm run deployment")

    def test_mcp_uppercase_allowlisted_bypasses_prefix(self) -> None:
        # The mcp__ denial is case-insensitive and precedes the allowlist.
        allowed, reason = self.call("MCP__github__x", {}, allowed=ALL_TOOLS + ("MCP__github__x",))
        self.assertFalse(allowed)
        self.assertIn("MCP tools are disabled", reason)

    def test_rm_flag_order_variants(self) -> None:
        # rm is outside the strict executable allowlist in any flag order.
        for command in ("rm -fr build", "rm -r build", "rm -f -r build", "rm -r --force build"):
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_unallowlisted_executables_denied(self) -> None:
        # The strict allowlist denies arbitrary executables outright.
        for command in ("make test", "cargo test", "go test ./...", "pytest", "ruff check", "./run.sh"):
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_python_prefix_executables_denied(self) -> None:
        # R6-01: only the exact documented CPython launcher names are allowed;
        # a python-* prefix is never sufficient.
        for command in (
            "python-evil run_tests.py",
            "python3-evil -m pytest",
            "python2 run_tests.py",
            "python3x run_tests.py",
            "python3. run_tests.py",
            "python3.14.2 run_tests.py",
        ):
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_python_interpreter_option_shift_denied(self) -> None:
        # R6-01: interpreter options that can shift or obscure the actual
        # execution target are denied, whatever follows them.
        for command in (
            "python3 -I evil.py",
            "python3 -u evil.py",
            "python3 -- evil.py",
            "python3 -O run_tests.py",
            "python3 -E run_tests.py",
            "python3 -S run_tests.py",
            "python3 -W ignore run_tests.py",
            "python3 -X dev run_tests.py",
            "python3 -I -m pytest",
            "python3 -i run_tests.py",
            "python3 --version run_tests.py",
            "python3",
        ):
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_python_exact_launcher_names_allowed(self) -> None:
        # R6-01: the exact documented launcher grammar still admits the
        # legitimate supported forms.
        self.assertCommandAllowed("python3 --version")
        self.assertCommandAllowed("python3 -m pytest")
        for name in ("python", "python3", "python3.14"):
            if shutil.which(name):
                with self.subTest(command=name):
                    self.assertCommandAllowed(f"{name} --version")

    def test_package_manager_global_option_bypass_denied(self) -> None:
        # R6-01: global options are rejected outright; a mutation subcommand
        # can never hide behind flags.
        for command in (
            "npm --prefix /tmp install",
            "npm --prefix=/tmp install",
            "npm -g install lodash",
            "npm --silent install",
            "pnpm --dir /tmp add lodash",
            "pnpm -C /tmp install",
            "yarn --cwd /tmp add lodash",
            "bun --cwd /tmp install",
            "npm --version",
        ):
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_nul_byte_clean_denial(self) -> None:
        # A NUL in file_path is a clean (False, reason) denial.
        allowed, _ = self.call("Read", {"file_path": "src/a\0b.txt"})
        self.assertFalse(allowed)

    def test_package_manager_unknown_subcommand_denied(self) -> None:
        # P0: a positive grammar must reject unrecognized subcommands, not
        # just the ones in a blacklist.  These all pass the current blacklist
        # because they aren't in PACKAGE_MUTATIONS and don't match
        # RISKY_SCRIPT_WORDS.
        for command in (
            "npm config set registry https://evil.example.com",
            "npm set foo bar",
            "npm cache clean --force",
            "npm rebuild",
            "npm rebuild lodash",
            "npm init -y",
            "npm publish",
            "npm dist-tag add pkg@1.0 latest",
            "pnpm config set registry https://evil.example.com",
            "pnpm store prune",
            "pnpm rebuild",
            "yarn config set registry https://evil.example.com",
            "yarn cache clean",
            "yarn create electron-app",
            "bun pm cache rm",
            "bun pm ls",
            "bun init",
            "bun publish",
            # Any unrecognized subcommand shape must be denied
            "npm foobar",
            "pnpm whatever",
            "yarn frobnicate",
            "bun nonsense",
        ):
            with self.subTest(command=command):
                self.assertCommandDenied(command)

    def test_package_manager_positive_grammar_allows_only_known_forms(self) -> None:
        # The exact approved forms that must survive.
        npm_forms = (
            "npm run test",
            "npm run lint",
            "npm test",
            "npm run check",
            "npm run verify",
            "npm run audit",
        )
        pnpm_forms = (
            "pnpm run test",
            "pnpm test",
        )
        yarn_forms = (
            "yarn run test",
            "yarn test",
        )
        bun_forms = (
            "bun run test",
            "bun test",
        )
        for command, needed in (
            *((c, "npm") for c in npm_forms),
            *((c, "pnpm") for c in pnpm_forms),
            *((c, "yarn") for c in yarn_forms),
            *((c, "bun") for c in bun_forms),
        ):
            with self.subTest(command=command):
                if not shutil.which(needed):
                    self.skipTest(f"{needed} not on PATH")
                self.assertCommandAllowed(command)


if __name__ == "__main__":
    unittest.main()
