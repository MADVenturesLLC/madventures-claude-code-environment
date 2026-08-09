from __future__ import annotations

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Any

from .guard import evaluate_tool_call
from .hook_policy import evaluate_profile


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _string_list(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "[]")
    value = json.loads(raw)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be a JSON array of strings")
    return tuple(value)


def evaluate_input(payload: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("MADCLAUDE_CONTROL_PLANE_ACTIVE") != "1":
        return {}
    root = os.environ.get("MADCLAUDE_REPO_ROOT")
    if not root:
        return _deny("Python control-plane policy is missing MADCLAUDE_REPO_ROOT.")
    try:
        allowed_subagents = _string_list("MADCLAUDE_ALLOWED_SUBAGENTS_JSON")
        agent_id = str(payload.get("agent_id") or "").strip()
        agent_type = str(payload.get("agent_type") or "").strip()
        if agent_id and (not agent_type or agent_type not in set(allowed_subagents)):
            return _deny(f"Tool call came from unapproved subagent {agent_type or '[missing]' }.")
        tool_name = str(payload.get("tool_name") or "")
        if agent_id and tool_name in {"Agent", "Task"}:
            return _deny("Nested subagent delegation is disabled in Python control-plane routes.")
        allowed, reason = evaluate_tool_call(
            repo=Path(root),
            tool_name=tool_name,
            tool_input=payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {},
            allowed_tools=_string_list("MADCLAUDE_ALLOWED_TOOLS_JSON"),
            mutates=os.environ.get("MADCLAUDE_MUTATES") == "1",
            scopes=_string_list("MADCLAUDE_ALLOWED_SCOPES_JSON"),
            allowed_subagents=allowed_subagents,
        )
    except Exception as exc:  # Fail closed without exposing environment values.
        return _deny(f"Python control-plane policy could not be evaluated: {exc}")
    return {} if allowed else _deny(reason)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--profile", choices=("control-plane", "baseline", "sql", "completion"), default="control-plane")
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            raise ValueError("hook input must be a JSON object")
        if args.profile == "control-plane":
            output = evaluate_input(payload)
            if output:
                sys.stdout.write(json.dumps(output, separators=(",", ":")))
            return 0
        raw_root = os.environ.get("MADCLAUDE_REPO_ROOT") or payload.get("cwd") or os.getcwd()
        allowed, reason = evaluate_profile(Path(str(raw_root)).expanduser().resolve(), payload, args.profile)
    except Exception as exc:
        sys.stderr.write(f"MAD Ventures hook denied malformed or unevaluable input: {exc}\n")
        return 2
    if allowed:
        return 0
    sys.stderr.write(reason.rstrip() + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
