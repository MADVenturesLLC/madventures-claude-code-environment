---
name: governed-feature
description: Implement a FounderOS or MAD Ventures feature through evidence, plan, bounded edits, tests, independent review, and explicit state reporting.
argument-hint: "<feature request>"
disable-model-invocation: true
---

# Governed feature delivery

## Gate 1 — Establish truth
Run the onboarding procedure. Pin repository state, governing decisions, requested behavior, data authority, feature flags, and acceptance criteria. Refuse to invent unavailable runtime, approval, ledger, or deployment state.

## Gate 2 — Plan before editing
Map the smallest coherent change set, affected contracts, migration/rollback needs, tests, security consequences, UI truth rules, and verification commands. Identify protected paths and Founder approvals. For consequential architecture, obtain an independent architecture judgment before building.

## Gate 3 — Implement narrowly
Use the approved builder role. Preserve public contracts unless change is explicit. Add or update tests with the behavior. Avoid opportunistic refactors. Keep generated artifacts, lockfiles, and migrations intentional.

## Gate 4 — Verify
Run formatting/lint, typecheck, targeted tests, broader tests where justified, build, and runtime/visual checks. Record exact commands, exit codes, and failures. “Tests passed” is not evidence unless the command and scope are stated.

## Gate 5 — Review
Use a reviewer independent of the builder. For governed or high-risk changes, pin the exact head SHA and run the canonical Tier-2 reviewer. Dispose every finding with evidence; a new SHA invalidates the earlier exact-SHA verdict.

## Gate 6 — Report state precisely
Distinguish `proposed`, `approved`, `implemented`, `verified`, `merged`, `deployed`, `activated`, `blocked`, and `unknown`. Do not collapse merged into deployed or deployed into activated. Founder authorization remains Founder-only.

## Deliverable
Provide changed files, behavior, verification evidence, review disposition, unresolved risks, and the exact next controlled action.
