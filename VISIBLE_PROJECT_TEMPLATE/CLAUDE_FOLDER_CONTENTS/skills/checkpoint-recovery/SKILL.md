---
name: checkpoint-recovery
description: Inspect Claude Code file checkpoints and Git state, explain recent edits, and prepare a safe selective restore without destructive repository commands.
argument-hint: "[change or file to inspect/restore]"
disable-model-invocation: true
---

# Checkpoint and recovery protocol

Claude Code file checkpoints and Git history solve different problems. Treat checkpoints as session-local edit recovery; treat Git as repository history.

## Procedure
1. Freeze new edits and capture `git status --short` plus `git diff --stat`.
2. Ask Claude Code to show recent changes/checkpoint history and identify the smallest checkpoint that contains the unwanted edit.
3. Compare the checkpoint scope with the current working tree. Flag files that were modified by the user, another agent, or a different process.
4. Prefer selective restore of the affected checkpoint/files. Never use `git reset --hard`, `git clean`, blanket checkout/restore, or force operations as a shortcut.
5. Re-run the narrowest relevant validation after recovery, then inspect the final diff.

## Required output before any restore
- target checkpoint/change;
- files affected;
- user or concurrent edits at risk;
- exact restore operation proposed;
- validation to rerun;
- rollback path if the recovery itself is wrong.

Do not perform a restore until the requested target is unambiguous. A checkpoint revert does not authorize rewriting Git history or discarding unrelated uncommitted work.
