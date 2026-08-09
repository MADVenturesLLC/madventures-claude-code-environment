"""Optional Local Control Plane MCP server (A9-05).

MCP is the interface layer; Python remains the sole deterministic enforcement
authority. This server:

- runs on stdio transport only, started only via the release launcher, and
  refuses to start when the integrity prelaunch fails or the current pointer
  is absent (disabled state);
- exposes exactly the locked tool surface: control_plane_status, routes_list,
  evidence_index, evidence_read, request_verification — all read-only except
  request_verification, which invokes the existing governed run_verify path
  (guarded by validate_verification_command) and returns the evidence-bundle
  reference produced by that machinery;
- never fabricates results, never writes evidence itself, and exposes no
  approval, lifecycle, restore, merge, deploy, or write primitives. Every tool
  response carries authority: "non-authoritative".

The `mcp` package is imported only inside serve(), which runs only inside the
release venv; the base CLI installation never imports it and stays
dependency-free. Protocol handling below (handle_jsonrpc / call_tool) is
stdlib-only so the dependency-free harness can exercise it via a stub
transport.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import guard, safe_read
from .config import get_route
from .errors import PolicyViolation
from .evidence import EVIDENCE_SOURCE_CAP_BYTES, read_evidence_source
from .guard import validate_verification_command
from .mcp_lifecycle import releases_root, verify_release_prelaunch
from .version import __version__
from .workflows import RuntimeOptions, run_verify

AUTHORITY = "non-authoritative"
PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "madclaude-local-control-plane"

TOOL_NAMES = (
    "control_plane_status",
    "routes_list",
    "evidence_index",
    "evidence_read",
    "request_verification",
)


@dataclass(frozen=True)
class ServerContext:
    home: Path
    release_dir: Path


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "control_plane_status",
            "description": "Non-authoritative snapshot of control-plane version and MCP release state.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "routes_list",
            "description": "List governed model/effort/tool routes. Non-authoritative.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "evidence_index",
            "description": "List Python verification evidence bundles for a repository. Non-authoritative.",
            "inputSchema": {
                "type": "object",
                "properties": {"repo": {"type": "string"}},
                "required": ["repo"],
                "additionalProperties": False,
            },
        },
        {
            "name": "evidence_read",
            "description": (
                "Read one file inside an evidence bundle with B3 hash-provenance reporting. "
                "Non-authoritative; oversized sources are reported, never streamed."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "bundle": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["repo", "bundle", "path"],
                "additionalProperties": False,
            },
        },
        {
            "name": "request_verification",
            "description": (
                "Request a governed Python verification run. Commands are validated by the same "
                "deterministic guard as the CLI; the evidence bundle is produced by the existing "
                "run_verify machinery. Non-authoritative."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "goal": {"type": "string"},
                    "commands": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                },
                "required": ["repo", "commands"],
                "additionalProperties": False,
            },
        },
    ]


def _evidence_root(repo: Path) -> Path:
    if not repo.is_dir():
        raise PolicyViolation(f"Repository does not exist: {repo}")
    return repo / ".claude" / "evidence" / "python-control-plane"


def _control_plane_status(context: ServerContext, _arguments: dict[str, Any]) -> dict[str, Any]:
    current = releases_root(context.home) / "current"
    return {
        "version": __version__,
        "python": sys.version.split()[0],
        "release": context.release_dir.name,
        "currentPresent": current.is_symlink(),
        "tools": list(TOOL_NAMES),
    }


def _routes_list(_context: ServerContext, _arguments: dict[str, Any]) -> dict[str, Any]:
    from .config import ROUTES

    return {"routes": {name: asdict(route) for name, route in ROUTES.items()}}


def _evidence_index(_context: ServerContext, arguments: dict[str, Any]) -> dict[str, Any]:
    root = _evidence_root(Path(str(arguments.get("repo", ""))).expanduser().resolve())
    bundles: list[dict[str, Any]] = []
    if root.is_dir():
        for manifest_path in sorted(root.glob("*/MANIFEST.json")):
            bundle_fd = safe_read.open_root(manifest_path.parent)
            try:
                try:
                    manifest = json.loads(safe_read.read_text(bundle_fd, "MANIFEST.json"))
                except (PolicyViolation, json.JSONDecodeError):
                    manifest = {}
            finally:
                os.close(bundle_fd)
            bundles.append(
                {
                    "bundle": manifest_path.parent.name,
                    "status": manifest.get("status") if isinstance(manifest, dict) else None,
                    "route": manifest.get("route") if isinstance(manifest, dict) else None,
                }
            )
    return {"bundles": bundles}


def _bundle_dir(root: Path, bundle_name: str) -> Path:
    """Resolve a caller-supplied bundle name to a directory beneath the
    evidence root, failing closed on anything but one safe component."""
    return root / safe_read.validate_component(bundle_name)


def _evidence_read(_context: ServerContext, arguments: dict[str, Any]) -> dict[str, Any]:
    root = _evidence_root(Path(str(arguments.get("repo", ""))).expanduser().resolve())
    bundle_name = str(arguments.get("bundle", ""))
    relative = str(arguments.get("path", ""))
    bundle = _bundle_dir(root, bundle_name)
    bundle_fd = safe_read.open_root(bundle)  # rejects symlinked/missing bundles
    try:
        declared: str | None = None
        try:
            manifest = json.loads(safe_read.read_text(bundle_fd, "MANIFEST.json"))
            for entry in manifest.get("files", []):
                if isinstance(entry, dict) and entry.get("path") == relative:
                    candidate = entry.get("sha256")
                    declared = candidate if isinstance(candidate, str) else None
                    break
        except (PolicyViolation, json.JSONDecodeError):
            declared = None
        source, buffer = read_evidence_source(bundle_fd, relative, declared)
        result: dict[str, Any] = {"path": relative, "bundle": bundle_name, "sources": [source]}
        if buffer is not None:
            # Content is decoded from the same single read buffer that was
            # hashed — never from a second open. Non-UTF-8 content is
            # reported, never lossy-decoded.
            try:
                result["content"] = buffer.decode("utf-8")
            except UnicodeDecodeError:
                result["contentEncoding"] = "binary"
        return result
    finally:
        os.close(bundle_fd)


def _request_verification(_context: ServerContext, arguments: dict[str, Any]) -> dict[str, Any]:
    if not guard.STRICT_VERIFICATION_ALLOWLIST:
        raise PolicyViolation(
            "request_verification is disabled until verification commands are constrained "
            "by the strict executable/subcommand allowlist."
        )
    repo = Path(str(arguments.get("repo", ""))).expanduser().resolve()
    commands = arguments.get("commands")
    if not isinstance(commands, list) or not commands or not all(isinstance(item, str) for item in commands):
        raise PolicyViolation("request_verification requires a non-empty string array of commands.")
    for command in commands:
        validate_verification_command(command)
    if not repo.is_dir():
        raise PolicyViolation(f"Repository does not exist: {repo}")
    goal = str(arguments.get("goal") or "MCP-requested verification")
    options = RuntimeOptions(
        backend="cli",
        billing_mode="subscription",
        allow_api_billing=False,
        allow_usage_credits=False,
        claude_path=shutil.which("claude") or "claude",
        timeout_seconds=600,
        verification_timeout_seconds=600,
        max_budget_usd=None,
        evidence_dir=repo / ".claude" / "evidence" / "python-control-plane",
    )
    outcome = run_verify(get_route("verify"), options, repo, goal, commands)
    # The evidence bundle is produced by the existing run_verify machinery;
    # this layer returns only its reference and status.
    return {
        "evidenceBundle": outcome.evidence_path,
        "status": outcome.status,
        "errors": outcome.errors,
    }


_TOOL_HANDLERS = {
    "control_plane_status": _control_plane_status,
    "routes_list": _routes_list,
    "evidence_index": _evidence_index,
    "evidence_read": _evidence_read,
    "request_verification": _request_verification,
}


def call_tool(name: str, arguments: dict[str, Any], context: ServerContext) -> dict[str, Any]:
    if name not in _TOOL_HANDLERS:
        raise PolicyViolation(f"Unknown tool: {name!r}")
    if not isinstance(arguments, dict):
        raise PolicyViolation("Tool arguments must be an object.")
    result = _TOOL_HANDLERS[name](context, arguments)
    result["authority"] = AUTHORITY
    return result


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle_jsonrpc(message: Any, context: ServerContext) -> dict[str, Any] | None:
    """Minimal JSON-RPC surface for the locked tool set. Returns None for
    notifications (messages without an id). Malformed frames produce error
    responses, never fabricated results."""
    if not isinstance(message, dict) or not isinstance(message.get("method"), str):
        return _jsonrpc_error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid JSON-RPC request")
    request_id = message.get("id")
    method = message["method"]
    if method == "initialize":
        if request_id is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": __version__, "authority": AUTHORITY},
            },
        }
    if method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if method == "tools/list":
        if request_id is None:
            return None
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tool_definitions()}}
    if method == "tools/call":
        if request_id is None:
            return None  # notifications never execute tools
        params = message.get("params")
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return _jsonrpc_error(request_id, -32602, "tools/call requires params.name")
        try:
            result = call_tool(params["name"], params.get("arguments") or {}, context)
        except PolicyViolation as exc:
            return _jsonrpc_error(request_id, -32602, str(exc))
        except Exception as exc:  # fail closed, never fabricate
            return _jsonrpc_error(request_id, -32603, f"Tool failed without producing a result: {type(exc).__name__}")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, indent=2, sort_keys=True)}],
                "structuredContent": result,
                "isError": False,
            },
        }
    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def serve(context: ServerContext) -> int:
    """Stdio serving via the mcp SDK; imported only inside the release venv."""
    try:
        import importlib.metadata

        if importlib.metadata.version("mcp") != "2.0.0":
            raise PolicyViolation("The MCP server requires exactly mcp==2.0.0 in the release venv.")
        from mcp.server.mcpserver import MCPServer
    except ImportError as exc:
        raise PolicyViolation(
            "The MCP server requires the release venv (mcp==2.0.0); the base installation "
            "deliberately stays dependency-free."
        ) from exc
    server = MCPServer(SERVER_NAME, version=__version__)

    # Explicit per-tool signatures so the SDK advertises the real input
    # schemas; every handler adapts straight into the stdlib call_tool core.
    def control_plane_status() -> dict[str, Any]:
        return call_tool("control_plane_status", {}, context)

    def routes_list() -> dict[str, Any]:
        return call_tool("routes_list", {}, context)

    def evidence_index(repo: str) -> dict[str, Any]:
        return call_tool("evidence_index", {"repo": repo}, context)

    def evidence_read(repo: str, bundle: str, path: str) -> dict[str, Any]:
        return call_tool("evidence_read", {"repo": repo, "bundle": bundle, "path": path}, context)

    def request_verification(repo: str, commands: list[str], goal: str = "") -> dict[str, Any]:
        arguments: dict[str, Any] = {"repo": repo, "commands": commands}
        if goal:
            arguments["goal"] = goal
        return call_tool("request_verification", arguments, context)

    handlers = {
        "control_plane_status": control_plane_status,
        "routes_list": routes_list,
        "evidence_index": evidence_index,
        "evidence_read": evidence_read,
        "request_verification": request_verification,
    }
    if set(handlers) != set(TOOL_NAMES):
        raise PolicyViolation("MCP SDK handler surface diverged from the locked tool surface.")
    for definition in tool_definitions():
        handler = handlers[definition["name"]]
        handler.__doc__ = definition["description"]
        server.add_tool(
            handler,
            name=definition["name"],
            description=definition["description"],
            structured_output=True,
        )
    server.run(transport="stdio")
    return 0


def _self_release_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    self_test = "--self-test" in argv
    staged = "--staged" in argv
    argv = [item for item in argv if item not in ("--self-test", "--staged")]
    home = Path(os.environ.get("MADCLAUDE_HOME") or (Path.home() / ".madclaude")).expanduser().resolve()
    release_dir = _self_release_dir()
    current = releases_root(home) / "current"
    try:
        if staged:
            # Invoked only by the BASE control plane (staged_self_test), which
            # ran install-tier verification before launching this interpreter.
            # No anchor or current pointer can exist pre-activation, and a
            # staged release never serves: self-test output only.
            if not self_test:
                raise PolicyViolation("A staged release cannot serve; --staged requires --self-test.")
            print(f"mcp self-test ok: {release_dir.name}")
            return 0
        if not current.is_symlink():
            raise PolicyViolation(
                "MCP control plane is disabled (no current release). Re-enable with: madclaude mcp re-enable"
            )
        if current.resolve() != release_dir:
            raise PolicyViolation(
                "This release is not the active one; only the release pointed to by current may serve."
            )
        if not (release_dir / "RELEASE_INTEGRITY.json").is_file():
            raise PolicyViolation("The MCP server must be started via the release launcher.")
        # Defense in depth: the sanctioned path (stable wrapper -> base
        # `mcp serve`) already ran externally anchored verification before any
        # release-owned code executed; this re-check keeps direct execution
        # fail-closed too.
        verify_release_prelaunch(release_dir, home=home)
        context = ServerContext(home=home, release_dir=release_dir)
        if self_test:
            print(f"mcp self-test ok: {release_dir.name}")
            return 0
        return serve(context)
    except PolicyViolation as exc:
        print(f"mcp server refused to start: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
