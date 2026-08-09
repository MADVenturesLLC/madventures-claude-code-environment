# Founder-approved coding model registry

**Registry purpose:** identify every permitted coding/review model or execution surface, its governed role, and its authority boundary. Registration does not grant credentials, network access, local-file access, write access, merge authority, deployment authority, or Founder approval.

## Claude Code native lanes

| Registry ID | Role | Default use | Authority boundary |
|---|---|---|---|
| `fable` | Judgment / planning tier | Consequential architecture, adversarial verification, final synthesis, high-cost autonomy | May recommend; cannot self-ratify governance, merge, deploy, activate, or substitute for Founder authorization |
| `opus` | Principal engineering tier | Demanding implementation, root cause, performance, deep technical review | Cannot independently approve its own authored work |
| `sonnet` | Everyday engineering tier | Feature work, refactoring, tests, debugging, documentation; alternate large builder | One accountable builder; normal repository permissions and review gates apply |
| `haiku` | Fan-out / mechanical tier | Search, file mapping, extraction, formatting, bounded scans | Do not use as final architecture or independent judgment authority |

Use aliases in package configuration so the account/provider resolves the currently available generation. Pin a dated model only for a documented compatibility or evidence reason.

**Billing boundary:** subscription authentication and model inclusion are separate. Fable may use usage credits depending on plan/seat. Verify `/status` and Usage settings; use the Python model-entitlement gate for deterministic automation.

## Founder-registered external lanes

| Registry ID | Current identity | Governed role | Access status |
|---|---|---|---|
| `grok-4.5` | Grok 4.5 | Primary large implementation builder when its approved connector is available | Registered; connector/credentials are not bundled; writes require the same path, test, review, and Founder gates as Claude builders |
| `hermes-local-code` | Local coding alias; current backend `deepseek-v4-flash` | Governed local repository reading and implementation | Registered for reads and writes through an approved local execution surface; backend changes require registry update; cannot review its own work independently |
| `codex` | Codex/GPT coding lane | Alternative implementation or independent verification when assigned | Registered identity; actual model/version and connector must be recorded per run; no default write or approval grant |
| `gemini` | Gemini reasoning/coding lane | Independent analysis, architecture challenge, or verification when assigned | Registered identity; actual model/version and connector must be recorded per run; no default write or approval grant |
| `cursor` | IDE execution surface, not a reviewer identity | Human-steered editing and model access | Registered tool surface; the underlying model identity and authored diff must be attributed separately |

## Founder-approved default routing

- Planning and costly judgment: Fable at high effort; use xhigh/max only when the task justifies it.
- Large implementation: Grok 4.5 primary; Sonnet as the Claude Code alternative.
- Medium/demanding implementation: Opus-class route when needed; otherwise Sonnet.
- Light/mechanical work: Haiku.
- Local-file coding: `hermes-local-code`, currently backed by `deepseek-v4-flash`.
- Selective in-session escalation: Sonnet main plus the Opus advisor when hard judgment is intermittent. The advisor remains part of the same session and is not Tier-2 independence. Fable is not currently offered as the Claude Code advisor; use it as the main model or a dedicated judgment worker.
- Tier-2 review: a model independent from the builder, preferably Fable at high/xhigh; Opus-class is the fallback. Never use the authoring model as the sole independent reviewer.

## Per-run audit record

For every external delegation record:

- registry ID and exact model/version if known;
- role (`planner`, `builder`, `reviewer`, `verifier`, or `synthesizer`);
- repository, branch, base SHA, and head SHA;
- read/write/network/command permissions granted;
- files or artifacts supplied;
- files changed;
- commands and tests run;
- output location;
- review and Founder authorization state.

A model or connector not listed here is unregistered. Stop and obtain Founder approval before granting it repository access.
