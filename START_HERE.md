# START HERE — MAD Ventures Claude Code Operating Environment v4.4.2

This is the shortest complete path from a downloaded ZIP to a governed MAD Ventures / FounderOS Claude Code session.

> On macOS, the canonical `project/.claude` source is hidden by Finder. Use `VISIBLE_PROJECT_TEMPLATE/` to inspect it, or right-click `INSTALL_MAC.command` and choose **Open** for guided installation.

## 1. Choose the deployment

Use the **full project environment** for:

- `FounderOS`;
- `founder-os-telegram`;
- `founder-os-console`;
- any repository that needs protected paths, scoped hooks, project rules, exact-SHA review, or read-only database evidence.

Use the **portable plugin** for other MAD Ventures repositories that need namespaced agents, skills, workflows, and global defense-in-depth hooks without the full FounderOS project policy.

Do not install both in the same repository unless duplicate namespaced and unnamespaced tools are intentional.

## 2. Verify prerequisites

```bash
claude --version
claude doctor
git --version
node --version
python3 --version
```

Required package floor:

- Claude Code `2.1.223` or newer;
- Node.js 18 or newer;
- Python 3.10 or newer;
- Git.

The package was audited against the official Claude Code `2.1.223` documentation on August 6, 2026. Model and preview-feature availability still depends on the live account, provider, organization policy, and region.

## 3. Validate the extracted package

Fast install-time integrity check:

```bash
python3 scripts/quick-validate.py
```

The guided macOS verifier is `VERIFY_PACKAGE.command`. For the exhaustive release suite:

```bash
python3 scripts/build-plugin.py
python3 scripts/validate-config.py
node scripts/validate-workflows.mjs
node scripts/test-hooks.mjs
bash scripts/smoke-test-install.sh
bash scripts/test-route-launcher.sh
bash scripts/test-cloud-session.sh
python3 python-control-plane/run-tests.py
```

A release is not ready when any check fails. A PowerShell warning is acceptable only on a machine without PowerShell; run the PowerShell installer in a controlled Windows test before organization-wide Windows deployment.

## 4. Install the full environment

### macOS, Linux, or WSL

```bash
chmod +x scripts/*.sh cloud/setup.sh project/.claude/cloud/session-start.sh
./scripts/install.sh /absolute/path/to/repository --profile auto --install-python-control-plane
```

Explicit profiles:

```bash
./scripts/install.sh ~/code/FounderOS --profile doctrine
./scripts/install.sh ~/code/founder-os-telegram --profile runtime
./scripts/install.sh ~/code/founder-os-console --profile console
./scripts/install.sh ~/code/another-project --profile generic
```

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1 -ProjectPath 'C:\code\FounderOS' -Profile doctrine -InstallPythonControlPlane
```

The installer creates a timestamped `.claude-backups/` snapshot, preserves an existing project profile, and does not silently replace shared settings or activate MCP/cloud dependency installation.

## 5. Complete the repository contract

Open:

```text
.claude/PROJECT_PROFILE.md
```

Replace every task-relevant placeholder with facts from the live repository and CI:

- purpose and repository type;
- default branch and remote;
- runtime/package manager;
- install, lint, typecheck, test, build, and runtime-verification commands;
- architecture boundaries;
- protected paths;
- governing decisions/workflows;
- current objective and acceptance criteria;
- known blockers and unavailable evidence.

Then inspect:

```text
.claude/FOUNDEROS.md
.claude/MODEL_REGISTRY.md
.claude/settings.json
.claude/profiles/
.claude/hooks/
.claude/control-plane/
```

Do not treat model registration as credential or authority grant.

## 6. Prove the subscription billing lane

The full installer places transparent control-plane source at `.claude/control-plane/` and, when
`--install-python-control-plane` / `-InstallPythonControlPlane` is selected, installs the user-level
`madclaude` wrapper without downloading a Python dependency.

Authenticate Claude Code through the subscription account:

```bash
claude auth login
claude auth status
madclaude auth-check --repo .
madclaude doctor --repo .
```

Repository-local alternative:

```bash
python3 .claude/control-plane/madclaude.py auth-check --repo .
```

> **Clean-lane note.** If your shell session or settings files carry any watched credential
> or routing variable (the fail-closed list in
> [docs/AUTHENTICATION_AND_BILLING.md](docs/AUTHENTICATION_AND_BILLING.md)), the preflight
> reports the subscription lane as unsafe — by design. Run the control plane on a dedicated
> clean config dir instead (it needs its own one-time `claude auth login`; credentials do
> not transfer from `~/.claude` by copying), stripping the full watched set:
>
> ```bash
> env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN \
>     -u CLAUDE_CODE_OAUTH_TOKEN -u CLAUDE_CODE_OAUTH_REFRESH_TOKEN -u CLAUDE_CODE_OAUTH_SCOPES \
>     -u CLAUDE_CODE_USE_BEDROCK -u CLAUDE_CODE_USE_VERTEX -u CLAUDE_CODE_USE_FOUNDRY -u CLAUDE_CODE_USE_ANTHROPIC_AWS \
>     -u ANTHROPIC_BASE_URL -u ANTHROPIC_BEDROCK_BASE_URL -u ANTHROPIC_VERTEX_BASE_URL -u ANTHROPIC_FOUNDRY_BASE_URL -u ANTHROPIC_CUSTOM_HEADERS \
>   CLAUDE_CONFIG_DIR=$HOME/.claude-control-plane madclaude auth-check --repo .
> ```

The governed default is Python orchestrating native `claude -p`:

```text
--backend cli
--billing-mode subscription
```

Every run receives structured output, strict empty MCP, route-specific tools, and an ephemeral
Python-generated `PreToolUse` hook. An active `ANTHROPIC_API_KEY`, bearer token, cloud-provider
route, custom Anthropic base URL, or API-key helper stops subscription mode before Claude executes.
Remove the conflicting route rather than assuming the saved login will outrank it.

The optional Agent SDK is not required for subscription use. Install it only for an explicitly
API-billed integration:

```bash
/path/to/package/scripts/install-python-control-plane.sh --with-sdk
```

```powershell
.\scripts\install-python-control-plane.ps1 -WithSdk
```

API billing still requires `--billing-mode api`, `--allow-api-billing`, and a positive
`--max-budget-usd` in the same invocation. Credential preflight does not prove the final invoice,
remaining plan allowance, or whether account-level extra usage is enabled.

## 7. Start the first governed session

From the target repository root:

```bash
claude --permission-mode plan --model sonnet --effort high
```

Inside Claude Code:

```text
/status
/doctor
/memory
/agents
/skills
/workflows
/hooks
/permissions
/founderos-onboard
/claude-doctor-plus full
```

Do not implement while repository identity, commands, authority, or acceptance criteria remain unknown.

## 8. Select the route by role

Run from the **target repository root** and invoke the launch script by its absolute package path when a repeatable route is useful:

```bash
/path/to/package/scripts/start-claude-route.sh fanout
/path/to/package/scripts/start-claude-route.sh everyday
/path/to/package/scripts/start-claude-route.sh deep
/path/to/package/scripts/start-claude-route.sh planning
/path/to/package/scripts/start-claude-route.sh judgment
/path/to/package/scripts/start-claude-route.sh max-judgment
/path/to/package/scripts/start-claude-route.sh best-available
/path/to/package/scripts/start-claude-route.sh advisor
/path/to/package/scripts/start-claude-route.sh ultracode
/path/to/package/scripts/start-claude-route.sh review
```

Routing doctrine:

| Work | Route |
|---|---|
| Search, file mapping, extraction, mechanical scans | Haiku; no effort override |
| Ordinary features, tests, debugging, refactoring | Sonnet high |
| Demanding implementation, root cause, performance | Opus xhigh |
| Consequential planning | Fable high in plan mode |
| Adversarial judgment and final synthesis | Fable xhigh |
| Rare unusually costly decision | Fable max |
| Account may not expose Fable | `best-available`; record the resolved model |
| Interactive coding with intermittent hard decisions | Sonnet high + Opus advisor |
| Exact-target review | Fable xhigh + review-only settings |

**Cheap fan-out, expensive judgment.** Do not spend Fable/Opus tokens on mechanical file reading. Do not allow Haiku to issue the final architecture or governance verdict.

**Fable billing check:** a subscription login does not prove Fable is included. Max includes a
bounded Fable allowance; Pro and standard seats use usage credits from the start. Python routes stop
when Fable entitlement cannot be proven unless you select `--model opus` / `--model sonnet` or add
`--allow-usage-credits` after checking account Usage settings. The acknowledgement does not enable or
cap credits.


The advisor shares the main conversation and is not independent review.

## 9. Run the governed build loop

For an ordinary feature:

Use the Python route for deterministic plan, approval, build, verification, and exact-SHA review evidence:

```bash
python3 .claude/control-plane/madclaude.py plan --repo . "<exact goal>"
python3 .claude/control-plane/madclaude.py approval-template "<exact goal>" \
  --plan-file /absolute/path/to/structured-output.json \
  --output /absolute/path/to/founder-approval.json
# Founder inspects and completes the generated approval file.
python3 .claude/control-plane/madclaude.py build --repo . \
  --plan-file /absolute/path/to/structured-output.json \
  --approval-file /absolute/path/to/founder-approval.json \
  "<exact goal>"
```

The Python route starts from a clean Git tree, enforces exact approved scopes, and runs approved
verification independently of the builder response.

## 10. Use subagents correctly

Recommended high-risk sequence:

```text
Founder/main session
  → Haiku explorer + dependency mapper
  → Fable architecture planner
  → one accountable Sonnet/Grok/Hermes builder
  → test verifier
  → security/adversarial review
  → edit-less exact-SHA independent reviewer
  → Founder decision
```

Only one lane owns a mutable file set unless separate Git worktrees isolate the work. Multiple model outputs are not independent merely because they have different names.

## 11. Choose cloud, Remote Control, or local background

Use:

- **Claude Code cloud** for persistent Anthropic-managed execution from pushed/committed or explicitly bundled repository state;
- **Remote Control** when execution must remain on the local machine with Hermes, local files, local MCP servers, or approved local connectors;
- **local background sessions** for work that can continue while the local interactive session remains available.

Routing command:

```text
/cloud-session route <task>
```

Cloud launch and retrieval:

```bash
claude --cloud 'Run the approved task.'
claude --teleport
```

Remote Control:

```bash
claude remote-control --name 'FounderOS Local Build'
```

Neither route grants merge, deployment, activation, governance, or Founder authority.

## 12. Preserve checkpoints and context

Before a risky command, workflow, background builder, compaction, or handoff:

```bash
git status --short
git diff --stat
git rev-parse HEAD
```

Use:

```text
/context
/compact
/rewind
/branch
/tasks
```

Checkpoint recovery is not universal. Direct Claude file-tool edits are covered; Bash mutations, generators, most subagent/workflow edits, external edits, and linked paths require Git/worktrees for durable recovery.

Before `/compact`, `/clear`, teleport, model handoff, or session end, preserve:

- goal and acceptance criteria;
- repository, branch, base/head SHA;
- Founder approvals and authority stops;
- files changed;
- exact commands/results;
- open findings and unknowns;
- next action.

Cloud sessions do not support `/clear`; create a new cloud session.

## 13. Verify before claiming completion

A final report must state:

- what changed;
- exact files changed;
- commands run and observed results;
- review target and reviewer independence;
- unresolved risks or unavailable evidence;
- lifecycle state: proposed, approved, implemented, verified, merged, deployed, or activated;
- action still requiring Founder authorization.

A merged PR is not deployed. A deployed change is not necessarily activated. Missing evidence is not healthy state.

## 14. Diagnose problems

```bash
claude --safe-mode
claude --debug 'config,hooks,mcp' --debug-file ./claude-debug.log
```

Then inspect:

```text
/status
/doctor
/context
/memory
/agents
/skills
/workflows
/hooks
/permissions
/plugin
/mcp
```

Return to the extracted package root to rerun package validators. The validators are not copied into every target repository.

## 15. Read next

- [`README.md`](README.md) — package scope and inventory;
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — full installation, merge, cloud, rollback, and release details;
- [`docs/COMMAND_PALETTE.md`](docs/COMMAND_PALETTE.md) — commands and workflows;
- [`docs/MODEL_ROUTING.md`](docs/MODEL_ROUTING.md) — model/effort/advisor/external routing;
- [`docs/DYNAMIC_WORKFLOWS.md`](docs/DYNAMIC_WORKFLOWS.md) — workflow behavior and security boundary;
- [`docs/SESSION_CONTEXT_CHECKPOINTS.md`](docs/SESSION_CONTEXT_CHECKPOINTS.md) — long-session and recovery discipline;
- [`docs/SECURITY_GOVERNANCE.md`](docs/SECURITY_GOVERNANCE.md) — hard authority boundaries;
- [`docs/CLOUD_ENVIRONMENT.md`](docs/CLOUD_ENVIRONMENT.md) — cloud and Remote Control setup.
