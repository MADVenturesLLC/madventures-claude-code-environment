# Parallelism, background work, teams, workflows, goals, and remote execution

Parallelism is useful only when work can be decomposed without losing ownership, truth, or review independence. The package defaults to the smallest reliable concurrency surface.

## Decision matrix

| Surface | Context | Communication | Editing isolation | Best use |
|---|---|---|---|---|
| Main conversation | shared | Founder ↔ Claude | current tree | tightly coupled work |
| Subagent | isolated worker inside parent session | reports to parent | usually shared tree unless isolated | bounded exploration/review/specialist task |
| Worktree subagent/session | isolated | reports or independently resumed | separate Git worktree | independent editor |
| Background session | separate persisted session | Founder attaches/steers | shared dir or worktree depending launch | long independent local work |
| Agent team | separate peer sessions with shared task coordination | peer-to-peer plus lead | must be planned | a few long-lived peers with true coordination needs |
| Dynamic workflow | script-owned orchestration and intermediate variables | no ordinary mid-run user input | agents act under session tools; isolation must be designed | repeatable fan-out, pipelines, loops, synthesis |
| `/goal` | same session across turns | no new Founder prompt required | current session/tree | bounded autonomous completion condition |
| Claude cloud | separate Anthropic-managed session | web/mobile/CLI monitoring | separate cloud workspace/branch | persistent remote execution and independent cloud tasks |
| Remote Control | same local session | terminal + web/mobile | whatever local session uses | remote steering of local files/tools/connectors |

Remote Control changes the control surface, not the concurrency or execution host.

## Subagents

Use a subagent when:

- a bounded task benefits from isolated context;
- the parent should receive a concise result rather than raw exploration;
- a specialist tool/model route is stable;
- the worker does not need peer-to-peer coordination.

Examples:

```text
Explore how error handling works. Return file/line evidence, call paths, tests, and unknowns. Do not edit.
```

```text
Use the security-reviewer to inspect only the changed authentication files and return findings-first output.
```

Constraints:

- most subagents share the parent working tree;
- their edits may not be covered by the parent checkpoint;
- nested delegation is bounded by package environment limits;
- built-in Explore/Plan behavior can differ from custom agents in what context they load;
- model/tool restrictions must be encoded in the agent, not merely stated casually.

## Worktrees

Use worktrees whenever two agents may edit independently:

```bash
claude --worktree auth-fix
```

Ownership rules:

- one worktree per independent editing lane;
- one accountable builder per resulting diff;
- explicit file/subsystem ownership;
- no shared migration, lockfile, generated file, or governance edits without coordination;
- integrate sequentially and rerun verification after merge/rebase.

A worktree is isolation, not approval.

## Background sessions and agent view

Dispatch:

```bash
claude --bg "Investigate the flaky test; do not edit"
claude --bg --agent root-cause-investigator "Develop competing hypotheses"
```

Monitor:

```bash
claude agents
claude agents --json
claude attach <session-id>
```

Use background sessions for tasks that can proceed independently. Prefer worktree-backed sessions for edits. The local machine/background service must remain available; use cloud when persistence independent of the laptop is required.

## Agent teams

Agent teams are experimental and disabled by default. Enable only after explicit review:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

Use teams when a small number of peers need to communicate and coordinate a shared task list, such as:

- competing architecture proposals with an adjudicating lead;
- incident investigation split across application, infrastructure, data, and security;
- independent worktree implementation streams with controlled integration;
- writer/reviewer iteration where the reviewer has fresh context.

Do not use a team when a workflow, subagent, or sequential plan is enough. Keep the team small—typically a lead plus two to four peers—and account for known resumption/coordination limitations.

## Dynamic workflows

Use a workflow when the orchestration itself should be repeatable:

- review every changed file and deduplicate findings;
- fan out a repository audit across domains;
- migrate a bounded file set in isolated copies/worktrees;
- keep fixing until a deterministic checker passes or progress stalls;
- gather independent hypotheses and run adversarial synthesis.

Official runtime constraints reflected by package policy:

- the JavaScript coordinates; agents perform tools;
- no ordinary mid-run user input;
- workflow agents run with edit acceptance and inherit the session allowlist;
- runs are background and resumable within the same session;
- concurrent and total-agent runtime caps exist, but package limits are intentionally lower;
- cost can grow quickly, so test on a small slice first.

Package defaults:

- `workflowSizeGuideline: "small"`;
- environmental target of at most eight concurrent subagents;
- maximum depth two;
- total session cap one hundred;
- explicit maximum rounds and no-progress stop for mutating loops.

These are controls and preferences, not proof that a generated script cannot exceed advice. Inspect the raw script.

## Goals

Use `/goal` when the same session should continue turn after turn until a measurable condition is demonstrated.

Good:

```text
/goal npm test -- auth exits 0, npm run lint exits 0, no files outside src/auth/** and test/auth/** change, or stop after 20 turns
```

The evaluator reads surfaced conversation evidence; it does not independently inspect files or run commands. A goal must include:

- one measurable end state;
- the exact check Claude must run and report;
- mutation constraints;
- a turn/time or no-progress bound;
- preserved authority gates.

A goal does not change permissions. It can be used interactively, programmatically, and through Remote Control where supported. Clear it with `/goal clear`.

## Claude cloud

Cloud is a separate execution environment and session. Use it for:

- persistent work after the local machine closes;
- parallel independent tasks on separate branches;
- web/mobile supervision;
- executing a committed approved plan.

Each `--cloud` task is independent. Do not assign overlapping files. Push exact inputs first, monitor `/tasks`, and verify the teleported/final branch locally.

## Remote Control

Remote Control keeps the session local. Use it when local files, MCP servers, tools, or Hermes are required. It can display subagent and workflow progress across devices, but it does not:

- make local work persistent while the machine is off;
- create separate file isolation;
- widen permissions;
- create review independence;
- transfer the repository into cloud.

For multiple remotely controlled sessions, use server mode with worktree spawning and a low capacity aligned to actual CPU/memory and review capacity.

## Cheap fan-out, expensive judgment

Recommended large-task pattern:

```text
Haiku explorers (bounded file groups)
        ↓
Sonnet consolidator (normalize evidence)
        ↓
Opus/Fable judgment (architecture or adversarial verdict)
        ↓
One accountable builder
        ↓
Independent exact-SHA reviewer
        ↓
Founder authorization
```

Do not have twenty expensive agents read the same repository. Do not use a cheap model as the sole high-risk judge.

## Ownership contract

Every parallel task must declare:

- task ID and owner;
- repository, branch/worktree, base SHA;
- allowed files/subsystems;
- prohibited shared files;
- model and role;
- whether editing is allowed;
- verifier and integration owner;
- expected artifact;
- stop condition.

If two tasks claim the same file, serialize or isolate/replan before work starts.

## Cost and stability controls

1. Start with one representative directory or module.
2. Group files by subsystem rather than one agent per file when possible.
3. Cap concurrency below hardware/service limits.
4. Cap total agents and rounds.
5. Stop after two repeated no-progress fingerprints.
6. Drop null/failed results explicitly and report them as unverified.
7. Preserve short structured findings, not raw dumps.
8. Monitor `/workflows`, `/tasks`, `/usage`, and `claude agents`.
9. Pause/stop a run when its scope or projected spend is no longer justified.
10. Re-run integration tests after combining parallel branches.

## Independence

A builder does not become independent by spawning another instance of the same authored context. An advisor is not independent. A workflow judge is not automatically independent. Tier-2 requires a fresh edit-less role on the exact immutable SHA, and every changed head requires re-review.
