---
name: pr-tier2-review
description: Prepare and execute an independent FounderOS Tier-2 review against one immutable base/head SHA pair with findings-first output.
argument-hint: "<repo> <base-sha> <head-sha> [scope]"
disable-model-invocation: true
---

# Canonical Tier-2 exact-SHA review

## Preconditions
Require:
- repository identity;
- governing review contract/DEC;
- base SHA and full head SHA;
- changed-file scope;
- builder identity or explicit statement that the reviewer did not author the change.

Resolve both SHAs locally and confirm the diff is immutable. Do not substitute the current branch head, PR head, or a newer commit.

## Review
Inspect the exact range for correctness, architecture, data/state truth, tests, security, failure modes, accessibility where relevant, governance, and scope drift. Run read-only commands and tests as appropriate. Do not edit files, install dependencies, commit, push, merge, deploy, activate, or authorize.

## Findings format
Findings first, ordered by severity. Each finding must include:
- severity and concise title;
- exact `file:line` or range;
- observed evidence;
- impact/failure mode;
- required disposition or proof that makes it non-blocking.

Then provide:
- exact base/head reviewed;
- commands and results;
- assumptions/unknowns;
- controlled verdict: `APPROVE`, `APPROVE WITH NON-BLOCKING FINDINGS`, `REQUEST CHANGES`, or `BLOCKED`.

A verdict applies only to the stated head SHA. Any code change, even a finding fix, creates a new head and requires re-review. Never call this Founder approval.
