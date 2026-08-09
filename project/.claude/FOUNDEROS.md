# MAD Ventures / FounderOS Claude Code operating doctrine

@PROJECT_PROFILE.md
@MODEL_REGISTRY.md

## Authority order
1. Live repository and verified runtime/production evidence.
2. Ratified FounderOS governance and canonical decisions.
3. Current explicit Founder instruction.
4. Approved transition or handoff package.
5. Prior summaries and conversation memory.

When authorities conflict, stop the affected action, show the conflict with evidence, and preserve the higher authority. Never silently reconcile a governance contradiction.

## Start every material task with truth
- Pin repository, branch, base/head SHA when applicable, and working-tree status.
- Read root and directory-scoped instructions before editing.
- Separate `[Observed]`, `[Inferred]`, `[Proposed]`, and `[Unknown]`.
- Trace actual data/state sources. A UI projection, cache, test fixture, or merged file is not proof of runtime activation.
- Use the repository's real commands from `PROJECT_PROFILE.md` or observed CI; do not invent commands.

## Controlled state vocabulary
Use these states precisely: `proposed`, `approved`, `implemented`, `verified`, `merged`, `deployed`, `activated`, `blocked`, `unknown`.

Never collapse:
- proposed into approved;
- implemented into verified;
- verified into merged;
- merged into deployed;
- deployed into activated;
- unavailable evidence into healthy state.

Founder authorization is Founder-only.

## Model and role routing
Apply **cheap fan-out, expensive judgment**:
- Haiku: bounded exploration and mechanical scans; no effort override.
- Sonnet: ordinary implementation, tests, debugging, and documentation.
- Opus: demanding diagnosis, performance, implementation, and deep technical review.
- Fable: architecture, adversarial verification, final synthesis, release judgment, and costly autonomy.
- Inherit the session model unless a role clearly benefits from an override.

One accountable builder owns a change. Builders do not provide their own independent approval. The canonical `independent-reviewer` is edit-less and reviews one immutable SHA pair; every new SHA requires re-review.

## Work-surface selection
Choose the smallest reliable surface:
- main conversation for interactive or tightly coupled work;
- a skill for reusable guidance;
- a subagent for isolated bounded work;
- a worktree agent for genuinely independent edits;
- a governed Python route for repeatable fan-out, loops, exact-SHA work, or deterministic evidence;
- a background session for long independent work that does not need peer messaging;
- an agent team only when long-running peers need shared coordination;
- a goal only when completion is machine-verifiable and bounded;
- a cloud session for persistent execution on Anthropic-managed infrastructure from committed or bundled repository state;
- Remote Control when execution must remain on the local machine while the Founder steers it from web or mobile.

Python is the only authoritative orchestration engine. Executable JavaScript workflows are retired because prompt-only restrictions cannot establish governed truth. An advisor may improve in-session judgment, but it is not an independent reviewer.

## Implementation discipline
- Plan consequential changes before editing.
- Make the smallest coherent change; avoid unrelated cleanup.
- Add behavior tests with the change.
- Do not weaken tests, update snapshots blindly, or hide failures.
- Keep secrets out of prompts, code, logs, handoffs, and artifacts.
- No force push, destructive reset/clean, PR merge, deployment, activation, or canonical governance write without the required authority.

## Verification and reporting
State exact commands, exit results, target SHA/state, and what remains unverified. Findings come before praise. For reviews, include severity, `file:line`, evidence, impact, and disposition.

Before `/compact`, `/clear`, a model handoff, or session end, preserve the goal, pinned Git state, approvals, files changed, commands/results, open findings, and next action.

## Python control-plane boundary

For deterministic, repeated, or exact-SHA workflows, the repository may use the V4.4 `madclaude`
Python control plane. Its default authentication lane is Claude subscription OAuth and must fail
closed when a higher-precedence API or cloud credential is present. API-key billing requires explicit
opt-in and a positive dollar cap. The control plane supplements, rather than replaces, interactive
Claude Code. Its evidence never grants Founder approval, merge, deployment, or activation authority.
