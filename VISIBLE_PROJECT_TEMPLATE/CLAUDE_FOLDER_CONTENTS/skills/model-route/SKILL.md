---
name: model-route
description: Classify a task by judgment cost, autonomy, fan-out, and verification needs, then choose the least expensive reliable model, effort, advisor, and execution surface per role.
argument-hint: "<task description>"
---

# Route work by role, not by habit

Apply the FounderOS doctrine: **cheap fan-out, expensive judgment**.

## Classify the work
Assess five dimensions:

1. **Judgment cost:** How expensive is a wrong conclusion to unwind?
2. **Mechanical volume:** How much search, reading, formatting, or repetitive scanning is required?
3. **Autonomy:** Will the agent run many steps without the Founder reviewing each one?
4. **Independence:** Must the verifier be separate from the builder?
5. **Escalation shape:** Is hard judgment continuous, or needed only at a few decision points?

## Default routing
- **Haiku:** bounded exploration, file discovery, symbol tracing, mechanical scans, formatting, and high-volume fan-out. Do not set an effort override for Haiku.
- **Sonnet:** everyday feature implementation, debugging, tests, documentation, and ordinary refactors.
- **Opus:** demanding interactive implementation, root-cause analysis, performance work, and deep technical review.
- **Fable:** architecture decisions, adversarial verification, final synthesis, release judgment, and complex multi-step autonomy where being wrong costs more than tokens.
- **No override:** inherit the session model when the task does not clearly justify a different tier.

## Advisor routing
Use `claude --advisor opus` or the opt-in `advisor-opus.settings.fragment.json` when Sonnet should handle routine execution but a stronger model should be available for planning, ambiguous failures, or completion checks. Do not enable an advisor merely to duplicate every decision.

The advisor is part of the same working session. It is not an independent Tier-2 reviewer and cannot approve its own session's work. Fable is not currently offered as the Claude Code advisor; use Fable as the main model, a dedicated subagent, or a workflow judgment stage instead.

## Effort routing
Use `low` for mechanical work, `medium` for ordinary implementation, `high` for difficult implementation or review, and `xhigh`/`max` only for consequential judgment. `ultracode` is a session mode that combines xhigh effort with automatic workflow orchestration; it is not a separate model. Never use effort as a substitute for evidence or independent review.

## Required response
Return:
- task classification;
- session model and effort recommendation;
- whether an advisor adds value and which supported advisor to use;
- each subagent role, model, effort, tools, and whether it may edit;
- expected fan-out/concurrency;
- final judge and independence boundary;
- cost-saving opportunities that do not weaken correctness.

Do not hard-code dated provider model IDs into shared package files. Prefer current aliases (`haiku`, `sonnet`, `opus`, `fable`, `best`) unless a verified compatibility requirement demands a pinned identifier.

## Billing boundary

Before selecting Fable or `best`, verify the active subscription lane and plan/seat entitlement. Fable can use usage credits from the start on Pro/standard seats. Prefer `madclaude` for automated routes because it applies a separate model-entitlement gate; native model routing cannot infer billing safety from authentication alone.
