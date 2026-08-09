# Model, effort, advisor, and external-lane routing

## Governing principle

**Cheap fan-out, expensive judgment.** Spend the strongest model where a wrong decision is costly to unwind. Do not spend judgment-tier tokens on mechanical discovery that can be safely delegated to a smaller model.

The package routes **per role**, not merely per session.

## Claude Code family lanes

| Lane | Default work | Do not use as |
|---|---|---|
| `haiku` | file discovery, symbol tracing, extraction, formatting, repetitive scans, cheap parallel exploration | final architecture authority, adversarial judge, broad autonomous editor |
| `sonnet` | everyday feature work, tests, debugging, documentation, ordinary refactors | sole final judge for high-risk work it authored |
| `opus` | demanding implementation, difficult diagnosis, performance analysis, deep technical review | high-volume mechanical fan-out |
| `fable` | costly architecture, adversarial verification, release judgment, final synthesis, long autonomy with expensive failure | default model for routine scanning or formatting |
| `best` | account/provider-selected strongest available route when portability matters more than a fixed family | proof of exact model identity |
| `opusplan` | stronger planning route followed by a lower-cost execution route where supported | independent review or a general model family |
| `inherit` / no override | safest subagent default when there is no clear reason to pin | a cost strategy by itself |

Use family aliases in shared files. Record the resolved model/version in review evidence when exact identity matters.

## Task classification

Before choosing a model, assess:

1. **Judgment cost:** how expensive is a wrong conclusion?
2. **Mechanical volume:** how much repetitive reading/searching is needed?
3. **Autonomy:** how many steps run without Founder review?
4. **Independence:** must the verifier be separate from the builder?
5. **Latency sensitivity:** is the Founder waiting in an interactive loop?
6. **Provider availability:** which aliases and preview features are actually exposed?
7. **Data locality:** does the task need approved local-only files or connectors?

## Default routing table

| Task | Primary route | Verification route |
|---|---|---|
| Repository map, file search, API extraction | Haiku, no effort override | Sonnet synthesis when conclusions matter |
| Ordinary feature, bug fix, refactor | Sonnet high | separate code/test reviewer; Opus for hard cases |
| Difficult interactive implementation | Opus high/xhigh | independent Opus or Fable according to risk |
| Architecture plan | Fable high/xhigh, or several Haiku/Sonnet lanes feeding Fable | adversarial Fable/Opus lane not used as builder |
| Performance diagnosis | Opus high/xhigh | independent benchmark and code reviewer |
| Security or governance judgment | Fable high/xhigh | exact-SHA independent reviewer and Founder gate |
| Large implementation | Founder-approved Grok 4.5 primary when its connector is available; Sonnet alternative | independent Claude/non-author model |
| Local-only repository coding | `hermes-local-code` through approved local surface, currently `deepseek-v4-flash` | independent model with recorded evidence |
| Final synthesis across many agents | Fable high/xhigh/max when justified | source/evidence reconciliation before verdict |

## Model choice is also a billing decision

Authentication and entitlement are separate. A saved subscription login avoids API-key billing, but
Fable may still use separately billed usage credits depending on plan and seat type. As of July 20,
2026, Max and premium seats include a bounded Fable allowance; Pro and standard seats use usage
credits from the start.

For Python routes, the model-entitlement gate allows proven Max Fable use with a warning and otherwise
requires one of these explicit choices:

```bash
# Conservative subscription model override
madclaude plan --repo . --model opus "<goal>"

# Keep Fable after reviewing Usage settings and accepting model-credit risk
madclaude plan --repo . --model fable --allow-usage-credits "<goal>"
```

The acknowledgement does not enable credits. Native `/model`, subagent, workflow, advisor, and route
launcher surfaces remain subject to the account's live model entitlement and Usage settings; verify
with `/status` before evidence-critical or high-volume work.

## The three native override points

### 1. Agent definition

Use frontmatter in `.claude/agents/*.md` when the role has a stable routing need:

```yaml
---
name: repository-explorer
description: Read-only repository exploration and concise evidence mapping.
tools: Read, Grep, Glob
model: haiku
---
```

Pin only clear wins. A model override can be blocked or substituted by organization allowlists.

### 2. One-off Agent delegation

A bounded delegation can choose a model at invocation time. Use this when the task is exceptional and does not justify a permanent registry entry.

### 3. Dynamic workflow stage

A workflow can route each `agent()` stage independently:

```js
const maps = await parallel(modules.map(module => () =>
  agent(`Map exports and consumers for ${module}.`, {
    label: `map ${module}`,
    model: 'haiku',
  })
));

const verdict = await agent(
  `Reconcile these maps and identify architecture risks:\n${maps.filter(Boolean).join('\n')}`,
  { label: 'architecture judgment', model: 'fable', effort: 'xhigh' }
);
```

The package still caps fan-out and uses a small workflow-size guideline. A script that can spawn many agents must include stop conditions, null-result handling, and a cost-aware small-slice test.

## Effort is a second dial

| Effort | Package use |
|---|---|
| `low` | cheap bounded mechanical work on supported models |
| `medium` | ordinary implementation and summarization |
| `high` | default for consequential feature work and review |
| `xhigh` | difficult diagnosis, architecture, or adversarial judgment |
| `max` | rare final judgment where the account supports it and the risk justifies cost |
| `ultracode` | session mode combining xhigh-style reasoning with automatic workflow planning for substantive tasks |

Do not set effort on package Haiku agents. Do not use effort as a substitute for tests, evidence, a separate reviewer, or Founder authorization.

## Advisor routing

The optional profile is:

```text
project/profiles/advisor-opus.settings.fragment.json
```

It contains:

```json
{
  "advisorModel": "opus"
}
```

Recommended session:

```bash
claude --model sonnet --effort high --advisor opus
```

Use Sonnet-main + Opus-advisor when:

- most turns are routine implementation;
- a few plan, ambiguity, recurring-error, or completion decisions deserve stronger judgment;
- switching the entire session to Opus would be unnecessary.

Do not use the advisor when:

- every turn needs the strongest model—switch the main model instead;
- the task is short or mechanical;
- independent review is required;
- the provider is Bedrock, Claude Platform on AWS, Google Cloud’s Agent Platform, or Microsoft Foundry;
- Fable is the intended advisor—Fable is currently not offered in that role.

Governance boundary: the advisor receives the full conversation and returns guidance to the same session. It is a second opinion, not an independent context, exact-SHA reviewer, or approval authority.

## Fast mode

`/fast` uses a supported Opus route with faster output. It does not select Haiku or lower the model family. Use it for latency-sensitive pair-programming and rapid diagnose/check loops where the account exposes the route and the added cost is acceptable.

Do not encode a specific historical Opus generation as a permanent package assumption. Verify the active model in `/status` and record it when evidence matters.

## Ultracode

Use:

```text
/effort ultracode
```

or:

```bash
claude --effort ultracode
```

for a session where substantive prompts should be considered for workflow orchestration. It resets with the session. It uses more agents/tokens and is not appropriate for routine edits.

A one-off prompt can request a workflow without changing the full session:

```text
ultracode: review every changed file, adversarially verify findings, and return one deduplicated report
```

## External model registry

The canonical package registry is `.claude/MODEL_REGISTRY.md`.

Registered external lanes:

- `grok-4.5` — Founder-approved primary large builder when the approved connector is available;
- `hermes-local-code` — local coding alias, currently backed by `deepseek-v4-flash`;
- `codex` — alternative implementation or verification when assigned;
- `gemini` — independent reasoning/verification when assigned;
- `cursor` — IDE execution surface; the underlying model must be attributed separately.

Registration does not grant credentials, network access, file access, write access, merge authority, deployment authority, or Founder approval. Every run records model identity, role, repository/SHA, permissions, files supplied/changed, commands, outputs, and review state.

## Independence rules

- The builder cannot be the sole independent reviewer of its own change.
- An advisor in the builder’s session is not independent.
- A prompt that says “be independent” does not create separation.
- Tier-2 review uses a fresh role, immutable base/head SHA, no mutation/delegation tools, and new review for every new head SHA.
- Workflow evidence can prepare a review package but cannot replace the canonical independent reviewer.
- Founder authorization remains Founder-only regardless of model capability.

## Cost-control checklist

1. Start with the smallest representative slice.
2. Use Haiku for broad search/read fan-out.
3. Return conclusions and evidence locations, not file dumps.
4. Use Sonnet for the everyday middle.
5. Escalate only judgment-heavy stages to Opus/Fable.
6. Bound workflow concurrency, total agents, rounds, and no-progress behavior.
7. Inspect `/usage`, `/workflows`, and `/tasks` during large runs.
8. Stop duplicated agents that are answering the same question.
9. Preserve independent verification even when optimizing cost.
