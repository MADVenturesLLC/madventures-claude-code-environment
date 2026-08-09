from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .errors import AgentRunError
from .guard import MUTATION_TOOLS, evaluate_tool_call
from .schemas import validate_instance

PACKAGE_SRC = Path(__file__).resolve().parents[1]
KNOWN_TOOLS = (
    "Read",
    "Grep",
    "Glob",
    "Edit",
    "Write",
    "NotebookEdit",
    "MultiEdit",
    "Agent",
    "Task",
    "Bash",
    "PowerShell",
    "WebFetch",
    "WebSearch",
    "Skill",
)
ALWAYS_DENIED = ("Bash", "PowerShell", "WebFetch", "WebSearch", "Skill", "mcp__*")


@dataclass(frozen=True)
class AgentRequest:
    route_name: str
    prompt: str
    cwd: Path
    claude_path: str
    environment: dict[str, str]
    model: str
    effort: str
    max_turns: int
    permission_mode: str
    tools: tuple[str, ...]
    schema: dict[str, Any]
    timeout_seconds: int
    mutates: bool = False
    allowed_scopes: tuple[str, ...] = ()
    max_budget_usd: float | None = None
    setting_sources: tuple[str, ...] = ("project",)
    system_append: str = ""
    backend: str = "cli"
    billing_mode: str = "subscription"
    subagents: tuple[str, ...] = ()


@dataclass
class AgentResponse:
    success: bool
    structured_output: dict[str, Any] | None
    raw_result: dict[str, Any] | None = None
    result_text: str = ""
    session_id: str | None = None
    total_cost_usd: float | None = None
    duration_ms: int = 0
    num_turns: int | None = None
    subtype: str | None = None
    terminal_reason: str | None = None
    errors: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    command: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _structured_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    structured = payload.get("structured_output")
    if isinstance(structured, dict):
        return structured
    result = payload.get("result")
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return None


def _control_plane_environment(request: AgentRequest) -> dict[str, str]:
    environment = dict(request.environment)
    # The ephemeral hook runs through this exact Python source. Do not inherit an untrusted PYTHONPATH.
    environment["PYTHONPATH"] = str(PACKAGE_SRC)
    environment.update(
        {
            "MADCLAUDE_CONTROL_PLANE_ACTIVE": "1",
            "MADCLAUDE_ROUTE": request.route_name,
            "MADCLAUDE_REPO_ROOT": str(request.cwd.resolve()),
            "MADCLAUDE_MUTATES": "1" if request.mutates else "0",
            "MADCLAUDE_ALLOWED_TOOLS_JSON": json.dumps(list(request.tools), separators=(",", ":")),
            "MADCLAUDE_ALLOWED_SCOPES_JSON": json.dumps(list(request.allowed_scopes), separators=(",", ":")),
            "MADCLAUDE_ALLOWED_SUBAGENTS_JSON": json.dumps(list(request.subagents), separators=(",", ":")),
        }
    )
    return environment


def _deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def make_pre_tool_policy_hook(request: AgentRequest):
    async def policy_hook(input_data: dict[str, Any], tool_use_id: str | None, context: Any) -> dict[str, Any]:
        del tool_use_id, context
        agent_id = str(input_data.get("agent_id") or "").strip()
        agent_type = str(input_data.get("agent_type") or "").strip()
        if agent_id and (not agent_type or agent_type not in set(request.subagents)):
            return _deny(f"Tool call came from unapproved subagent {agent_type or '[missing]' }.")
        tool_name = str(input_data.get("tool_name") or "")
        if agent_id and tool_name in {"Agent", "Task"}:
            return _deny("Nested subagent delegation is disabled in Python control-plane routes.")
        allowed, reason = evaluate_tool_call(
            repo=request.cwd,
            tool_name=tool_name,
            tool_input=input_data.get("tool_input") if isinstance(input_data.get("tool_input"), dict) else {},
            allowed_tools=request.tools,
            mutates=request.mutates,
            scopes=request.allowed_scopes,
            allowed_subagents=request.subagents,
        )
        return {} if allowed else _deny(reason)

    return policy_hook


def _allowed_tool_specs(request: AgentRequest) -> list[str]:
    specs = [tool for tool in request.tools if tool != "Agent"]
    if "Agent" in request.tools:
        specs.extend(f"Agent({name})" for name in request.subagents)
    return specs


def _disallowed_tools(request: AgentRequest) -> list[str]:
    allowed = set(request.tools)
    denied = list(ALWAYS_DENIED)
    for tool in KNOWN_TOOLS:
        if tool == "Agent" and "Agent" in allowed:
            continue
        if tool not in allowed:
            denied.append(tool)
    # Task is kept denied even when Agent is enabled so only the current explicit Agent surface is used.
    denied.append("Task")
    if not request.mutates:
        denied.extend(sorted(MUTATION_TOOLS))
    return list(dict.fromkeys(denied))


def _hook_command() -> str:
    argv = [sys.executable, "-m", "madclaude.hook_cli"]
    return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)


@contextmanager
def _ephemeral_policy_settings() -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="madclaude-policy-") as temp:
        path = Path(temp) / "settings.json"
        payload = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": _hook_command(),
                                "timeout": 30,
                            }
                        ],
                    }
                ]
            }
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        if os.name != "nt":
            path.chmod(0o600)
        yield path


def _redact_command(command: list[str], *, settings_path: Path, prompt: str) -> list[str]:
    redacted: list[str] = []
    for item in command:
        if item == str(settings_path):
            redacted.append("[EPHEMERAL POLICY SETTINGS]")
        elif item == prompt:
            redacted.append("[PROMPT REDACTED FROM COMMAND EVIDENCE]")
        else:
            redacted.append(item)
    return redacted


class CliBackend:
    """Default subscription-first backend: Python governs the native `claude -p` process."""

    name = "cli"

    def run(self, request: AgentRequest) -> AgentResponse:
        if request.backend != "cli":
            raise AgentRunError(f"CLI backend received mismatched backend value: {request.backend}")
        if request.mutates and not request.allowed_scopes:
            raise AgentRunError("Mutating CLI routes require at least one Founder-approved scope.")
        if "Agent" in request.tools and not request.subagents:
            raise AgentRunError("Agent tool is enabled but the route has no approved subagent registry.")

        with _ephemeral_policy_settings() as policy_settings:
            command = [
                request.claude_path,
                "-p",
                "--output-format",
                "json",
                "--json-schema",
                json.dumps(request.schema, separators=(",", ":")),
                "--model",
                request.model,
                "--effort",
                request.effort,
                "--permission-mode",
                request.permission_mode,
                "--max-turns",
                str(request.max_turns),
                "--setting-sources",
                ",".join(request.setting_sources),
                "--settings",
                str(policy_settings),
                "--tools",
                ",".join(request.tools),
                "--allowedTools",
                ",".join(_allowed_tool_specs(request)),
                "--disallowedTools",
                ",".join(_disallowed_tools(request)),
                "--strict-mcp-config",
            ]
            if request.system_append:
                command.extend(["--append-system-prompt", request.system_append])
            if request.subagents:
                command.extend(
                    [
                        "--append-subagent-system-prompt",
                        (
                            "Operate read-only, remain inside the repository, do not delegate further, "
                            "and return concise conclusions with exact file evidence to the parent agent."
                        ),
                    ]
                )
            if request.billing_mode == "api" and request.max_budget_usd is not None:
                command.extend(["--max-budget-usd", f"{request.max_budget_usd:.4f}"])
            command.append(request.prompt)

            started = time.monotonic()
            try:
                completed = subprocess.run(
                    command,
                    cwd=str(request.cwd),
                    env=_control_plane_environment(request),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=request.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise AgentRunError(f"Claude run exceeded {request.timeout_seconds} seconds.") from exc
            except OSError as exc:
                raise AgentRunError(f"Claude CLI could not be started: {exc}") from exc
            duration = int((time.monotonic() - started) * 1000)
            command_evidence = _redact_command(command, settings_path=policy_settings, prompt=request.prompt)

        payload: dict[str, Any] | None = None
        errors: list[str] = []
        try:
            parsed = json.loads(completed.stdout.strip())
            if isinstance(parsed, dict):
                payload = parsed
            else:
                errors.append("Claude JSON output was not an object.")
        except json.JSONDecodeError as exc:
            errors.append(f"Claude output was not valid JSON: {exc}")

        structured = _structured_from_payload(payload or {}) if payload else None
        if structured is not None:
            errors.extend(validate_instance(structured, request.schema))
        else:
            errors.append("Claude did not return structured_output matching the requested schema.")

        total_cost = (payload or {}).get("total_cost_usd")
        if (
            request.billing_mode == "api"
            and request.max_budget_usd is not None
            and isinstance(total_cost, (int, float))
            and total_cost > request.max_budget_usd
        ):
            errors.append(
                f"Client-estimated cost ${total_cost:.4f} exceeded the configured "
                f"${request.max_budget_usd:.4f} ceiling."
            )
        if completed.returncode != 0:
            errors.append(f"Claude exited {completed.returncode}.")

        success = completed.returncode == 0 and not errors and structured is not None
        return AgentResponse(
            success=success,
            structured_output=structured,
            raw_result=payload,
            result_text=str((payload or {}).get("result") or ""),
            session_id=(payload or {}).get("session_id"),
            total_cost_usd=total_cost,
            duration_ms=duration,
            num_turns=(payload or {}).get("num_turns"),
            subtype=(payload or {}).get("subtype"),
            terminal_reason=(payload or {}).get("terminal_reason"),
            errors=errors,
            stdout=completed.stdout,
            stderr=completed.stderr,
            command=command_evidence,
        )


class SdkBackend:
    """Optional Agent SDK backend. V4.4 permits it only in an explicit API-billed lane."""

    name = "sdk"

    def run(self, request: AgentRequest) -> AgentResponse:
        if request.billing_mode != "api":
            raise AgentRunError(
                "The Agent SDK backend is an optional API-billed lane in V4.4. Use the default CLI "
                "backend for Claude subscription usage, or explicitly select API billing."
            )
        return asyncio.run(self._run(request))

    async def _run(self, request: AgentRequest) -> AgentResponse:
        try:
            from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, ResultMessage, query
        except ImportError as exc:
            raise AgentRunError(
                "The optional SDK backend requires `claude-agent-sdk==0.2.131`. Reinstall the "
                "Python control plane with `--with-sdk`; API billing gates still apply at runtime."
            ) from exc

        stderr_lines: list[str] = []
        denied = _disallowed_tools(request)
        hook = make_pre_tool_policy_hook(request)
        options = ClaudeAgentOptions(
            tools=list(request.tools),
            allowed_tools=_allowed_tool_specs(request),
            system_prompt={"type": "preset", "preset": "claude_code", "append": request.system_append},
            permission_mode=request.permission_mode,
            max_turns=request.max_turns,
            max_budget_usd=request.max_budget_usd,
            disallowed_tools=denied,
            model=request.model,
            output_format={"type": "json_schema", "schema": request.schema},
            cwd=str(request.cwd),
            cli_path=request.claude_path,
            env=_control_plane_environment(request),
            setting_sources=list(request.setting_sources),
            strict_mcp_config=True,
            mcp_servers={},
            skills=[],
            plugins=[],
            hooks={"PreToolUse": [HookMatcher(hooks=[hook], timeout=30)]},
            effort=request.effort,
            enable_file_checkpointing=True,
            stderr=stderr_lines.append,
        )

        started = time.monotonic()
        final: Any = None
        caught: Exception | None = None
        try:
            async for message in query(prompt=request.prompt, options=options):
                if isinstance(message, ResultMessage):
                    final = message
        except Exception as exc:  # SDKs can raise after yielding an error ResultMessage.
            caught = exc
        duration = int((time.monotonic() - started) * 1000)
        if final is None:
            detail = f": {caught}" if caught else ""
            raise AgentRunError(f"Agent SDK returned no ResultMessage{detail}") from caught

        structured = getattr(final, "structured_output", None)
        errors = validate_instance(structured, request.schema) if isinstance(structured, dict) else [
            "Agent SDK returned no structured_output."
        ]
        sdk_errors = getattr(final, "errors", None)
        if isinstance(sdk_errors, list):
            errors.extend(str(item) for item in sdk_errors if item)
        if caught is not None and getattr(final, "subtype", None) != "success":
            errors.append(f"Agent SDK terminated with an exception after its final result: {caught}")

        total_cost = getattr(final, "total_cost_usd", None)
        if (
            request.max_budget_usd is not None
            and isinstance(total_cost, (int, float))
            and total_cost > request.max_budget_usd
        ):
            errors.append(
                f"Client-estimated cost ${total_cost:.4f} exceeded the configured "
                f"${request.max_budget_usd:.4f} ceiling."
            )
        success = getattr(final, "subtype", None) == "success" and not errors
        return AgentResponse(
            success=success,
            structured_output=structured if isinstance(structured, dict) else None,
            raw_result={
                "subtype": getattr(final, "subtype", None),
                "session_id": getattr(final, "session_id", None),
                "terminal_reason": getattr(final, "terminal_reason", None),
                "stop_reason": getattr(final, "stop_reason", None),
            },
            result_text=str(getattr(final, "result", "") or ""),
            session_id=getattr(final, "session_id", None),
            total_cost_usd=total_cost,
            duration_ms=duration,
            num_turns=getattr(final, "num_turns", None),
            subtype=getattr(final, "subtype", None),
            terminal_reason=getattr(final, "terminal_reason", None),
            errors=errors,
            stderr="\n".join(stderr_lines),
            command=["claude-agent-sdk", request.route_name, request.model, request.effort, "[API-BILLED]"],
        )


def backend_for(name: str):
    if name == "cli":
        return CliBackend()
    if name == "sdk":
        return SdkBackend()
    raise AgentRunError(f"Unsupported backend: {name}")
