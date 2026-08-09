---
name: founderos-onboard
description: Establish repository truth, governing authority, commands, risks, and current state before any FounderOS or MAD Ventures work begins.
argument-hint: "[optional focus or repository path]"
disable-model-invocation: true
---

# FounderOS onboarding

## Outcome
Produce a compact, evidence-backed repository map that lets a builder begin without guessing. This is a discovery step, not implementation.

## Procedure
1. Confirm the repository root, current branch, `git status --short`, latest commit, remotes, and whether the requested target is a branch, working tree, PR, or immutable SHA.
2. Read, in authority order, the root `CLAUDE.md`, `.claude/CLAUDE.md`, `.claude/FOUNDEROS.md`, `PROJECT_PROFILE.md`, applicable `.claude/rules/`, repository governance documents, and the closest directory-scoped instructions.
3. Identify the repository type: doctrine/governance, runtime, console, SaaS product, library, or infrastructure.
4. Locate entry points, package manager, build/test/lint/typecheck commands, CI definitions, migrations, environment contracts, deployment surfaces, and protected authority paths.
5. Trace the requested area through callers, state sources, tests, and verification surfaces. Distinguish live behavior from documentation, proposed behavior, mocks, fixtures, and projections.
6. Search for unfinished work, contradictory instructions, skipped tests, feature flags, unsafe defaults, and stale references that materially affect the task.
7. Fill or update `.claude/PROJECT_PROFILE.md` only when explicitly authorized. Otherwise report missing profile fields.

## Required output
Use this order:

- **Controlled status:** repository, branch/SHA, clean/dirty, scope.
- **Authority map:** governing files and any conflicts.
- **Architecture map:** entry points, data flow, tests, verification.
- **Commands:** exact install, lint, typecheck, test, build, and runtime checks actually observed.
- **Risks and unknowns:** evidence gaps and state ambiguity.
- **Recommended next action:** the smallest safe next step.

Label statements `[Observed]`, `[Inferred]`, `[Proposed]`, or `[Unknown]`. Do not edit code, silently resolve governance conflicts, or claim a system state that was not verified.
