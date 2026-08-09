---
name: workflow-author
description: Design or extend a governed Python control-plane route with explicit evidence, authority, model, scope, and stop boundaries.
argument-hint: "<workflow capability>"
disable-model-invocation: true
---

# Author a governed workflow capability

Python is the only authoritative orchestration engine. Do not create executable JavaScript workflows
or use prompt text as an enforcement bridge.

1. Reuse an existing `madclaude` route or `repo-audit --profile` when it covers the capability.
2. Define inputs, immutable target, evidence source, output schema, mutation policy, and stop condition.
3. Keep one accountable builder per worktree; Python runs verification independently.
4. Keep model and effort choices inside the route eligibility envelope.
5. Require SHA-bound Founder approval before mutation and participation records before Tier-2.
6. Emit canonical artifacts plus `EXECUTION_RECORD.json`; never store hidden reasoning.
7. Add the smallest test that proves the new gate or branch and run the full control-plane harness.

Never expose approval grant, unrestricted checkpoint restore, merge, deploy, activation, protected
authority mutation, credentials, or production writes through a model-callable surface.
