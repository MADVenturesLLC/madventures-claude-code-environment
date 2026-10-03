# MAD Ventures FounderOS portable plugin v4.4.2

This plugin is the portable, namespaced distribution of the MAD Ventures Claude Code Operating Environment.

## Load without installing

```bash
claude --plugin-dir ./plugin/madventures-founderos
```

Commands appear under the `madventures-founderos:` namespace, for example:

```text
/madventures-founderos:founder-command
```

## Important boundary

The full project installation is authoritative for FounderOS repositories because project agents can use scoped permission modes and agent-specific hooks. Claude Code ignores `permissionMode`, `hooks`, and `mcpServers` in plugin-shipped agent frontmatter. This plugin therefore:

- omits the `neon-reader` agent, which requires a separately configured read-only database identity and scoped SQL guard;
- removes shell and write tools from agents that depend on project plan-mode enforcement;
- ships the same Python-backed baseline hook policy as the project package;
- exposes no executable JavaScript workflows; governed orchestration remains in the Python control plane.

Do not enable this plugin and the full project package in the same repository unless you intentionally want both namespaced and unnamespaced copies. The project installation remains the stronger governed deployment.

## Python control-plane boundary

The plugin bundles the Python policy modules needed by its thin hook adapter. It does not expose governed workflow execution or completion authority; use the full project installation for `.claude/control-plane/`, canonical evidence artifacts, and completion gates. The default Python lane uses the local Claude subscription and fails closed on API-key/provider overrides; separate API billing is always explicit. The 14 former workflow capabilities map to governed Python routes documented in `python-control-plane/WORKFLOW_MIGRATION.json` in the full package.
