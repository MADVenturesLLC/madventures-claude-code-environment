# MAD Ventures Claude control plane 4.4.1

A transparent, subscription-first Python control plane for governed FounderOS and MAD Ventures
engineering workflows.

Python does not make Claude smarter. This package uses Python to control stage ordering,
authentication, tools, scopes, structured output, verification, exact-SHA isolation, evidence, and
bounded repair.

## Runtime requirements

- Python 3.10 or newer
- Git
- native Claude Code CLI 2.1.223 or newer
- an authenticated Claude subscription for the default backend
- optional `claude-agent-sdk==0.2.131` only for the explicit API-billed backend

## Install

From the V4.4 package root:

```bash
./scripts/install-python-control-plane.sh
```

PowerShell:

```powershell
.\scripts\install-python-control-plane.ps1
```

The default installation performs no dependency download. It creates an isolated Python runtime,
copies this transparent source, and installs the `madclaude` wrapper.

Optional API SDK adapter:

```bash
./scripts/install-python-control-plane.sh --with-sdk
```

```powershell
.\scripts\install-python-control-plane.ps1 -WithSdk
```

## Default execution path

```text
Python orchestrator
  -> authentication and billing preflight
  -> native `claude -p`
  -> saved Claude subscription login
  -> structured JSON Schema output
  -> ephemeral PreToolUse policy
  -> route-specific tools and read-only subagents
  -> Python verification and evidence
```

Default options:

```text
--backend cli
--billing-mode subscription
```

No API key or Agent SDK is required.

## Billing safety

Run:

```bash
claude auth login
madclaude auth-check --repo .
```

Subscription mode refuses to start if an API key, bearer token, provider route, gateway, custom base
URL, or API-key helper could supersede or obscure the saved login.

Separate API billing requires:

```text
--billing-mode api
--allow-api-billing
--max-budget-usd <positive>
ANTHROPIC_API_KEY present in the caller's secure environment
```

The optional SDK additionally requires `--backend sdk`. Credential preflight proves the observed
credential lane only; it does not prove remaining plan allowance, model-specific entitlement,
account-level extra usage, or the final invoice. A Fable or ambiguous model on Pro/unproven seat
classes is blocked unless you choose `--model opus` / `--model sonnet` or explicitly add
`--allow-usage-credits`. That flag does not enable credits.

## Routes

```text
plan
build
verify
tier2
release-readiness
repo-audit
security-audit
ui-review
fix-until-green
```

List the live registry:

```bash
madclaude routes --json
```

Read-only planning and audit routes may invoke only their registered read-only subagents. Build and
repair routes expose no Agent tool and retain one accountable mutation lane.

## Examples

Plan:

```bash
madclaude plan --repo . --model opus "Plan the approved objective"
```

Create a non-approved Founder approval template:

```bash
madclaude approval-template \
  "Plan the approved objective" \
  --plan-file /absolute/path/to/structured-output.json \
  --output /absolute/path/to/founder-approval.json
```

Build after Founder review and completion of the approval file:

```bash
madclaude build --repo . \
  --plan-file /absolute/path/to/structured-output.json \
  --approval-file /absolute/path/to/founder-approval.json \
  "Plan the approved objective"
```

Exact-SHA Tier-2 review:

```bash
madclaude tier2 --repo . \
  --base-sha <40-character-base-sha> \
  --head-sha <40-character-head-sha> \
  --verify "npm test" \
  "Independent exact-SHA review"
```

Bounded repair:

```bash
madclaude fix-until-green --repo . \
  --allowed-scope src/auth \
  --allowed-scope tests/auth \
  --verify "python -m pytest tests/auth" \
  --max-rounds 3 \
  "Repair the approved defect"
```

## Policy model

Every native CLI run receives a temporary settings file with a Python `PreToolUse` hook. The hook:

- enforces the exact route tool allowlist;
- blocks shell, web, Skill, MCP, and nested delegation;
- blocks secret-bearing paths;
- blocks FounderOS authority/control-plane paths from mutation;
- enforces explicit write scopes;
- restricts Agent calls to the route's registered subagent names;
- denies subagent mutation because read-only child agents inherit the same policy.

The temporary settings file is removed after execution. A project Python-backed hook provides a second
layer when the full V4.4 project environment is installed.

## Evidence and exit codes

Evidence is written under:

```text
.claude/evidence/python-control-plane/<route>/<run-id>/
```

It is redacted and SHA-256 manifested, but remains local/untrusted until a governed evidence process
accepts it.

```text
0   completed
3   preflight/configuration/repository/policy/backend/runtime error
10  route executed but controlled gate failed
130 interrupted
```

## Tests

```bash
python3 run-tests.py
```

From the parent V4.4 package:

```bash
bash scripts/test-python-control-plane.sh
```
