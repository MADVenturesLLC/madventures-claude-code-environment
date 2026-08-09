from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any


def _project_claude_assets() -> Path:
    test_file = Path(__file__).resolve()
    package_candidate = test_file.parents[2] / "project" / ".claude"
    if (package_candidate / "hooks").is_dir() and (package_candidate / "agents").is_dir():
        return package_candidate

    installed_candidate = test_file.parents[1].parent
    if (installed_candidate / "hooks").is_dir() and (installed_candidate / "agents").is_dir():
        return installed_candidate

    raise FileNotFoundError(
        "Could not locate project .claude hook/agent assets from canonical or installed layout."
    )


def install_control_plane_assets(repo: Path) -> None:
    project_claude = _project_claude_assets()
    hooks_source = project_claude / "hooks"
    hooks_destination = repo / ".claude" / "hooks"
    hooks_destination.mkdir(parents=True, exist_ok=True)
    for name in ("hook-adapter.mjs",):
        shutil.copy2(hooks_source / name, hooks_destination / name)

    agents_source = project_claude / "agents"
    agents_destination = repo / ".claude" / "agents"
    agents_destination.mkdir(parents=True, exist_ok=True)
    for path in agents_source.glob("*.md"):
        shutil.copy2(path, agents_destination / path.name)

    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'node "${CLAUDE_PROJECT_DIR}/.claude/hooks/hook-adapter.mjs" control-plane',
                            "timeout": 15,
                        }
                    ],
                }
            ]
        }
    }
    (repo / ".claude" / "settings.json").write_text(
        json.dumps(settings, indent=2) + "\n", encoding="utf-8"
    )


def make_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "tests@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Control Plane Tests"], check=True)
    (path / "README.md").write_text("# Test repository\n", encoding="utf-8")
    (path / ".gitignore").write_text(
        ".claude/evidence/python-control-plane/\n", encoding="utf-8"
    )
    install_control_plane_assets(path)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "initial"], check=True)
    return path


def fake_claude(
    path: Path,
    structured_output: dict[str, Any],
    *,
    auth_status: dict[str, Any] | None = None,
    total_cost_usd: float = 0.0,
    capture_path: Path | None = None,
    exit_code: int = 0,
    stdout: str | None = None,
    sleep_seconds: float = 0.0,
) -> Path:
    default_subscription = {
        "loggedIn": True,
        "authMethod": "claude.ai",
        "subscriptionType": "max",
        "apiProvider": "firstParty",
        "email": "mike.daley@example.com",
        "orgName": "MAD Ventures Holdings",
    }
    explicit_status = auth_status
    capture = str(capture_path) if capture_path else None
    script = f'''#!/usr/bin/env python3
import json, os, pathlib, sys, time
args = sys.argv[1:]
if args[:2] == ["auth", "status"]:
    explicit = {explicit_status!r}
    if explicit is not None:
        status = explicit
    elif os.environ.get("ANTHROPIC_API_KEY"):
        status = {{
            "loggedIn": True,
            "authMethod": "api_key",
            "apiKeySource": "ANTHROPIC_API_KEY",
            "apiProvider": "firstParty",
            "subscriptionType": "api",
        }}
    else:
        status = {default_subscription!r}
    print(json.dumps(status))
    raise SystemExit(0)
if "--bare" in args:
    print("bare mode forbidden", file=sys.stderr)
    raise SystemExit(9)
capture = {capture!r}
if capture:
    settings = None
    if "--settings" in args:
        index = args.index("--settings") + 1
        settings_path = pathlib.Path(args[index])
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    selected_env = {{name: os.environ.get(name) for name in (
        "MADCLAUDE_CONTROL_PLANE_ACTIVE",
        "MADCLAUDE_ROUTE",
        "MADCLAUDE_REPO_ROOT",
        "MADCLAUDE_MUTATES",
        "MADCLAUDE_ALLOWED_TOOLS_JSON",
        "MADCLAUDE_ALLOWED_SCOPES_JSON",
        "MADCLAUDE_ALLOWED_SUBAGENTS_JSON",
        "MADCLAUDE_BILLING_MODE",
        "PYTHONPATH",
    )}}
    pathlib.Path(capture).write_text(json.dumps({{"args": args, "settings": settings, "env": selected_env}}), encoding="utf-8")
if {sleep_seconds!r}:
    time.sleep({sleep_seconds!r})
raw_stdout = {stdout!r}
if raw_stdout is not None:
    sys.stdout.write(raw_stdout)
    raise SystemExit({exit_code!r})
print(json.dumps({{
  "type": "result",
  "subtype": "success",
  "session_id": "00000000-0000-4000-8000-000000000001",
  "num_turns": 3,
  "total_cost_usd": {total_cost_usd!r},
  "structured_output": {structured_output!r}
}}))
raise SystemExit({exit_code!r})
'''
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_CUSTOM_HEADERS",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_FOUNDRY",
        "CLAUDE_CODE_USE_ANTHROPIC_AWS",
        "ANTHROPIC_BEDROCK_BASE_URL",
        "ANTHROPIC_VERTEX_BASE_URL",
        "ANTHROPIC_FOUNDRY_BASE_URL",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "CLAUDE_CODE_OAUTH_REFRESH_TOKEN",
        "CLAUDE_CODE_OAUTH_SCOPES",
    ):
        env.pop(name, None)
    return env
