---
name: release-readiness
description: Evaluate an immutable release candidate across code, tests, migrations, security, observability, rollback, deployment, and FounderOS authority gates.
argument-hint: "<tag|sha|release candidate>"
disable-model-invocation: true
---

# Release-readiness gate

Pin the candidate SHA/tag and target environment. A moving branch is not a release candidate.

## Evidence domains
1. **Code integrity:** clean diff, intended files only, generated artifacts understood, dependencies locked.
2. **Verification:** lint, typecheck, tests, build, runtime checks, visual/accessibility checks where applicable.
3. **Data:** migrations reviewed, backward/forward compatibility, backups, restore/rollback, reconciliation.
4. **Security:** secrets, permissions, authentication/authorization, external writes, dependency risks.
5. **Operations:** config/flags, observability, alerts, runbook, ownership, failure containment.
6. **Governance:** required reviews, exact-SHA dispositions, Founder approvals, protected decision state.
7. **Deployment:** target, sequence, health criteria, rollback trigger, post-deploy verification.

## Verdict
Return `READY`, `READY WITH EXPLICIT CONDITIONS`, `NOT READY`, or `BLOCKED BY MISSING EVIDENCE`. List every condition with an owner and proof required.

Do not deploy or activate. Do not infer production health from CI, merge status, or a local build. State separately whether the candidate is implemented, verified, merged, deployed, and activated.
