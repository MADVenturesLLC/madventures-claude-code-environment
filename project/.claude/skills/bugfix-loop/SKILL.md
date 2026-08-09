---
name: bugfix-loop
description: Drive a bug from reproducible evidence through root cause, minimal correction, regression test, and verified closure without speculative edits.
argument-hint: "<bug, failing test, or incident>"
disable-model-invocation: true
---

# Evidence-first bug-fix loop

1. **Reproduce:** capture the exact command, environment, input, observed output, expected output, and frequency. Do not begin by changing code.
2. **Reduce:** find the smallest failing path. Trace callers, state boundaries, flags, persistence, mocks, and recent changes.
3. **Root cause:** explain the causal chain and identify the first incorrect state transition or assumption. Separate the root cause from downstream symptoms.
4. **Lock with a test:** add a failing regression test or deterministic verification when feasible. If no automated test is possible, define a repeatable manual check and why.
5. **Fix minimally:** change the smallest coherent surface; preserve unrelated behavior. Avoid broad refactors during incident correction.
6. **Verify both directions:** prove the regression now passes and that adjacent behavior remains intact. Run lint/typecheck/build/runtime checks proportional to risk.
7. **Adversarial review:** ask an independent reviewer how the fix could be incomplete, overfit, unsafe, or masking a second defect.
8. **Report:** include reproduction, root cause, changed files, test evidence, residual risk, and state.

Stop rather than guess when reproduction depends on unavailable secrets, production-only data, or an unverified external system. Never label a symptom suppression as root-cause resolution.
