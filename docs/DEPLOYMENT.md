# Deployment guide

## Prerequisites

Required:

- Claude Code `2.1.223` or newer; this release was audited against the official `2.1.223` documentation on 2026-08-06;
- Git;
- Node.js 18 or newer for hooks, workflows, status line, and JavaScript validation;
- Python 3.10 or newer for configuration validation and release packaging;
- a reviewed understanding of the target repository’s existing `.claude` configuration.

Recommended:

- begin from a clean Git working tree;
- record repository, branch, head SHA, and remote before installation;
- validate the extracted package before installing;
- inspect shared settings, model registry, hooks, and all mutating workflows;
- use a test clone or branch for the first installation into a high-risk repository.

## Validate the extracted package first

Run these commands from the **extracted package root**, not from the target repository:

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

Package validation is read-only by default. Release maintainers can explicitly refresh the generated report with `python3 scripts/validate-config.py --report docs/VALIDATION_REPORT.md` before regenerating the manifest.

Or run the complete release pipeline, which rebuilds the generated plugin, validates both distributions, runs hook/install/route/cloud tests, generates SHA-256 evidence, and emits a universal ZIP, a macOS/Linux TAR.GZ, and a portable-plugin ZIP:

```bash
bash scripts/build-release.sh
```

Default outputs:

```text
../MADVentures-Claude-Code-Environment-v4.4.1.zip
../MADVentures-Claude-Code-Environment-v4.4.1.tar.gz
../MADVentures-FounderOS-Claude-Code-Plugin-v4.4.1.zip
```

Custom ZIP, plugin, and TAR.GZ output paths can be supplied as the first, second, and third arguments:

```bash
bash scripts/build-release.sh /secure/releases/full.zip /secure/releases/plugin.zip /secure/releases/full.tar.gz
```

The installer invokes the fast cryptographic package preflight automatically. Use `--full-validation` or `-FullValidation` for the exhaustive release suite; use `--skip-validation` or `-SkipValidation` only in a controlled test after separate verification.

## macOS, Linux, and WSL

```bash
chmod +x scripts/*.sh cloud/setup.sh project/.claude/cloud/session-start.sh
./scripts/install.sh /absolute/path/to/repository
```

Options:

```text
--profile NAME         auto | generic | doctrine | runtime | console
--force-settings       Replace instead of deterministically merging settings
--workspace PATH       Install the shared workspace instruction layer
--install-global       Install optional user-level doctrine/status-line assets
--install-managed      Install the non-overridable managed deny baseline
--managed-dir PATH     Override the platform managed-settings directory
--install-python-control-plane
                       Install the dependency-free subscription-first madclaude wrapper
--with-python-sdk      Also install the optional API-billed Agent SDK adapter
--full-validation      Run the exhaustive release validator before installation
--skip-validation      Skip pre-install validation (not recommended)
--dry-run              Print intended operations without writing
--help                 Show usage
```

Examples:

```bash
./scripts/install.sh ~/code/FounderOS --profile doctrine
./scripts/install.sh ~/code/founder-os-telegram --profile runtime
./scripts/install.sh ~/code/founder-os-console --profile console
./scripts/install.sh ~/code/new-saas --profile generic --install-global
./scripts/install.sh ~/code/unknown-repo --profile auto --dry-run
./scripts/install.sh ~/MADVenturesOPs/FounderOS --workspace ~/MADVenturesOPs --install-global
```

The same launcher owns the complete repository lifecycle:

```bash
./scripts/install.sh update /absolute/path/to/repository
./scripts/install.sh status /absolute/path/to/repository --json
./scripts/install.sh doctor /absolute/path/to/repository --json
./scripts/install.sh uninstall /absolute/path/to/repository --dry-run
./scripts/install.sh restore /absolute/path/to/repository --backup /absolute/path/to/backup
```

## Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install.ps1 -ProjectPath 'C:\code\FounderOS' -Profile doctrine
```

Options:

```text
-Profile auto|generic|doctrine|runtime|console
-Action install|update|status|doctor|uninstall|restore
-Workspace C:\path\to\MADVenturesOPs
-ForceSettings
-InstallGlobal
-InstallManaged
-ManagedDir C:\path\to\managed-settings
-InstallPythonControlPlane
-SkipValidation
-DryRun
```

## Transaction and merge behavior

The installer first creates a timestamped backup:

```text
<repo>/.claude-backups/<UTC timestamp>/
```

The Bash and PowerShell entry points are thin launchers for `scripts/environment-lifecycle.py`. That single engine then:

1. validates Python 3.10+, Node.js 18+, Git, Claude Code 2.1.223+, package inputs, and active settings JSON before writes;
2. copies the transparent Python control-plane source into `.claude/control-plane/`;
3. copies `.claude/FOUNDEROS.md` and `.claude/MODEL_REGISTRY.md`;
4. creates `.claude/CLAUDE.md` if absent, or appends `@FOUNDEROS.md` exactly once;
5. preserves an existing `.claude/PROJECT_PROFILE.md`;
6. seeds the selected profile only when no profile exists;
7. removes the 14 retired package workflows and eight retired hook engines by exact managed name;
8. deterministically merges mandatory hook and deny policy into active settings while preserving unrelated settings, or replaces settings only with `--force-settings`;
9. installs inactive MCP and local-settings examples;
10. copies repository, review, audit, and cloud settings profiles into `.claude/profiles/`;
11. copies examples into `.claude/examples/`;
12. appends one version-independent marked block to `.gitignore` without duplicating older versioned markers;
13. runs installed adapter, route-registry, invariant, and 55-test Python control-plane checks before recording success;
14. records version, package identity, managed-file hashes, selected scopes, backup, and settings strategy in `.claude/INSTALLATION_STATE.json` plus the readable installation record.

Any failure restores the exact pre-operation snapshot. Existing files with package-managed names are backed up and replaced; unrelated custom files remain. An update stops if an unknown executable workflow or JavaScript hook would violate the approved single-engine boundary.

## Profile selection

### `auto`

Auto-detects the canonical doctrine, runtime, or console repositories using observed paths and repository name. Falls back to `generic`.

### `generic`

Use for MAD Ventures repositories outside the canonical FounderOS trio. Complete every task-relevant placeholder before implementation.

### `doctrine`

Use for `MADVenturesLLC/FounderOS`. It includes known authority paths for the constitution, role registry, decisions, path audit, workflows, and attribution checks.

### `runtime`

Use for `founder-os-telegram` or the governed runtime. It emphasizes executed-only durable writes, kill switches, runtime verification, truth-state separation, and no inference from console projections.

### `console`

Use for `founder-os-console`. It emphasizes source provenance, truthful unavailable states, accessibility, reduced motion, and separation among runtime, approvals, activity, and ledger evidence.

## Optional global layer

`--install-global` or `-InstallGlobal` installs:

```text
~/.claude/madventures-statusline.mjs
~/.claude/MADVENTURES.md
~/.claude/examples/madventures-v4.4/settings.json.fragment
~/.claude/examples/madventures-v4.4/claude.json.fragment
```

It does **not** blindly merge settings fragments. User settings may already contain authentication, enterprise policy, plugins, MCP, permissions, themes, and personal preferences.

To enable the status line after review, merge the supplied status-line object into `~/.claude/settings.json`. Keep `~/.claude.json`-only fields in the separate fragment supplied for that file.

### Environment identity marker

Installed environments identify themselves on the Claude status line as `[MAD_OS Env]` — so you can tell at a glance that a session is running inside the governed MAD Ventures Claude Code environment, not a vanilla Claude session. The marker triggers when:

- `MADVENTURES_ENV=1` is present in the session `env` (set by the canonical project settings), **or**
- the project's `.claude/` carries an install-state record (`INSTALLATION_STATE.json` / `MADVENTURES_INSTALLATION_STATE.json`).

The project layer ships the statusline script at `.claude/hooks/madventures-statusline.mjs` and the canonical settings reference it via a relative path (`node .claude/hooks/madventures-statusline.mjs` — `statusLine.command` does not expand `${CLAUDE_PROJECT_DIR}`, unlike hook commands); the global layer ships `~/.claude/madventures-statusline.mjs` for `--install-global`. Both are byte-identical copies of `global/madventures-statusline.mjs`.

Shell-prompt marker: with `--install-global` the `MADVENTURES_ENV=1` env flag is also available to the shell, so a prompt can render a `MAD_OS` tag (see `global/settings.json.fragment`).


Important for cloud use: user-home files remain local-machine state. Critical FounderOS behavior is duplicated at the project level so it travels with the repository.

## Workspace and hard global layers

`--workspace /Users/michaeldaley/MADVenturesOPs` installs the shared ancestor instruction file and records its package identity. This is behavioral context for descendant repositories; it is not represented as hard authority.

`--install-managed` installs `managed/20-madventures-baseline.json` into the platform managed-settings drop-in directory. That is the non-overridable global deny baseline. It is explicit because the default macOS/Linux location may require administrator-controlled deployment. Use `--managed-dir` for an organization-managed or test destination.

The resulting hierarchy is:

```text
managed global baseline        hard native enforcement
user global layer              personal/shared conveniences
MADVenturesOPs workspace       ancestor behavioral context
repository .claude             local settings, hooks, profiles, Python control plane
SHA-bound task artifacts       plan, approval, scope, verification, review, acceptance
```

## Repository-local Python control plane

The full environment always installs transparent source at:

```text
.claude/control-plane/
```

Native `claude -p` is the governed default. It uses the authenticated Claude subscription lane and
does not require an API key or Agent SDK. Prove the lane before the first route:

```bash
claude auth login
claude auth status
python3 .claude/control-plane/madclaude.py auth-check --repo .
python3 .claude/control-plane/madclaude.py doctor --repo .
```

Subscription mode stops when an API key, bearer token, provider route, custom base URL, gateway, or
API-key helper could override or obscure the saved login. Separate API billing requires
`--billing-mode api`, `--allow-api-billing`, and a positive `--max-budget-usd` in the same invocation.
Neither installer sets credentials or changes account billing settings.

Install the user-level wrapper from the package root:

```bash
./scripts/install-python-control-plane.sh
```

```powershell
.\scripts\install-python-control-plane.ps1
```

The default wrapper installation creates `~/.madclaude/venv/`, copies source to
`~/.madclaude/app/`, and creates `madclaude`. It downloads no Python dependency. Each default run
uses native `claude -p` plus an ephemeral Python-generated `PreToolUse` policy.

Install the optional exact-version Agent SDK only for an explicitly API-billed integration:

```bash
./scripts/install-python-control-plane.sh --with-sdk
```

```powershell
.\scripts\install-python-control-plane.ps1 -WithSdk
```

The full installer options are:

```text
--install-python-control-plane / -InstallPythonControlPlane
--with-python-sdk / -WithPythonSdk
```

The second option implies the first and adds the optional API SDK dependency.

## MCP activation

The package installs `.mcp.example.json`, never an active `.mcp.json`.

The GitHub example:

- uses the current remote server base URL;
- exposes only `repos,pull_requests,actions` toolsets;
- enables header-based read-only mode;
- references an environment variable rather than embedding a token.

Before activation:

1. review endpoints, toolsets, and required actions;
2. use least-privilege credentials supplied through an approved secret path;
3. copy only approved entries into an active configuration;
4. verify with `/mcp` and `/status`;
5. keep `.mcp.json` gitignored;
6. never infer that read-only MCP replaces GitHub repository permissions or branch protection.

## Optional portable plugin

The package also includes `plugin/madventures-founderos/` for portable, namespaced tooling. The full project environment is the recommended FounderOS deployment because it includes project rules, settings, project profiles, agent-specific permission modes, and scoped hooks.

Temporary load:

```bash
claude --plugin-dir ./plugin/madventures-founderos
```

Persistent personal installation:

```bash
./scripts/install-plugin.sh --scope user
```

```powershell
.\scripts\install-plugin.ps1 -Scope user
```

The plugin installer supports project scope, but refuses coexistence with the full environment unless explicitly overridden. See `docs/PLUGIN_DEPLOYMENT.md`.

## Claude Code cloud environment

Repository installation copies the cloud session script but does **not** activate dependency installation.

To configure the Anthropic-managed VM:

1. review `cloud/README.md` and `docs/CLOUD_ENVIRONMENT.md`;
2. create `MAD Ventures — Governed Build` in the environment selector at `claude.ai/code`;
3. begin with Trusted network access;
4. paste reviewed non-secret values from `cloud/environment.env.example`;
5. paste `cloud/setup.sh` as the environment setup script;
6. select the environment locally with `/remote-env`;
7. run `mad-cloud-doctor` in a cloud session to verify the VM tools.

To activate repository dependency installation, merge `project/profiles/cloud-session-start.settings.fragment.json` into `.claude/settings.json` and set `MADVENTURES_CLOUD_INSTALL_DEPS=true`. Do this only after verifying the repository's lockfile and install policy.

Do not store secrets in cloud environment variables.

## Remote Control for local-only tools

Remote Control is not Claude Code cloud. It keeps the Claude Code process, repository, filesystem, MCP servers, and approved local connectors on the local machine while an authorized browser or mobile client steers that same session.

Use it when Hermes/local-code access, local-only files, or local MCP services are required:

```bash
claude remote-control --name "FounderOS Local Build"
# or start an interactive session that immediately exposes Remote Control
claude --remote-control "FounderOS Local Build"
```

Inside an active local session:

```text
/remote-control FounderOS Local Build
```

The local machine must remain available. Remote Control does not copy local credentials into Anthropic-managed cloud, create reviewer independence, or grant merge/deploy/activation authority. Review `docs/CLOUD_ENVIRONMENT.md` before enabling it.

## Optional advisor profile

The base settings deliberately do not enable an advisor. Use one of these opt-in paths only on a supported Anthropic API/account route:

```bash
claude --model sonnet --effort high --advisor opus
/path/to/package/scripts/start-claude-route.sh advisor
```

Inside a supported session:

```text
/advisor opus
/advisor off
```

For a persistent local preference, review and merge `project/profiles/advisor-opus.settings.fragment.json` into the intended settings scope. The advisor receives the same conversation and therefore cannot provide FounderOS Tier-2 independence. Fable is not currently an advisor option.

## Optional role-routed session launchers

From a target repository, launch a bounded model/effort profile without changing committed settings:

```bash
/path/to/package/scripts/start-claude-route.sh everyday
/path/to/package/scripts/start-claude-route.sh planning --name architecture-session
/path/to/package/scripts/start-claude-route.sh advisor
/path/to/package/scripts/start-claude-route.sh review
```

```powershell
& 'C:\path\to\package\scripts\start-claude-route.ps1' everyday
& 'C:\path\to\package\scripts\start-claude-route.ps1' planning
& 'C:\path\to\package\scripts\start-claude-route.ps1' advisor
& 'C:\path\to\package\scripts\start-claude-route.ps1' review
```

The ten launch profiles are `fanout`, `everyday`, `deep`, `planning`, `judgment`, `max-judgment`, `best-available`, `advisor`, `ultracode`, and `review`. Fable-pinned routes fail honestly when Fable is unavailable; use `best-available` only when an explicit fallback is acceptable. The `review` launcher composes plan mode with the hardened review-only settings profile. It is not a dynamic workflow and does not replace the exact-SHA `independent-reviewer` contract.

## Post-install verification

From the **target repository**:

```bash
claude --version
claude doctor
claude --safe-mode
claude --permission-mode plan
```

`--safe-mode` is a diagnostic baseline; it disables customizations for that session. Exit and start a normal session to test the installed environment.

Inside a normal session:

```text
/status
/doctor
/memory
/agents
/skills
/workflows
/founderos-onboard
```

Verify:

- `.claude/PROJECT_PROFILE.md` contains the real repository commands and paths;
- `.claude/MODEL_REGISTRY.md` reflects current Founder approvals;
- `.claude/profiles/advisor-opus.settings.fragment.json` exists but `advisorModel` is absent from base `.claude/settings.json`;
- 20 agents appear;
- 31 skills appear;
- 8 scoped rule files exist;
- `.claude/control-plane/madclaude.py --version` reports `4.4.1`;
- `madclaude auth-check` proves the intended subscription lane without exposing credentials;
- the control-plane test suite passes without a live Claude call;
- zero executable JavaScript workflows are installed;
- all ten route-launcher profiles produce the documented CLI arguments in the package smoke test;
- the cloud bootstrap file is present but `SessionStart` is not active unless explicitly merged;
- hooks load without startup errors;
- `node scripts/validate-workflows.mjs` confirms all 14 capabilities map to Python and no competing JavaScript engine remains;
- the independent reviewer cannot edit or delegate;
- the Neon reader denies non-read-only SQL;
- destructive commands are denied;
- MCP remains inactive unless intentionally configured;
- the repository’s actual test/build/audit commands pass.

The package validator does not live inside the installed repository. To re-run package validation, return to the extracted package directory and run `python3 scripts/validate-config.py` there. The repository-local control-plane tests can be run with `python3 .claude/control-plane/run-tests.py`.

## Rollback

Every mutating lifecycle command creates a timestamped snapshot. A mid-operation failure restores it automatically. For an explicit restore:

```bash
./scripts/install.sh restore /absolute/path/to/repository \
  --backup /absolute/path/to/repository/.claude-backups/<timestamp-operation>
```

The restore command accepts only backups inside that repository's `.claude-backups` directory and creates a pre-restore safety snapshot first. Use Git/provider recovery separately for implementation changes, cloud environments, deployments, databases, or external systems.

## Update and uninstall

```bash
./scripts/install.sh update /absolute/path/to/repository --dry-run
./scripts/install.sh update /absolute/path/to/repository
./scripts/install.sh doctor /absolute/path/to/repository --json
./scripts/install.sh uninstall /absolute/path/to/repository --dry-run
./scripts/install.sh uninstall /absolute/path/to/repository
```

Update removes only known retired or previously recorded managed files, preserves unrelated files, reconciles active settings, and reruns installed-copy tests. Uninstall uses the state inventory and baseline backup, refuses changed managed files unless `--force` is explicit, preserves unrelated files, and is idempotent when already absent. Shared workspace/global layers are not silently removed when one repository is uninstalled because other repositories may depend on them.

## Release archive verification

The release builder now fails closed if a packaged file changes after manifest generation. It opens the release archives, rejects unsafe or duplicate paths, verifies every SHA-256 entry and manifest record, confirms component counts, and checks that the standalone plugin is byte-for-byte identical to the plugin bundled in the full environment. It then extracts the newly built full ZIP and TAR.GZ and runs fresh install, legacy migration, rollback, hierarchy, status/doctor, and uninstall gates from those extracted artifacts.

```bash
python3 scripts/verify-release.py \
  /path/to/MADVentures-Claude-Code-Environment-v4.4.1.zip \
  /path/to/MADVentures-FounderOS-Claude-Code-Plugin-v4.4.1.zip
```

The build also emits a `.sha256` sidecar beside each ZIP.
