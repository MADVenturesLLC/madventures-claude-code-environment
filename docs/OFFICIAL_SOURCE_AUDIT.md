# Official-source audit

**Audit date:** 2026-08-06  
**Package:** MAD Ventures Claude Code Operating Environment `4.4.1`  
**Technical authority:** current Anthropic/Claude Code documentation and official integration documentation

Community directories, articles, copied examples, and user-supplied excerpts were used to discover useful ideas. They were not treated as configuration authority. Every setting, command, frontmatter field, workflow behavior, and portability claim in this release was either checked against an official source or deliberately labeled as package policy rather than a Claude Code guarantee.

## Version decision

- Current official Claude Code release observed during this audit: `2.1.223` on 2026-08-06.
- Package minimum: `2.1.223`.
- The floor is driven by the shared `workflowSizeGuideline` behavior and current model/workflow support used by the package.
- Newer clients are preferred because recent releases include workflow sandbox, permission, worktree, background-agent, and model-restriction fixes.

The package does not assume that every account exposes every model or preview feature. Actual availability remains controlled by account, plan, provider, organization policy, region, and managed settings.

## Accepted and implemented

### Repository extension surfaces

- project instructions and imports under `.claude/`;
- project-scoped rules;
- reusable skills under `.claude/skills/`;
- custom subagents under `.claude/agents/`;
- Python-governed workflow routes; JavaScript workflow execution was retired by Audit 6;
- deterministic command hooks and a status line;
- project settings plus separately reviewed user/global fragments;
- a portable, namespaced plugin distribution.

### Subagents and parallel work

- isolated subagent context;
- built-in and custom role routing;
- per-agent tools, model, effort, turn limits, permission mode, skills, hooks, memory, background behavior, and worktree isolation where supported;
- background sessions and agent view;
- worktrees for independent editing lanes;
- experimental agent teams only as an explicit opt-in;
- `/goal` only for bounded, verifiable completion conditions.

### Workflow boundary

Official JavaScript workflow support was evaluated, but its model-only execution surface could not
call the deterministic Python authority directly. Audit 6 therefore retired all executable workflow
scripts and preserved their capabilities through Python routes, skills, and audit profiles. This avoids
treating an “evidence-only” prompt as a hard permission boundary.

### Models, effort, and advisor

- aliases instead of fragile dated model IDs in shared configuration;
- `best`, `fable`, `opus`, `sonnet`, `haiku`, and `opusplan` where appropriate;
- role-specific model overrides in agents and workflows;
- effort routing with `low`, `medium`, `high`, `xhigh`, and `max` where supported;
- `ultracode` as a session effort/orchestration mode rather than a model;
- `/fast` as supported Opus acceleration rather than a smaller-model switch;
- an **inactive** `advisorModel: "opus"` fragment for Sonnet-main / Opus-advisor sessions.

The advisor is experimental, receives the full session transcript, and is not independent Tier-2 review. It requires the Anthropic API path and is not currently offered with Fable as the advisor. The package therefore never counts an advisor consultation as independent approval.

### Python orchestration, native CLI, SDK, and billing precedence

V4.4 implements the official distinction among interactive Claude Code, the supported programmatic
`claude -p` interface, the Agent SDK, and direct Messages API use.

The governed Python default is native `claude -p` under the authenticated Claude subscription login.
Python supplies structured JSON Schema output, project settings, explicit tools, model/effort/turn
limits, strict empty MCP, and an ephemeral `PreToolUse` hook. This preserves subscription usage while
adding deterministic orchestration and policy enforcement.

The package implements documented credential precedence: when `ANTHROPIC_API_KEY` is present,
Claude Code uses the API credential instead of subscription usage, including non-interactive `-p`
execution. Subscription mode therefore fails closed on API keys, bearer tokens, provider routes,
gateways, custom base URLs, and API-key helpers. API billing requires explicit mode, acknowledgement,
and a positive client-side budget gate.

The Agent SDK is an optional adapter pinned to `claude-agent-sdk==0.2.131`. It is not installed by
default and V4.4 permits it only in the explicitly API-billed lane. This is package policy for billing
clarity, not a claim that Python changes model intelligence.

The audit also incorporates Anthropic's June 16, 2026 support update: the announced separate monthly
Agent SDK credit transition was paused, so existing subscription-authenticated Agent SDK and
`claude -p` behavior remains against subscription usage limits. Account-level extra usage can still
create separately billed consumption after included plan limits when enabled. Authentication
preflight cannot inspect that setting or prove the final invoice.

### Sessions, context, and recovery

- `/context`, `/compact`, `/clear`, `/rewind`, `/branch`, named sessions, resume, fork, and handoff guidance;
- automatic compaction and auto memory;
- file checkpointing enabled;
- explicit checkpoint limitations for Bash, most subagent/workflow edits, concurrent/external changes, and linked paths;
- Git as the durable history and recovery authority.

### Remote execution

- Claude Code on the web / cloud sessions through `--cloud`;
- retrieval with `--teleport`;
- a reviewed cloud setup script and non-secret environment template;
- an opt-in cloud-only `SessionStart` dependency bootstrap;
- Remote Control as a separate surface that leaves execution, tools, MCP servers, files, and connectors on the local machine;
- local background sessions and agent view as a third, non-cloud option.

### MCP

- inactive examples only;
- GitHub remote MCP base URL with bounded toolsets and `X-MCP-Readonly: true`;
- Figma remote MCP example;
- environment-variable token references rather than embedded credentials.

## Corrections made to supplied or community material

### Unsupported nested model object

This was not installed:

```json
{
  "model": {
    "default": "...",
    "planning": "...",
    "quickTasks": "..."
  }
}
```

Claude Code uses the `model` setting, model aliases, fallback chains, plan-specific routes such as `opusplan`, agent/skill frontmatter, runtime delegation, and workflow stage options.

### Unsupported token-limit object

This was not installed:

```json
{
  "limits": {
    "maxTokensPerTurn": 4096,
    "maxContextTokens": 100000
  }
}
```

Those are not documented Claude Code project settings. Context is managed with model windows, automatic compaction, `/autocompact`, `/compact`, session design, isolated subagents, and supported environment controls.

### `--cwd` startup example

The package changes directory before starting a normal session:

```bash
cd /path/to/project
claude
```

`--cwd` is retained only where officially documented, such as filtering `claude agents`.

### Debug environment variable and log path

The old `CLAUDE_CODE_DEBUG=1` and fixed `~/.claude/logs/claude-code.log` recipe was removed. Supported routes include:

```bash
DEBUG=1 claude
claude --debug
claude --debug-file /absolute/path/to/debug.log
```

`CLAUDE_CODE_DEBUG_LOGS_DIR` is, despite its name, a **file path**. It does not enable debug mode by itself.

### Universal “undo” claim

The package does not promise universal undo. Checkpoints cover direct file-tool edits in the current session. Bash mutations, most background/subagent/workflow edits, concurrent edits, external changes, and symlink/hard-link changes require Git or another recovery mechanism.

### Workflow read-only claim

Workflow agents always run with edit acceptance. No workflow in this package is described as technically immutable. The project `independent-reviewer` remains the hard edit-less exact-SHA review lane.

### Background work wording

Background sessions and workflows can continue while the interactive session remains usable. The package does not promise asynchronous delivery by an assistant outside the active Claude Code runtime. The local host or cloud session must actually be running.

### Model-generation claims

Shared files use family aliases. Marketing names and dated IDs are not hard-coded as universal facts. Exact resolved model identity must be recorded in evidence when it matters.

## Package policy versus product behavior

The following are MAD Ventures / FounderOS policy, not built-in Claude Code guarantees:

- Founder authorization is Founder-only;
- one accountable builder owns each change;
- builder and independent reviewer remain separate;
- external models must be Founder-registered;
- state language must distinguish proposed, approved, implemented, verified, merged, deployed, and activated;
- live access defaults off;
- mutating workflows require explicit scope and approval references;
- no merge, deploy, activation, authority change, or credential mutation without the governing gate.

## Account-specific checks still required

Static package validation cannot prove:

- installed Claude Code version or account entitlements;
- Fable, Opus, Sonnet, Haiku, advisor, fast mode, ultracode, cloud, Remote Control, or agent-team availability;
- organization model allowlists or managed settings;
- GitHub/Figma MCP authentication;
- repository-specific build/test commands;
- real cloud network policy or setup success;
- database identity and read-only enforcement;
- production deployment or activation state;
- remaining subscription allowance, account-level extra-usage settings, or authoritative billing.

Run `claude --version`, `claude doctor`, `/status`, and the target repository’s real verification commands after installation.

## Official references

- Authentication: <https://code.claude.com/docs/en/authentication>
- CLI reference / print mode: <https://code.claude.com/docs/en/cli-reference>
- Costs and usage: <https://code.claude.com/docs/en/costs>
- Subscription Agent SDK update: <https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan>
- Agent SDK overview: <https://code.claude.com/docs/en/agent-sdk/overview>
- Python Agent SDK reference: <https://code.claude.com/docs/en/agent-sdk/python>
- Structured outputs: <https://code.claude.com/docs/en/agent-sdk/structured-outputs>
- Claude Code features in the SDK: <https://code.claude.com/docs/en/agent-sdk/claude-code-features>
- Python SDK releases: <https://github.com/anthropics/claude-agent-sdk-python/releases>

- https://code.claude.com/docs/en/changelog
- https://code.claude.com/docs/en/claude-directory
- https://code.claude.com/docs/en/settings
- https://code.claude.com/docs/en/model-config
- https://code.claude.com/docs/en/advisor
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/agents
- https://code.claude.com/docs/en/agent-view
- https://code.claude.com/docs/en/agent-teams
- https://code.claude.com/docs/en/workflows
- https://code.claude.com/docs/en/goal
- https://code.claude.com/docs/en/checkpointing
- https://code.claude.com/docs/en/sessions
- https://code.claude.com/docs/en/commands
- https://code.claude.com/docs/en/cli-reference
- https://code.claude.com/docs/en/env-vars
- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/claude-code-on-the-web
- https://code.claude.com/docs/en/cloud-environments
- https://code.claude.com/docs/en/remote-control
- https://github.com/github/github-mcp-server
- https://developers.figma.com/docs/figma-mcp-server/

- Fable plan/usage-credit rules: <https://support.claude.com/en/articles/15424964-claude-fable-5-on-your-plan>
