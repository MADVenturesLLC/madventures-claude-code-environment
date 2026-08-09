# Architecture

## Objective

Create a reusable Claude Code control plane that increases engineering speed without weakening FounderOS authority, repository truth, review independence, access control, or evidence quality. The package must work locally, in worktrees, in background sessions, through Remote Control, and in Anthropic-managed cloud sessions while keeping the same governed operating contract.

## Three-surface architecture

### Repository control plane

Committed project files under `.claude/` carry the durable engineering contract:

- operating doctrine and state language;
- repository-specific profile;
- Founder-approved model registry;
- scoped rules;
- subagents;
- skills;
- workflows;
- deterministic hooks;
- shared project settings;
- optional cloud SessionStart script;
- opt-in Opus advisor settings fragment.

This layer travels with the repository and is therefore the primary portability mechanism for cloud sessions and teammates.

### Python governed-execution plane

The full project installation embeds `.claude/control-plane/`, a Python state machine above native
`claude -p`. It owns authentication/billing preflight, plan-hash approval binding, Git and scope
checks, deterministic verification, exact-SHA worktrees, structured schemas, evidence hashing,
bounded repair, and exit status.

It does not replace the repository control plane. Project doctrine, skills, agents, hooks, and
settings still load into Claude. Python determines whether a controlled workflow may start, advance,
or claim success. This distinction lets model judgment remain flexible while critical state
transitions remain deterministic.

Native `claude -p` is the governed subscription default. Python supplies structured JSON Schema
output, project settings, strict empty MCP, route-specific tools/subagents, and an ephemeral
`PreToolUse` policy file on every run. Read-only routes may fan out only to registered specialists;
mutation routes retain one accountable builder. The optional pinned Agent SDK adapter is installed
only for an explicitly API-billed lane.

### Portable plugin surface

The generated `plugin/madventures-founderos/` package exposes a namespaced, reusable subset across MAD Ventures repositories:

- 19 portable agents;
- 31 reusable skills;
- 0 executable JavaScript workflows; 14 former capabilities map to governed Python routes;
- plugin-root-aware deterministic hooks.

It deliberately excludes `neon-reader`, strips unsupported agent-level permission and hook fields, and hardens plan/review agents through tool removal. It is a portability surface, not a substitute for repository settings, rules, branch protection, database roles, or the full project control plane.

### Remote execution planes

Remote Control keeps execution on the local host while exposing the session through web/mobile. It preserves the local filesystem, MCP servers, tools, and approved local-only connectors, and therefore inherits the local machine's security posture and uptime requirements.

### Cloud execution plane

Assets under `cloud/` configure the Anthropic-managed VM:

- network posture guidance;
- non-secret environment values;
- a VM setup script for missing tools;
- an optional repository dependency bootstrap;
- launch, monitor, and teleport procedures.

Neither Remote Control nor the cloud layer creates authority. Remote Control supplies a remote control surface for the local execution plane; cloud supplies an Anthropic-managed execution environment for the repository control plane.

## Layer model

### 1. Doctrine and authority

`.claude/FOUNDEROS.md` defines stable cross-project doctrine and imports:

```text
@PROJECT_PROFILE.md
@MODEL_REGISTRY.md
```

The profile contains repository facts: purpose, branch, package manager, required checks, entry points, protected paths, governing decisions, current objective, and acceptance criteria.

The authority order is:

1. verified repository/runtime/production evidence;
2. ratified FounderOS governance;
3. current explicit Founder instruction;
4. approved transition or handoff package;
5. prior summaries or memory.

### 2. Model registry

`.claude/MODEL_REGISTRY.md` separates model identity from permission. It records native Claude lanes and Founder-registered external lanes such as Grok, Hermes Local Code, Codex, Gemini, and Cursor as an execution surface.

Registration alone grants nothing. Per-run access, role, connector, model version, SHAs, commands, changed files, and evidence remain auditable. The optional Opus advisor improves selected decisions inside a Sonnet-led session but does not create reviewer independence.

### 3. Scoped rules

`.claude/rules/` keeps stable, path-specific policy out of one oversized instruction file. Rules activate only where governance, runtime, UI, tests, documentation, or evidence paths require them.

### 4. Skills

Skills are reusable operating procedures loaded on demand. They tell Claude how to execute a class of work without permanently consuming base context. Skills do not create an independent worker or permission boundary.

### 5. Subagents

Subagents are isolated workers with bounded prompts, tools, model, effort, turns, permission mode, optional memory, and hooks.

Role separation is explicit:

- explorer ≠ planner;
- planner ≠ builder;
- builder ≠ reviewer;
- reviewer ≠ Founder approver;
- exact-SHA independent reviewer ≠ author of the change.

The canonical independent reviewer has no edit/write/delegation/shell tools. Python owns exact-SHA command execution.

### 6. Worktrees, background sessions, and teams

Worktrees isolate parallel mutation. Background sessions handle long independent tasks. Agent teams handle a few long-running peers that must coordinate through shared tasks and messages.

Parallel mutation requires explicit ownership and separate worktrees/branches. Shared context does not prevent file conflicts.

### 7. Governed workflows

Python is the only authoritative orchestration engine. It owns loops, branching, bounded fan-out,
schemas, scope enforcement, exact-SHA isolation, verification commands, and evidence manifests. The 14
former JavaScript workflow capabilities are mappings, not executable scripts.

### 8. Goals and bounded autonomy

A goal lets one session continue until a verifiable condition passes. The package treats goals as governed autonomy, not open-ended persistence. Every goal needs:

- exact completion verifier;
- bounded mutation scope;
- prohibited paths/actions;
- maximum rounds and no-progress stop;
- Founder authority gates;
- final command evidence.

### 9. Hooks and permissions

Settings rules establish default allow/ask/deny behavior. One JavaScript adapter sends tool,
configuration, stop, and task-completion events to Python policy. The `neon-reader` adds the scoped
SQL profile; the independent reviewer needs no shell hook because it has no shell tool.

These are defense in depth. True external boundaries remain GitHub permissions, branch protection, cloud IAM, database roles, secret management, deployment approvals, and human authorization.

### 10. Session operations

Checkpoints, `/rewind`, `/context`, `/compact`, `/branch`, named sessions, handoff artifacts, background tasks, Remote Control, cloud sessions, and teleport reduce the risk that long tasks become unrecoverable or context-poisoned.

Critical state is pinned before compaction or handoff: goal, repository, branch/SHA, approvals, changed files, command results, findings, unknowns, and next action.

### 11. Portable generation and synchronization

`scripts/build-plugin.py` generates the portable plugin from canonical project agents and skills, the
single hook adapter, and the shared Python baseline policy. Validation proves source synchronization,
permitted agent-field adaptation, database-agent exclusion, plugin-root hook paths, command
namespacing, and installer coexistence behavior.

Project agents remain the governing source because the full project environment can carry repository rules, settings, agent-scoped hooks, permission modes, and local profiles that the portable plugin cannot safely reproduce.

### 12. Validation and release integrity

The package validates:

- version and required documentation;
- JSON syntax and known settings fields;
- agent and skill frontmatter;
- model/effort compatibility rules encoded by the package;
- hook references and behavior;
- workflow metadata, syntax, and imports;
- expected component counts;
- model-registry and doctrine imports;
- inactive MCP shape and read-only headers;
- absence of credential-shaped values;
- installer syntax, backup behavior, idempotence, and preservation rules;
- cloud script syntax and opt-in behavior;
- release manifest and SHA-256 checksums;
- project/plugin source synchronization and plugin installation behavior.

### 13. Python orchestration and evidence

Nine route configurations combine a model, effort, tools, permission mode, schema, turn bound, and
mutation policy. The control plane captures a redacted authentication report and hashes every local
evidence artifact. Build and repair routes are the only mutating Python routes. Exact-SHA review and
release readiness use detached temporary worktrees and literal full SHAs.

The Python layer never commits, pushes, merges, deploys, activates, or creates Founder authority.

## Execution patterns

### Interactive governed feature

```text
Founder request
  → /founderos-onboard
  → bounded exploration/dependency mapping
  → architecture planning when consequential
  → one accountable builder
  → tests
  → specialist reviews
  → exact-SHA independent review when governed
  → Founder decision
```

### Cheap fan-out, expensive judgment

```text
many Haiku evidence scans
  → Sonnet implementation or intermediate synthesis
  → Opus deep technical review
  → Fable architecture/adversarial/final judgment
```

### Governed Python build

```text
subscription auth proof
  → evidence-grounded plan
  → plan-bound Founder approval document
  → one scoped builder
  → Python changed-file scope check
  → Python-run verification
  → evidence bundle
  → exact-SHA independent review
```

Use this path when repeatability and machine-enforced gates matter more than continuous interactive
steering. Use normal Claude Code for pairing, visual exploration, and checkpoint-heavy iteration.

### External-model build

```text
approved task packet
  → registered external builder (for example Grok or Hermes Local Code)
  → local diff and command verification
  → independent model reviewer not used as builder
  → Founder decision
```

### Workflow fan-out

```text
saved workflow
  → parallel/pipeline agents
  → structured intermediate results
  → deduplication and adversarial checking
  → one final result in the main session
```

### Plan local, execute cloud

```text
local plan mode + Founder approval
  → committed and pushed plan
  → claude --cloud on an isolated branch
  → /tasks monitoring
  → teleport into a clean local checkout
  → re-verify SHA, diff, tests, reviews, and authority
```

## Non-goals

This package does not:

- make any model a Founder approver;
- install or authenticate third-party model connectors;
- grant production, GitHub, database, cloud, or deployment credentials;
- make a prompt-only evidence workflow technically immutable;
- replace Git, CI, branch protection, test environments, observability, IAM, or secret management;
- guarantee model availability, generation mapping, context window, fast mode, or effort level outside the account/provider;
- claim deployment or activation from code, PR, or local test state alone.
