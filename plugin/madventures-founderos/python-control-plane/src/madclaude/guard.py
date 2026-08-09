from __future__ import annotations

import fnmatch
import os
import re
import shlex
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from .errors import PolicyViolation

MUTATION_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
WEB_TOOLS = {"WebFetch", "WebSearch"}
SHELL_TOOLS = {"Bash", "PowerShell"}
ALIASES = {"Task": "Agent"}

SENSITIVE_FILE_PATTERNS = (
    re.compile(r"(^|/)\.env(?:\.[^/]+)?$", re.I),
    re.compile(r"(^|/)(?:id_rsa|id_ed25519|id_ecdsa)(?:\.pub)?$", re.I),
    re.compile(r"\.(?:pem|p12|pfx|key|keystore|jks|kdbx)$", re.I),
    re.compile(r"(^|/)(?:\.npmrc|\.netrc|\.pypirc)$", re.I),
    re.compile(r"(^|/)\.aws/credentials$", re.I),
    re.compile(r"(^|/)\.config/gcloud/application_default_credentials\.json$", re.I),
    re.compile(r"(^|/)(?:credentials|service[-_]?account)(?:\.[^/]*)?\.json$", re.I),
    re.compile(r"(^|/)secrets?\.(?:json|ya?ml|toml)$", re.I),
)
ALLOWED_ENV_TEMPLATES = re.compile(r"(^|/)\.env\.(?:example|sample|template|defaults?)$", re.I)
PROTECTED_AUTHORITY_PATTERNS = (
    re.compile(r"(^|/)\.git(?:/|$)", re.I),
    re.compile(r"(^|/)CLAUDE\.md$", re.I),
    re.compile(r"(^|/)\.claude/(?:FOUNDEROS|MODEL_REGISTRY|PROJECT_PROFILE|INSTALLATION_RECORD)\.md$", re.I),
    re.compile(r"(^|/)\.claude/(?:settings(?:\.local)?\.json|rules|hooks|control-plane|evidence)(?:/|$)", re.I),
    re.compile(r"(^|/)01-constitution(?:/|$)", re.I),
    re.compile(r"(^|/)04-agents/role-registry\.md$", re.I),
    re.compile(r"(^|/)07-decisions/decision-log\.md$", re.I),
    re.compile(r"(^|/)decision-id-reservations\.md$", re.I),
    re.compile(r"(^|/)evidence(?:/|$)", re.I),
)
SECRET_CONTENT_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)

DANGEROUS_PATTERNS = (
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[^\s]*[fdx]",
    r"\bgit\s+push\b",
    r"\bgh\s+(?:pr\s+merge|release\s+create|api)\b",
    r"\brm\s+-[^\s]*r[^\s]*f",
    r"\b(?:mkfs|fdisk|parted|shutdown|reboot|halt|poweroff|dd)\b",
    r"\bclaude\b[^\n]*(?:--dangerously-skip-permissions|--allow-dangerously-skip-permissions)\b",
    r"\b(?:del|erase|rmdir)\b[^\n]*(?:\\Windows|C:\\)",
)
SHELL_CONTROL = re.compile(r"(?:&&|\|\||[;|<>`]|\$\()")
NETWORK_OR_AUTHORITY_EXECUTABLES = {
    "curl", "wget", "http", "httpie", "ssh", "scp", "sftp", "rsync",
    "aws", "gcloud", "az", "kubectl", "helm", "terraform", "tofu", "pulumi",
    "vercel", "wrangler", "netlify", "fly", "heroku", "doctl", "gh",
    "docker", "podman", "compose", "psql", "mysql", "sqlite3", "mongosh", "redis-cli",
}
SHELL_EXECUTABLES = {"sh", "bash", "zsh", "fish", "dash", "ksh", "cmd", "cmd.exe", "powershell", "pwsh"}
READ_ONLY_GIT_SUBCOMMANDS = {
    "status", "diff", "show", "log", "rev-parse", "ls-files", "grep", "merge-base",
    "cat-file", "describe", "blame", "branch", "remote",
}
# R6-01 (P0): positive package-manager verification grammar.
# Only these exact subcommand shapes are permitted; everything else is
# denied.  This replaces the old blacklist (PACKAGE_MUTATIONS +
# RISKY_SCRIPT_WORDS) which allowed unknown subcommands like `npm config`,
# `npm cache clean`, `npm rebuild`, `pnpm store prune`, etc.
PACKAGE_MANAGER_VERIFICATION_SUBCOMMANDS = frozenset({"run", "test"})
PACKAGE_MANAGER_VERIFICATION_SCRIPTS = frozenset({
    "test", "check", "verify", "lint", "audit",
})
SAFE_PYTHON_MODULES = {
    "pytest", "unittest", "compileall", "coverage", "mypy", "ruff", "pyright", "tox", "nox",
}

# Strict verification-command contract (Audit 9 remediation): only these
# executables may ever run as verification commands, each further constrained
# by the per-executable argument-shape rules in validate_verification_command.
# Anything else — including launcher prefixes such as env/nice/xargs/time and
# mutation tools such as rm — is denied regardless of arguments. The MCP
# request_verification tool stays disabled unless this flag is True.
STRICT_VERIFICATION_ALLOWLIST = True
VERIFICATION_EXECUTABLE_ALLOWLIST = frozenset({"git", "node", "npm", "pnpm", "yarn", "bun", "py"})

# Exact Python launcher-name grammar (R6-01). Only the documented CPython
# launcher names are verification executables: "python", "python3", and the
# versioned "python3.<minor>" form (including the free-threaded
# "python3.<minor>t" build). This is an exact full match, never a prefix:
# "python-evil", "python2", "python3x", and any other python-* name is denied.
PYTHON_LAUNCHER_NAME = re.compile(r"python(?:3(?:\.\d{1,2}t?)?)?")

# The only Python interpreter options permitted in a verification command.
# They produce version/help output and can never redirect execution; a
# command built from them may contain nothing else. Every other interpreter
# option (-I, -u, -O, -E, -s, -S, -W, -X, --, ...) can shift or obscure the
# actual execution target and is denied outright (R6-01).
PYTHON_INFORMATIONAL_FLAGS = frozenset({"--version", "-V", "-h", "--help"})
SENSITIVE_GLOB_SAMPLES = (
    ".env", ".env.local", "private.pem", "id_rsa", ".npmrc", "credentials.json", "service-account.json"
)


def normalize_scope(scope: str) -> str:
    value = scope.strip().replace("\\", "/")
    if not value or value == ".":
        return ""
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise PolicyViolation(f"Allowed scope must be repository-relative and cannot escape: {scope}")
    return str(path).rstrip("/")


def within_scopes(path: str, scopes: tuple[str, ...]) -> bool:
    normalized = str(PurePosixPath(path.replace("\\", "/")))
    for raw in scopes:
        scope = normalize_scope(raw)
        if not scope or normalized == scope or normalized.startswith(scope + "/"):
            return True
    return False


def enforce_scopes(paths: tuple[str, ...], scopes: tuple[str, ...]) -> None:
    if not scopes:
        raise PolicyViolation("At least one explicit allowed scope is required for mutation.")
    violations = [path for path in paths if not within_scopes(path, scopes)]
    if violations:
        raise PolicyViolation(
            "Claude changed files outside the Founder-approved scope: " + ", ".join(sorted(violations))
        )


def validate_scopes(repo: Path, scopes: tuple[str, ...]) -> tuple[str, ...]:
    root = repo.resolve()
    normalized: list[str] = []
    for scope in scopes:
        value = normalize_scope(scope)
        target = (root / value).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise PolicyViolation(f"Scope escapes repository: {scope}") from exc
        if is_sensitive_path(value) or is_protected_authority_path(value):
            raise PolicyViolation(f"Founder-approved mutation scope is intrinsically protected: {scope}")
        normalized.append(value)
    if not normalized:
        raise PolicyViolation("At least one explicit allowed scope is required.")
    return tuple(dict.fromkeys(normalized))


def is_sensitive_path(path: str | Path) -> bool:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if ALLOWED_ENV_TEMPLATES.search(normalized):
        return False
    return any(pattern.search(normalized) for pattern in SENSITIVE_FILE_PATTERNS)


def is_protected_authority_path(path: str | Path) -> bool:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return any(pattern.search(normalized) for pattern in PROTECTED_AUTHORITY_PATTERNS)


def contains_sensitive_material(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_CONTENT_PATTERNS)


def reject_sensitive_changed_paths(paths: tuple[str, ...]) -> None:
    blocked = [path for path in paths if is_sensitive_path(path)]
    if blocked:
        raise PolicyViolation(
            "Exact-SHA evidence capture refused because the diff includes credential-bearing paths: "
            + ", ".join(sorted(blocked))
        )


def _repo_relative(repo: Path, raw: str | None, *, default_to_repo: bool = False) -> tuple[Path, str]:
    root = repo.resolve()
    if not raw:
        if default_to_repo:
            return root, ""
        raise PolicyViolation("Tool call did not provide a path.")
    if "\0" in raw:
        raise PolicyViolation("Tool path contains a NUL byte.")
    candidate = Path(raw).expanduser()
    absolute = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        relative = absolute.relative_to(root).as_posix()
    except ValueError as exc:
        raise PolicyViolation(f"Tool path escapes the repository: {raw}") from exc
    return absolute, relative


def _target_has_sensitive_files(target: Path, *, cap: int = 20_000) -> bool:
    if target.is_file():
        return is_sensitive_path(target.name)
    seen = 0
    if not target.exists():
        return False
    for path in target.rglob("*"):
        if ".git" in path.parts:
            continue
        seen += 1
        if seen > cap:
            return True
        if path.is_file() and is_sensitive_path(path.relative_to(target).as_posix()):
            return True
    return False


def _glob_is_safe_for_secrets(pattern: str) -> bool:
    return bool(pattern) and not any(fnmatch.fnmatch(sample, pattern) for sample in SENSITIVE_GLOB_SAMPLES)


def evaluate_tool_call(
    *,
    repo: Path,
    tool_name: str,
    tool_input: dict[str, Any],
    allowed_tools: tuple[str, ...],
    mutates: bool,
    scopes: tuple[str, ...] = (),
    allowed_subagents: tuple[str, ...] = (),
) -> tuple[bool, str]:
    name = ALIASES.get(tool_name, tool_name)
    allowed = {ALIASES.get(item, item) for item in allowed_tools}
    if name.lower().startswith("mcp__"):
        return False, "MCP tools are disabled in deterministic Python control-plane routes."
    if name not in allowed:
        return False, f"Tool {name} is not in the governed route allowlist."
    if name in SHELL_TOOLS:
        return False, "Shell tools are disabled; Python executes reviewed verification commands independently."
    if name in WEB_TOOLS:
        return False, "Web tools are disabled in deterministic repository routes."

    if name == "Agent":
        subagent = str(
            tool_input.get("subagent_type")
            or tool_input.get("agent_type")
            or tool_input.get("name")
            or ""
        ).strip()
        if not subagent:
            return False, "Agent invocation did not identify a registered subagent type."
        if subagent not in set(allowed_subagents):
            return False, f"Subagent {subagent} is not approved for this governed route."
        return True, "allowed"

    if name in {"Read", "Edit", "Write"}:
        raw = str(tool_input.get("file_path") or "")
        try:
            _, relative = _repo_relative(repo, raw)
        except PolicyViolation as exc:
            return False, str(exc)
        if is_sensitive_path(relative):
            return False, f"Credential or secret-bearing path is protected: {relative}"
        if name in MUTATION_TOOLS:
            if not mutates:
                return False, f"Route is read-only; {name} is denied."
            if is_protected_authority_path(relative):
                return False, f"FounderOS authority/control-plane path is protected: {relative}"
            if not within_scopes(relative, scopes):
                return False, f"Write path is outside Founder-approved scopes: {relative}"
        return True, "allowed"

    if name == "NotebookEdit":
        raw = str(tool_input.get("notebook_path") or tool_input.get("file_path") or "")
        try:
            _, relative = _repo_relative(repo, raw)
        except PolicyViolation as exc:
            return False, str(exc)
        if not mutates:
            return False, "Route is read-only; NotebookEdit is denied."
        if is_sensitive_path(relative) or is_protected_authority_path(relative):
            return False, f"Protected notebook path: {relative}"
        if not within_scopes(relative, scopes):
            return False, f"Notebook path is outside Founder-approved scopes: {relative}"
        return True, "allowed"

    if name == "MultiEdit":
        edits = tool_input.get("edits")
        if not isinstance(edits, list) or not edits:
            return False, "MultiEdit requires a non-empty edits array."
        if not mutates:
            return False, "Route is read-only; MultiEdit is denied."
        for edit in edits:
            if not isinstance(edit, dict):
                return False, "MultiEdit entries must be objects."
            raw = str(edit.get("file_path") or edit.get("path") or "")
            try:
                _, relative = _repo_relative(repo, raw)
            except PolicyViolation as exc:
                return False, str(exc)
            if is_sensitive_path(relative) or is_protected_authority_path(relative):
                return False, f"Protected MultiEdit path: {relative}"
            if not within_scopes(relative, scopes):
                return False, f"MultiEdit path is outside Founder-approved scopes: {relative}"
        return True, "allowed"

    if name == "Grep":
        raw = str(tool_input.get("path") or "")
        try:
            target, relative = _repo_relative(repo, raw, default_to_repo=True)
        except PolicyViolation as exc:
            return False, str(exc)
        if relative and is_sensitive_path(relative):
            return False, f"Credential or secret-bearing search path is protected: {relative}"
        glob = str(tool_input.get("glob") or "")
        if _target_has_sensitive_files(target) and not _glob_is_safe_for_secrets(glob):
            return False, "Grep over a tree containing secrets requires a file-type glob that cannot match secret files."
        return True, "allowed"

    if name == "Glob":
        raw = str(tool_input.get("path") or "")
        try:
            _repo_relative(repo, raw, default_to_repo=True)
        except PolicyViolation as exc:
            return False, str(exc)
        pattern = str(tool_input.get("pattern") or "")
        if any(marker in pattern.lower() for marker in (".env", "*.pem", "*.key", "id_rsa", "credential", "secret")):
            return False, "Glob pattern explicitly targets credential-bearing paths."
        return True, "allowed"

    if name in MUTATION_TOOLS and not mutates:
        return False, f"Route is read-only; {name} is denied."
    return True, "allowed"


def validate_verification_command(command: str) -> list[str]:
    text = command.strip()
    if not text:
        raise PolicyViolation("Verification command cannot be empty.")
    if SHELL_CONTROL.search(text):
        raise PolicyViolation(
            "Verification commands must be single direct commands. Supply multiple --verify flags "
            "instead of shell chaining, pipes, redirects, substitutions, or separators."
        )
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            raise PolicyViolation(f"Destructive or authority-changing verification command denied: {command}")
    try:
        argv = shlex.split(text, posix=os.name != "nt")
    except ValueError as exc:
        raise PolicyViolation(f"Invalid verification command quoting: {exc}") from exc
    if not argv:
        raise PolicyViolation("Verification command cannot be empty.")

    executable_name = Path(argv[0]).name.lower()
    is_python_launcher = bool(PYTHON_LAUNCHER_NAME.fullmatch(executable_name))
    if STRICT_VERIFICATION_ALLOWLIST and not (
        is_python_launcher or executable_name in VERIFICATION_EXECUTABLE_ALLOWLIST
    ):
        raise PolicyViolation(
            f"Executable is outside the strict verification allowlist "
            f"(python, python3, python3.<minor>[t], py, git, node, npm, pnpm, yarn, bun): {argv[0]}"
        )
    if executable_name in NETWORK_OR_AUTHORITY_EXECUTABLES:
        raise PolicyViolation(f"Network, deployment, database, or authority CLI is not a verification command: {argv[0]}")
    if executable_name in SHELL_EXECUTABLES:
        raise PolicyViolation("Shell interpreters are blocked for deterministic verification; use a direct tool or package script.")

    if executable_name == "git":
        if len(argv) < 2 or argv[1].lower() not in READ_ONLY_GIT_SUBCOMMANDS:
            raise PolicyViolation("Only read-only Git subcommands are permitted as verification commands.")
        if argv[1].lower() == "branch" and any(item in argv[2:] for item in ("-d", "-D", "-m", "-M", "-c", "-C", "--delete", "--move", "--copy")):
            raise PolicyViolation("Git branch mutation is not verification.")

    if executable_name in {"npm", "pnpm", "yarn", "bun"}:
        if len(argv) < 2:
            raise PolicyViolation("Package-manager verification requires an explicit subcommand.")
        # R6-01: global options are rejected outright instead of parsed. A
        # mutation subcommand must never hide behind flags
        # (e.g. `npm --prefix /tmp install`).
        if argv[1].startswith("-"):
            raise PolicyViolation(
                f"Package-manager global options are not deterministic verification commands: {argv[1]}"
            )
        first = argv[1].lower()
        # P0 positive grammar: only exact approved subcommand shapes survive.
        # Everything else — config, cache, rebuild, init, publish, store, pm,
        # create, install, and any unrecognized subcommand — is denied.
        if first not in PACKAGE_MANAGER_VERIFICATION_SUBCOMMANDS:
            raise PolicyViolation(
                f"Package-manager subcommand is not an approved verification form: {first}"
            )
        if first == "run":
            if len(argv) < 3:
                raise PolicyViolation("Package-manager `run` requires an explicit script name.")
            script = argv[2].lower()
            if script not in PACKAGE_MANAGER_VERIFICATION_SCRIPTS:
                raise PolicyViolation(
                    f"Package-manager script is not an approved verification form: {script}"
                )
        elif first == "test":
            # `npm test` / `pnpm test` / `yarn test` / `bun test` — the
            # bare `test` subcommand is an approved verification form.
            pass

    if executable_name in {"npx", "pnpx", "bunx"}:
        raise PolicyViolation("On-demand package execution is blocked; use a pinned package script instead.")

    if is_python_launcher or executable_name == "py":
        # R6-01: Python command shapes are parsed explicitly so the executed
        # module/script is identified deterministically. Only three shapes
        # survive: informational flags alone, `-m <allowlisted module> ...`,
        # or `<explicitly-named verification script> ...`. Anything else —
        # bare invocation, unknown interpreter options, or option ordering
        # that could shift the execution target — is denied.
        tokens = argv[1:]
        lowered = [item.lower() for item in tokens]
        if "-c" in lowered or "--command" in lowered:
            raise PolicyViolation("Inline Python execution is blocked for deterministic verification.")
        if not tokens:
            raise PolicyViolation(
                "Bare Python invocation is non-deterministic; name an allowlisted module or verification script."
            )
        if tokens[0] == "-m":
            if len(tokens) < 2 or tokens[1].startswith("-"):
                raise PolicyViolation("Python -m requires an explicit module name.")
            module = tokens[1].lower()
            if module not in SAFE_PYTHON_MODULES:
                raise PolicyViolation(f"Python module is outside the verification allowlist: {module}")
        elif tokens[0].startswith("-"):
            unknown = [token for token in tokens if token not in PYTHON_INFORMATIONAL_FLAGS]
            if unknown:
                raise PolicyViolation(
                    f"Unsupported Python interpreter option for deterministic verification: {unknown[0]}"
                )
        else:
            script = tokens[0].replace("\\", "/").lower()
            if not re.search(r"(?:test|check|verify|lint|audit)", script):
                raise PolicyViolation("Python verification scripts must be explicitly named test/check/verify/lint/audit.")

    if executable_name == "node":
        if len(argv) < 2 or argv[1] not in {"--check", "-c"}:
            raise PolicyViolation("Direct Node execution is blocked; use `node --check` or a pinned package script.")

    executable = shutil.which(argv[0])
    if not executable:
        raise PolicyViolation(f"Verification executable was not found on PATH: {argv[0]}")
    argv[0] = executable
    return argv
