# Claude Code field reference for MAD Ventures

This is the compact reference for the operating features deliberately included or corrected in this package.

## Subagents

Claude can delegate bounded work to custom agents. The package uses role-specific agents for exploration, dependency mapping, planning, building, testing, specialist review, release judgment, and final synthesis. The main session may invoke them automatically from their descriptions or explicitly by name.

Built-in Explore and Plan modes remain useful, but FounderOS roles add stable model, effort, tools, instructions, and independence boundaries. Use subagents to isolate context; return conclusions and exact evidence rather than raw file dumps.

## Dynamic workflows

Saved JavaScript workflows live under `.claude/workflows/` for a project, under the user configuration for personal commands, or under `workflows/` in a plugin. They use top-level `await` and orchestration primitives such as `agent()`, `pipeline()`, and `parallel()`.

Use `/workflows` to inspect phases, agents, tokens, elapsed time, pause/resume state, and results. Workflow scripts cannot directly access the shell/filesystem; their agents do the work. They cannot accept ordinary user input mid-run. Resume is session-local.

Workflow-spawned agents run with edit acceptance and inherit the session tool allowlist. A prompt that says “read-only” is therefore intent, not a hard permission boundary. Use the edit-less `independent-reviewer` for governed exact-SHA review.

## Background sessions, agent view, and teams

```bash
claude --bg --agent founder-os-explorer 'Map the repository; do not edit.'
claude agents
```

Background work continues only while the relevant local or cloud Claude Code runtime exists. Use Agent view and `/tasks` to inspect active work. Agent teams are experimental and disabled by default; enable them only for a few long-running peers that need coordination, not as a replacement for bounded workflows or one accountable builder.

## Goals

```text
/goal npm test exits 0, npm run lint exits 0, only src/auth/** and tests/auth/** change, or stop after 20 turns
/goal
/goal clear
```

A goal should define a machine-verifiable completion condition, allowed mutation scope, authority stops, and a bound. Its evaluator reads transcript evidence rather than independently rerunning commands, so require exact command results in the final evidence.

## Checkpoints and history

Claude Code checkpoints direct file edits before prompts. Use `/rewind` (or the applicable keyboard shortcut) to restore code, conversation, both, or summarize from a checkpoint. Use Git for durable recovery, especially for Bash, generators, external tools, subagents, and workflows.

Useful requests:

```text
Show the recent changes you made and the current git diff.
Undo the last direct edit using checkpoint history, then verify git diff.
```

## Context management

```text
/context             inspect context composition
/autocompact <tokens>  move the automatic-compaction threshold for the session
/compact             summarize older context and continue
/clear               clean conversation context after preserving state
/btw <question>      ask a no-tools side question outside the main history
/tasks               inspect background shells, subagents, and cloud work
/branch              preserve the current path and explore an alternative
```

Do not compact before recording the current goal, Git state, decisions, changed files, command results, blockers, and next action. Cloud sessions support `/compact` and `/context` but not `/clear`; create a new cloud session instead.

## Model routing

Shared files use aliases:

- `haiku` — high-volume mechanical fan-out;
- `sonnet` — everyday coding;
- `opus` — demanding implementation/diagnosis/review;
- `fable` — top judgment where available;
- `best` — Fable when available, otherwise current Opus;
- `inherit` — use the session route.

Agent definitions can set `model` and supported `effort`. One-off delegated agents and workflow stages can also override the model. Omit an override when the fit is uncertain.

## Effort and fast mode

Effort-capable models expose `low`, `medium`, `high`, `xhigh`, and `max` according to model/account support. Haiku is not assigned an effort override in this package. `ultracode` is a session mode combining high reasoning with automatic workflow orchestration; it is not a sixth model tier.

`/fast` accelerates supported Opus output without changing to a smaller model. Availability and pricing remain account/model dependent.

## Advisor

```bash
claude --model sonnet --effort high --advisor opus
```

```text
/advisor opus
/advisor off
```

The advisor is an opt-in same-session second opinion. It sees the conversation, is provider/account gated, and is not independent review. Fable is not currently offered as the advisor. The package keeps `advisorModel` out of shared base settings and supplies an inactive Opus fragment plus an executable `advisor` route.

## Startup and resumption

```bash
cd /path/to/project
claude --model sonnet --effort high --permission-mode plan
claude --continue
claude --resume
claude --resume <name-or-id> --fork-session
claude --worktree <name>
claude --bg --agent founder-os-explorer 'Map the repository; do not edit.'
```

Do not use an undocumented top-level `claude --cwd` startup pattern. Change directory first. `--cwd` has other command-specific uses.

## Cloud versus Remote Control

```bash
claude --cloud 'Run the approved repository task.'
claude --teleport
claude remote-control --name 'FounderOS Local Build'
```

Cloud runs on Anthropic-managed infrastructure and should receive pushed/committed or explicitly bundled repository state. Remote Control steers a Claude Code process that remains on the local machine, preserving local files, MCP servers, tools, and approved local connectors. Neither surface grants new authority.

## Debugging

```bash
claude --version
claude doctor
claude --safe-mode
claude --debug 'config,hooks,mcp' --debug-file ./claude-debug.log
```

Use a deterministic `--debug-file` instead of assuming a fixed log path.

## Environment variables

Common supported variables used or documented by this package include:

- `ANTHROPIC_API_KEY` — API authentication when applicable;
- `ANTHROPIC_MODEL` — environment-level model override;
- `CLAUDE_CONFIG_DIR` — alternate user configuration root;
- `DEBUG=1` — enable debug output for a launch;
- `CLAUDE_CODE_DEBUG_LOGS_DIR` — despite its name, an override for the debug **file path**; it does not enable debugging;
- `CLAUDE_CODE_SUBAGENT_MODEL` — global delegated-agent override; use cautiously;
- `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`;
- `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`;
- `CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION`;
- `CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING`;
- `CLAUDE_CODE_DISABLE_AUTO_MEMORY`;
- `DISABLE_AUTO_COMPACT`.

Do not use the community-only `CLAUDE_CODE_MODEL` example where the documented variable is `ANTHROPIC_MODEL`. Do not treat environment variables as a secret store in shared cloud environments.

## Unsupported settings corrected by this package

The package does not use nested model routing such as `model.default/planning/quickTasks`, nor unrecognized `limits.maxTokensPerTurn/maxContextTokens` project settings. Routing belongs in the session model, fallback chain, agent frontmatter, delegated-agent call, and workflow stage.
