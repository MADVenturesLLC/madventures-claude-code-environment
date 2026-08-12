"""A10-A: canonical secret-pattern registry integrity tests.

DEC-20260812-01 A10-A acceptance criteria covered here:
  - single authoritative registry exists; a test asserts no divergent
    second copy of primitives (identity assertion: the consumers MUST be
    the very tuples exported by secrets_patterns, not copies);
  - both consumers cover all audit-confirmed shapes via their own forms;
  - a benign-string corpus survives redaction unscrubbed (anchored
    boundaries, no over-scrub).
"""

from __future__ import annotations

import re
import unittest

from madclaude import evidence, guard, secrets_patterns
from madclaude.evidence import redact
from madclaude.guard import contains_sensitive_material


class RegistryIntegrityTests(unittest.TestCase):
    def test_registry_primitive_names_are_unique(self) -> None:
        names = [p.name for p in secrets_patterns.REGISTRY]
        self.assertEqual(len(names), len(set(names)), f"duplicate primitive names: {names}")

    def test_registry_is_nonempty_and_covers_audit_shapes(self) -> None:
        # Audit-confirmed shapes from DEC-20260812-01 A10-A scope item 2.
        names = {p.name for p in secrets_patterns.REGISTRY}
        for expected in (
            "sk_ant",
            "sk_proj",
            "github_token",
            "aws_access_key",
            "claude_env_assign",
            "bearer",
            "pem_private_key",
            "url_userinfo",
        ):
            self.assertIn(expected, names, f"registry missing audit shape {expected}")

    def test_detection_consumer_is_the_registry_tuple(self) -> None:
        # No divergent second copy: guard must consume the exported tuple by
        # identity, never a recompiled or copied pattern set.
        self.assertIs(guard.SECRET_CONTENT_PATTERNS, secrets_patterns.DETECTION_PATTERNS)

    def test_redaction_consumer_is_the_registry_tuple(self) -> None:
        self.assertIs(evidence.SECRET_VALUES, secrets_patterns.REDACTION_PATTERNS)

    def test_no_stray_hardcoded_secret_literals_in_consumers(self) -> None:
        # Guard against a future edit re-adding a divergent literal pattern
        # beside the registry import. Scan the two consumer files for the
        # audit shape tokens; they may appear only in comments or in the
        # registry import line.
        import inspect

        for module in (guard, evidence):
            source = inspect.getsource(module)
            for token in ("sk-ant-", "sk-proj-", "AKIA", "ghp_", "PRIVATE KEY-----"):
                # A divergent compiled literal would appear as a string in
                # an re.compile(...) call. Tokens in comments and the
                # secrets_patterns import are allowed; compiled literals are
                # not.
                compiled_literals = re.findall(r're\.compile\(\s*[rf]?"[^"]*' + re.escape(token), source)
                self.assertEqual(
                    compiled_literals,
                    [],
                    f"{module.__name__} contains a divergent hardcoded pattern for {token!r}",
                )


class DetectionCorpusTests(unittest.TestCase):
    """Detection is recall-optimized: every audit shape must be flagged."""

    SHAPES = (
        # GitHub
        "token is ghp_0123456789012345678901234567890123456789 end",
        "oauth gho_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij end",
        "user ghu_abcdefghijklmnopqrstuvwxyzABCDEFGHIJ end",
        "server ghs_0123456789abcdef0123456789abcdef01 end",
        "refresh ghr_0123456789abcdef0123456789abcdef01 end",
        # AWS
        "aws AKIAIOSFODNN7EXAMPLE present",
        # OpenAI
        "key sk-proj-abcdefghijklmnopqrstuvwxyz",
        # Anthropic (existing coverage)
        "anthropic sk-ant-api03-abcdefghijklmnopqrstuvwxyz",
        # env assigns
        "ANTHROPIC_API_KEY=sk-ant-api03-secretvalue",
        "export CLAUDE_CODE_OAUTH_TOKEN: abcdef",
        # Bearer
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
        # PEM header
        "-----BEGIN RSA PRIVATE KEY-----",
        "-----BEGIN EC PRIVATE KEY-----",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        # URL userinfo
        "https://user:pass123@example.com/path",
    )

    def test_all_audit_shapes_detected(self) -> None:
        for text in self.SHAPES:
            with self.subTest(text=text[:40]):
                self.assertTrue(contains_sensitive_material(text), f"detector missed: {text[:60]}")

    def test_benign_text_not_detected(self) -> None:
        benign = (
            "the quick brown fox",
            "sk-ant is not a key by itself",
            "AKIA alone is not an AWS key",
            "ghp_ prefix with nothing after",
            "https://example.com/path?q=1",
            "the bearer scheme is documented in the handbook",
            "my password manager is Bitwarden",
            "BEGIN section of the report",
        )
        for text in benign:
            with self.subTest(text=text[:40]):
                self.assertFalse(contains_sensitive_material(text), f"detector false-positive: {text}")


class RedactionCorpusTests(unittest.TestCase):
    """Redaction is replacement-safe: audit shapes become [REDACTED];
    benign text survives byte-for-byte."""

    def test_all_audit_shapes_redacted(self) -> None:
        cases = (
            ("token ghp_0123456789012345678901234567890123456789 end", "ghp_0123456789012345678901234567890123456789", "ghp_0123456789012345678901234567890123456789"),
            ("aws AKIAIOSFODNN7EXAMPLE here", "AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7EXAMPLE"),
            ("key sk-proj-abcdefghijklmnopqrstuvwxyz", "sk-proj-abcdefghijklmnopqrstuvwxyz", "sk-proj-abcdefghijklmnopqrstuvwxyz"),
            ("anthropic sk-ant-api03-abcdefghijklmnopqrstuvwxyz", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz"),
            ("ANTHROPIC_API_KEY=sk-ant-api03-secretvalue", "sk-ant-api03-secretvalue", "sk-ant-api03-secretvalue"),
            ("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig", "eyJhbGciOiJIUzI1NiJ9.payload.sig", "eyJhbGciOiJIUzI1NiJ9.payload.sig"),
        )
        for original, secret, _ in cases:
            with self.subTest(secret=secret[:24]):
                result = redact(original)
                self.assertNotIn(secret, result)
                self.assertIn("[REDACTED]", result)

    def test_pem_block_fully_scrubbed(self) -> None:
        block = (
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEAxL4m\n"
            "-----END RSA PRIVATE KEY-----"
        )
        result = redact(f"key below:\n{block}\nend")
        self.assertNotIn("MIIEpAIBAAKCAQEAxL4m", result)
        self.assertNotIn("BEGIN RSA", result)
        self.assertIn("[REDACTED]", result)

    def test_url_userinfo_keeps_url_readable(self) -> None:
        result = redact("db = postgres://alice:s3cr3t@db.example.com:5432/app")
        self.assertNotIn("alice:s3cr3t", result)
        self.assertIn("postgres://[REDACTED]@db.example.com:5432/app", result)

    def test_benign_strings_survive_redaction(self) -> None:
        benign = (
            "the quick brown fox jumps over the lazy dog",
            "sk-ant by itself is not a key",
            "AKIA is not an AWS key by itself",
            "ghp_ with nothing after is fine",
            "https://example.com/path?tab=repositories",
            "the bearer scheme is documented in docs/auth.md",
            "password manager rotation policy",
            "BEGIN:VCALENDAR\\nVERSION:2.0\\nEND:VCALENDAR",
            "user:pass@example.com in prose (no scheme)",
            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ test@host",
        )
        for text in benign:
            with self.subTest(text=text[:40]):
                self.assertEqual(redact(text), text, f"over-scrub: {text[:60]}")

    def test_dict_and_nested_values_redacted(self) -> None:
        payload = {
            "ok": True,
            "headers": {"Authorization": "Bearer abc.def.ghi"},
            "endpoint": "https://user:pass@host/x",
            "note": "see sk-proj-abcdefgh",
        }
        result = redact(payload)
        self.assertNotIn("abc.def.ghi", str(result))
        self.assertNotIn("user:pass", str(result))
        self.assertNotIn("sk-proj-abcdefgh", str(result))
        self.assertEqual(result["ok"], True)


if __name__ == "__main__":
    unittest.main()
