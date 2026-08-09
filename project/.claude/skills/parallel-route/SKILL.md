---
name: parallel-route
description: Select the safest and most efficient Claude Code execution surface across subagents, worktrees, background sessions, agent teams, workflows, goals, and cloud sessions.
argument-hint: "<task and constraints>"
---

# Parallel execution router

Classify the task before spawning anything.

## Surface selection
- **Main conversation:** tightly coupled interactive work requiring frequent Founder steering.
- **Subagent:** one bounded investigation or specialist review whose raw context should stay isolated.
- **Worktree agent:** an independent edit stream with non-overlapping ownership.
- **Background session:** a long-running independent task that does not need peer messaging.
- **Agent team:** a handful of peers that must coordinate through shared tasks and messages.
- **Dynamic workflow:** repeatable scripted fan-out, loops, schemas, or many-agent synthesis.
- **Goal:** one session should continue autonomously until a concrete verifier passes.
- **Cloud session:** work should persist remotely and can start from committed/pushed repository state.

## Routing doctrine
Use the smallest surface that reliably fits. Prefer cheap Haiku fan-out for mechanical evidence, Sonnet for ordinary implementation, Opus for deep technical diagnosis, and Fable for costly architecture, adversarial verification, or final synthesis. Omit model overrides when inheritance is safer.

## Collision control
Name one accountable owner. Parallel mutation requires isolated worktrees or distinct branches and explicit file/subsystem ownership. Never run two autonomous builders against the same files. Keep governance, merge, deployment, activation, secrets, and destructive recovery behind Founder approval.

## Output
Return: selected surface, topology, model/effort route, ownership map, maximum concurrency, expected checkpoints, stop conditions, and why simpler surfaces were rejected.
