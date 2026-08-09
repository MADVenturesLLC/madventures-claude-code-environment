from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import __version__, term
from .approval import approval_template
from .auth import preflight_auth
from .config import ROUTES, get_route
from .errors import MadClaudeError
from .approval import load_json_at
from .execution import load_execution_record, select_builder, select_independent_reviewer
from .mcp_lifecycle import (
    disable,
    enable,
    install_release,
    releases_root,
    reenable,
    remove,
    rollback,
    serve,
    staged_self_test,
    status,
    verify_record_level,
    verify_release_prelaunch,
    wrapper_path,
)
from .git import get_state, repository_root
from .schemas import export_schemas
from .workflows import (
    RuntimeOptions,
    dry_run_preview,
    run_audit,
    run_build,
    run_exact_sha,
    run_fix_until_green,
    run_plan,
    run_verify,
)

EXIT_OK = 0
EXIT_ERROR = 3
EXIT_GATE_FAILED = 10

# Single explicit package-identity manifest location (R6-04), identical in
# both layouts: <package root>/MANIFEST.json in the source tree and
# $MADCLAUDE_HOME/MANIFEST.json in the installed layout, where the installer
# places it deliberately. No fallback search across parent directories.
PACKAGE_IDENTITY_MANIFEST_NAME = "MANIFEST.json"
EXPECTED_PACKAGE_NAME = f"MADVentures-Claude-Code-Environment-v{__version__}"


def _validate_identity_manifest(candidate: Path) -> Path:
    """Parse and validate the package-identity manifest BEFORE it is ever
    hashed for release identity. Missing, malformed, or unrelated manifests
    fail closed with a typed, actionable error."""
    if not candidate.is_file():
        raise MadClaudeError(
            f"Package identity manifest is missing: {candidate}. Reinstall the control plane so "
            "the installer can place this immutable identity input."
        )
    try:
        manifest = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MadClaudeError(f"Package identity manifest is unreadable or invalid JSON: {candidate}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise MadClaudeError(f"Package identity manifest must contain a JSON object: {candidate}")
    if manifest.get("package") != EXPECTED_PACKAGE_NAME:
        raise MadClaudeError(
            f"Package identity manifest names an unrelated package {manifest.get('package')!r} "
            f"(expected {EXPECTED_PACKAGE_NAME!r}): {candidate}"
        )
    if manifest.get("version") != __version__:
        raise MadClaudeError(
            f"Package identity manifest version {manifest.get('version')!r} does not match the "
            f"control-plane version {__version__!r}: {candidate}"
        )
    files = manifest.get("files")
    if (
        manifest.get("algorithm") != "SHA-256"
        or not isinstance(manifest.get("fileCount"), int)
        or not isinstance(files, list)
        or manifest["fileCount"] != len(files)
    ):
        raise MadClaudeError(
            f"Package identity manifest schema is malformed (SHA-256 algorithm, fileCount, and "
            f"files are required and must agree): {candidate}"
        )
    return candidate


def _package_identity_manifest() -> Path:
    return _validate_identity_manifest(Path(__file__).resolve().parents[3] / PACKAGE_IDENTITY_MANIFEST_NAME)


def _common(parser: argparse.ArgumentParser, *, model: bool = True, dry_run: bool = True) -> None:
    parser.add_argument("--repo", default=".", help="Repository root or a path inside it.")
    parser.add_argument(
        "--backend",
        choices=("cli", "sdk"),
        default="cli",
        help=(
            "Default: cli. Python orchestrates the native `claude -p` process and preserves the "
            "authenticated Claude Code subscription lane. The optional SDK backend is API-billed only."
        ),
    )
    parser.add_argument("--billing-mode", choices=("subscription", "api"), default="subscription")
    parser.add_argument("--allow-api-billing", action="store_true", help="Second explicit gate required for API billing.")
    parser.add_argument("--claude-path", help="Absolute Claude Code native binary path.")
    if model:
        parser.add_argument("--model", help="Override the governed route model alias.")
        parser.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max"))
        parser.add_argument("--max-turns", type=int)
        parser.add_argument(
            "--allow-usage-credits",
            action="store_true",
            help=(
                "Acknowledge that the selected model may use separately billed Claude usage "
                "credits. Required for Fable when plan/seat inclusion cannot be proven. This "
                "does not enable credits or authorize API-key billing."
            ),
        )
    parser.add_argument("--timeout", type=int, default=3600, help="Claude run timeout in seconds.")
    parser.add_argument("--verification-timeout", type=int, default=900, help="Timeout per verification command.")
    parser.add_argument(
        "--max-budget-usd",
        type=float,
        help="Required positive client-side estimate cap for API mode; optional and non-billing in subscription mode.",
    )
    parser.add_argument("--evidence-dir", help="Default: <repo>/.claude/evidence/python-control-plane")
    if dry_run:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate auth, repository, approval, scope, SHA, and commands without Claude, commands, worktrees, edits, or evidence writes.",
        )
    parser.add_argument("--json", action="store_true", help="Print machine-readable outcome JSON.")


def _repo(path: str) -> Path:
    return repository_root(Path(path).expanduser().resolve())


def _options(args: argparse.Namespace, repo: Path) -> RuntimeOptions:
    evidence = Path(args.evidence_dir).expanduser() if args.evidence_dir else repo / ".claude" / "evidence" / "python-control-plane"
    if not evidence.is_absolute():
        evidence = repo / evidence
    return RuntimeOptions(
        backend=args.backend,
        billing_mode=args.billing_mode,
        allow_api_billing=args.allow_api_billing,
        allow_usage_credits=getattr(args, "allow_usage_credits", False),
        claude_path=args.claude_path,
        timeout_seconds=args.timeout,
        verification_timeout_seconds=args.verification_timeout,
        max_budget_usd=args.max_budget_usd,
        evidence_dir=evidence.resolve(),
    )


def _print(value: Any, machine: bool, *, theme: str | None = None) -> None:
    if machine:
        print(json.dumps(value, indent=2, sort_keys=True))
        return
    resolved = term.resolve_theme(theme)
    if isinstance(value, dict):
        for key, item in value.items():
            label = term.style(key, "key", theme=resolved)
            if isinstance(item, (dict, list, tuple)):
                print(f"{label}: {json.dumps(item, indent=2, sort_keys=True)}")
            else:
                text = str(item)
                if text == "completed":
                    text = term.style(text, "ok", theme=resolved)
                elif text in {"failed", "error"}:
                    text = term.style(text, "error", theme=resolved)
                print(f"{label}: {text}")
    else:
        print(value)


def _add_goal(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("goal", help="Exact workflow goal.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="madclaude",
        description="Subscription-first Python control plane for governed Claude Code engineering.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--theme",
        choices=("auto", "light", "dark", "plain"),
        default=None,
        help="Human-output theme (cosmetic only; JSON/hook/evidence output is never styled).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    auth = sub.add_parser("auth-check", help="Prove the selected billing/authentication lane without inference.")
    _common(auth, model=False, dry_run=False)

    doctor = sub.add_parser("doctor", help="Inspect Python, Git, Claude CLI, authentication, repository state, and the optional Agent SDK.")
    _common(doctor, model=False, dry_run=False)

    routes = sub.add_parser("routes", help="List governed model/effort/tool routes.")
    routes.add_argument("--json", action="store_true")

    schemas = sub.add_parser("export-schemas", help="Write all structured-output JSON schemas.")
    schemas.add_argument("destination", nargs="?", default="schemas")

    approval = sub.add_parser("approval-template", help="Create a non-approved template bound to a plan SHA-256.")
    approval.add_argument("goal")
    approval.add_argument("--plan-file", required=True)
    approval.add_argument("--output", required=True)

    plan = sub.add_parser("plan", help="Produce a read-only implementation plan.")
    _add_goal(plan)
    _common(plan)

    build = sub.add_parser("build", help="Execute a Founder-approved plan within exact scopes.")
    _add_goal(build)
    _common(build)
    build.add_argument("--plan-file", required=True)
    build.add_argument("--approval-file", required=True)

    verify = sub.add_parser("verify", help="Run deterministic commands and have Claude interpret the evidence.")
    _add_goal(verify)
    _common(verify)
    verify.add_argument("--verify", action="append", required=True, dest="verification")

    for name, help_text in (
        ("tier1", "Exact-SHA Tier-1 technical review."),
        ("tier2", "Independent exact-SHA Tier-2 review."),
        ("release-readiness", "Exact-SHA release-readiness evidence assessment."),
        ("architecture-validation", "Exact-SHA architecture-invariant validation, separate from Tier-2."),
    ):
        exact = sub.add_parser(name, help=help_text)
        _add_goal(exact)
        _common(exact, model=name != "tier2")
        exact.add_argument("--base-sha", required=True, help="Full 40-character base SHA.")
        exact.add_argument("--head-sha", required=True, help="Full 40-character head SHA.")
        exact.add_argument("--verify", action="append", default=[], dest="verification")
        if name == "tier2":
            exact.add_argument(
                "--execution-record",
                action="append",
                required=True,
                help="Prior Python EXECUTION_RECORD.json; repeat for every planner, builder, verifier, and Tier-1 participant.",
            )

    for name in ("repo-audit", "security-audit", "ui-review"):
        audit = sub.add_parser(name, help=ROUTES[name].description)
        _add_goal(audit)
        _common(audit)
        if name == "repo-audit":
            audit.add_argument(
                "--profile",
                choices=("general", "docs-drift", "performance", "test-gap", "incident"),
                default="general",
            )

    fix = sub.add_parser("fix-until-green", help="Bounded repair loop driven by deterministic verification.")
    _add_goal(fix)
    _common(fix)
    fix.add_argument("--allowed-scope", action="append", required=True, dest="scopes")
    fix.add_argument("--verify", action="append", required=True, dest="verification")
    fix.add_argument("--max-rounds", type=int, default=3)

    mcp = sub.add_parser("mcp", help="Optional MCP release lifecycle (inactive by default; stdio transport only).")
    mcp_sub = mcp.add_subparsers(dest="mcp_command", required=True)
    mcp_install = mcp_sub.add_parser("install", help="Build an isolated MCP release offline from a reviewed wheelhouse.")
    mcp_install.add_argument("--wheelhouse", required=True, type=Path)
    mcp_install.add_argument("--lock", required=True, type=Path)
    mcp_install.add_argument("--arch", required=True, choices=("arm64", "x86_64"))
    mcp_install.add_argument("--home", type=Path)
    mcp_install.add_argument("--json", action="store_true")
    mcp_verify = mcp_sub.add_parser("verify", help="Run the pre-launch integrity tier against a release.")
    mcp_verify.add_argument("--release", type=Path, help="Release directory (default: the current pointer target).")
    mcp_verify.add_argument("--home", type=Path)
    mcp_verify.add_argument("--deep", action="store_true", help="Re-run full RECORD-level venv verification (drift detection).")
    mcp_verify.add_argument("--json", action="store_true")
    mcp_enable = mcp_sub.add_parser("enable", help="Verify a release and activate it via the atomic current pointer.")
    mcp_enable.add_argument("--release", required=True, type=Path)
    mcp_enable.add_argument("--home", type=Path)
    mcp_enable.add_argument("--json", action="store_true")
    mcp_disable = mcp_sub.add_parser("disable", help="Remove only the current pointer; wrapper and releases are preserved.")
    mcp_disable.add_argument("--home", type=Path)
    mcp_disable.add_argument("--json", action="store_true")
    mcp_reenable = mcp_sub.add_parser("re-enable", help="Verify the preserved release, then recreate the current pointer.")
    mcp_reenable.add_argument("--home", type=Path)
    mcp_reenable.add_argument("--json", action="store_true")
    mcp_remove = mcp_sub.add_parser("remove", help="Delete only releases the ownership record proves are owned.")
    mcp_remove.add_argument("--identity", required=True)
    mcp_remove.add_argument("--home", type=Path)
    mcp_remove.add_argument("--json", action="store_true")
    mcp_rollback = mcp_sub.add_parser("rollback", help="Re-point current to a preserved prior release.")
    mcp_rollback.add_argument("--identity", required=True)
    mcp_rollback.add_argument("--home", type=Path)
    mcp_rollback.add_argument("--json", action="store_true")
    mcp_status = mcp_sub.add_parser("status", help="Report activation state; --deep adds RECORD-level drift detection.")
    mcp_status.add_argument("--home", type=Path)
    mcp_status.add_argument("--deep", action="store_true")
    mcp_status.add_argument("--json", action="store_true")
    mcp_serve = mcp_sub.add_parser(
        "serve", help="Externally verified launch entry used by the stable wrapper (not for direct use)."
    )
    mcp_serve.add_argument("--home", type=Path)
    mcp_serve.add_argument("serve_args", nargs=argparse.REMAINDER)
    mcp_selftest = mcp_sub.add_parser(
        "self-test", help="Base-orchestrated pre-activation self-test of a staged release."
    )
    mcp_selftest.add_argument("--release", required=True, type=Path)
    mcp_selftest.add_argument("--home", type=Path)
    mcp_selftest.add_argument("--json", action="store_true")
    return parser


def _mcp_home(args: argparse.Namespace) -> Path:
    raw = getattr(args, "home", None)
    if raw:
        return Path(raw).expanduser().resolve()
    environment = os.environ.get("MADCLAUDE_HOME")
    if environment:
        return Path(environment).expanduser().resolve()
    return Path.home() / ".madclaude"


def _mcp_command(args: argparse.Namespace) -> int:
    home = _mcp_home(args)
    if args.mcp_command == "install":
        release = install_release(
            home=home,
            app_source=Path(__file__).resolve().parent,
            wheelhouse=args.wheelhouse.expanduser().resolve(),
            lock_file=args.lock.expanduser().resolve(),
            architecture=args.arch,
            python=sys.executable,
            package_version=__version__,
            source_manifest=_package_identity_manifest(),
        )
        _print({"identity": release.name, "release": str(release), "status": "staged-not-activated"}, args.json, theme=getattr(args, "theme", None))
        return EXIT_OK
    if args.mcp_command == "verify":
        if args.release:
            release_dir = args.release.expanduser().resolve()
        else:
            current = releases_root(home) / "current"
            if not current.is_symlink():
                raise MadClaudeError("No active MCP release: the current pointer is absent (disabled state).")
            release_dir = current.resolve()
        integrity = verify_release_prelaunch(release_dir, home=home)
        payload: dict[str, Any] = {"identity": integrity["identity"], "prelaunch": "verified"}
        if args.deep:
            drift = verify_record_level(release_dir)
            payload["recordLevel"] = "verified" if not drift else "drift-detected"
            payload["drift"] = drift
            if drift:
                _print(payload, args.json, theme=getattr(args, "theme", None))
                return EXIT_GATE_FAILED
        _print(payload, args.json, theme=getattr(args, "theme", None))
        return EXIT_OK
    if args.mcp_command == "enable":
        release = enable(home, args.release.expanduser())
        _print({"identity": release.name, "status": "enabled"}, args.json, theme=getattr(args, "theme", None))
        return EXIT_OK
    if args.mcp_command == "disable":
        disable(home)
        _print({"status": "disabled", "wrapper": str(wrapper_path(home))}, args.json, theme=getattr(args, "theme", None))
        return EXIT_OK
    if args.mcp_command == "re-enable":
        release = reenable(home)
        _print({"identity": release.name, "status": "re-enabled"}, args.json, theme=getattr(args, "theme", None))
        return EXIT_OK
    if args.mcp_command == "remove":
        _print(remove(home, args.identity), args.json, theme=getattr(args, "theme", None))
        return EXIT_OK
    if args.mcp_command == "rollback":
        release = rollback(home, args.identity)
        _print({"identity": release.name, "status": "rolled-back"}, args.json, theme=getattr(args, "theme", None))
        return EXIT_OK
    if args.mcp_command == "status":
        report = status(home, deep=args.deep)
        _print(report, args.json, theme=getattr(args, "theme", None))
        return EXIT_GATE_FAILED if report.get("drift") else EXIT_OK
    if args.mcp_command == "serve":
        extra = list(args.serve_args)
        if extra[:1] == ["--"]:
            extra = extra[1:]
        return serve(home, extra)
    if args.mcp_command == "self-test":
        release_dir = args.release.expanduser().resolve()
        staged_self_test(home, release_dir)
        _print({"release": release_dir.name, "status": "staged-self-test-ok"}, args.json, theme=getattr(args, "theme", None))
        return EXIT_OK
    raise MadClaudeError(f"Unsupported mcp command: {args.mcp_command}")


def _route(args: argparse.Namespace, name: str):
    route = get_route(
        name,
        model=getattr(args, "model", None),
        effort=getattr(args, "effort", None),
        max_turns=getattr(args, "max_turns", None),
    )
    if name == "review":
        participants: list[dict[str, Any]] = []
        for record_path in getattr(args, "execution_record", []):
            record = load_execution_record(Path(record_path).expanduser().resolve())
            raw = record.get("participants")
            if isinstance(raw, list):
                participants.extend(raw)
        route = select_independent_reviewer(route, {"participants": participants})
    return route


def _dry_run(args: argparse.Namespace, repo: Path, options: RuntimeOptions) -> dict[str, Any]:
    route_name = {
        "tier1": "tier1-review",
        "tier2": "review",
        "release-readiness": "release-readiness",
    }.get(args.command, args.command)
    route = _route(args, route_name)
    kwargs: dict[str, Any] = {
        "route": route,
        "options": options,
        "repo": repo,
        "goal": args.goal,
    }
    if args.command == "build":
        plan_path = Path(args.plan_file).expanduser().resolve()
        route = select_builder(route, load_json_at(repo, plan_path), getattr(args, "model", None))
        kwargs["route"] = route
        kwargs.update(
            plan_file=plan_path,
            approval_file=Path(args.approval_file).expanduser().resolve(),
        )
    elif args.command in {"tier1", "tier2", "release-readiness", "architecture-validation"}:
        kwargs.update(base_ref=args.base_sha, head_ref=args.head_sha, commands=args.verification)
    elif args.command == "verify":
        kwargs.update(commands=args.verification)
    elif args.command == "fix-until-green":
        kwargs.update(commands=args.verification, scopes_input=tuple(args.scopes), max_rounds=args.max_rounds)
    return dry_run_preview(**kwargs)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "routes":
            data = {name: asdict(route) for name, route in ROUTES.items()}
            _print(data, args.json, theme=getattr(args, "theme", None))
            return EXIT_OK
        if args.command == "export-schemas":
            destination = Path(args.destination).expanduser().resolve()
            export_schemas(destination)
            print(destination)
            return EXIT_OK
        if args.command == "approval-template":
            plan = Path(args.plan_file).expanduser().resolve()
            output = Path(args.output).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(approval_template(plan, args.goal), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if os.name != "nt":
                output.chmod(0o600)
            print(output)
            return EXIT_OK

        if args.command == "mcp":
            return _mcp_command(args)

        repo = _repo(args.repo)
        if args.command in {"auth-check", "doctor"}:
            report = preflight_auth(
                mode=args.billing_mode,
                repo=repo,
                claude_path=args.claude_path,
                allow_api_billing=args.allow_api_billing,
                max_budget_usd=args.max_budget_usd,
            )
            data: dict[str, Any] = {"version": __version__, "auth": report.public_dict()}
            if args.command == "doctor":
                state = get_state(repo)
                try:
                    import claude_agent_sdk  # type: ignore

                    sdk_version = getattr(claude_agent_sdk, "__version__", "installed-version-not-exported")
                    sdk = True
                except ImportError:
                    sdk = False
                    sdk_version = None
                data.update(
                    {
                        "python": sys.version.split()[0],
                        "git": shutil.which("git"),
                        "repository": state.to_dict(),
                        "sdkInstalled": sdk,
                        "sdkVersion": sdk_version,
                        "optionalSdkVersion": "0.2.131",
                        "defaultBackend": "cli",
                        "defaultBillingMode": "subscription",
                        "mcpEnabledInControlPlane": False,
                    }
                )
            _print(data, args.json, theme=getattr(args, "theme", None))
            return EXIT_OK

        options = _options(args, repo)
        if getattr(args, "dry_run", False):
            _print(_dry_run(args, repo, options), args.json, theme=getattr(args, "theme", None))
            return EXIT_OK

        if args.command == "plan":
            outcome = run_plan(_route(args, "plan"), options, repo, args.goal)
        elif args.command == "build":
            plan_path = Path(args.plan_file).expanduser().resolve()
            route = select_builder(_route(args, "build"), load_json_at(repo, plan_path), getattr(args, "model", None))
            outcome = run_build(
                route,
                options,
                repo,
                args.goal,
                plan_path,
                Path(args.approval_file).expanduser().resolve(),
            )
        elif args.command == "verify":
            outcome = run_verify(_route(args, "verify"), options, repo, args.goal, args.verification)
        elif args.command == "tier2":
            outcome = run_exact_sha(
                _route(args, "review"), options, repo, args.goal, args.base_sha, args.head_sha, args.verification
            )
        elif args.command == "tier1":
            outcome = run_exact_sha(
                _route(args, "tier1-review"), options, repo, args.goal, args.base_sha, args.head_sha, args.verification
            )
        elif args.command == "release-readiness":
            outcome = run_exact_sha(
                _route(args, "release-readiness"), options, repo, args.goal, args.base_sha, args.head_sha, args.verification
            )
        elif args.command == "architecture-validation":
            outcome = run_exact_sha(
                _route(args, "architecture-validation"), options, repo, args.goal, args.base_sha, args.head_sha, args.verification
            )
        elif args.command in {"repo-audit", "security-audit", "ui-review"}:
            outcome = run_audit(
                _route(args, args.command),
                options,
                repo,
                args.goal,
                getattr(args, "profile", "general"),
            )
        elif args.command == "fix-until-green":
            if args.max_rounds < 1 or args.max_rounds > 3:
                raise MadClaudeError("--max-rounds must be between 1 and 3.")
            outcome = run_fix_until_green(
                _route(args, "fix-until-green"),
                options,
                repo,
                args.goal,
                tuple(args.scopes),
                args.verification,
                args.max_rounds,
            )
        else:
            raise MadClaudeError(f"Unsupported command: {args.command}")
        _print(outcome.to_dict(), args.json, theme=getattr(args, "theme", None))
        return EXIT_OK if outcome.status == "completed" else EXIT_GATE_FAILED
    except MadClaudeError as exc:
        payload = {"status": "error", "error": str(exc)}
        _print(payload, getattr(args, "json", False), theme=getattr(args, "theme", None))
        return EXIT_ERROR
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
