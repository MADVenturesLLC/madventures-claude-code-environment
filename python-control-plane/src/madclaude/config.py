from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

RouteName = Literal[
    "plan",
    "build",
    "verify",
    "review",
    "tier1-review",
    "release-readiness",
    "repo-audit",
    "security-audit",
    "ui-review",
    "fix-until-green",
    "architecture-validation",
]


@dataclass(frozen=True)
class RouteConfig:
    name: str
    model: str
    effort: str
    max_turns: int
    mutates: bool
    tools: tuple[str, ...]
    permission_mode: str
    schema: str
    description: str
    exact_sha: bool = False
    strict_mcp: bool = True
    subagents: tuple[str, ...] = ()
    eligible_models: tuple[str, ...] = ()
    independence_verified: bool = False


# Model aliases intentionally resolve through the authenticated Claude Code account. Availability can
# differ by account/provider, so the package does not hard-code dated model identifiers.
ROUTES: dict[str, RouteConfig] = {
    "plan": RouteConfig(
        name="plan",
        model="fable",
        effort="high",
        max_turns=28,
        mutates=False,
        tools=("Read", "Grep", "Glob", "Agent"),
        permission_mode="dontAsk",
        schema="plan",
        description="Architecture and implementation planning grounded in repository evidence.",
        subagents=("founder-os-explorer", "dependency-mapper"),
        eligible_models=("fable",),
    ),
    "build": RouteConfig(
        name="build",
        model="sonnet",
        effort="high",
        max_turns=48,
        mutates=True,
        tools=("Read", "Grep", "Glob", "Edit", "Write"),
        permission_mode="acceptEdits",
        schema="build",
        description="Founder-approved bounded implementation; Python runs verification independently.",
        eligible_models=("grok", "sonnet", "opus", "codex", "hermes"),
    ),
    "verify": RouteConfig(
        name="verify",
        model="opus",
        effort="high",
        max_turns=24,
        mutates=False,
        tools=("Read", "Grep", "Glob"),
        permission_mode="dontAsk",
        schema="verify",
        description="Interpret deterministic command evidence without editing source files.",
        eligible_models=("opus", "haiku"),
    ),
    "review": RouteConfig(
        name="review",
        model="fable",
        effort="xhigh",
        max_turns=36,
        mutates=False,
        tools=("Read", "Grep", "Glob"),
        permission_mode="dontAsk",
        schema="review",
        description="Independent exact-SHA review in an isolated detached worktree.",
        exact_sha=True,
        eligible_models=("fable", "opus", "haiku"),
    ),
    "tier1-review": RouteConfig(
        name="tier1-review",
        model="opus",
        effort="high",
        max_turns=30,
        mutates=False,
        tools=("Read", "Grep", "Glob"),
        permission_mode="dontAsk",
        schema="review",
        description="Read-only exact-SHA Tier-1 technical review recorded before Tier-2 selection.",
        exact_sha=True,
        eligible_models=("opus", "sonnet", "fable", "codex"),
    ),
    "release-readiness": RouteConfig(
        name="release-readiness",
        model="fable",
        effort="xhigh",
        max_turns=36,
        mutates=False,
        tools=("Read", "Grep", "Glob"),
        permission_mode="dontAsk",
        schema="release-readiness",
        description="Exact-SHA release evidence assessment without merge or deployment authority.",
        exact_sha=True,
        eligible_models=("fable", "opus", "haiku"),
    ),
    "repo-audit": RouteConfig(
        name="repo-audit",
        model="opus",
        effort="high",
        max_turns=42,
        mutates=False,
        tools=("Read", "Grep", "Glob", "Agent"),
        permission_mode="dontAsk",
        schema="repo-audit",
        description="Repository-wide architecture, quality, security, performance, and governance audit.",
        subagents=(
            "founder-os-explorer",
            "dependency-mapper",
            "security-reviewer",
            "performance-optimizer",
            "governance-auditor",
        ),
        eligible_models=("opus", "fable"),
    ),
    "security-audit": RouteConfig(
        name="security-audit",
        model="fable",
        effort="high",
        max_turns=40,
        mutates=False,
        tools=("Read", "Grep", "Glob", "Agent"),
        permission_mode="dontAsk",
        schema="security-audit",
        description="Adversarial repository security audit with evidence and uncertainty labels.",
        subagents=("security-reviewer", "adversarial-verifier"),
        eligible_models=("fable", "opus"),
    ),
    "ui-review": RouteConfig(
        name="ui-review",
        model="opus",
        effort="high",
        max_turns=36,
        mutates=False,
        tools=("Read", "Grep", "Glob", "Agent"),
        permission_mode="dontAsk",
        schema="ui-review",
        description="Truthful UI implementation review; no invented runtime or visual evidence.",
        subagents=("ui-reviewer", "founder-os-explorer"),
        eligible_models=("opus", "fable"),
    ),
    "fix-until-green": RouteConfig(
        name="fix-until-green",
        model="sonnet",
        effort="high",
        max_turns=32,
        mutates=True,
        tools=("Read", "Grep", "Glob", "Edit", "Write"),
        permission_mode="acceptEdits",
        schema="fix-until-green",
        description="Bounded repair rounds driven by Python-executed verification failures.",
        eligible_models=("sonnet", "opus", "codex"),
    ),
    "architecture-validation": RouteConfig(
        name="architecture-validation",
        model="opus",
        effort="max",
        max_turns=36,
        mutates=False,
        tools=("Read", "Grep", "Glob"),
        permission_mode="dontAsk",
        schema="architecture-validation",
        description="Read-only exact-SHA validation of architecture invariants; separate from Tier-2.",
        exact_sha=True,
        eligible_models=("opus",),
    ),
}


def get_route(
    name: str,
    *,
    model: str | None = None,
    effort: str | None = None,
    max_turns: int | None = None,
) -> RouteConfig:
    try:
        route = ROUTES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown route: {name}") from exc
    selected_model = model or route.model
    if selected_model not in route.eligible_models:
        raise ValueError(
            f"Model {selected_model!r} is not eligible for route {name!r}; "
            f"allowed: {', '.join(route.eligible_models)}"
        )
    if effort is not None and effort != route.effort:
        raise ValueError(f"Effort override {effort!r} is not eligible for route {name!r}; required: {route.effort}")
    if max_turns is not None and not 1 <= max_turns <= route.max_turns:
        raise ValueError(f"max_turns for route {name!r} must be between 1 and {route.max_turns}")
    return replace(
        route,
        model=selected_model,
        effort=effort or route.effort,
        max_turns=max_turns or route.max_turns,
    )
