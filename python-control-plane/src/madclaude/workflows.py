from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .approval import load_json_at, validate_approval
from .artifacts import write_canonical_artifact
from .auth import child_environment, enforce_model_billing_policy, preflight_auth
from .backend import AgentRequest, AgentResponse, backend_for
from .config import RouteConfig
from .errors import AgentRunError, PolicyViolation, RepositoryError
from .evidence import EvidenceBundle, redact
from .execution import execution_record, select_builder
from .git import (
    assert_ancestor,
    detached_worktree,
    diff_files,
    diff_text,
    get_state,
    require_clean,
    require_unchanged,
    resolve_full_sha,
    working_tree_fingerprint,
)
from .guard import (
    contains_sensitive_material,
    enforce_scopes,
    reject_sensitive_changed_paths,
    validate_scopes,
)
from .prompts import (
    BASE_SYSTEM_APPEND,
    architecture_prompt,
    audit_prompt,
    build_prompt,
    plan_prompt,
    release_prompt,
    repair_prompt,
    review_prompt,
    verify_prompt,
)
from .schemas import schema_for
from .verification import VerificationResult, failure_fingerprint, run_commands, validate_commands


@dataclass(frozen=True)
class RuntimeOptions:
    backend: str
    billing_mode: str
    allow_api_billing: bool
    allow_usage_credits: bool
    claude_path: str | None
    timeout_seconds: int
    verification_timeout_seconds: int
    max_budget_usd: float | None
    evidence_dir: Path


@dataclass
class WorkflowOutcome:
    route: str
    status: str
    evidence_path: str
    structured_output: dict[str, Any] | None
    verification: list[dict[str, Any]]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_profile(repo: Path, max_chars: int = 40_000) -> str:
    candidates = [repo / ".claude" / "PROJECT_PROFILE.md", repo / ".claude" / "FOUNDEROS.md", repo / "CLAUDE.md"]
    chunks: list[str] = []
    for path in candidates:
        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")
            chunks.append(f"## {path.relative_to(repo)}\n{content}")
    text = "\n\n".join(chunks)
    return text[:max_chars] + ("\n[PROFILE TRUNCATED]" if len(text) > max_chars else "")


def _validate_backend(route: RouteConfig, options: RuntimeOptions) -> None:
    if options.backend == "cli":
        return
    if options.backend == "sdk":
        if options.billing_mode != "api":
            raise AgentRunError(
                "The optional Agent SDK backend is API-billed in V4.4. Use the default CLI "
                "backend for subscription usage, or select `--billing-mode api` with both API gates."
            )
        if not options.allow_api_billing or options.max_budget_usd is None or options.max_budget_usd <= 0:
            raise AgentRunError(
                "The SDK backend requires `--allow-api-billing` and a positive `--max-budget-usd`."
            )
        return
    raise AgentRunError(f"Unsupported backend: {options.backend}")


def _validate_route_agents(repo: Path, route: RouteConfig) -> None:
    for name in route.subagents:
        path = repo / ".claude" / "agents" / f"{name}.md"
        if not path.is_file():
            raise AgentRunError(
                f"Route {route.name} requires project subagent {name}, but {path} is missing. "
                "Install the V4.4 project environment before running this route."
            )


def _agent_run(
    *,
    route: RouteConfig,
    options: RuntimeOptions,
    repo: Path,
    prompt: str,
    bundle: EvidenceBundle,
    allowed_scopes: tuple[str, ...] = (),
    evidence_prefix: str = "",
) -> AgentResponse:
    _validate_backend(route, options)
    _validate_route_agents(repo, route)
    auth = preflight_auth(
        mode=options.billing_mode,
        repo=repo,
        claude_path=options.claude_path,
        allow_api_billing=options.allow_api_billing,
        max_budget_usd=options.max_budget_usd,
    )
    auth = enforce_model_billing_policy(
        auth, model=route.model, allow_usage_credits=options.allow_usage_credits
    )
    bundle.write_json(f"{evidence_prefix}auth.json", auth.public_dict())
    environment = child_environment(auth)
    request = AgentRequest(
        route_name=route.name,
        prompt=prompt,
        cwd=repo,
        claude_path=auth.claude_path,
        environment=environment,
        model=route.model,
        effort=route.effort,
        max_turns=route.max_turns,
        permission_mode=route.permission_mode,
        tools=route.tools,
        schema=schema_for(route.schema),
        timeout_seconds=options.timeout_seconds,
        mutates=route.mutates,
        allowed_scopes=allowed_scopes,
        max_budget_usd=options.max_budget_usd,
        system_append=BASE_SYSTEM_APPEND,
        backend=options.backend,
        billing_mode=options.billing_mode,
        setting_sources=("project",),
        subagents=route.subagents,
    )
    bundle.write_json(
        f"{evidence_prefix}request.json",
        {
            "backend": options.backend,
            "billingMode": options.billing_mode,
            "route": _route_public_dict(route),
            "cwd": str(repo),
            "maxBudgetUsd": options.max_budget_usd,
            "usageCreditsAcknowledged": options.allow_usage_credits,
            "allowedScopes": list(allowed_scopes),
            "allowedSubagents": list(route.subagents),
            "mcpEnabled": False,
        },
    )
    bundle.write_text(f"{evidence_prefix}prompt.txt", prompt + "\n")
    response = backend_for(options.backend).run(request)
    bundle.write_json(f"{evidence_prefix}agent-response.json", response.to_dict())
    if response.structured_output is not None:
        bundle.write_json(f"{evidence_prefix}structured-output.json", response.structured_output)
    return response


def _route_public_dict(route: RouteConfig) -> dict[str, Any]:
    payload = asdict(route)
    payload["tools"] = list(route.tools)
    payload["subagents"] = list(route.subagents)
    return payload


def _unchanged_error(before: Any, after: Any, label: str) -> str | None:
    try:
        require_unchanged(before, after, label)
    except RepositoryError as exc:
        return str(exc)
    return None


def _write_verification_artifact(
    bundle: EvidenceBundle,
    repo: Path,
    head_sha: str,
    results: list[VerificationResult],
) -> None:
    artifact = {
        "schemaVersion": 1,
        "repository": str(repo),
        "headSha": head_sha,
        "workingTreeFingerprint": working_tree_fingerprint(repo),
        "commands": [item.to_dict() for item in results],
        "failed": [item.command for item in results if item.status == "failed"],
        "skipped": [item.command for item in results if item.status not in {"passed", "failed"}],
        "residualRisks": [] if results and all(item.status == "passed" for item in results) else ["Verification is incomplete or failed."],
        "verifier": {"role": "python-control-plane", "model": None},
        "evidenceSource": "local_evidence",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    bundle.write_json("VERIFICATION.json", artifact)
    status = "passed" if results and all(item.status == "passed" for item in results) else "failed"
    write_canonical_artifact(
        bundle,
        "VERIFICATION",
        artifact,
        repository=repo,
        base_sha=head_sha,
        head_sha=head_sha,
        status=status,
    )


def _finalize(
    bundle: EvidenceBundle,
    route: RouteConfig,
    repo: Path,
    starting_sha: str,
    final_sha: str,
    status: str,
) -> None:
    bundle.write_json(
        "EXECUTION_RECORD.json",
        execution_record(
            route=route,
            repository=repo,
            starting_sha=starting_sha,
            final_sha=final_sha,
            status=status,
            evidence_path=bundle.path,
        ),
    )
    bundle.finalize(status)


def run_plan(route: RouteConfig, options: RuntimeOptions, repo: Path, goal: str) -> WorkflowOutcome:
    before = get_state(repo)
    bundle = EvidenceBundle(options.evidence_dir, route.name)
    bundle.write_json("git-before.json", before.to_dict())
    response = _agent_run(
        route=route,
        options=options,
        repo=repo,
        prompt=plan_prompt(goal, before.to_dict(), read_profile(repo)),
        bundle=bundle,
    )
    if response.structured_output is not None:
        bundle.write_json("PLAN.json", response.structured_output)
    after = get_state(repo)
    bundle.write_json("git-after.json", after.to_dict())
    errors = list(response.errors)
    if error := _unchanged_error(before, after, "Plan route"):
        errors.append(error)
    status = "completed" if response.success and not errors else "failed"
    if response.structured_output is not None:
        write_canonical_artifact(
            bundle,
            "PLAN",
            response.structured_output,
            repository=repo,
            base_sha=before.head_sha,
            head_sha=after.head_sha,
            status=status,
        )
    _finalize(bundle, route, repo, before.head_sha, after.head_sha, status)
    return WorkflowOutcome(route.name, status, str(bundle.path), response.structured_output, [], errors)


def run_audit(
    route: RouteConfig,
    options: RuntimeOptions,
    repo: Path,
    goal: str,
    audit_profile: str = "general",
) -> WorkflowOutcome:
    before = get_state(repo)
    bundle = EvidenceBundle(options.evidence_dir, route.name)
    bundle.write_json("git-before.json", before.to_dict())
    response = _agent_run(
        route=route,
        options=options,
        repo=repo,
        prompt=audit_prompt(goal, route.name, before.to_dict(), read_profile(repo), audit_profile),
        bundle=bundle,
    )
    after = get_state(repo)
    bundle.write_json("git-after.json", after.to_dict())
    errors = list(response.errors)
    if error := _unchanged_error(before, after, f"{route.name} route"):
        errors.append(error)
    status = "completed" if response.success and not errors else "failed"
    _finalize(bundle, route, repo, before.head_sha, after.head_sha, status)
    return WorkflowOutcome(route.name, status, str(bundle.path), response.structured_output, [], errors)


def run_build(
    route: RouteConfig,
    options: RuntimeOptions,
    repo: Path,
    goal: str,
    plan_file: Path,
    approval_file: Path,
) -> WorkflowOutcome:
    before = require_clean(repo)
    plan = load_json_at(repo, plan_file)
    route = select_builder(route, plan, route.model)
    approval, scopes, acceptance, commands = validate_approval(repo, plan_file, approval_file, goal)
    validate_commands(commands)
    bundle = EvidenceBundle(options.evidence_dir, route.name)
    bundle.write_json("git-before.json", before.to_dict())
    bundle.write_json("approved-plan.json", plan)
    bundle.write_json("founder-approval.json", approval)
    response = _agent_run(
        route=route,
        options=options,
        repo=repo,
        prompt=build_prompt(goal, plan, approval, scopes, acceptance, commands, before.to_dict()),
        bundle=bundle,
        allowed_scopes=scopes,
    )
    after_agent = get_state(repo)
    bundle.write_json("git-after-agent.json", after_agent.to_dict())
    errors = list(response.errors)
    if not after_agent.changed_files:
        errors.append("Builder produced no repository changes.")
    if response.structured_output and response.structured_output.get("status") != "implemented":
        errors.append("Builder did not report an implemented result.")
    try:
        enforce_scopes(after_agent.changed_files, scopes)
    except PolicyViolation as exc:
        errors.append(str(exc))
    verification = run_commands(repo, commands, options.verification_timeout_seconds)
    verification_dicts = [item.to_dict() for item in verification]
    bundle.write_json("verification.json", verification_dicts)
    final_state = get_state(repo)
    _write_verification_artifact(bundle, repo, final_state.head_sha, verification)
    bundle.write_json("git-after-verification.json", final_state.to_dict())
    try:
        enforce_scopes(final_state.changed_files, scopes)
    except PolicyViolation as exc:
        errors.append(str(exc))
    if any(item.status != "passed" for item in verification):
        errors.append("One or more independently executed verification commands failed.")
    status = "completed" if response.success and not errors else "failed"
    acceptance_artifact = {
        "schemaVersion": 1,
        "criteria": acceptance,
        "status": "passed" if status == "completed" else "failed",
        "verificationArtifact": "VERIFICATION.json",
        "evidenceSource": "local_evidence",
    }
    handoff_artifact = {
        "schemaVersion": 1,
        "goal": goal,
        "repository": str(repo),
        "startingSha": before.head_sha,
        "currentSha": final_state.head_sha,
        "builder": {"model": route.model, "route": route.name},
        "changedFiles": list(final_state.changed_files),
        "verificationArtifact": "VERIFICATION.json",
        "acceptanceArtifact": "ACCEPTANCE.json",
        "status": status,
        "residualRisks": errors,
        "evidenceSource": "local_evidence",
    }
    bundle.write_json("ACCEPTANCE.json", acceptance_artifact)
    bundle.write_json("HANDOFF.json", handoff_artifact)
    write_canonical_artifact(
        bundle, "PLAN", plan, repository=repo, base_sha=before.head_sha, head_sha=final_state.head_sha, status=status
    )
    write_canonical_artifact(
        bundle,
        "ACCEPTANCE",
        acceptance_artifact,
        repository=repo,
        base_sha=before.head_sha,
        head_sha=final_state.head_sha,
        status=status,
    )
    write_canonical_artifact(
        bundle,
        "HANDOFF",
        handoff_artifact,
        repository=repo,
        base_sha=before.head_sha,
        head_sha=final_state.head_sha,
        status=status,
    )
    _finalize(bundle, route, repo, before.head_sha, final_state.head_sha, status)
    return WorkflowOutcome(route.name, status, str(bundle.path), response.structured_output, verification_dicts, errors)


def run_verify(
    route: RouteConfig,
    options: RuntimeOptions,
    repo: Path,
    goal: str,
    commands: list[str],
) -> WorkflowOutcome:
    before = get_state(repo)
    bundle = EvidenceBundle(options.evidence_dir, route.name)
    results = run_commands(repo, commands, options.verification_timeout_seconds)
    compact = [item.compact() for item in results]
    bundle.write_json("git-before.json", before.to_dict())
    bundle.write_json("verification.json", [item.to_dict() for item in results])
    _write_verification_artifact(bundle, repo, before.head_sha, results)
    response = _agent_run(
        route=route,
        options=options,
        repo=repo,
        prompt=verify_prompt(goal, compact, before.to_dict()),
        bundle=bundle,
    )
    after = get_state(repo)
    bundle.write_json("git-after.json", after.to_dict())
    errors = list(response.errors)
    if any(item.status != "passed" for item in results):
        errors.append("Deterministic verification failed.")
    if error := _unchanged_error(before, after, "Verification route"):
        errors.append(error)
    status = "completed" if response.success and not errors else "failed"
    _finalize(bundle, route, repo, before.head_sha, after.head_sha, status)
    return WorkflowOutcome(route.name, status, str(bundle.path), response.structured_output, [item.to_dict() for item in results], errors)


def run_exact_sha(
    route: RouteConfig,
    options: RuntimeOptions,
    repo: Path,
    goal: str,
    base_ref: str,
    head_ref: str,
    commands: list[str],
) -> WorkflowOutcome:
    if route.name == "review" and not route.independence_verified:
        raise PolicyViolation("Tier-2 review requires Python-verified participant exclusion.")
    validate_commands(commands)
    base_sha = resolve_full_sha(repo, base_ref, require_literal=True)
    head_sha = resolve_full_sha(repo, head_ref, require_literal=True)
    assert_ancestor(repo, base_sha, head_sha)
    files = diff_files(repo, base_sha, head_sha)
    reject_sensitive_changed_paths(files)
    raw_diff, truncated = diff_text(repo, base_sha, head_sha)
    if contains_sensitive_material(raw_diff):
        raise PolicyViolation("Exact-SHA diff appears to contain credential material; capture was blocked before model access.")
    safe_diff = str(redact(raw_diff))
    bundle = EvidenceBundle(options.evidence_dir, route.name)
    bundle.write_json(
        "review-target.json",
        {"repository": str(repo), "baseSha": base_sha, "headSha": head_sha, "changedFiles": files, "diffTruncated": truncated},
    )
    bundle.write_text("review.diff", safe_diff)
    verification: list[VerificationResult] = []
    response: AgentResponse
    worktree_error: str | None = None
    with detached_worktree(repo, head_sha) as worktree:
        before = get_state(worktree)
        verification = run_commands(worktree, commands, options.verification_timeout_seconds) if commands else []
        bundle.write_json("verification.json", [item.to_dict() for item in verification])
        _write_verification_artifact(bundle, repo, head_sha, verification)
        compact = [item.compact() for item in verification]
        if route.name in {"review", "tier1-review"}:
            prompt = review_prompt(goal, str(repo), base_sha, head_sha, files, safe_diff, truncated, compact)
        elif route.name == "architecture-validation":
            prompt = architecture_prompt(goal, str(repo), base_sha, head_sha, files, safe_diff, truncated, compact)
        else:
            prompt = release_prompt(goal, str(repo), base_sha, head_sha, files, safe_diff, truncated, compact)
        response = _agent_run(route=route, options=options, repo=worktree, prompt=prompt, bundle=bundle)
        after = get_state(worktree)
        bundle.write_json("worktree-before.json", before.to_dict())
        bundle.write_json("worktree-after.json", after.to_dict())
        worktree_error = _unchanged_error(before, after, "Exact-SHA review worktree")
    errors = list(response.errors)
    if worktree_error:
        errors.append(worktree_error)
    if truncated:
        errors.append("Diff exceeded the evidence cap and was truncated; approval/readiness cannot be asserted.")
    if any(item.status != "passed" for item in verification):
        errors.append("One or more exact-SHA verification commands failed.")
    status = "completed" if response.success and not errors else "failed"
    if response.structured_output is not None:
        artifact = {
            "review": "TIER2_REVIEW.json",
            "tier1-review": "REVIEW.json",
            "architecture-validation": "ARCHITECTURE_VALIDATION.json",
        }.get(route.name, "RELEASE_READINESS.json")
        bundle.write_json(artifact, response.structured_output)
        canonical = {"TIER2_REVIEW.json": "TIER2_REVIEW", "REVIEW.json": "REVIEW"}.get(artifact)
        if canonical:
            write_canonical_artifact(
                bundle,
                canonical,
                response.structured_output,
                repository=repo,
                base_sha=base_sha,
                head_sha=head_sha,
                status=status,
            )
    _finalize(bundle, route, repo, base_sha, head_sha, status)
    return WorkflowOutcome(
        route.name,
        status,
        str(bundle.path),
        response.structured_output,
        [item.to_dict() for item in verification],
        errors,
    )


def run_fix_until_green(
    route: RouteConfig,
    options: RuntimeOptions,
    repo: Path,
    goal: str,
    scopes_input: tuple[str, ...],
    commands: list[str],
    max_rounds: int,
) -> WorkflowOutcome:
    if not 1 <= max_rounds <= 3:
        raise PolicyViolation("Repair max_rounds must be between 1 and 3.")
    before = require_clean(repo)
    scopes = validate_scopes(repo, scopes_input)
    validate_commands(commands)
    bundle = EvidenceBundle(options.evidence_dir, route.name)
    bundle.write_json("git-before.json", before.to_dict())
    fingerprints: set[str] = set()
    all_errors: list[str] = []
    last_structured: dict[str, Any] | None = None
    last_results: list[VerificationResult] = []
    for round_number in range(1, max_rounds + 1):
        results = run_commands(repo, commands, options.verification_timeout_seconds)
        last_results = results
        bundle.write_json(f"round-{round_number:02d}-verification-before.json", [item.to_dict() for item in results])
        if all(item.status == "passed" for item in results):
            after = get_state(repo)
            enforce_scopes(after.changed_files, scopes)
            bundle.write_json("git-after.json", after.to_dict())
            _write_verification_artifact(bundle, repo, after.head_sha, results)
            acceptance = {
                "schemaVersion": 1,
                "status": "passed",
                "verificationArtifact": "VERIFICATION.json",
                "evidenceSource": "local_evidence",
            }
            handoff = {
                "schemaVersion": 1,
                "goal": goal,
                "repository": str(repo),
                "startingSha": before.head_sha,
                "currentSha": after.head_sha,
                "changedFiles": list(after.changed_files),
                "verificationArtifact": "VERIFICATION.json",
                "acceptanceArtifact": "ACCEPTANCE.json",
                "status": "completed",
                "residualRisks": all_errors,
                "evidenceSource": "local_evidence",
            }
            bundle.write_json("ACCEPTANCE.json", acceptance)
            bundle.write_json("HANDOFF.json", handoff)
            write_canonical_artifact(
                bundle, "ACCEPTANCE", acceptance, repository=repo,
                base_sha=before.head_sha, head_sha=after.head_sha, status="completed",
            )
            write_canonical_artifact(
                bundle, "HANDOFF", handoff, repository=repo,
                base_sha=before.head_sha, head_sha=after.head_sha, status="completed",
            )
            _finalize(bundle, route, repo, before.head_sha, after.head_sha, "completed")
            return WorkflowOutcome(route.name, "completed", str(bundle.path), last_structured, [item.to_dict() for item in results], all_errors)
        fingerprint = f"{failure_fingerprint(results)}:{working_tree_fingerprint(repo)}"
        if fingerprint in fingerprints:
            all_errors.append("Verification failure repeated without progress; bounded loop stopped.")
            break
        fingerprints.add(fingerprint)
        state_before_agent = get_state(repo)
        content_before_agent = working_tree_fingerprint(repo)
        response = _agent_run(
            route=route,
            options=options,
            repo=repo,
            prompt=repair_prompt(
                goal,
                round_number,
                scopes,
                [item.compact() for item in results if item.status != "passed"],
                state_before_agent.changed_files,
            ),
            bundle=bundle,
            allowed_scopes=scopes,
            evidence_prefix=f"round-{round_number:02d}-",
        )
        last_structured = response.structured_output
        all_errors.extend(response.errors)
        if not response.success:
            all_errors.append("Repair agent did not return a valid structured result; bounded loop stopped.")
            break
        state_after_agent = get_state(repo)
        content_after_agent = working_tree_fingerprint(repo)
        enforce_scopes(state_after_agent.changed_files, scopes)
        bundle.write_json(f"round-{round_number:02d}-git-after.json", state_after_agent.to_dict())
        if content_after_agent == content_before_agent:
            all_errors.append("Repair round produced no working-tree content change; bounded loop stopped.")
            break
    final_state = get_state(repo)
    bundle.write_json("git-after.json", final_state.to_dict())
    _write_verification_artifact(bundle, repo, final_state.head_sha, last_results)
    handoff_artifact = {
        "schemaVersion": 1,
        "goal": goal,
        "repository": str(repo),
        "startingSha": before.head_sha,
        "currentSha": final_state.head_sha,
        "attempts": len(fingerprints),
        "failureFingerprints": sorted(fingerprints),
        "changedFiles": list(final_state.changed_files),
        "verificationArtifact": "VERIFICATION.json",
        "status": "failed",
        "residualRisks": all_errors,
        "nextAction": "architecture-validation-or-founder-escalation",
        "evidenceSource": "local_evidence",
    }
    bundle.write_json("HANDOFF.json", handoff_artifact)
    write_canonical_artifact(
        bundle,
        "HANDOFF",
        handoff_artifact,
        repository=repo,
        base_sha=before.head_sha,
        head_sha=final_state.head_sha,
        status="failed",
    )
    _finalize(bundle, route, repo, before.head_sha, final_state.head_sha, "failed")
    return WorkflowOutcome(
        route.name,
        "failed",
        str(bundle.path),
        last_structured,
        [item.to_dict() for item in last_results],
        all_errors or [f"Verification did not pass within {max_rounds} rounds."],
    )


def dry_run_preview(
    *,
    route: RouteConfig,
    options: RuntimeOptions,
    repo: Path,
    goal: str,
    plan_file: Path | None = None,
    approval_file: Path | None = None,
    base_ref: str | None = None,
    head_ref: str | None = None,
    commands: list[str] | None = None,
    scopes_input: tuple[str, ...] = (),
    max_rounds: int | None = None,
) -> dict[str, Any]:
    _validate_backend(route, options)
    _validate_route_agents(repo, route)
    auth = preflight_auth(
        mode=options.billing_mode,
        repo=repo,
        claude_path=options.claude_path,
        allow_api_billing=options.allow_api_billing,
        max_budget_usd=options.max_budget_usd,
    )
    auth = enforce_model_billing_policy(
        auth, model=route.model, allow_usage_credits=options.allow_usage_credits
    )
    state = get_state(repo)
    preview: dict[str, Any] = {
        "status": "dry-run",
        "version": 1,
        "route": _route_public_dict(route),
        "goal": goal,
        "repository": state.to_dict(),
        "backend": options.backend,
        "billingMode": options.billing_mode,
        "usageCreditsAcknowledged": options.allow_usage_credits,
        "billing": auth.public_dict(),
        "wouldInvokeClaude": False,
        "wouldRunVerification": False,
        "wouldCreateWorktree": False,
        "wouldWriteEvidence": False,
    }
    supplied_commands = commands or []
    if route.name == "build":
        if not plan_file or not approval_file:
            raise PolicyViolation("Build dry-run requires plan and approval files.")
        require_clean(repo)
        _, scopes, acceptance, approved_commands = validate_approval(repo, plan_file, approval_file, goal)
        validate_commands(approved_commands)
        preview.update(
            {
                "allowedScopes": scopes,
                "acceptanceCriteria": acceptance,
                "verificationCommands": approved_commands,
                "wouldRunVerification": True,
            }
        )
    elif route.exact_sha:
        if not base_ref or not head_ref:
            raise PolicyViolation("Exact-SHA dry-run requires base and head SHAs.")
        validate_commands(supplied_commands)
        base_sha = resolve_full_sha(repo, base_ref, require_literal=True)
        head_sha = resolve_full_sha(repo, head_ref, require_literal=True)
        assert_ancestor(repo, base_sha, head_sha)
        files = diff_files(repo, base_sha, head_sha)
        reject_sensitive_changed_paths(files)
        preview.update(
            {
                "baseSha": base_sha,
                "headSha": head_sha,
                "changedFiles": files,
                "verificationCommands": supplied_commands,
                "wouldRunVerification": bool(supplied_commands),
                "wouldCreateWorktree": True,
            }
        )
    elif route.name == "fix-until-green":
        require_clean(repo)
        scopes = validate_scopes(repo, scopes_input)
        validate_commands(supplied_commands)
        preview.update(
            {
                "allowedScopes": scopes,
                "verificationCommands": supplied_commands,
                "maxRounds": max_rounds,
                "wouldRunVerification": True,
            }
        )
    elif route.name == "verify":
        validate_commands(supplied_commands)
        preview.update({"verificationCommands": supplied_commands, "wouldRunVerification": True})
    return preview
