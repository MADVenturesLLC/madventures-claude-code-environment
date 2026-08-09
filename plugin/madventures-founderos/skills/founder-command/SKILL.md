---
name: founder-command
description: Select the correct FounderOS skill, subagent, Python route, or session mode for a task without over-orchestrating it.
argument-hint: "<goal or current task>"
---

# FounderOS command router

Start with the smallest reliable operating surface. Do not launch a workflow merely because one exists.

## Decision order
1. **Direct conversation:** one tightly coupled task, interactive Founder supervision, and no reusable orchestration.
2. **Skill:** repeatable procedure or checklist whose next step still depends on judgment.
3. **Subagent:** one bounded isolated assignment, such as exploration, planning, implementation, testing, or review.
4. **Worktree agent:** independent edits that must not collide with the main checkout.
5. **Python route:** repeatable fan-out, synthesis, bounded loops, or cross-checking that needs deterministic enforcement and evidence.
6. **Agent team:** a few long-running peers that need shared coordination and communication.

## Command palette

### Understand and plan
- `/founderos-onboard` — pin repository state, governing files, commands, and unknowns.
- `/model-route <task>` — select models and effort per role.
- `madclaude plan` — governed repository plan.
- `madclaude repo-audit` — cross-cutting repository audit.
- `madclaude repo-audit --profile docs-drift` — compare docs and lifecycle claims to executable reality.

### Build and repair
- `/governed-feature` — interactive approved feature procedure.
- `madclaude build` — one **mutating Python route** requiring SHA-bound Founder approval and scope.
- `/bugfix-loop` — interactive root-cause-first repair.
- `madclaude fix-until-green` — bounded Python repair route.
- `/multi-agent-build` — planner/builder/reviewer decomposition.

### Verify and review
- `madclaude verify` — Python runs mandatory gates before model interpretation.
- `madclaude tier1` — exact-SHA technical review and `REVIEW.json` evidence.
- `madclaude tier2` — exact-SHA independent review with manifest-bound participant exclusion.
- `madclaude repo-audit --profile test-gap` — behavior-to-test coverage analysis.
- `/pr-tier2-review` — exact-SHA independent review procedure.

### Risk and operations
- `madclaude security-audit` — adversarial security audit.
- `madclaude repo-audit --profile performance` — measurement-first performance audit.
- `madclaude repo-audit --profile incident` — incident timeline and competing-hypothesis analysis.
- `madclaude release-readiness` — release/deployment/activation boundary review.
- `madclaude ui-review` — truthful UI, accessibility, state, and visual review.

### Session health
- `/session-control` — choose compact, clear, handoff, or resume.
- `/checkpoint-recovery` — recover through checkpoints and Git evidence.
- `/claude-doctor-plus` — package and repository health audit.

## Required answer
Return the selected surface and command, model/effort route, whether edits are allowed, expected evidence, and the stop condition. Python is the only authoritative orchestration engine; do not substitute prompt-only JavaScript automation.
