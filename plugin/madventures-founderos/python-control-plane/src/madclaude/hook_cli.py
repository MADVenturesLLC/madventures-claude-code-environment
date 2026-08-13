from __future__ import annotations

import json
import os
import sys
import argparse
from pathlib import Path
from typing import Any

from .escalation_state import CALLER_FIELDS, DenialJournal
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


def _journal_denial(payload: dict[str, Any], reason: str) -> None:
    """A10-C (Q2/Q5): write a durable denial record on a denial exit.

    Best-effort in the sense that a journal failure must never turn a
    denial into a permit — the caller already decided to deny. The record
    carries the tool name, the redacted target, the resolved route and risk
    tier from the payload, the denial reason (A10-A-redacted by the journal
    before write), the control id (the payload's own control id when
    present, else the stable marker of this journal writer), and the
    evidence_ref computed by the journal. Requires MADCLAUDE_REPO_ROOT to
    locate the protected evidence tree; without it, the denial still stands
    and nothing is journaled (fail-closed on the decision, no crash on the
    side effect).
    """
    root = os.environ.get("MADCLAUDE_REPO_ROOT")
    if not root:
        return
    raw_input = payload.get("tool_input")
    tool_input = raw_input if isinstance(raw_input, dict) else {}
    fields = {
        "objective_id": str(payload.get("objective_id") or os.environ.get("MADCLAUDE_OBJECTIVE_ID") or ""),
        "action_type": str(payload.get("tool_name") or "unknown"),
        "action_target": str(tool_input.get("command") or tool_input.get("file_path") or tool_input.get("url") or ""),
        "resolved_route": str(payload.get("route") or "baseline"),
        "risk_tier": str(payload.get("risk_tier") or "unknown"),
        "denial_reason": reason,
        "control_id": str(payload.get("control_id") or "journal-writer"),
    }
    missing = [f for f in CALLER_FIELDS if f not in fields]
    if missing:
        return
    try:
        DenialJournal(Path(root)).record_denial(fields)
    except Exception:
        # Q5: a denial that cannot be journaled is still a denial. Never
        # surface storage error details; never crash the hook.
        return


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
                # A10-C (Q2): journal every denial exit, then report deny.
                try:
                    decision = output.get("hookSpecificOutput", {})
                    if decision.get("permissionDecision") == "deny":
                        _journal_denial(payload, str(decision.get("permissionDecisionReason") or "denied"))
                except Exception:
                    pass
                sys.stdout.write(json.dumps(output, separators=(",", ":")))
            return 0
        raw_root = os.environ.get("MADCLAUDE_REPO_ROOT") or payload.get("cwd") or os.getcwd()
        allowed, reason = evaluate_profile(Path(str(raw_root)).expanduser().resolve(), payload, args.profile)
    except Exception as exc:
        sys.stderr.write(f"MAD Ventures hook denied malformed or unevaluable input: {exc}\n")
        return 2
    if not allowed:
        # A10-C (Q2/Q5): the denial is journaled durably before the hook
        # reports it. A journal failure never turns this deny into a permit.
        try:
            _journal_denial(payload, reason)
        except Exception:
            pass
        sys.stderr.write(reason.rstrip() + "\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
