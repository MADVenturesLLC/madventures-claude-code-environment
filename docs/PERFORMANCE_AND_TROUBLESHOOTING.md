# Performance, context, cost, and troubleshooting

## Optimization principle

Optimize the whole engineering loop, not only response latency:

```text
correct routing → compact evidence → bounded fan-out → one accountable builder → real gates → independent judgment
```

The central cost rule is **cheap fan-out, expensive judgment**. Haiku should perform bounded search, extraction, and mechanical scans. Sonnet handles ordinary implementation. Opus handles demanding diagnosis and technical review. Fable is reserved for consequential architecture, adversarial verification, final synthesis, and long autonomy where a wrong answer is more expensive than the tokens.

## Context efficiency

1. Keep conclusions and decisions in the main context; keep file dumps inside subagents or workflow variables.
2. Give agents exact targets, expected output shape, mutation policy, and stop condition.
3. Read only the relevant file ranges first; broaden after evidence points to a dependency.
4. Use `/compact` when the objective is stable and old detail is crowding current evidence.
5. Preserve a `SESSION STATE` handoff before compaction, clearing, or model transfer.
6. Use `/clear` or a named new session when the goal, repository, authority boundary, or review independence changes.
7. Re-read changed files, project profile, and governing instructions after compaction.
8. Use a clean edit-less context for exact-SHA independent review.

## Fan-out and concurrency

The package shared baseline targets eight concurrent subagents and a `small` workflow size guideline. That is intentionally below the runtime maximum and is advisory rather than a guarantee.

Use parallel agents only when their questions are independent. Group files by subsystem instead of spawning one worker per file when a group can fit safely in context. Every workflow must have:

- a bounded input set;
- maximum rounds or total-agent expectation;
- a no-progress stop;
- filtered null/error results;
- one final evidence-weighted synthesizer;
- explicit mutation class.

Start with one directory, one PR, or one service before scaling to a whole monorepo.

## Model and effort tuning

| Situation | Route |
|---|---|
| Slow mechanical exploration | More focused Haiku workers, shorter output schema, fewer duplicate searches |
| Ordinary coding latency | Sonnet high; lower to medium only when the task is truly routine |
| Difficult interactive problem | Opus high/xhigh |
| Consequential judgment | Fable high/xhigh/max, with independent evidence lanes |
| Interactive Opus latency | `/fast` when the current supported model/account exposes it |
| Too much workflow spend | Lower fan-out, smaller slice, fewer review lanes, or use a skill/subagent instead |
| Uncertain route | Inherit the session model rather than pinning prematurely |

Fast mode accelerates supported Opus output; it is not a downgrade to Haiku or Sonnet. `ultracode` combines high reasoning with automatic workflow planning for substantive tasks and resets with the session. Do not leave it on for routine work.

## Checkpoint and recovery performance

Checkpoints are valuable for direct Claude file edits and conversation recovery, but Git is the durable recovery system. Before package-manager operations, generators, formatters, migrations, background agents, or workflows that may edit:

```bash
git status --short
git diff --stat
git rev-parse HEAD
```

Create a branch, commit, or worktree when recovery must be durable. Do not rely on `/rewind` for Bash-created changes, external edits, or most background/workflow changes.

## Diagnostic ladder

Run the least invasive check first:

```bash
claude --version
claude doctor
python3 scripts/validate-config.py
node scripts/validate-workflows.mjs
bash scripts/smoke-test-install.sh
claude --safe-mode
claude --debug 'config,hooks,mcp' --debug-file ./claude-debug.log
```

Inside Claude Code inspect:

```text
/status
/doctor
/context
/memory
/agents
/skills
/workflows
/hooks
/permissions
/plugin
```

## Common issues

### Slow responses

- Confirm the session did not remain on Fable/max or ultracode after the hard stage.
- Check whether the prompt requests redundant repository-wide scans.
- Inspect `/context`; compact only after preserving state.
- Reduce workflow slice and agent count.
- Keep full command logs and file contents out of synthesis prompts.
- Check provider/account rate limits and current model availability.

### Tool failures

- Read the exact permission decision and active setting source in `/status` and `/permissions`.
- Verify current directory, repository trust, allowed paths, executable availability, and sandbox/network policy.
- Inspect hook output before changing permissions.
- Do not solve a missing allow rule by globally enabling bypass permissions.

### Hook failures

- Run package hook tests.
- Confirm Node.js is installed and the command path uses `CLAUDE_PROJECT_DIR` or `CLAUDE_PLUGIN_ROOT` correctly.
- Use `claude --debug 'hooks' --debug-file <path>`.
- Start `claude --safe-mode`; if the issue disappears, isolate one customization layer at a time.

### Agent does not appear or route correctly

- Check frontmatter, filename/name match, supported model alias, and duplicate definitions.
- Remember project/user agent definitions can override same-named plugin agents.
- Plugin agents are namespaced and cannot enforce plugin-shipped `permissionMode`, `hooks`, or `mcpServers` frontmatter.
- Restart or `/reload-plugins` after changing plugin components.

### Governed route does not run

- Run `madclaude doctor --repo .` and confirm the intended subscription/authentication lane.
- Run `node scripts/validate-workflows.mjs`; it must report 14 mapped capabilities and zero executable JavaScript workflows.
- Use `madclaude <route> --dry-run` to validate repository, approval, scope, SHA, command, model, and billing gates without execution.
- Inspect the emitted error; Python fails closed instead of falling back to prompt-only orchestration.

### Context or memory problems

- Use `/context` to identify the largest contributors.
- Move repeated procedures into skills and broad scans into subagents/workflows.
- Use `/compact` for the same task; use `/clear` or a new named session for a different task.
- Verify that automatic memory contains no stale authority or credential material.

### Model unavailable

- Use `/model` and `/status` to inspect what the account/provider exposes.
- Prefer aliases and fallbacks over guessed dated IDs.
- Do not silently replace Fable judgment with Haiku. Report the downgrade and adjust the review plan.

### Plugin/project duplication

Choose one primary deployment. Use the project environment for FounderOS repositories. Use the plugin for portable namespaced tools in other MAD Ventures projects. Remove or disable duplicate copies before diagnosing routing.

## Doctor Plus verdict

Run `/claude-doctor-plus full` after installation, after a Claude Code upgrade that changes configuration behavior, and before declaring the environment production-ready. Static validation proves package shape and syntax; only the real account, repository, and runtime can prove model availability, organization policy, live MCP authentication, and project commands.
