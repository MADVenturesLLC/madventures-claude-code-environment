# Upgrade from FounderOS Claude Code Environment v4.0–v4.3

V4.4 is a governed replacement package, not a blind overlay. Install it through the supplied installer so existing repository-specific settings and project facts are backed up and preserved.

## What changed

### Component expansion

| Component | V4.4 |
|---|---:|
| Project subagents | 20 |
| Portable plugin subagents | 19 |
| Skills | 31 |
| Python control-plane routes | 11 |
| Executable JavaScript workflows | 0 |
| Scoped rules | 8 |
| Python-backed hook adapters | 1 |
| Settings/profile fragments | 4 settings-oriented profiles plus 3 repository profiles |

The plugin excludes `neon-reader` because plugin agents cannot enforce the project agent’s scoped SQL hook and permission mode.

### Python control plane

V4.4 adds a repository-local, subscription-first Python control plane while retaining every v4.3
interactive surface. It defaults to native `claude -p` under the saved subscription login, performs
an auth/billing preflight, injects an ephemeral `PreToolUse` policy, requires plan-bound Founder
approval for builds, executes verification independently, enforces scopes, and isolates exact-SHA
review in detached worktrees. The pinned Agent SDK is an optional API-only adapter.

Existing repositories gain `.claude/control-plane/` during installation. Local evidence under
`.claude/evidence/python-control-plane/` remains ignored. Review
`docs/AUTHENTICATION_AND_BILLING.md` before any automation.

### Workflow layer

V4.4 adds or completes:

- `/founder-build` with structured Founder approval and allowed-scope gates;
- security, performance, incident-root-cause, documentation-drift, and test-gap workflows;
- workflow compilation and metadata validation;
- null-result handling, bounded loops, no-progress stops, and cost guidance;
- plugin distribution of namespaced workflows;
- explicit warning that workflow workers run with edit acceptance.

### Model and role governance

V4.4 adds:

- `.claude/MODEL_REGISTRY.md`;
- Founder-registered Grok 4.5 and `hermes-local-code` (currently `deepseek-v4-flash`);
- Codex, Gemini, and Cursor lanes with attribution requirements;
- Claude family routing for Fable, Opus, Sonnet, and Haiku;
- an inactive Sonnet-main / Opus-advisor settings fragment;
- a hard rule that advisor guidance is not independent review.

### Remote execution

V4.4 distinguishes:

- Claude Code cloud: Anthropic-managed execution from cloned/bundled repository state;
- Remote Control: web/mobile steering of the local Claude Code process and local tools;
- local background sessions and agent view.

It includes a reviewed cloud setup script, non-secret environment template, allowed-domain template, cloud task examples, an opt-in cloud-only dependency bootstrap, and behavioral tests for that bootstrap.

### Installation and release engineering

V4.4 includes:

- Bash and PowerShell full-environment installers;
- Bash and PowerShell plugin installers;
- idempotent imports and `.gitignore` markers;
- timestamped backups;
- settings coexistence protection;
- generated plugin synchronization;
- JSON/frontmatter/hook/workflow validation;
- hook runtime tests;
- install and cloud bootstrap smoke tests;
- SHA-256 manifest generation;
- full and plugin ZIP release builders.

### Documentation corrections

V4.4 removes or corrects:

- unsupported nested `model` and `limits` settings;
- general `claude --cwd` startup advice;
- `CLAUDE_CODE_DEBUG=1` and fixed-log-path assumptions;
- universal checkpoint/undo claims;
- claims that a workflow prompt can create a hard read-only worker;
- confusion between cloud execution and Remote Control;
- fixed historic model-generation assumptions in shared files.

## Pre-upgrade checklist

From the target repository:

```bash
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
```

Then:

1. preserve any intended uncommitted work;
2. archive the existing `.claude` configuration;
3. identify custom agents, skills, commands, rules, hooks, workflows, MCP servers, and local settings;
4. record current project profile facts and model approvals;
5. inspect V4.4 `CHANGELOG.md`, `README.md`, `FOUNDEROS.md`, `MODEL_REGISTRY.md`, settings, hooks, and mutating workflows;
6. validate the extracted V4.4 package before installation.

## Upgrade commands

### macOS, Linux, WSL

```bash
cd /path/to/MADVentures-Claude-Code-Environment-v4.4.1
python3 scripts/validate-config.py
./scripts/install.sh /absolute/path/to/repository --profile auto
```

### Windows PowerShell

```powershell
Set-Location C:\path\to\MADVentures-Claude-Code-Environment-v4.4.1
python .\scripts\validate-config.py
.\scripts\install.ps1 -ProjectPath 'C:\path\to\repository' -Profile auto
```

The lifecycle engine creates `.claude-backups/<timestamp-operation>/`, preserves an existing `.claude/PROJECT_PROFILE.md`, removes the retired package workflow/hook engines by exact name, and deterministically merges mandatory Python-adapter enforcement into active shared settings. `--force-settings` / `-ForceSettings` remains an explicit full replacement option.

## Required manual reconciliation

### 1. Project profile

Keep verified repository-specific commands, architecture, protected paths, current objective, and acceptance criteria. Merge only accurate V4.4 template additions.

### 2. Settings

Compare:

```text
.claude/settings.json
.claude/settings.founderos-v4.4.example.json
```

The installer performs the baseline reconciliation and records the result. Review the active file and candidate to confirm enterprise policy, organization constraints, approved plugins/MCP, and repository-specific permissions remain correct. Do not blindly widen allowlists.

### 3. Model registry

Confirm every permitted Claude and external model lane. Registration must reflect current Founder approval and actual connector identity. Update `hermes-local-code` if its backend changes.

### 4. Custom tools

Move durable procedures into skills; keep always-on doctrine concise. Resolve name collisions before installing the portable plugin beside a full project environment.

### 5. Cloud and Remote Control

Do not enable the cloud `SessionStart` fragment until dependency installation has been reviewed in that repository. Do not enable Remote Control by default merely because the package documents it.

## Post-upgrade verification

From the package root:

```bash
python3 scripts/build-plugin.py
python3 scripts/validate-config.py
node scripts/validate-workflows.mjs
node scripts/test-hooks.mjs
bash scripts/smoke-test-install.sh
bash scripts/test-cloud-session.sh
```

From the target repository:

```bash
claude --version
claude doctor
claude --safe-mode
```

Then start normally and inspect:

```text
/status
/memory
/agents
/skills
/workflows
/hooks
/permissions
/founderos-onboard
/claude-doctor-plus full
```

Verify the real repository lint, type, test, build, runtime, path-audit, and security commands.

## Rollback

```bash
./scripts/install.sh restore /absolute/path/to/repository \
  --backup /absolute/path/to/repository/.claude-backups/<timestamp-update>
```

Failed updates restore automatically. Explicit restore creates its own safety snapshot first. Cloud state, portable plugins, deployments, databases, and external systems remain separate recovery scopes.
