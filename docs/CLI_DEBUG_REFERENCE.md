# CLI and debugging reference

This reference records the launch, session, model, background, cloud, Remote Control, context, and debugging surfaces used by this package. Account- or provider-gated flags can be accepted by Claude Code without appearing in `claude --help`; verify them with the installed client and official docs.

## Start, name, and resume sessions

```bash
cd /path/to/project
claude
claude "Explain this repository and stop before editing"
claude --permission-mode plan
claude --name auth-refactor
claude --continue
claude --resume
claude --resume auth-refactor
claude --resume <session-id> --fork-session
```

Inside a session:

```text
/rename auth-refactor
/resume
/branch
/subtask investigate the failing auth test without editing
```

Use a named session for every substantial build, incident, review, or cloud handoff. A generated display title is useful in lists but is not necessarily a stable resume handle.

### Directory behavior

For a normal session, change directory before launch:

```bash
cd /path/to/project
claude
```

Do not treat `claude --cwd /path` as the general startup form. `--cwd` is documented for commands such as `claude agents --cwd` that filter the agent dashboard. Use `--add-dir` only after reviewing the additional trust boundary.

## Models, effort, fast mode, and advisor

```bash
claude --model sonnet --effort high
claude --model opus --effort xhigh
claude --model fable --effort xhigh
claude --model best --effort max
claude --model opusplan
claude --fallback-model opus,haiku
claude --effort ultracode
claude --advisor opus
```

Inside Claude Code:

```text
/model
/effort
/fast
/advisor opus
/advisor off
```

Rules:

- prefer aliases in shared configuration;
- record the resolved exact model when evidence depends on it;
- do not add an effort override to package Haiku agents;
- `ultracode` combines high reasoning with automatic workflow orchestration for the session;
- `/fast` accelerates a supported Opus route; it is not a smaller model;
- the advisor is experimental, requires the Anthropic API route, and sees the full conversation;
- Fable is not currently accepted as the advisor;
- an advisor consultation is never FounderOS Tier-2 independence.

The `--advisor` flag may not appear in `claude --help`. Use `/advisor` or the inactive profile fragment when the account supports it.

## Worktrees, subagents, and background sessions

```bash
claude --worktree feature-auth
claude --bg "Investigate the flaky test and report evidence; do not edit"
claude --bg --agent founder-os-explorer "Map the runtime request path"
claude agents
claude agents --cwd /path/to/project
claude agents --json
claude attach <session-id>
```

Inside a session:

```text
/tasks
/agents
/subtask map the authentication flow
```

Distinguish:

- `/agents`: information about available subagent definitions;
- `claude agents`: agent view for independent/background sessions;
- a subagent: isolated work inside one parent session;
- a background session: its own persisted Claude Code session;
- a worktree session: an isolated Git checkout suitable for independent edits.

Parallel editors must have non-overlapping file ownership or isolated worktrees.

## Dynamic workflows

```text
/workflows
/deep-research <question>
/founder-plan <goal>
/founder-verify
```

One-off request:

```text
ultracode: audit every changed API route, adversarially verify findings, and return one ranked report
```

Workflows run in the background and the interactive session remains responsive. Review the phase plan and raw JavaScript before launch. Workflow workers run with edit acceptance and inherit the tool allowlist, even when the parent is in plan mode; use the exact-SHA `independent-reviewer` for the hard edit-less boundary.

## Cloud sessions

Create a new Anthropic-managed cloud session from the current repository:

```bash
git status --short
git push
claude --cloud "Execute the approved plan in docs/plan.md; do not merge or deploy"
```

Inside the local session:

```text
/remote-env
/tasks
```

Retrieve a cloud session locally:

```bash
claude --teleport
claude --teleport <cloud-session-id>
```

Cloud notes:

- `--cloud` starts a new cloud session; it does not upload uncommitted local files;
- push the required branch/plan first, or use the separately documented non-GitHub bundle path;
- `--teleport` is cloud-to-local continuation, not a general local-to-cloud session upload;
- `/compact` and `/context` work in cloud sessions; `/clear` does not—start a new cloud session instead;
- re-check repository, branch, SHA, diff, and commands after teleporting.

## Remote Control

Server mode:

```bash
cd /path/to/project
claude remote-control --name "FounderOS Console"
```

Interactive local session with remote access:

```bash
claude --remote-control "FounderOS Console"
```

From an existing session:

```text
/remote-control FounderOS Console
```

Remote Control is not cloud execution. Claude Code, the filesystem, commands, project settings, MCP servers, and local connectors remain on the local machine. The machine must remain available; organization policy, login method, provider endpoint, and account eligibility still apply.

For concurrent Remote Control sessions, prefer worktree spawning rather than shared-directory editing:

```bash
claude remote-control --spawn worktree --capacity 4 --name "MAD Ventures Build Room"
```

## Safe diagnostic startup

```bash
claude --safe-mode
claude --setting-sources user,project,local
claude --settings /absolute/path/to/settings.json
claude --disable-slash-commands
```

`--safe-mode` is a clean diagnostic baseline. It is not the normal governed environment and should not be used to claim package features loaded correctly.

## Debugging

```bash
claude --debug
claude --debug "api,hooks,mcp"
claude --debug "!statsig,!file"
claude --debug-file /tmp/claude-debug.log
DEBUG=1 claude
claude --verbose
claude doctor
```

Important correction:

- `CLAUDE_CODE_DEBUG_LOGS_DIR` overrides the **debug log file path**, despite its name;
- setting it alone does not enable debugging;
- enable debugging with `--debug`, `/debug`, or `DEBUG=1`;
- `--debug-file <path>` both enables debugging and selects the file, and takes precedence.

Do not rely on a fixed `~/.claude/logs/claude-code.log` location. The normal default is session-specific under Claude’s debug directory and can change with configuration.

## Programmatic mode

```bash
claude -p "Run the requested read-only analysis and return JSON"
cat logs.txt | claude -p "Explain the failure"
claude -c -p "Check the latest changes"
claude -p "Run the bounded verifier" --allowedTools "Read,Grep,Glob,Bash"
```

Programmatic mode has no person available for ordinary prompts. Do not use it for unreviewed mutations, authority changes, credential access, or commands that need interactive approval. Use strict `--allowedTools`, explicit output formats, bounded turn/cost controls where supported, and a deterministic completion condition.

## Context and recovery commands

```text
/status
/context
/autocompact <token-count>
/compact preserve goal, approvals, SHA, changed files, verification, and next action
/clear
/rewind
/branch
/btw <question>
/tasks
/goal <condition>
/goal clear
```

Use `/compact` to retain the same session with a summary. Use `/clear` for a new conversation after writing a durable handoff. Use `/rewind` only within its documented file-edit scope; Git remains the recovery authority.

## Useful flags

| Flag | Purpose |
|---|---|
| `--add-dir` | Grant the session access to another directory |
| `--agent` | Start with a named custom subagent/persona |
| `--allowedTools` | Pre-authorize selected tool calls |
| `--disallowedTools` | Remove or deny selected tools |
| `--model` | Select a family alias or full provider model ID |
| `--fallback-model` | Ordered model fallback chain |
| `--effort` | Set reasoning effort, including `ultracode` when supported |
| `--advisor` | Select an advisor for one session when supported |
| `--permission-mode` | Select the session permission behavior |
| `--worktree` | Start in an isolated Git worktree |
| `--bg` | Dispatch a background session |
| `--cloud` | Start a new cloud session from the current repository |
| `--teleport` | Continue an eligible cloud session locally |
| `--remote-control` | Expose an interactive local session to web/mobile |
| `--safe-mode` | Disable customizations for diagnosis |
| `--debug` | Enable selected debug categories |
| `--debug-file` | Enable debugging and write to a chosen file |
| `--continue` | Resume the most recent session for the directory |
| `--resume` | Resume by picker, ID, or assigned name |
| `--fork-session` | Resume into a new session ID |
| `--name` | Assign a stable session name |

## Environment variables used or recognized by this package

Do not commit secret values.

| Variable | Purpose / package policy |
|---|---|
| `ANTHROPIC_API_KEY` | API authentication where Console/API billing is intentionally used; never commit it |
| `ANTHROPIC_MODEL` | Session model override below CLI priority |
| `CLAUDE_CONFIG_DIR` | Relocate the user configuration root |
| `CLAUDE_CODE_SUBAGENT_MODEL` | Override subagent/workflow model routing for the session; can defeat role routing, so use cautiously |
| `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` | Bound nested delegation depth |
| `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` | Bound concurrent subagents |
| `CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` | Bound total subagent fan-out |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | Trigger auto-compaction earlier as a percentage |
| `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | Change the auto-compact window where supported |
| `CLAUDE_CODE_DEBUG_LOGS_DIR` | Debug **file path**, not directory; does not enable debug mode |
| `CLAUDE_CODE_DEBUG_LOG_LEVEL` | Minimum debug level written |
| `DEBUG` | Set to `1` to enable debug mode |
| `MAX_THINKING_TOKENS` | Provider/model thinking budget control where supported |
| `CLAUDE_CODE_DISABLE_FILE_CHECKPOINTING` | Disable file checkpointing; package default leaves it enabled |
| `CLAUDE_CODE_DISABLE_AUTO_MEMORY` | Disable automatic memory |
| `DISABLE_AUTO_COMPACT` | Disable automatic compaction |
| `CLAUDE_CODE_DISABLE_ADVISOR_TOOL` | Disable the advisor surface entirely |
| `CLAUDE_CODE_DISABLE_WORKFLOWS` | Disable workflows where supported |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | Explicitly enable experimental agent teams; package baseline leaves them off |
| `CLAUDE_CODE_REMOTE` | Product-set signal for a remote/cloud runtime; do not manually treat it as authorization |

## Unsupported examples deliberately omitted

Do not add these community examples to shared `settings.json`:

```json
{
  "model": {
    "default": "...",
    "planning": "...",
    "quickTasks": "..."
  },
  "limits": {
    "maxTokensPerTurn": 4096,
    "maxContextTokens": 100000
  }
}
```

## Troubleshooting sequence

1. Record repository, branch, SHA, and working tree.
2. Run `claude --version`; update if below `2.1.223`.
3. Run `claude doctor`.
4. Run `/status` and inspect managed/user/project/local setting precedence.
5. Reproduce with `claude --safe-mode`.
6. Validate project JSON, agent/skill frontmatter, hooks, and workflows.
7. Run `claude --debug "hooks,config,mcp" --debug-file <absolute-path>`.
8. Remove one customization layer at a time rather than deleting all state.
9. Verify account/provider/model/preview eligibility separately from package correctness.
10. Never “solve” a configuration problem by enabling bypass permissions globally.
