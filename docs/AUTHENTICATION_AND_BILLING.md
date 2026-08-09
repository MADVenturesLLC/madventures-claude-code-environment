# Authentication and billing controls

## Governing decision

V4.4 is **subscription first**.

The default Python route does not call the Anthropic Messages API and does not require an
`ANTHROPIC_API_KEY`. Python launches the native Claude Code CLI in print mode (`claude -p`) after
proving that Claude Code is authenticated through a Claude subscription lane. The optional Python
Agent SDK adapter is disabled unless the caller explicitly selects the separate API-billed lane.

This design exists because authentication precedence changes billing behavior:

- a saved Claude subscription login can power ordinary Claude Code and `claude -p` usage;
- when `ANTHROPIC_API_KEY` is present, Claude Code uses the API credential instead of subscription
  usage, including non-interactive `-p` runs;
- API usage is billed separately through Claude Console;
- account-level **extra usage / usage credits**, when enabled by the account owner, may allow
  continued separately billed usage after included plan limits are exhausted.

The control plane proves the credential lane visible at launch. It cannot inspect the user's invoice,
organization billing ledger, remaining plan allowance, model-specific plan entitlements, Team or
Enterprise seat class, or account-level extra-usage setting.

> **Current-policy correction:** Anthropic's June 16, 2026 support update says the previously
> announced change to a separate monthly Agent SDK credit was paused. Existing behavior remains in
> effect: subscription-authenticated Agent SDK and `claude -p` usage continues to draw from the
> subscription's usage limits. V4.4 does not encode the earlier June 15 cutoff claim.

## Model entitlement is a separate billing gate

A Claude subscription login does **not** prove that every model is included in that plan. Starting
July 20, 2026, Fable 5 is included within a plan-specific weekly allowance on Max and premium
Team/seat-based Enterprise seats. On Pro and standard Team/seat-based Enterprise seats, Fable uses
pay-as-you-go usage credits from the start. Usage-based Enterprise and API access use standard API
rates.

The Python control plane therefore applies a second, model-level gate after authentication:

- Max + an explicit Fable model: allowed with a warning because the package cannot observe the
  remaining Fable allowance or whether usage credits will be used after it is exhausted;
- Pro + Fable: blocked unless the operator uses `--allow-usage-credits` or overrides the route with
  `--model opus` / `--model sonnet`;
- Team, Enterprise, unreported seat class, or ambiguous aliases such as `best` / `inherit`: blocked
  unless the operator uses an included exact model or explicitly acknowledges the risk;
- API mode: already requires the separate API billing gates and does not use this subscription-model
  acknowledgement.

`--allow-usage-credits` is an acknowledgement only. It does not enable usage credits, prove that
credits are available, cap charges, or authorize an API key. To guarantee that a run cannot use
separately billed usage credits, disable usage credits in the Claude account and choose a model
included in the plan. Verify the active lane with `/status` and review account Usage settings.

Native Claude Code sessions, agents, and JavaScript workflows outside the Python control plane do not
receive this executable model gate. Apply the same model/plan check before launching a Fable or
`best` route there.

## Default sequence

```bash
claude auth login
claude auth status
madclaude auth-check --repo .
```

Repository-local alternative:

```bash
python3 .claude/control-plane/madclaude.py auth-check --repo .
```

Every model-backed route repeats this preflight immediately before Claude starts.

## Subscription-mode fail-closed checks

The default `--billing-mode subscription` run stops before model execution if it detects any
credential or routing mechanism that could supersede or obscure the saved subscription lane:

```text
ANTHROPIC_API_KEY
ANTHROPIC_AUTH_TOKEN
CLAUDE_CODE_USE_BEDROCK
CLAUDE_CODE_USE_VERTEX
CLAUDE_CODE_USE_FOUNDRY
CLAUDE_CODE_USE_ANTHROPIC_AWS
ANTHROPIC_BASE_URL
ANTHROPIC_BEDROCK_BASE_URL
ANTHROPIC_VERTEX_BASE_URL
ANTHROPIC_FOUNDRY_BASE_URL
ANTHROPIC_CUSTOM_HEADERS
apiKeyHelper
credential/routing variables injected through known Claude settings env blocks
```

The report identifies the conflicting variable or settings path but never reads or prints the secret
value.

A successful subscription preflight reports one of these lanes:

```text
subscription-saved-login
subscription-oauth-token
```

Ambiguous authentication is a hard stop. V4.4 does not infer “subscription” from a generic OAuth
label alone.

## Why native `claude -p` is the default

`claude -p` is Claude Code's supported non-interactive interface. It retains the user's Claude Code
login and supports structured JSON output, model/effort routing, explicit tools, settings, hooks,
turn limits, and strict MCP configuration.

V4.4 wraps each invocation with an ephemeral `PreToolUse` policy file. The policy is generated by
Python, passed with `--settings`, and deleted after the run. This means scope, secret, tool, and
subagent restrictions do not depend on the reviewed commit already containing V4.4 configuration.

## Optional Agent SDK lane

The Agent SDK is not needed for subscription use in this package. It is an optional adapter for an
explicit API-billed integration:

```bash
./scripts/install-python-control-plane.sh --with-sdk
```

or:

```powershell
.\scripts\install-python-control-plane.ps1 -WithSdk
```

Selecting `--backend sdk` without all API billing gates fails closed.

## Explicit API mode

Separate API billing requires all of the following in the same invocation:

```text
--backend cli          # or: --backend sdk after optional SDK installation
--billing-mode api
--allow-api-billing
--max-budget-usd <positive number>
ANTHROPIC_API_KEY present in the caller's secure environment
```

Example:

```bash
madclaude repo-audit \
  --repo . \
  --billing-mode api \
  --allow-api-billing \
  --max-budget-usd 5 \
  "Audit the repository"
```

The package never asks for, creates, logs, copies, or stores the key. Alternate bearer, gateway,
cloud-provider, helper, custom-base-URL, and OAuth routes are rejected in API mode so the requested
billing lane is not ambiguous.

`--max-budget-usd` is a client-side API stop, not an authoritative invoice or FounderOS ledger
record. Returned `total_cost_usd` values are estimates and are recorded as such.

## Clear API routing from the current shell

Inspect variable names only:

```bash
env | grep -E '^(ANTHROPIC_|CLAUDE_CODE_USE_)' | cut -d= -f1
```

Remove conflicting variables from the current shell:

```bash
unset ANTHROPIC_API_KEY
unset ANTHROPIC_AUTH_TOKEN
unset CLAUDE_CODE_USE_BEDROCK
unset CLAUDE_CODE_USE_VERTEX
unset CLAUDE_CODE_USE_FOUNDRY
unset CLAUDE_CODE_USE_ANTHROPIC_AWS
unset ANTHROPIC_BASE_URL
unset ANTHROPIC_BEDROCK_BASE_URL
unset ANTHROPIC_VERTEX_BASE_URL
unset ANTHROPIC_FOUNDRY_BASE_URL
unset ANTHROPIC_CUSTOM_HEADERS
```

Also remove stale exports from shell profiles, environment managers, and `.env` loaders before
relaunching Claude Code.

PowerShell, current process only:

```powershell
'ANTHROPIC_API_KEY',
'ANTHROPIC_AUTH_TOKEN',
'CLAUDE_CODE_USE_BEDROCK',
'CLAUDE_CODE_USE_VERTEX',
'CLAUDE_CODE_USE_FOUNDRY',
'CLAUDE_CODE_USE_ANTHROPIC_AWS',
'ANTHROPIC_BASE_URL',
'ANTHROPIC_BEDROCK_BASE_URL',
'ANTHROPIC_VERTEX_BASE_URL',
'ANTHROPIC_FOUNDRY_BASE_URL',
'ANTHROPIC_CUSTOM_HEADERS' | ForEach-Object {
  Remove-Item "Env:$_" -ErrorAction SilentlyContinue
}
```

Then run:

```bash
claude auth status
madclaude auth-check --repo .
```

## Saved login and setup tokens

Interactive saved login is preferred for personal development. An approved non-interactive Claude
Code environment may use a token produced by `claude setup-token` and supplied as
`CLAUDE_CODE_OAUTH_TOKEN`. Treat it as a secret: never commit, print, share, or repurpose it as a
third-party application credential.

## Evidence boundary

A successful preflight may record:

```text
requested billing mode
credential lane
logged-in state
subscription type when reported
auth method when reported
API provider when reported
masked account hint
conflict names
warnings
```

It does not record credential values. It proves only what the control plane observed at launch; it
does not prove final billing, account-level extra-usage state, remaining subscription allowance, or
an authoritative cost ledger.

## Official references

- [Claude Code authentication](https://code.claude.com/docs/en/authentication)
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Claude Code costs and usage](https://code.claude.com/docs/en/costs)
- [Claude Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview)
- [Agent SDK subscription usage update](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)
- [Fable 5 plan and usage-credit rules](https://support.claude.com/en/articles/15424964-claude-fable-5-on-your-plan)
