#!/usr/bin/env python3
"""Build the portable MAD Ventures FounderOS Claude Code plugin from project sources."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "project" / ".claude"
PLUGIN = ROOT / "plugin" / "madventures-founderos"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
POLICY_MODULES = (
    "__init__.py", "version.py", "errors.py", "safe_read.py", "guard.py", "git.py", "evidence.py",
    "artifacts.py", "hook_policy.py", "hook_cli.py", "secrets_patterns.py",
)


def policy_module_closure(source_dir: Path) -> frozenset[str]:
    """Transitive closure of intra-package imports starting from the hook
    entry point (hook_cli). Every madclaude submodule the hook can reach must
    ship in the plugin; a missing module is a runtime ImportError in the
    governed hook path, so this is computed, not assumed."""
    import ast

    closure: set[str] = set()
    pending = ["hook_cli.py"]
    while pending:
        name = pending.pop()
        if name in closure:
            continue
        closure.add(name)
        tree = ast.parse((source_dir / name).read_text(encoding="utf-8"), filename=name)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level and node.level >= 1:
                if node.module:
                    candidate = node.module.split(".")[0] + ".py"
                    if (source_dir / candidate).is_file():
                        pending.append(candidate)
                for alias in node.names:
                    candidate = alias.name + ".py"
                    if (source_dir / candidate).is_file():
                        pending.append(candidate)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("madclaude."):
                        candidate = alias.name.split(".")[1] + ".py"
                        if (source_dir / candidate).is_file():
                            pending.append(candidate)
    return frozenset(closure)


def remove_frontmatter_blocks(raw: str, blocked: set[str]) -> list[str]:
    lines = raw.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        match = re.match(r"^([A-Za-z0-9_-]+):", line)
        if match:
            skipping = match.group(1) in blocked
            if skipping:
                continue
        if skipping and line.startswith((" ", "\t")):
            continue
        if skipping and not line.strip():
            continue
        if skipping:
            skipping = False
        output.append(line)
    return output


def transform_agent(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$", text)
    if not match:
        raise ValueError(f"Missing frontmatter: {source}")
    raw, body = match.groups()
    plan_mode = bool(re.search(r"^permissionMode:\s*plan\s*$", raw, re.MULTILINE))
    lines = remove_frontmatter_blocks(raw, {"permissionMode", "hooks", "mcpServers"})

    transformed: list[str] = []
    inserted_disallowed = False
    for line in lines:
        if plan_mode and line.startswith("tools:"):
            tools = [part.strip() for part in line.split(":", 1)[1].split(",") if part.strip()]
            tools = [tool for tool in tools if tool not in {"Bash", "PowerShell", "Edit", "Write", "NotebookEdit"}]
            line = "tools: " + ", ".join(tools)
            transformed.append(line)
            transformed.append("disallowedTools: Edit, Write, NotebookEdit, Bash, PowerShell")
            inserted_disallowed = True
            continue
        transformed.append(line)

    if plan_mode and not inserted_disallowed:
        transformed.append("disallowedTools: Edit, Write, NotebookEdit, Bash, PowerShell")

    portability = (
        "\n\n## Portable plugin boundary\n\n"
        "This plugin-shipped agent does not receive project-agent `permissionMode`, scoped hooks, or inline MCP configuration. "
        "Its tool list is intentionally reduced where the project version depends on those controls. For the strongest FounderOS "
        "governance, install the project environment instead of relying only on this portable plugin."
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("---\n" + "\n".join(transformed) + "\n---\n" + body.rstrip() + portability + "\n", encoding="utf-8")


def main() -> None:
    if PLUGIN.exists():
        shutil.rmtree(PLUGIN)
    (PLUGIN / ".claude-plugin").mkdir(parents=True)

    manifest = {
        "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
        "name": "madventures-founderos",
        "displayName": "MAD Ventures FounderOS",
        "version": VERSION,
        "description": "Portable FounderOS Claude Code skills, subagents, and guarded hooks for MAD Ventures engineering.",
        "author": {"name": "MAD Ventures Holdings LLC"},
        "keywords": ["claude-code", "founderos", "governance", "workflows", "subagents"],
    }
    (PLUGIN / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    shutil.copytree(SOURCE / "skills", PLUGIN / "skills")
    # The governed environment retired executable JavaScript workflows (Audit 6).
    # The plugin therefore carries an empty workflows directory by design; create
    # it rather than failing when the source tree no longer has one.
    (PLUGIN / "workflows").mkdir(parents=True, exist_ok=True)

    agent_dest = PLUGIN / "agents"
    agent_dest.mkdir()
    for source in sorted((SOURCE / "agents").glob("*.md")):
        if source.stem == "neon-reader":
            continue
        transform_agent(source, agent_dest / source.name)

    hooks = PLUGIN / "hooks"
    hooks.mkdir()
    shutil.copy2(SOURCE / "hooks" / "hook-adapter.mjs", hooks / "hook-adapter.mjs")
    policy_source = ROOT / "python-control-plane" / "src" / "madclaude"
    policy_destination = PLUGIN / "python-control-plane" / "src" / "madclaude"
    closure = policy_module_closure(policy_source)
    missing = set(closure) - set(POLICY_MODULES)
    if missing:
        raise SystemExit(
            f"POLICY_MODULES is missing modules from the hook import closure: {sorted(missing)}"
        )
    policy_destination.mkdir(parents=True)
    for name in POLICY_MODULES:
        shutil.copy2(policy_source / name, policy_destination / name)
    hook_config = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [{
                        "type": "command",
                        "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/hook-adapter.mjs\" baseline",
                        "timeout": 10,
                    }],
                }
            ],
            "ConfigChange": [
                {
                    "hooks": [{
                        "type": "command",
                        "command": "node \"${CLAUDE_PLUGIN_ROOT}/hooks/hook-adapter.mjs\" baseline",
                        "timeout": 10,
                    }],
                }
            ],
        },
    }
    (hooks / "hooks.json").write_text(json.dumps(hook_config, indent=2) + "\n", encoding="utf-8")

    readme = f"""# MAD Ventures FounderOS portable plugin v{VERSION}

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
"""
    (PLUGIN / "README.md").write_text(readme, encoding="utf-8")
    (PLUGIN / "NOTICE.md").write_text(
        "# Notice\n\nOwner: MAD Ventures Holdings LLC / FounderOS.\n\n"
        "This package contains configuration and operating instructions, not Claude model weights or Anthropic software. "
        "Claude, Claude Code, and Anthropic are trademarks of Anthropic PBC.\n",
        encoding="utf-8",
    )

    print(
        f"Built plugin {PLUGIN.relative_to(ROOT)}: "
        f"{len(list((PLUGIN / 'agents').glob('*.md')))} agents, "
        f"{len(list((PLUGIN / 'skills').glob('*/SKILL.md')))} skills, "
        f"{len(list((PLUGIN / 'workflows').glob('*.js')))} workflows"
    )


if __name__ == "__main__":
    main()
