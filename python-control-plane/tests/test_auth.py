from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from madclaude.auth import child_environment, enforce_model_billing_policy, preflight_auth
from madclaude.errors import AuthPreflightError
from support import clean_env, fake_claude, make_git_repo


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.repo = make_git_repo(root / "repo")
        self.cli = fake_claude(root / "claude", {
            "status": "ready", "summary": "ok", "repository_findings": [],
            "plan_steps": [{"step": "x", "files": [], "rationale": "x", "acceptance": []}],
            "acceptance_mapping": [], "verification_plan": [], "risks": [],
            "stop_conditions": [], "founder_decisions_required": [], "confidence": "high"
        })
        self.env = clean_env()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_subscription_login_is_accepted_and_api_vars_are_stripped(self) -> None:
        report = preflight_auth(mode="subscription", repo=self.repo, claude_path=str(self.cli), env=self.env)
        self.assertTrue(report.safe)
        self.assertEqual(report.credential_lane, "subscription-saved-login")
        child = child_environment(report, {**self.env, "ANTHROPIC_API_KEY": "should-strip"})
        self.assertNotIn("ANTHROPIC_API_KEY", child)
        self.assertEqual(child["ENABLE_CLAUDEAI_MCP_SERVERS"], "false")


    def test_max_fable_is_allowed_with_plan_specific_warning(self) -> None:
        report = preflight_auth(mode="subscription", repo=self.repo, claude_path=str(self.cli), env=self.env)
        guarded = enforce_model_billing_policy(report, model="fable")
        self.assertTrue(any("included on Max" in item for item in guarded.warnings))

    def test_pro_fable_requires_explicit_usage_credit_acknowledgement(self) -> None:
        pro_cli = fake_claude(
            Path(self.temp.name) / "claude-pro",
            {"status": "ready"},
            auth_status={
                "loggedIn": True,
                "authMethod": "claude.ai",
                "subscriptionType": "pro",
                "apiProvider": "firstParty",
            },
        )
        report = preflight_auth(mode="subscription", repo=self.repo, claude_path=str(pro_cli), env=self.env)
        with self.assertRaisesRegex(AuthPreflightError, "usage credits"):
            enforce_model_billing_policy(report, model="fable")

    def test_pro_fable_can_run_only_after_explicit_acknowledgement(self) -> None:
        pro_cli = fake_claude(
            Path(self.temp.name) / "claude-pro-ack",
            {"status": "ready"},
            auth_status={
                "loggedIn": True,
                "authMethod": "claude.ai",
                "subscriptionType": "pro",
                "apiProvider": "firstParty",
            },
        )
        report = preflight_auth(mode="subscription", repo=self.repo, claude_path=str(pro_cli), env=self.env)
        guarded = enforce_model_billing_policy(report, model="fable", allow_usage_credits=True)
        self.assertTrue(any("explicitly acknowledged" in item for item in guarded.warnings))

    def test_cli_below_minimum_version_fails_closed(self) -> None:
        old_cli = fake_claude(
            Path(self.temp.name) / "claude-old",
            {"status": "ready"},
            version_string="1.2.3 (Claude Code)",
        )
        with self.assertRaisesRegex(AuthPreflightError, "below this package's"):
            preflight_auth(mode="subscription", repo=self.repo, claude_path=str(old_cli), env=self.env)

    def test_unparseable_cli_version_fails_closed(self) -> None:
        opaque_cli = fake_claude(
            Path(self.temp.name) / "claude-opaque",
            {"status": "ready"},
            version_string="not-a-version-string",
        )
        with self.assertRaisesRegex(AuthPreflightError, "not parseable"):
            preflight_auth(mode="subscription", repo=self.repo, claude_path=str(opaque_cli), env=self.env)

    def test_subscription_rejects_generic_oauth_without_subscription_proof(self) -> None:
        ambiguous_cli = fake_claude(
            Path(self.temp.name) / "claude-ambiguous",
            {"status": "ready"},
            auth_status={"loggedIn": True, "authMethod": "oauth", "apiProvider": "firstParty"},
        )
        with self.assertRaises(AuthPreflightError):
            preflight_auth(mode="subscription", repo=self.repo, claude_path=str(ambiguous_cli), env=self.env)

    def test_subscription_oauth_token_is_explicit_proof(self) -> None:
        token_cli = fake_claude(
            Path(self.temp.name) / "claude-token",
            {"status": "ready"},
            auth_status={"loggedIn": True, "authMethod": "oauth", "apiProvider": "firstParty"},
        )
        report = preflight_auth(
            mode="subscription",
            repo=self.repo,
            claude_path=str(token_cli),
            env={**self.env, "CLAUDE_CODE_OAUTH_TOKEN": "not-printed"},
        )
        self.assertEqual(report.credential_lane, "subscription-oauth-token")
        self.assertNotIn("not-printed", str(report.public_dict()))

    def test_auth_report_masks_account_identifiers(self) -> None:
        report = preflight_auth(mode="subscription", repo=self.repo, claude_path=str(self.cli), env=self.env)
        public = report.public_dict()
        self.assertNotIn("mike.daley@example.com", str(public))
        self.assertNotIn("MAD Ventures Holdings", str(public))
        self.assertIn("mi***@example.com", str(public))

    def test_subscription_rejects_every_higher_precedence_lane(self) -> None:
        for name, value in (
            ("ANTHROPIC_API_KEY", "not-printed"),
            ("ANTHROPIC_AUTH_TOKEN", "not-printed"),
            ("ANTHROPIC_BASE_URL", "https://example.invalid"),
            ("ANTHROPIC_CUSTOM_HEADERS", "x-api-key:not-printed"),
            ("CLAUDE_CODE_USE_BEDROCK", "1"),
            ("CLAUDE_CODE_USE_VERTEX", "1"),
            ("CLAUDE_CODE_USE_FOUNDRY", "1"),
            ("CLAUDE_CODE_USE_ANTHROPIC_AWS", "1"),
        ):
            with self.subTest(name=name), self.assertRaises(AuthPreflightError):
                preflight_auth(
                    mode="subscription", repo=self.repo, claude_path=str(self.cli),
                    env={**self.env, name: value},
                )

    def test_subscription_rejects_api_key_helper_without_reading_value(self) -> None:
        settings = self.repo / ".claude" / "settings.local.json"
        settings.parent.mkdir(exist_ok=True)
        settings.write_text(json.dumps({"apiKeyHelper": "/bin/echo"}), encoding="utf-8")
        with self.assertRaises(AuthPreflightError):
            preflight_auth(mode="subscription", repo=self.repo, claude_path=str(self.cli), env=self.env)

    def test_api_mode_requires_mode_gate_and_positive_budget(self) -> None:
        api_env = {**self.env, "ANTHROPIC_API_KEY": "not-printed"}
        with self.assertRaises(AuthPreflightError):
            preflight_auth(mode="api", repo=self.repo, claude_path=str(self.cli), env=api_env)
        with self.assertRaises(AuthPreflightError):
            preflight_auth(
                mode="api", repo=self.repo, claude_path=str(self.cli), allow_api_billing=True,
                env=api_env,
            )
        report = preflight_auth(
            mode="api", repo=self.repo, claude_path=str(self.cli), allow_api_billing=True,
            max_budget_usd=2.5, env=api_env,
        )
        self.assertEqual(report.credential_lane, "anthropic-api-key-explicit")
        self.assertNotIn("not-printed", str(report.public_dict()))

    def test_api_mode_rejects_ambiguous_route(self) -> None:
        with self.assertRaises(AuthPreflightError):
            preflight_auth(
                mode="api", repo=self.repo, claude_path=str(self.cli), allow_api_billing=True,
                max_budget_usd=1.0,
                env={**self.env, "ANTHROPIC_API_KEY": "x", "ANTHROPIC_BASE_URL": "https://example.invalid"},
            )


    def test_subscription_rejects_credential_in_settings_env_block(self) -> None:
        settings = self.repo / ".claude" / "settings.json"
        settings.parent.mkdir(exist_ok=True)
        settings.write_text(json.dumps({"env": {"ANTHROPIC_API_KEY": "not-printed"}}), encoding="utf-8")
        with self.assertRaises(AuthPreflightError):
            preflight_auth(mode="subscription", repo=self.repo, claude_path=str(self.cli), env=self.env)

    def test_api_mode_rejects_ambiguous_auth_status(self) -> None:
        ambiguous_cli = fake_claude(
            Path(self.temp.name) / "claude-api-ambiguous",
            {"status": "ready"},
            auth_status={
                "loggedIn": True,
                "authMethod": "claude.ai",
                "subscriptionType": "max",
                "apiProvider": "firstParty",
            },
        )
        with self.assertRaises(AuthPreflightError):
            preflight_auth(
                mode="api",
                repo=self.repo,
                claude_path=str(ambiguous_cli),
                allow_api_billing=True,
                max_budget_usd=1.0,
                env={**self.env, "ANTHROPIC_API_KEY": "not-printed"},
            )

    def test_api_mode_rejects_oauth_and_bearer_alternates(self) -> None:
        for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN"):
            with self.subTest(name=name), self.assertRaises(AuthPreflightError):
                preflight_auth(
                    mode="api",
                    repo=self.repo,
                    claude_path=str(self.cli),
                    allow_api_billing=True,
                    max_budget_usd=1.0,
                    env={**self.env, "ANTHROPIC_API_KEY": "x", name: "alternate"},
                )



if __name__ == "__main__":
    unittest.main()
