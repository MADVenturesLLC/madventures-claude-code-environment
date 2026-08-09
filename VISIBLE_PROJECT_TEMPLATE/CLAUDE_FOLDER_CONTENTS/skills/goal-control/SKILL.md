---
name: goal-control
description: Define a bounded autonomous Claude Code goal with a machine-verifiable completion condition, no-progress limit, safety gates, and final evidence report.
argument-hint: "<desired end state and verifier>"
disable-model-invocation: true
---

# Governed autonomy with goals

Use a goal only when completion can be checked objectively.

## Goal contract
Define:
1. the exact end state;
2. one or more executable verifiers;
3. allowed mutation scope;
4. prohibited files and external systems;
5. maximum rounds or no-progress threshold;
6. Founder stop gates;
7. required final evidence.

Good completion conditions include a named test suite passing, a type-check returning zero, a reproducible build succeeding, or a bounded issue list reaching zero. “Improve the codebase” is not a valid goal.

## Safety
Do not place merge, deployment, activation, governance authority, credential work, destructive recovery, or production mutation inside an autonomous goal. Stop after two consecutive rounds with no measurable progress or when the same failure signature repeats without new evidence.

## Recommended prompt shape

```text
/goal The task is complete when <verifier> passes. You may edit only <scope>. Stop immediately for <authority gates>. Run at most <N> repair rounds, stop after two no-progress rounds, and return changed files plus exact command evidence.
```

## Final evidence
Report the verifier command, exit status, relevant output, changed files, residual risks, unverified claims, and the next human decision. Never equate a passing local check with merge, deployment, or activation.
