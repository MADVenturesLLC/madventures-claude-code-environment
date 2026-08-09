from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

from .errors import AuthPreflightError

API_ENV_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
SUBSCRIPTION_ENV_VARS = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_REFRESH_TOKEN",
    "CLAUDE_CODE_OAUTH_SCOPES",
)
CLOUD_ROUTE_ENV_VARS = (
    "CLAUDE_CODE_USE_BEDROCK",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_USE_FOUNDRY",
    "CLAUDE_CODE_USE_ANTHROPIC_AWS",
)
ROUTING_ENV_VARS = (
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_BEDROCK_BASE_URL",
    "ANTHROPIC_VERTEX_BASE_URL",
    "ANTHROPIC_FOUNDRY_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
)
SUBSCRIPTION_TYPES = {"pro", "max", "team", "enterprise"}


@dataclass(frozen=True)
class AuthReport:
    requested_mode: str
    safe: bool
    claude_path: str
    credential_lane: str
    logged_in: bool
    subscription_type: str | None = None
    auth_method: str | None = None
    api_provider: str | None = None
    account_hint: str | None = None
    conflicts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    status: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = redact_auth_status(self.status)
        return data


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() not in {"0", "false", "no", "off"})


def find_claude_cli(override: str | None = None) -> str:
    candidate = override or shutil.which("claude")
    if not candidate:
        raise AuthPreflightError(
            "Claude Code CLI was not found. Install Claude Code and run `claude auth login` "
            "before using the Python control plane."
        )
    path = Path(candidate).expanduser()
    if not path.exists() or not path.is_file():
        raise AuthPreflightError(f"Claude CLI path does not exist: {path}")
    if os.name == "nt" and path.suffix.lower() in {".cmd", ".bat"}:
        raise AuthPreflightError(
            "Refusing a .cmd/.bat Claude launcher. Install the native Claude Code binary or pass "
            "the absolute path to claude.exe."
        )
    return str(path.resolve())


def _extract_json(text: str) -> dict[str, Any]:
    raw = text.strip()
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(raw[start : end + 1])
                return value if isinstance(value, dict) else {}
            except json.JSONDecodeError:
                pass
    raise AuthPreflightError("`claude auth status` did not return valid JSON.")


def run_auth_status(claude_path: str, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [claude_path, "auth", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
            env=dict(env or os.environ),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuthPreflightError(f"Could not inspect Claude authentication: {exc}") from exc
    payload_text = result.stdout or result.stderr
    if not payload_text.strip():
        raise AuthPreflightError("`claude auth status` returned no authentication details.")
    payload = _extract_json(payload_text)
    if result.returncode != 0 and not payload.get("loggedIn"):
        raise AuthPreflightError(
            "Claude Code is not logged in. Run `claude auth login` for your subscription, then retry."
        )
    return payload


def _settings_paths(repo: Path, env: Mapping[str, str]) -> list[Path]:
    config_dir = Path(env.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser()
    paths = [
        config_dir / "settings.json",
        config_dir / "settings.local.json",
        repo / ".claude" / "settings.json",
        repo / ".claude" / "settings.local.json",
    ]
    if os.name == "nt":
        program_data = env.get("PROGRAMDATA")
        if program_data:
            paths.append(Path(program_data) / "ClaudeCode" / "managed-settings.json")
    else:
        paths.extend(
            [
                Path("/etc/claude-code/managed-settings.json"),
                Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
            ]
        )
    return paths


def find_credential_overrides(repo: Path, env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Return credential/routing markers from settings without reading secret values."""
    environment = dict(env or os.environ)
    found: list[str] = []
    watched = (*API_ENV_VARS, *SUBSCRIPTION_ENV_VARS, *CLOUD_ROUTE_ENV_VARS, *ROUTING_ENV_VARS)
    for path in _settings_paths(repo.resolve(), environment):
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("apiKeyHelper"):
            found.append(f"apiKeyHelper:{path}")
        injected = data.get("env") if isinstance(data, dict) else None
        if isinstance(injected, dict):
            for name in watched:
                if injected.get(name):
                    found.append(f"settings-env:{name}:{path}")
    return tuple(sorted(set(found)))


def find_api_key_helpers(repo: Path, env: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Backward-compatible alias retained for package integrations."""
    return tuple(item for item in find_credential_overrides(repo, env) if item.startswith("apiKeyHelper:"))


def _first(status: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = status.get(key)
        if value not in (None, ""):
            return value
    return None


def _mask_text(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if "@" in text:
        name, domain = text.split("@", 1)
        return f"{name[:2]}***@{domain}"
    if len(text) <= 4:
        return "***"
    return f"{text[:2]}***{text[-2:]}"


def redact_auth_status(status: Mapping[str, Any]) -> dict[str, Any]:
    safe_keys = {
        "loggedIn",
        "authMethod",
        "apiProvider",
        "apiKeySource",
        "subscriptionType",
        "orgName",
        "email",
        "loginMethod",
    }
    redacted: dict[str, Any] = {}
    for key, value in status.items():
        if key not in safe_keys:
            continue
        if key in {"email", "orgName"} and isinstance(value, str):
            value = _mask_text(value)
        redacted[key] = value
    return redacted


def _credential_conflicts(
    repo: Path,
    environment: Mapping[str, str],
) -> tuple[list[str], list[str], list[str], list[str], list[str]]:
    api = [name for name in API_ENV_VARS if environment.get(name)]
    subscription = [name for name in SUBSCRIPTION_ENV_VARS if environment.get(name)]
    cloud = [name for name in CLOUD_ROUTE_ENV_VARS if _truthy(environment.get(name))]
    routes = [name for name in ROUTING_ENV_VARS if environment.get(name)]
    settings = list(find_credential_overrides(repo, environment))
    return api, subscription, cloud, routes, settings


def preflight_auth(
    *,
    mode: str,
    repo: Path,
    claude_path: str | None = None,
    allow_api_billing: bool = False,
    max_budget_usd: float | None = None,
    env: Mapping[str, str] | None = None,
) -> AuthReport:
    environment = dict(env or os.environ)
    cli = find_claude_cli(claude_path)
    present_api, present_subscription, present_cloud, present_routes, settings_markers = _credential_conflicts(
        repo, environment
    )

    if mode == "subscription":
        conflicts = [*present_api, *present_cloud, *present_routes, *settings_markers]
        if conflicts:
            raise AuthPreflightError(
                "Subscription mode is fail-closed because a higher-precedence API, gateway, or "
                "cloud credential is active: " + ", ".join(conflicts) + ". Remove it and rerun "
                "`madclaude auth-check`. No credential was printed or changed."
            )
    elif mode == "api":
        if not allow_api_billing:
            raise AuthPreflightError(
                "API mode requires `--allow-api-billing`. This prevents a Claude Console key from "
                "silently replacing subscription usage."
            )
        if max_budget_usd is None or max_budget_usd <= 0:
            raise AuthPreflightError(
                "API mode requires a positive `--max-budget-usd` in addition to "
                "`--allow-api-billing`."
            )
        ambiguous = [*present_subscription, *present_cloud, *present_routes, *settings_markers]
        if environment.get("ANTHROPIC_AUTH_TOKEN"):
            ambiguous.append("ANTHROPIC_AUTH_TOKEN")
        if ambiguous:
            raise AuthPreflightError(
                "API mode cannot prove a single direct Anthropic API-key lane while these alternate "
                "credentials/routes are active: " + ", ".join(sorted(set(ambiguous)))
            )
        if not environment.get("ANTHROPIC_API_KEY"):
            raise AuthPreflightError(
                "API mode requires ANTHROPIC_API_KEY in the current process environment. The control "
                "plane never reads, stores, or prints the key value."
            )
    else:
        raise AuthPreflightError(f"Unsupported billing mode: {mode}")

    status = run_auth_status(cli, environment)
    logged_in = bool(_first(status, "loggedIn", "logged_in"))
    auth_method = str(_first(status, "authMethod", "auth_method", "loginMethod") or "") or None
    provider = str(_first(status, "apiProvider", "api_provider") or "") or None
    api_key_source = str(_first(status, "apiKeySource", "api_key_source") or "") or None
    subscription = str(_first(status, "subscriptionType", "subscription_type") or "").lower() or None
    raw_account_hint = str(_first(status, "orgName", "organizationName", "email") or "") or None
    account_hint = _mask_text(raw_account_hint)

    method_text = (auth_method or "").lower()
    provider_text = (provider or "").lower()
    key_source_text = (api_key_source or "").lower()

    if mode == "subscription":
        if not logged_in:
            raise AuthPreflightError(
                "No active Claude login was detected. Run `claude auth login`, choose your Claude "
                "subscription, and retry."
            )
        has_oauth_token = bool(environment.get("CLAUDE_CODE_OAUTH_TOKEN"))
        recognized_subscription = subscription in SUBSCRIPTION_TYPES
        explicit_subscription_method = any(
            token in method_text for token in ("claude.ai", "subscription", "pro", "max", "team", "enterprise")
        )
        console_like = any(token in method_text for token in ("api", "console", "key"))
        key_like = bool(key_source_text) or any(token in key_source_text for token in ("api", "key", "helper"))
        cloud_like = any(token in provider_text for token in ("bedrock", "vertex", "foundry", "gateway", "aws"))
        if console_like or key_like or cloud_like:
            raise AuthPreflightError(
                "Claude is logged in, but the active credential appears to be an API, key-helper, "
                "gateway, or cloud-provider lane rather than a Claude subscription. Run "
                "`claude auth login` without `--console`, then confirm with `claude auth status`."
            )
        if not (recognized_subscription or explicit_subscription_method or has_oauth_token):
            raise AuthPreflightError(
                "Claude authentication is active but a Pro, Max, Team, Enterprise, claude.ai, or "
                "`CLAUDE_CODE_OAUTH_TOKEN` subscription lane could not be proven from `claude auth "
                "status`. Generic OAuth alone is not accepted. Refusing to guess."
            )
        warnings: list[str] = [
            "Credential preflight proves the Claude subscription authentication lane only. It cannot prove "
            "model-specific plan entitlements (including whether Fable uses usage credits), whether "
            "account-level extra usage/usage credits are enabled, remaining allowance, or final "
            "billing. It is not an authoritative billing statement."
        ]
        if not recognized_subscription:
            warnings.append(
                "Subscription tier was not reported explicitly; the lane was accepted only because "
                "claude.ai/subscription authentication or CLAUDE_CODE_OAUTH_TOKEN was explicitly proven."
            )
        lane = "subscription-oauth-token" if has_oauth_token else "subscription-saved-login"
        return AuthReport(
            requested_mode=mode,
            safe=True,
            claude_path=cli,
            credential_lane=lane,
            logged_in=True,
            subscription_type=subscription,
            auth_method=auth_method,
            api_provider=provider,
            account_hint=account_hint,
            warnings=tuple(warnings),
            status=status,
        )

    direct_key_proven = (
        "anthropic_api_key" in key_source_text
        or key_source_text in {"environment", "env"}
        or any(token in method_text for token in ("api_key", "apikey", "api key"))
    )
    if not direct_key_proven:
        raise AuthPreflightError(
            "ANTHROPIC_API_KEY is present, but `claude auth status` did not prove that the active "
            "credential is the direct API-key lane. Refusing to charge an ambiguous provider route."
        )
    return AuthReport(
        requested_mode=mode,
        safe=True,
        claude_path=cli,
        credential_lane="anthropic-api-key-explicit",
        logged_in=logged_in,
        subscription_type=subscription,
        auth_method=auth_method,
        api_provider=provider,
        account_hint=account_hint,
        warnings=(
            "This run uses separate Claude Console API billing. Client-side cost fields are estimates, "
            "not authoritative invoices.",
        ),
        status=status,
    )


def enforce_model_billing_policy(
    report: AuthReport,
    *,
    model: str,
    allow_usage_credits: bool = False,
) -> AuthReport:
    """Fail closed when a subscription route may require model-specific usage credits.

    Authentication lane and model entitlement are separate facts. Fable is included for Max plans,
    but it uses usage credits from the start on Pro and some standard seats. Team/Enterprise seat
    class is not reliably exposed by `claude auth status`, so those lanes require an explicit
    acknowledgement or a non-Fable model override. This function never enables usage credits.
    """
    if report.requested_mode != "subscription":
        return report

    normalized = model.strip().lower()
    fable_selected = "fable" in normalized
    entitlement_ambiguous = normalized in {"best", "best-available", "inherit", "default"}
    if not (fable_selected or entitlement_ambiguous):
        return report

    subscription = (report.subscription_type or "").lower()
    if fable_selected and subscription == "max":
        return replace(
            report,
            warnings=report.warnings
            + (
                "Fable is included on Max only within its plan-specific weekly allowance. The "
                "control plane cannot observe remaining Fable allowance or whether usage credits "
                "will be used after that allowance is exhausted.",
            ),
        )

    if not allow_usage_credits:
        model_label = model or "[unreported]"
        plan_label = report.subscription_type or "unreported/seat-unspecified"
        raise AuthPreflightError(
            f"Subscription authentication was proven, but model `{model_label}` may use separately "
            f"billed usage credits for plan/seat `{plan_label}`. Fable uses usage credits from the "
            "start on Pro and standard seats, and `claude auth status` cannot reliably prove "
            "Team/Enterprise seat class. Use `--model opus` or `--model sonnet`, or rerun with "
            "`--allow-usage-credits` after reviewing account Usage settings. This flag only "
            "acknowledges the risk; it does not enable credits."
        )

    return replace(
        report,
        warnings=report.warnings
        + (
            f"Usage-credit risk explicitly acknowledged for model `{model}`. This acknowledgement "
            "does not enable credits, prove entitlement, cap charges, or replace account billing "
            "controls.",
        ),
    )


def child_environment(report: AuthReport, source: Mapping[str, str] | None = None) -> dict[str, str]:
    environment = dict(source or os.environ)
    if report.requested_mode == "subscription":
        for name in (*API_ENV_VARS, *CLOUD_ROUTE_ENV_VARS, *ROUTING_ENV_VARS):
            environment.pop(name, None)
    else:
        for name in (*SUBSCRIPTION_ENV_VARS, "ANTHROPIC_AUTH_TOKEN", *CLOUD_ROUTE_ENV_VARS, *ROUTING_ENV_VARS):
            environment.pop(name, None)
    environment["MADCLAUDE_BILLING_MODE"] = report.requested_mode
    environment["ENABLE_CLAUDEAI_MCP_SERVERS"] = "false"
    environment["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    environment["CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS"] = "1"
    return environment
