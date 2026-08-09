---
name: claude-doctor-plus
description: Audit the installed MAD Ventures Claude Code environment, configuration precedence, agents, skills, workflows, hooks, plugins, Git state, and repository profile.
argument-hint: "[full|configuration|workflows|hooks|plugin]"
disable-model-invocation: true
---

# Claude Doctor Plus

Run a read-only environment health review. `claude doctor` remains the product diagnostic; this skill adds package-specific checks.

## Required checks
1. Record `claude --version` and confirm it meets the package minimum.
2. Run `claude doctor`; preserve warnings and failures verbatim in the evidence summary.
3. Verify the active repository, branch, worktree, and trust boundary.
4. Inspect configuration precedence: managed, CLI, local, project, and user. Identify duplicate agents, skills, workflows, or plugin/project collisions.
5. Validate `.claude/settings.json`, agent and skill frontmatter, hook references, workflow JavaScript, and inactive MCP examples with the package scripts when present.
6. Confirm `.claude/PROJECT_PROFILE.md` contains no unresolved `REPLACE_ME` values and its commands match CI/package scripts.
7. Confirm protected-path, secret, destructive-command, SQL, and independent-review guards are present and tested.
8. Confirm checkpoints are enabled but do not misrepresent their coverage; Git remains the durable recovery boundary.
9. Inspect `/status`, `/agents`, `/skills`, `/workflows`, `/hooks`, `/permissions`, and `/memory` interactively where available.
10. Check model alias availability and organization/provider restrictions without replacing aliases with guessed dated IDs.

## Verdicts
- `HEALTHY`
- `HEALTHY_WITH_WARNINGS`
- `BLOCKED_CONFIGURATION`
- `BLOCKED_VERSION`
- `INCOMPLETE`

Return findings first, exact commands and results, configuration source for each effective setting, remediation sequence, and any account-specific checks that could not be performed. Do not change settings during the audit unless explicitly authorized after presenting the diff.
