---
name: multi-agent-build
description: Run a bounded FounderOS multi-agent build with cheap evidence fan-out, expensive judgment, one accountable builder, and independent verification.
argument-hint: "<build goal>"
disable-model-invocation: true
---

# Multi-agent build protocol

## Topology
Use this default graph, pruning roles that add no value:

Founder request → exploration fan-out → architecture planner → one accountable builder → test verifier → specialist reviewers → independent judge → Founder decision.

## Rules
- Spawn multiple Haiku explorers only for independent search domains: architecture, tests, governance, dependencies, and runtime truth. Give each a bounded question.
- Send compact evidence summaries to the planner. Do not flood the main context with raw file contents.
- Use Fable/high effort for architecture when a wrong decision is expensive; otherwise inherit the session model.
- Designate exactly one accountable implementation owner. Parallel builders must use isolated worktrees and non-overlapping ownership.
- Use Sonnet for ordinary implementation and testing; Opus for demanding diagnosis/review; Fable/xhigh for adversarial or final judgment.
- A reviewer must not review its own authored changes. The exact-SHA independent reviewer cannot edit.
- Cap concurrency; default to no more than eight active subagents unless the task and environment justify more.
- Record outputs, failures, and unresolved disagreement. Consensus is not evidence.

## Stop gates
Stop for Founder authority before governance changes, external writes, merges, deployments, activation, destructive recovery, or material scope expansion.

## Final synthesis
Return one coherent decision: architecture chosen, alternatives rejected, changes made, verification, review findings, cost/agent usage, residual risk, and next gate.
