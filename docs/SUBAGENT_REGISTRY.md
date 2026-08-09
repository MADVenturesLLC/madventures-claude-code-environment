# Subagent registry

## Routing doctrine

Subagents isolate context and specialize responsibility. They are not votes of equal authority. The main session remains accountable for selecting the right worker and reconciling results under repository evidence and FounderOS governance.

| Agent | Model / effort | Mode | Primary responsibility |
|---|---|---|---|
| `founder-os-explorer` | Haiku / none | plan | Find entry points, governing files, tests, commands, and current evidence |
| `dependency-mapper` | Haiku / none | plan | Map imports, callers, contracts, coupling, and blast radius |
| `architecture-planner` | Fable / high | plan | Compare durable implementation options and issue a build-ready plan |
| `orchestration-coordinator` | Fable / high | plan | Select skills, agents, worktrees, workflows, and gates for large tasks |
| `feature-builder` | Sonnet / high | default | Own one coherent feature implementation and tests |
| `worktree-builder` | Sonnet / high | default | Build an isolated change in a Git worktree |
| `root-cause-investigator` | Opus / xhigh | plan | Diagnose hard failures before edits |
| `test-verifier` | Sonnet / high | plan | Run and interpret real verification gates without changing behavior |
| `code-reviewer` | Opus / high | plan | Findings-first correctness, maintainability, and regression review |
| `security-reviewer` | Fable / xhigh | plan | Threat, auth, secrets, injection, dependency, and boundary review |
| `independent-reviewer` | Fable / xhigh | plan | Edit-less, exact-SHA FounderOS Tier-2 review |
| `adversarial-verifier` | Fable / xhigh | plan | Try to refute plausible findings, plans, and claims |
| `final-synthesizer` | Fable / xhigh | plan | Reconcile independent reports into one controlled verdict |
| `governance-auditor` | Sonnet / high | plan | Check roles, DEC/workflow compliance, attribution, and state language |
| `decision-proposer` | Sonnet / high | default | Draft a proposed decision without self-ratifying it |
| `doc-updater` | Sonnet / medium | default | Update docs and handoffs after behavior and evidence are settled |
| `neon-reader` | Sonnet / medium | default | Read-only Neon/Postgres evidence with deterministic SQL guard |
| `performance-optimizer` | Opus / high | plan | Measure, localize, and propose/verify performance improvements |
| `ui-reviewer` | Opus / high | plan | Review UI truth, accessibility, interaction, and premium visual execution |
| `release-verifier` | Fable / xhigh | plan | Separate build readiness from merge, deploy, and activation authority |

## Automatic and explicit triggering

Agent descriptions are written so Claude can choose them automatically from context. You can also request a named role directly:

```text
Use founder-os-explorer to map error handling and cite exact files.
Use architecture-planner to compare the smallest durable options before any edit.
Use feature-builder as the one accountable builder after the plan is approved.
Use independent-reviewer on base <sha> and head <sha>; do not edit.
```

CLI examples:

```bash
claude --agent founder-os-explorer --permission-mode plan
claude --agent root-cause-investigator --model opus --effort xhigh
claude --agent independent-reviewer --model fable --effort xhigh
```

## Model inheritance

An agent with no model override inherits the session model. This is the safest default when routing is uncertain. This registry pins only clear role wins:

- cheap Haiku exploration;
- Sonnet implementation and tests;
- Opus demanding technical work;
- Fable costly judgment.

Do not hard-code dated model IDs into each agent unless an enterprise deployment requires provider-specific pinning. Aliases track the currently exposed generation.

## Tool design

Agent frontmatter lists tool names such as `Read`, `Grep`, `Glob`, `Bash`, `Edit`, `Write`, and `Agent`. Granular command patterns belong in settings permissions or hooks, not in the agent’s `tools:` list.

The independent reviewer omits edit tools and has a per-agent shell guard. The Neon reader has a per-agent SQL guard. Those are stronger controls than prose alone, but external access controls remain authoritative.

## Delegation patterns

### Explore before build

```text
founder-os-explorer
  + dependency-mapper
  → architecture-planner
  → feature-builder
  → test-verifier
  → code-reviewer
```

### High-risk change

```text
architecture-planner
  + security-reviewer
  + governance-auditor
  → one builder
  → test-verifier
  → adversarial-verifier
  → independent-reviewer on immutable SHA
  → Founder decision
```

### UI work

```text
founder-os-explorer
  → architecture-planner when structural
  → feature-builder
  → test-verifier
  → ui-reviewer
  → code-reviewer
```

## Nesting, background work, and task visibility

Only `orchestration-coordinator` is intentionally granted the `Agent` tool in this registry. A nested spawn can occur only when the active agent has that tool and the configured depth has not been reached. The shared project baseline sets:

```text
CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=2
CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=8
CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION=100
```

These are conservative package limits for ordinary delegation, not the separate dynamic-workflow runtime limits. Background subagents remain visible through `/tasks`; dynamic workflow runs are inspected through `/workflows`. Use worktrees for simultaneous mutable lanes and keep the main session responsible for reconciling results.

## Subagent constraints

- Do not delegate the same mutable files to simultaneous builders outside isolated worktrees.
- Do not treat multiple model outputs as independent when they share authored assumptions or unverified summaries.
- Do not let the builder invoke itself as the independent reviewer.
- Do not allow a reviewer to drift from the pinned SHA.
- Keep worker returns short: conclusions, paths, line ranges, commands/results, uncertainties, and next action.
- Subagent edits are generally outside the main session’s checkpoint restore boundary; use Git/worktrees for durable isolation and recovery.

## Portable plugin adaptation

The generated plugin carries 19 of the 20 project agents. It excludes `neon-reader` because safe database access depends on an agent-scoped SQL guard and a separately provisioned read-only database identity.

Plugin agents are generated from the project registry with deliberate reductions:

- agent-level `permissionMode`, `hooks`, and `mcpServers` are removed;
- plan/review roles lose shell and mutation tools where the project version relied on plan mode;
- the plugin `independent-reviewer` is restricted to `Read`, `Grep`, and `Glob` and explicitly disallows edit, shell, delegation, web, and MCP tools;
- project agents remain canonical whenever governance strength matters.

Use the plugin for portable, namespaced assistance. Use the full project installation for FounderOS-governed builds, exact-SHA review, database evidence, protected paths, and repository-specific policy.

