---
name: repository-audit
description: Audit an entire repository for architecture, governance, tests, security, operability, stale state, and prioritized execution gaps.
argument-hint: "[repository or audit focus]"
disable-model-invocation: true
---

# Full repository audit

Use bounded parallel exploration for architecture, tests/CI, dependencies, security, governance/docs, and runtime/operations. Synthesize conclusions in the main context.

Evaluate:
- stated purpose versus actual code;
- entry points and dependency boundaries;
- dead, duplicated, or unreachable paths;
- configuration and environment contracts;
- test quality, skipped/flaky coverage, and CI truth;
- secrets, permissions, supply-chain and deployment risk;
- observability, failure recovery, and data durability;
- stale docs, contradictory decisions, and unimplemented claims;
- maintenance hotspots and upgrade debt.

Findings first, with evidence and severity. Then provide an architecture map, maturity scores, top five risks, top five high-leverage improvements, a sequenced backlog, and what must be verified in a live environment. Distinguish source-level evidence from production behavior.
