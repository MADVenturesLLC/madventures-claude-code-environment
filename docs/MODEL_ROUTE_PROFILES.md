# Executable model route profiles

These launchers make model selection a role decision instead of a permanent project setting. They use Claude Code aliases rather than dated model IDs, so the live account/provider remains the authority for availability and alias resolution.

The package was audited against the official Claude Code `2.1.223` documentation on August 6, 2026. The committed minimum is `2.1.223`, matching the security and workflow baseline validated for this release. Re-check `/model`, `/status`, and the provider policy after upgrades.

## Launch

Run from the target repository root:

```bash
/path/to/package/scripts/start-claude-route.sh everyday
/path/to/package/scripts/start-claude-route.sh planning 'Design the migration; do not edit.'
/path/to/package/scripts/start-claude-route.sh advisor
/path/to/package/scripts/start-claude-route.sh review
```

```powershell
& 'C:\path\to\package\scripts\start-claude-route.ps1' everyday
& 'C:\path\to\package\scripts\start-claude-route.ps1' planning
& 'C:\path\to\package\scripts\start-claude-route.ps1' advisor
& 'C:\path\to\package\scripts\start-claude-route.ps1' review
```

Extra arguments pass through to `claude`, so supported options such as `--name`, `--worktree`, `--resume`, and a starting prompt remain available.

## Profiles

| Profile | Route | Intended work | Boundary |
|---|---|---|---|
| `fanout` | Haiku, no effort override | exploration, file mapping, extraction, mechanical scans | no architecture or final verdict |
| `everyday` | Sonnet, high | normal feature work, tests, debugging, refactoring, documentation | ordinary engineering lane |
| `deep` | Opus, xhigh | demanding implementation, root cause, performance, deep technical review | use only when the problem merits it |
| `planning` | Fable, high, plan mode | consequential architecture and implementation planning | evidence/plan only; no implementation authority |
| `judgment` | Fable, xhigh | architecture decisions, adversarial verification, final synthesis | no Founder approval or lifecycle authority |
| `max-judgment` | Fable, max | one bounded decision where the cost of being wrong is unusually high | rare, explicit, session-specific |
| `best-available` | `best`, xhigh | high-judgment work when the account may not expose Fable | explicit fallback; record the resolved model |
| `advisor` | Sonnet high + Opus advisor | interactive coding with intermittent hard decisions | same conversation; never independent review |
| `ultracode` | `best`, ultracode | substantive tasks that benefit from automatic workflow planning | higher cost; session-only |
| `review` | Fable xhigh + review-only settings + plan mode | exact-target evidence and independent review | no edit tools; shell constrained by the review guard |

## Billing acknowledgement for Fable routes

These native launchers do not inspect plan seat class or account Usage settings. Fable can use usage
credits from the start on Pro/standard seats and after the included allowance on Max/premium seats.
Before launching `planning`, `judgment`, `max-judgment`, `best-available`, `ultracode`, or `review`,
verify `/status` and account Usage settings. Use the Python control plane when an executable
model-entitlement gate is required.

## Availability and failure behavior

- `planning`, `judgment`, `max-judgment`, and `review` intentionally name `fable`. They should fail clearly when the account/provider does not expose Fable rather than silently downgrade a governance-critical lane.
- `best-available` is the deliberate fallback. Record the model shown by `/status` in the evidence package.
- `advisor` is experimental and provider/account gated. It uses Sonnet as the primary session model and Opus as an advisor. The advisor sees the same conversation, so it cannot independently review the session’s own work.
- Fable is not currently an advisor option. Use it as the main session model or a dedicated judgment worker.
- The base project settings do not enable an advisor. The profile and `project/profiles/advisor-opus.settings.fragment.json` remain opt-in.

## Important rules

1. **Cheap fan-out, expensive judgment.** Haiku reads and extracts; Fable decides only when the judgment cost justifies it.
2. **Inherit unless the win is clear.** Do not pin every ad-hoc worker. Per-agent and workflow-stage overrides should be intentional.
3. **Do not confuse model choice with authority.** No model can merge, deploy, activate, ratify governance, or issue Founder authorization.
4. **Fast mode is separate.** `/fast` accelerates a supported Opus route; it does not switch to a smaller model. Availability and pricing are live account facts.
5. **Ultracode is not persisted here.** It is a session mode for high-reasoning workflow orchestration and resets with the session.
6. **The review profile is not a workflow.** Workflow workers accept edits. Use the canonical project `independent-reviewer` or this hardened direct-session profile for the exact-SHA boundary.
7. **Different model does not automatically mean independent.** Independence also requires a fresh context, edit-less tools, immutable target, no authorship, and no self-review.

## Per-role override points

- Agent definition: `model` and supported `effort` in `.claude/agents/*.md`.
- One-off delegation: the Agent tool’s model/effort parameters.
- Dynamic workflow: each `agent()` call can select a model and supported effort.
- Session launch: these role profiles or `/model`, `/effort`, and `/advisor`.

Use `/model-route <task>` when uncertain, then verify the live route with `/status` before relying on it.
