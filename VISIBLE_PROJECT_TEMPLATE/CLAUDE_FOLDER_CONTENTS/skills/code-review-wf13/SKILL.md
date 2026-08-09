---
name: code-review-wf13
description: Run FounderOS WF-13 code review with role separation, exact change scope, tests, findings disposition, and auditable evidence.
argument-hint: "<base-sha> <head-sha> [review tier]"
disable-model-invocation: true
---

# WF-13 code review

Confirm the workflow version and governing role registry before review. Record builder, reviewer tier, base/head SHAs, repository, changed files, and whether the reviewer is independent.

Review the immutable diff for behavior, contracts, tests, security, governance, observability, and rollback. Findings must be evidence-backed and dispositioned. The builder remains accountable for remediation; the reviewer must not silently patch findings and then approve its own changes.

Create an evidence block containing:
- workflow/run identifier;
- participants and models;
- exact SHA pair;
- commands and results;
- findings and dispositions;
- final controlled verdict;
- remaining approval/merge/deployment gates.

Do not equate a WF-13 review verdict with Founder authorization. Re-run against every new head SHA.
