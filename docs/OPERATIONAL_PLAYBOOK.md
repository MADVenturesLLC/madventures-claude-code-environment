# MAD Ventures / FounderOS operational playbook

This is the recommended end-to-end operating sequence for Claude Code. It is intentionally stricter than a generic coding assistant workflow because FounderOS separates evidence, implementation, review, authorization, deployment, and activation.

## 1. Pin truth before choosing a tool

Record:

```bash
pwd
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
git remote -v
```

Then read:

```text
.claude/CLAUDE.md
.claude/FOUNDEROS.md
.claude/PROJECT_PROFILE.md
.claude/MODEL_REGISTRY.md
nearest directory-scoped CLAUDE.md and rules
ratified decisions relevant to the task
```

Inside Claude Code:

```text
/founderos-onboard
```

Stop if repository, branch, objective, authority, or verification commands are unknown.

## 2. Classify the request

Use:

```text
/founder-command <goal>
/model-route <goal>
```

Choose the smallest reliable surface:

- main conversation for tightly coupled interactive work;
- skill for a reusable procedure;
- subagent for bounded context isolation;
- worktree/background session for independent editing;
- workflow for repeatable fan-out, schemas, or loops;
- agent team only when peers need direct coordination;
- `/goal` only for machine-verifiable bounded autonomy;
- cloud for Anthropic-managed persistent execution;
- Remote Control for local execution steered remotely.

Do not start with a multi-agent fleet merely because it is available.

## 3. Route models by role

Default:

- Haiku: exploration and mechanical fan-out;
- Sonnet: everyday implementation and tests;
- Opus: difficult implementation, diagnosis, performance, deep review;
- Fable: architecture, adversarial judgment, final synthesis, costly autonomy;
- inherit when no clear override is justified.

Optional:

```bash
claude --model sonnet --effort high --advisor opus
```

Use the advisor for intermittent hard decisions, never as Tier-2 independence.

External builders and reviewers must be listed in `.claude/MODEL_REGISTRY.md` and have a per-run audit record.

## 4. Investigate before planning

For an unfamiliar or high-risk task:

```text
Explore how <behavior> actually works. Return concise observed evidence, file/line locations, state sources, tests, and unknowns. Do not edit.
```

Or invoke:

```text
/founder-plan <goal>
```

A valid investigation distinguishes:

- observed runtime/repository evidence;
- inferred behavior;
- proposed change;
- unknown/unavailable evidence.

Do not use a UI projection, test fixture, cached value, or merged file as proof of production activation.

## 5. Produce an approval-ready plan

The plan must include:

- goal and non-goals;
- current observed behavior;
- architecture and data-flow impact;
- exact files/subsystems likely to change;
- role/model assignment;
- testing and runtime verification;
- security, governance, migration, rollout, and rollback implications;
- acceptance criteria;
- stop conditions and unresolved questions.

For material scope, stop after the plan and obtain Founder approval. Save approved plans into the repository when cloud/autonomous execution will rely on them.

## 6. Build through one accountable lane

Interactive route:

```text
/governed-feature
```

Structured workflow route:

```text
/founder-build {
  "goal": "...",
  "approvedPlan": "docs/approved-plan.md",
  "founderApproved": true,
  "approvalReference": "Founder message / decision reference",
  "allowedScope": ["src/...", "tests/..."]
}
```

Build rules:

- one builder owns the coherent diff;
- use worktrees for parallel editors;
- no unrelated cleanup;
- preserve protected paths;
- add behavior tests with the change;
- do not weaken tests or blindly update snapshots;
- stop on authority, credential, destructive, merge, deploy, or activation gates.

## 7. Verify from evidence

Run the real commands from `PROJECT_PROFILE.md` or observed CI:

```text
/founder-verify
```

Verification should cover, as applicable:

- formatting/lint;
- type checking;
- focused unit/integration tests;
- full relevant regression suite;
- build/package output;
- runtime behavior;
- security and dependency checks;
- UI rendering, accessibility, reduced motion, state truth, and performance;
- migration/rollback readiness.

Report exact commands, exit results, and anything not run. “Looks correct” is not verification.

## 8. Review independently

First-pass review:

```text
/founder-changed-files-review
```

Specialist reviews as needed:

```text
/security-audit
/performance-audit
/ui-visual-verification
/dependency-audit
```

Tier-2 exact-SHA review:

```text
/pr-tier2-review
```

Pin base and head SHA. The canonical independent reviewer cannot edit, delegate, merge, or approve on behalf of the Founder. Any new head SHA invalidates the old exact-SHA review and requires re-review.

An advisor, reviewer in the builder’s context, or workflow stage is not a substitute for this boundary.

## 9. Prepare release evidence

Use:

```text
/release-readiness
```

Confirm:

- approved scope and final diff;
- all required checks;
- open findings and dispositions;
- migration and rollback;
- observability and alerting;
- security/credential handling;
- deployment owner and procedure;
- activation criteria;
- evidence storage;
- exact lifecycle state.

Merged is not deployed. Deployed is not activated.

## 10. Choose remote execution deliberately

```text
/cloud-session route <task>
```

### Cloud

Push the exact inputs first, then:

```bash
claude --cloud "Execute docs/approved-plan.md within the allowed scope; do not merge or deploy"
```

### Remote Control

For local files/connectors:

```bash
claude --remote-control "FounderOS Local Build"
```

### Local background

```bash
claude --bg "Run the bounded investigation and report evidence"
```

Never assign overlapping files to simultaneous sessions without worktree isolation.

## 11. Use goals only with a real verifier

Good:

```text
/goal npm test -- auth exits 0, npm run lint exits 0, only src/auth/** and test/auth/** change, or stop after 20 turns
```

Bad:

```text
/goal make the dashboard world class
```

Include a no-progress/time/turn bound and preserve Founder gates. A goal changes turn continuation, not permissions or authority.

## 12. Preserve context before transition

Before `/compact`, `/clear`, teleport, external delegation, or session end:

```text
/context-handoff
```

Preserve objective, approvals, repository/branch/SHA, observed facts, decisions, changed files, command results, open findings, and exact next action.

## Standard daily sequences

### Small bug

```text
/founderos-onboard
/bugfix-loop
/founder-verify
/founder-changed-files-review
```

### Consequential feature

```text
/founderos-onboard
/model-route <goal>
/founder-plan <goal>
Founder approves plan
/governed-feature
/founder-verify
/founder-changed-files-review
/pr-tier2-review
/release-readiness
Founder authorization
```

### Large audit

```text
/founderos-onboard
/founder-repository-audit
/security-audit
/performance-audit
/final-synthesis via Fable judgment lane
```

### Incident

```text
/incident-response
/founder-incident-root-cause
implement smallest authorized correction
/founder-verify
independent review
post-incident evidence and governance update
```

## Global stop conditions

Stop and report rather than improvise when:

- the repository or SHA is ambiguous;
- authorities conflict;
- requested model/connector is unregistered;
- protected paths or credentials are required;
- two builders would edit the same files;
- verification commands are unknown or cannot run;
- the task crosses approved scope;
- no-progress repeats;
- a workflow becomes unexpectedly large;
- a merge, deploy, activation, or governance decision needs Founder authorization.
