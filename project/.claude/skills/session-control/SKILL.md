---
name: session-control
description: Control context, compaction, resumption, checkpoints, and evidence handoffs during long Claude Code sessions without losing repository truth.
argument-hint: "[status|compact|handoff|resume-plan]"
---

# Session and context control

Use this skill when a build is long, the context is noisy, the goal has shifted, or a handoff/resume is needed.

## Preserve before compacting
Capture:
- the exact goal and acceptance criteria;
- repository, branch, base SHA, head SHA, and working-tree status;
- authoritative decisions and Founder approvals;
- files read and changed;
- commands run with results;
- open findings, blockers, and unresolved uncertainty;
- the next concrete action.

Write durable task state to a repository-approved handoff file only when requested. Otherwise provide a concise in-chat handoff block.

## Choose the control
- Use `/compact` when the goal and task remain the same but old conversational detail is crowding out current evidence.
- Use `/clear` only after durable state has been captured and a clean context is safer than retaining the current thread.
- Use `claude --resume` to continue the most recent relevant session, and verify repository/branch before trusting resumed assumptions.
- Start a new session when authority, repository, security boundary, or task identity materially changes.

## Context hygiene
Keep conclusions in the main context; delegate file dumps and broad searches to subagents. Re-read changed files and authoritative instructions after compaction. Never assume a compacted summary proves current code state.

## Output
Return a `SESSION STATE` block with pinned Git state, completed work, verified results, open risks, and next command. Mark any field that cannot be verified as `[Unknown]`.
