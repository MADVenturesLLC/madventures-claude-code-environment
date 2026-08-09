# Changelog

## 4.4.1 — 2026-08-06

### Delivery correction

- Added a Finder/Explorer-visible inspection mirror at `VISIBLE_PROJECT_TEMPLATE/`.
- Added top-level guided launchers: `INSTALL_MAC.command`, `INSTALL_WINDOWS.ps1`, and `VERIFY_PACKAGE.command`.
- Added `README_FIRST.txt`, `OPEN_ME_FIRST.md`, `DELIVERY_FIX.md`, and a complete `PACKAGE_CONTENTS.txt` index.
- Changed normal installation to a fast cryptographic preflight; exhaustive release validation remains available with `--full-validation` / `-FullValidation`.
- Added a macOS-friendly TAR.GZ release alongside the universal ZIP.
- Preserved the complete V4.4 agent, skill, workflow, hook, model-routing, governance, and Python control-plane architecture.

## 4.4.0 — 2026-08-06

### Added: subscription-first Python control plane

- Transparent Python source copied to `.claude/control-plane/` by the full repository installer.
- Native `claude -p` as the default programmatic backend under the authenticated Claude subscription
  login; no `ANTHROPIC_API_KEY` or Agent SDK dependency is required.
- Ephemeral Python-generated `PreToolUse` settings for every CLI run, enforcing route tools,
  read/write scope, secret paths, authority paths, allowed subagents, strict empty MCP, and
  non-delegating mutation lanes independently of the target commit.
- Optional `claude-agent-sdk==0.2.131` extra, installed only with `--with-sdk` / `-WithSdk` and
  restricted to explicitly acknowledged API billing.
- Fail-closed authentication preflight before every model-backed route:
  - proves a subscription OAuth/saved-login lane by default;
  - rejects `ANTHROPIC_API_KEY`, bearer tokens, Bedrock/Vertex/Foundry routing, custom base URLs,
    API-key helpers, and settings-injected credential routes in subscription mode;
  - requires `--billing-mode api --allow-api-billing --max-budget-usd <positive>` before separate
    API billing can run;
  - warns that credential proof does not reveal invoice state, remaining plan allowance, model
    entitlement, or account-level extra-usage settings;
  - adds a second fail-closed Fable/ambiguous-model gate with `--allow-usage-credits` acknowledgement
    or explicit Sonnet/Opus override when inclusion cannot be proven.
- Nine governed Python routes: plan, approved build, verification, exact-SHA Tier-2 review,
  exact-SHA release readiness, repository audit, security audit, UI review, and bounded repair.
- Route-specific read-only subagent fan-out for planning/audits; mutation routes retain one
  accountable builder.
- Plan-bound Founder approval template with SHA-256 binding, exact goal match, allowed scopes,
  acceptance criteria, and direct verification commands.
- Python-executed verification, detached review worktrees, secret/diff guards, structured JSON
  Schemas, redacted evidence bundles, and bounded no-progress/repeated-failure stops.
- Dependency-free default Bash and PowerShell control-plane installers; optional SDK installation is
  explicit and exact-version pinned.
- Thirty-six Python unit/integration tests plus shell installer/auth/dry-run coverage.
- Authentication/billing, architecture, invocation, approval, deployment, and validation guidance.

### Corrected

- Removed the earlier claim that subscription Agent SDK/`claude -p` runs use a separate monthly
  credit after a June 15 cutoff. Anthropic's June 16 update paused that change; current
  subscription-authenticated usage continues against the subscription usage limits.
- Removed the incorrect SDK-default / CLI-fallback design. The CLI is now the governed subscription
  default; the SDK is an optional API-only adapter in this package.
- Added a billing-precedence stop so a present API key cannot silently supersede the subscription
  login in non-interactive `claude -p` runs.

### Changed

- Expanded full project environment to 20 agents, 31 skills, 14 workflows, 8 scoped rules, and 8
  project hook modules.
- Expanded portable plugin to 19 agents, 31 skills, and 14 workflows. The plugin's Python skill is
  guidance only; Python source and installers remain full-package content.
- Full installers copy the repository-local control plane and optionally install a dependency-free
  user-level wrapper with `--install-python-control-plane` / `-InstallPythonControlPlane`.
- `--with-python-sdk` / `-WithPythonSdk` additionally installs the optional API SDK adapter.
- Release validation now covers Python compilation, schemas, policy hooks, constrained subagents,
  subscription/API auth gates, dependency-free installation, exact-SHA behavior, and archive shape.

### Retained from v4.3

- Twenty role-routed project agents and nineteen portable plugin agents.
- Thirty-one on-demand skills, including the Python control-plane skill.
- Fourteen dynamic JavaScript workflows with explicit mutating/evidence boundaries.
- Ten executable model-route launchers.
- FounderOS doctrine, model registry, profiles, cloud/Remote Control guidance, checkpoint/context
  guidance, optional advisor profile, portable plugin, and exact-SHA independent-review architecture.

## 4.3.0 — 2026-08-06

- Completed the 20-agent, 30-skill, 14-workflow Claude Code operating environment.
- Added the generated portable plugin, ten model launch profiles, advisor profile, cloud/Remote
  Control distinction, command palette, expanded validation, and verified release archives.

## 4.2.0 — 2026-08-06

- Added first-class workflows, role-specific subagents, skills, scoped rules, hooks, repository
  profiles, cross-platform installers, context/checkpoint guidance, and static validation.
- Corrected unsupported settings, tool frontmatter, WebFetch syntax, checkpoint claims, workflow
  read-only claims, dated model assumptions, and SQL-hook scope.

## 4.0.0

- Initial FounderOS Claude Code environment package supplied for upgrade.
