# Portable plugin deployment

## Why a plugin exists

The project package under `project/.claude/` is designed for one governed repository. The optional plugin under `plugin/madventures-founderos/` is a self-contained, versioned distribution of skills and guarded agents for reuse across MAD Ventures projects. Governed orchestration remains in the Python control plane.

Use the **full project installation** for FounderOS repositories. Use the **plugin** when portability and namespacing matter more than repository-specific controls.

## Temporary test

From the extracted package root:

```bash
claude --plugin-dir ./plugin/madventures-founderos
```

Then inspect `/plugin`, `/agents`, and `/skills`, and run:

```text
/madventures-founderos:founder-command
```

This loads the plugin for that launch without copying it to a skills directory.

## Persistent personal installation

### macOS, Linux, WSL

```bash
./scripts/install-plugin.sh --scope user
```

### Windows PowerShell

```powershell
.\scripts\install-plugin.ps1 -Scope user
```

The plugin is copied to:

```text
~/.claude/skills/madventures-founderos/
```

A directory under a Claude skills directory that contains `.claude-plugin/plugin.json` is loaded as a skills-directory plugin on the next session. Restart Claude Code or use `/reload-plugins`, then verify:

```bash
claude plugin list
```

## Project-scoped plugin

Use this only in a project that is **not** already using the full environment:

```bash
./scripts/install-plugin.sh --scope project --project /absolute/path/to/repository
```

```powershell
.\scripts\install-plugin.ps1 -Scope project -ProjectPath 'C:\absolute\path\to\repository'
```

The installer refuses coexistence with `.claude/FOUNDEROS.md` unless explicitly overridden. Keeping both creates namespaced and unnamespaced copies and can make routing/debugging harder.

## Security adaptation

Claude Code intentionally ignores `permissionMode`, `hooks`, and `mcpServers` in plugin-shipped agent frontmatter. The plugin builder therefore:

1. excludes `neon-reader`, because safe use requires a separately configured read-only database identity plus an agent-scoped SQL guard;
2. removes shell and write tools from project agents that depend on plan-mode enforcement;
3. removes unsupported agent frontmatter;
4. bundles one thin adapter plus the shared Python baseline policy;
5. preserves the exact-SHA independent reviewer as a shell-less, edit-less plugin agent;
6. leaves repository-specific settings, rules, project profile, MCP examples, and lifecycle authority in the full project package.

The plugin contains 19 agents, 31 skills, zero executable JavaScript workflows, and the Python modules needed by its baseline hook. It does not expose governed workflow execution or completion authority. The full project package contains 20 agents, including the scoped `neon-reader`, plus the complete Python control plane and evidence gate.

## Rebuild after changing source assets

The plugin is generated from the project agents, skills, and hooks:

```bash
python3 scripts/build-plugin.py
python3 scripts/validate-config.py
```

Do not hand-edit generated plugin copies without also updating the source or builder; the next rebuild will replace them.

## Update or remove

Run the installer with `--force` or `-Force` after reviewing the current copy. It backs up the existing plugin before replacement.

To disable a skills-directory plugin without deleting it:

```bash
claude plugin disable madventures-founderos@skills-dir
```

To remove it, delete the installed plugin directory after preserving any local changes. There is no marketplace uninstall step for a skills-directory plugin.

## What the plugin does not do

It does not install credentials, MCP authentication, database access, branch protection, cloud environments, or organization policy. It does not make workflow “read-only” prompts technically immutable. It does not replace Founder authorization or the repository’s exact-SHA review process.
