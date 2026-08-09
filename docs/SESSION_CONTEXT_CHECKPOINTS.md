# Sessions, context, checkpoints, and durable handoffs

A long Claude Code build succeeds when repository truth survives compaction, interruption, model changes, background work, and human handoff. Conversation history is useful, but Git state and written evidence remain the durable authority.

## Name substantial sessions

At launch:

```bash
claude --name console-focus-transaction
```

During a session:

```text
/rename console-focus-transaction
```

Resume:

```bash
claude --continue
claude --resume
claude --resume console-focus-transaction
```

Use names tied to a task, PR, incident, or gate. Do not use a generated title as the only durable reference.

## Context controls

### Inspect

```text
/context
/status
```

Use `/context` to see what consumes the window. Keep always-on `CLAUDE.md` doctrine factual and compact; move procedural detail into skills, agents, and workflows.

### Compact

```text
/compact preserve goal, approvals, repository/branch/SHA, changed files, command results, open findings, and exact next action
```

Use `/compact` when:

- the task remains the same;
- the current session contains valuable decisions;
- older exploration can be summarized;
- a handoff block has been written first for high-risk work.

Auto-compaction remains enabled. `/autocompact <tokens>` or supported environment controls can move the threshold, but compaction is not a substitute for a durable project profile or Git evidence.

### Clear

```text
/clear
```

Use `/clear` when:

- the objective has materially changed;
- stale assumptions are contaminating decisions;
- the task should begin from a clean context;
- a durable handoff exists.

`/clear` starts a new conversation context and clears an active `/goal`. In a local process, `/rewind` may expose the previous session entry until the process exits. Cloud sessions do not support `/clear`; start a new cloud session instead.

### Branch or subtask

```text
/branch
/subtask investigate the failing cache invalidation test without editing
```

Use `/branch` to try a different approach while preserving the original conversation. Use `/subtask` for a bounded isolated result returned to the parent. Neither automatically creates independent review authority.

### Side question

```text
/btw what does this error code mean?
```

Use `/btw` for no-tools questions that should not expand the main conversation history.

## Checkpoints

File checkpointing is enabled in the shared package settings. Claude Code captures checkpoints before user prompts and stores them with the session so `/rewind` remains available after resume.

Open the menu:

```text
/rewind
```

Typical actions include:

- restore code and conversation;
- restore conversation only;
- restore code only;
- summarize from a selected point;
- summarize up to a selected point.

### What checkpoints cover

They track changes made by Claude’s direct file-editing tools in the current session.

### What checkpoints do not reliably restore

- file mutations made through Bash/PowerShell commands;
- most edits made by background subagents, workflows, or other sessions;
- manual changes from editors or external processes;
- concurrent worktree/session changes;
- symlinked or hard-linked paths;
- remote service changes, database writes, PR actions, deployments, or activations.

A foreground forked skill can be a special case, but package recovery policy remains conservative: inspect Git before relying on rewind.

### Checkpoint rule

**Checkpoint = quick local undo. Git = durable history.**

Before a consequential mutating stage:

```bash
git status --short
git diff --stat
git rev-parse HEAD
```

Use a branch/worktree and make reviewed commits at coherent boundaries. Do not use checkpointing as permission to run destructive shell commands.

## View recent changes

Ask Claude to show evidence, then verify with Git:

```bash
git status --short
git diff --stat
git diff --name-only
git diff
git log --oneline --decorate -n 12
```

“Show me the recent changes you made” is a useful prompt, but the answer is narrative. The working tree and commit graph are authoritative.

## Goals and resumption

A goal can persist when an active session is resumed:

```text
/goal npm test -- auth exits 0, npm run lint exits 0, no files outside src/auth and test/auth change, or stop after 20 turns
```

Use `/goal` with no argument to inspect status and `/goal clear` to stop it. The evaluator reads the conversation evidence; it does not independently run commands. Therefore the condition must require Claude to surface command results and include a bound.

Do not use vague goals such as “make it world class.”

## Background sessions and agent view

Background sessions have their own transcripts and lifecycle:

```bash
claude --bg "Investigate the flaky integration test"
claude agents
claude attach <session-id>
```

Do not assume the foreground session’s checkpoint can restore background-session edits. Use a worktree for background editors and Git for recovery.

## Remote Control session state

Remote Control is the same local session viewed from another device. Its transcript, checkpoints, filesystem, MCP servers, tools, subagents, and workflows remain on the local host. A remote message does not create a new cloud copy or a separate independence boundary.

Name the session and verify the local branch before enabling remote access.

## Cloud session context

Cloud sessions are separate sessions on Anthropic-managed infrastructure:

- `/compact` and `/context` work;
- `/clear` does not;
- project `.claude` content travels through the repository;
- local user-home memory/configuration does not automatically become cloud project state;
- teleporting brings the session into the local CLI, after which actual Git state must be reverified.

Do not rely on a cloud narrative as proof of local files or deployment state.

## Durable handoff contract

Before compaction, clear, teleport, model switch, external delegation, or session end, write:

```markdown
# Session handoff

## Goal
...

## Authority and approvals
- Founder approval reference:
- Allowed scope:
- Prohibited actions:

## Repository state
- Repository:
- Working directory:
- Branch:
- Base SHA:
- Current head SHA:
- Working tree:

## Observed facts
- ...

## Decisions made
- ...

## Files changed
- path — reason

## Verification
- command — exit/result

## Open findings / unknowns
- ...

## Exact next action
1. ...

## Stop conditions
- ...
```

Use `examples/SESSION_HANDOFF.md` and `/context-handoff` for the full pattern.

## Context-efficiency rules

1. Put stable facts and authority in repository files.
2. Put reusable procedures in skills.
3. Put bounded specialist work in subagents.
4. Put large repeatable fan-out in workflows.
5. Return conclusions and file/line evidence, not raw dumps.
6. Compact after a coherent milestone, not in the middle of an unresolved decision.
7. Clear when the task changes, not merely because the session is long.
8. Verify every resumed or teleported session against Git before editing.
9. Keep one accountable builder and one current source of truth.
