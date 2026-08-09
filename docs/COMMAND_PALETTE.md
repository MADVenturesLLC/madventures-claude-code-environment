# FounderOS command palette

This is the day-to-day operating map for the MAD Ventures Claude Code environment. Start with `/founder-command <goal>` when the correct surface is unclear.

## Session controls

| Command | Use |
|---|---|
| `/status` | Show active model, context, account, settings, and environment state |
| `/doctor` | Run Claude Code product diagnostics |
| `/memory` | Inspect loaded instructions and memory |
| `/agents` | Inspect available subagents |
| `/skills` | Inspect available skills |
| `/workflows` | Monitor, pause, resume, stop, inspect, or save workflow runs |
| `/permissions` | Inspect and change session permission behavior |
| `/hooks` | Inspect loaded hooks |
| `/model` | Select or inspect the session model |
| `/advisor` | Enable, change, inspect, or disable an in-session advisor; this is not independent review |
| `/effort` | Select reasoning effort; use `ultracode` only for substantive workflow-oriented sessions |
| `/fast` | Toggle supported Opus fast mode; this is faster Opus, not a smaller model |
| `/context` | Inspect what is consuming the current context window |
| `/autocompact <tokens>` | Move the automatic compaction threshold when no environment override is active |
| `/btw <question>` | Ask a no-tools side question without adding it to the main conversation history |
| `/tasks` | Inspect running shells, background agents, and cloud/background work |
| `/goal <condition>` | Define or inspect a machine-verifiable autonomous completion condition |
| `/remote-control [name]` | Expose the current local execution session to an authorized web/mobile control window |
| `/branch` | Fork an alternate conversational approach while preserving the original |
| `/compact` | Summarize older context while retaining the session |
| `/clear` | Start a clean local conversational context after preserving durable state; cloud sessions require a new session instead |
| `/rewind` | Open checkpoint history and choose code/conversation recovery |

Additional inspection commands used during deployment include `/mcp`, `/plugin`, `/remote-env`, and `/reload-plugins`. Product commands are account/version gated; verify their presence in the installed client rather than assuming a community example is supported.

## FounderOS skills

### Intake, routing, and context

- `/founder-command <goal>` — choose direct work, skill, subagent, worktree, workflow, team, goal, or cloud session.
- `/founderos-onboard` — pin repository, branch, instructions, commands, governance, architecture, and unknowns.
- `/founderos-doctrine` — apply evidence, authority, lifecycle, and role-separation rules.
- `/model-route <task>` — route model and effort by judgment cost and mechanical volume.
- `/session-control` — decide compact, clear, handoff, resume, or new session.
- `/checkpoint-recovery` — recover safely using checkpoint scope plus Git.
- `/context-handoff` and `/handoff-create` — preserve exact state for compaction, resumption, or another model.
- `/claude-doctor-plus` — package-specific environment health audit.
- `/python-control-plane` — operating contract and examples for deterministic Python routes.

### Planning and building

- `/governed-feature` — interactive feature procedure from evidence through verification.
- `/bugfix-loop` — root-cause-first repair loop.
- `/multi-agent-build` — planner → one builder → independent verification/review.
- `/workflow-author` — design a bounded dynamic workflow with schemas and stop conditions.
- `/parallel-route` — choose safe parallelism and non-overlapping ownership.
- `/cloud-session route <task>` — choose Anthropic-managed cloud, Remote Control, or local/background execution and prepare the selected route.
- `/goal-control` — define machine-verifiable autonomous completion conditions.

### Review and operations

- `/pr-tier2-review` — exact-SHA independent review contract.
- `/code-review-wf13` — findings-first code-review workflow.
- `/release-readiness` — correctness, operations, rollout, rollback, and lifecycle boundary.
- `/security-audit`, `/performance-audit`, `/repository-audit`, `/dependency-audit` — specialist audits.
- `/ui-visual-verification` — rendered UI, accessibility, motion, data truth, and performance.
- `/incident-response` — controlled containment, evidence, diagnosis, correction, and verification.
- `/decision-propose`, `/doc-update`, `/path-audit`, `/attribution-check` — governance and documentation support.
- `/external-model-delegation` — controlled handoff to Grok, Hermes local code, Codex, Gemini, or another registered model.

## Python command surface

Python routes are terminal commands, not Claude slash commands. Use the repository-local launcher:

| Command | Purpose |
|---|---|
| `madclaude auth-check` | Prove subscription or explicitly authorized API lane |
| `madclaude doctor` | Inspect Python, Git, Claude CLI, auth, repository, and optional SDK |
| `madclaude routes` | Show model/effort/tool/schema defaults |
| `madclaude plan` | Evidence-grounded structured plan |
| `madclaude approval-template` | Generate a non-approved template bound to a plan SHA-256 |
| `madclaude build` | Execute an exact Founder-approved plan and scope |
| `madclaude verify` | Run direct deterministic commands and interpret results |
| `madclaude tier2` | Exact-SHA independent review in a detached worktree |
| `madclaude release-readiness` | Exact-SHA release evidence without authority |
| `madclaude repo-audit` | Repository architecture/quality/governance audit |
| `madclaude security-audit` | Adversarial structured security audit |
| `madclaude ui-review` | Truthful UI implementation review |
| `madclaude fix-until-green` | Bounded scoped repair loop |

Example:

```bash
python3 .claude/control-plane/madclaude.py auth-check --repo .
python3 .claude/control-plane/madclaude.py plan --repo . "<exact goal>"
```

The Python route is not automatically better than an interactive session. Use it when deterministic
state transitions, evidence, or exact-SHA isolation justify the additional ceremony.

## Governed Python routes

The 14 JavaScript implementations are retired. Use `madclaude plan`, `build`, `verify`, `tier1`, `tier2`,
`release-readiness`, `repo-audit`, `security-audit`, `ui-review`, `fix-until-green`, and
`architecture-validation`. Specialized
docs-drift, performance, test-gap, and incident analysis use `repo-audit --profile <name>`.

Python enforces the model envelope, one-builder mutation, approval and scope gates, deterministic
commands, exact SHAs, Tier-2 independence, evidence classes, and execution records. It never grants
merge, deployment, activation, protected-authority mutation, credential access, or production writes.

## Recommended daily sequence

```text
/founderos-onboard
/model-route <goal>
madclaude plan <goal>
Founder reviews/approves the SHA-bound plan
madclaude build <goal> --plan-file ... --approval-file ...
madclaude verify <goal> --verify ...
madclaude tier1 <goal> --base-sha ... --head-sha ... --verify ...
madclaude tier2 <goal> --base-sha ... --head-sha ... --execution-record ...
Founder authorization
```

## Portable plugin names

When using the optional plugin, commands are namespaced:

```text
/madventures-founderos:founder-command
```

The unnamespaced project installation is the stronger FounderOS deployment because it includes project settings, rules, agent-specific permission modes, and scoped hooks.
