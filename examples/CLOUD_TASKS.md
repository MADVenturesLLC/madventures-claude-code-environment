# Cloud task patterns

## Plan locally, execute remotely

```text
Goal: Produce an implementation plan only. Inspect the repository, map dependencies, identify protected paths, define verification commands, and stop for Founder approval before editing.
```

After approval, commit and push the plan, then launch:

```bash
claude --cloud "Execute the approved plan at docs/approved-plan.md. Keep one accountable builder, run required checks, request independent review, and stop before merge/deployment/activation."
```

## Parallel non-overlapping tasks

```bash
claude --cloud "Fix the isolated auth test failure. Own only auth tests and auth implementation files."
claude --cloud "Audit documentation drift only. Do not edit runtime code."
claude --cloud "Review UI accessibility and produce findings only. Do not modify files."
```

## Monitor and retrieve

Inside a local Claude Code session:

```text
/tasks
```

From a clean checkout of the same repository:

```bash
claude --teleport
```

Before teleporting, verify the local working tree is clean and the cloud branch has been pushed.
