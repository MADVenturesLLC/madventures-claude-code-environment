---
name: python-control-plane
description: Route a governed task through the subscription-first MAD Ventures Python control plane with authentication, approval, scope, exact-SHA, subagent, and evidence safeguards.
argument-hint: "<plan|build|verify|tier2|release-readiness|repo-audit|security-audit|ui-review|fix-until-green> <goal>"
disable-model-invocation: true
---

# Use the MAD Ventures Python control plane

Run from the repository root:

```bash
python3 .claude/control-plane/madclaude.py <command> --repo . ...
```

A user-level `madclaude` wrapper is installed by the optional control-plane installer. On Windows,
use `python` when appropriate.

## Default subscription lane

```bash
claude auth login
madclaude auth-check --repo .
```

The default route is:

```text
--backend cli --billing-mode subscription
```

Python launches native `claude -p`. No `ANTHROPIC_API_KEY` or Agent SDK is required. Subscription
mode must stop when an API key, bearer token, provider route, custom base URL, gateway, or API-key
helper can outrank or obscure the saved subscription login. Never ask for, echo, or persist secrets.

Separate API billing requires all explicit gates:

```text
--billing-mode api --allow-api-billing --max-budget-usd <positive>
```

`--max-budget-usd` is a client-side estimate guard, not an invoice guarantee. Auth preflight does not
prove remaining plan allowance or account-level extra-usage settings.

## Optional SDK

The Agent SDK is not required for subscription use. Install it only for the explicit API lane:

```bash
./scripts/install-python-control-plane.sh --with-sdk
```

Then select `--backend sdk` together with all API billing gates.

## Governed routes

### Plan

```bash
madclaude plan --repo . "Design the exact approved objective"
```

The plan route may use only the registered read-only explorer and dependency-mapper subagents.

### Create a non-approved approval template

```bash
madclaude approval-template \
  "Design the exact approved objective" \
  --plan-file /absolute/path/to/structured-output.json \
  --output /absolute/path/to/founder-approval.json
```

The Founder must inspect and complete the template. A boolean without an inspectable approval
reference is insufficient.

### Build

```bash
madclaude build --repo . \
  --plan-file /absolute/path/to/structured-output.json \
  --approval-file /absolute/path/to/founder-approval.json \
  "Design the exact approved objective"
```

Build exposes one accountable mutation lane and no subagent delegation.

### Verify

```bash
madclaude verify --repo . \
  --verify "npm test" \
  --verify "npm run build" \
  "Verify the approved implementation"
```

### Exact-SHA Tier-2 review

```bash
madclaude tier2 --repo . \
  --base-sha 0123456789abcdef0123456789abcdef01234567 \
  --head-sha fedcba9876543210fedcba9876543210fedcba98 \
  --verify "npm test" \
  "Independently review the exact implementation"
```

### Release readiness

Use the same full-SHA arguments with `release-readiness`. Evidence never authorizes merge,
deployment, activation, or a governance-state change.

### Bounded repair

```bash
madclaude fix-until-green --repo . \
  --allowed-scope src/auth \
  --allowed-scope tests/auth \
  --verify "npm test" \
  --max-rounds 3 \
  "Repair the approved auth defect"
```

## Safety and evidence

- Every native CLI run receives an ephemeral Python-generated `PreToolUse` hook.
- MCP, web, shell, Skill, nested delegation, and credential access are disabled inside model routes.
- Read-only audit routes may use only route-specific registered subagents.
- Mutation routes have no Agent tool and remain single-builder.
- Verification commands are parsed direct commands, not shell pipelines.
- Build and repair changes are checked against exact approved scopes.
- Exact-SHA review runs in a detached temporary worktree and proves it remained unchanged.
- Evidence is written under `.claude/evidence/python-control-plane/` and remains local/untrusted until
  a governed promotion process accepts it.
- A new commit invalidates an older SHA-bound verdict.
