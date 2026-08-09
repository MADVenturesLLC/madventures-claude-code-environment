# Python control-plane invocation examples

Run from the target repository root after the full v4.4 installation.

## Preflight

```bash
python3 .claude/control-plane/madclaude.py auth-check --repo .
python3 .claude/control-plane/madclaude.py doctor --repo .
python3 .claude/control-plane/madclaude.py routes --json
```

## Repository plan

```bash
python3 .claude/control-plane/madclaude.py plan --repo . \
  --model fable \
  --effort high \
  --allow-usage-credits \
  "Plan the approved command-center focus transaction without changing governed data semantics"
```

On Pro or an unproven Team/Enterprise seat, omit the acknowledgement and use `--model opus` to avoid
selecting a model that requires usage credits from the start. `--allow-usage-credits` only records the
operator's acknowledgement; it does not enable credits.

## Approval template

```bash
PLAN=/absolute/path/from-plan-outcome/structured-output.json
python3 .claude/control-plane/madclaude.py approval-template \
  "Plan the approved command-center focus transaction without changing governed data semantics" \
  --plan-file "$PLAN" \
  --output /tmp/founder-approval.json
```

Inspect `/tmp/founder-approval.json`. Do not set `founderApproved` to true unless the Founder approves
the exact plan hash, scopes, criteria, and commands.

## Approved build

```bash
python3 .claude/control-plane/madclaude.py build --repo . \
  --plan-file "$PLAN" \
  --approval-file /tmp/founder-approval.json \
  "Plan the approved command-center focus transaction without changing governed data semantics"
```

## Deterministic verification

```bash
python3 .claude/control-plane/madclaude.py verify --repo . \
  --verify "npm test" \
  --verify "npm run lint" \
  --verify "npm run build" \
  "Verify the current command-center implementation"
```

## Security audit

```bash
python3 .claude/control-plane/madclaude.py security-audit --repo . \
  --allow-usage-credits \
  "Audit authentication, authorization, secrets handling, trust boundaries, and unsafe execution paths"
```

## UI implementation review

```bash
python3 .claude/control-plane/madclaude.py ui-review --repo . \
  "Review the command center for truthful data states, accessibility, motion parity, and implementation risks"
```

A repository-only UI review cannot prove rendered appearance. Pair it with the package's browser and
visual-verification procedures when screenshots/runtime access are available.

## Exact-SHA Tier-2

```bash
BASE_SHA=$(git rev-parse origin/main^{commit})
HEAD_SHA=$(git rev-parse HEAD^{commit})
python3 .claude/control-plane/madclaude.py tier2 --repo . \
  --allow-usage-credits \
  --base-sha "$BASE_SHA" \
  --head-sha "$HEAD_SHA" \
  --verify "npm test" \
  --verify "npm run build" \
  "Perform independent Tier-2 review of the exact head"
```

## Release readiness

```bash
python3 .claude/control-plane/madclaude.py release-readiness --repo . \
  --allow-usage-credits \
  --base-sha "$BASE_SHA" \
  --head-sha "$HEAD_SHA" \
  --verify "npm test" \
  --verify "npm run build" \
  "Assess exact-SHA release readiness without merging or deploying"
```

## Bounded repair

```bash
python3 .claude/control-plane/madclaude.py fix-until-green --repo . \
  --allowed-scope app/components/command-center \
  --allowed-scope app/styles.css \
  --allowed-scope tests \
  --verify "npm test" \
  --verify "npm run build" \
  --max-rounds 3 \
  "Repair the approved command-center regression"
```

## Explicit API-billed run

This is intentionally not the default:

```bash
python3 .claude/control-plane/madclaude.py repo-audit --repo . \
  --billing-mode api \
  --allow-api-billing \
  --max-budget-usd 5 \
  "Audit the repository"
```

The command still requires `ANTHROPIC_API_KEY` to be securely present. Never paste the key into the
command, prompt, approval document, or evidence directory.
