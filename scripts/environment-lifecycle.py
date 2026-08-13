#!/usr/bin/env python3
"""Deterministic install, update, status, doctor, uninstall, and restore lifecycle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
SERIES = f"v{VERSION.rsplit('.', 1)[0]}"
STATE_REL = Path(".claude/INSTALLATION_STATE.json")
RECORD_REL = Path(".claude/INSTALLATION_RECORD.md")
MARKER_BEGIN = "# >>> MAD Ventures Claude Code Environment >>>"
MARKER_END = "# <<< MAD Ventures Claude Code Environment <<<"
PACKAGE_DIRS = ("agents", "skills", "hooks", "rules", "cloud")
LEGACY_WORKFLOWS = tuple(
    f"founder-{name}.js"
    for name in (
        "plan", "build", "verify", "tier2-evidence", "release-readiness",
        "repository-audit", "security-audit", "ui-review", "fix-until-green",
        "changed-files-review", "docs-drift", "performance-audit",
        "test-gap-analysis", "incident-root-cause",
    )
)
LEGACY_HOOKS = (
    "guard-authority-paths.mjs", "guard-control-plane.mjs", "guard-destructive.mjs",
    "guard-readonly-sql.mjs", "guard-secret-paths.mjs", "check-frontmatter.mjs",
    "guard-independent-review-shell.mjs", "hook-utils.mjs",
)
LEGACY_HOOK_COMMANDS = (
    "guard-authority-paths", "guard-control-plane", "guard-destructive",
    "guard-readonly-sql", "guard-secret-paths", "check-frontmatter",
    "guard-independent-review-shell", "hook-utils",
)
REQUIRED_FILES = (
    "project/.claude/settings.json", "project/.claude/FOUNDEROS.md",
    "project/.claude/MODEL_REGISTRY.md", "python-control-plane/bin/madclaude.py",
    "python-control-plane/run-tests.py", "project/.claude/hooks/hook-adapter.mjs",
)


class LifecycleError(RuntimeError):
    pass


def log(message: str) -> None:
    print(f"[MAD-ENV] {message}")


def snapshot_path(project: Path, operation: str) -> Path:
    """Return the deterministic pre-change snapshot path used by `snapshot()`.

    Pure computation only; does not create any directory or file. Matches the
    `<timestamp>-<operation>` convention produced by the real apply path so the
    dry-run plan describes the exact path `apply` would write.
    """
    backups = project / ".claude-backups"
    stamp = timestamp()
    return backups / f"{stamp}-{operation}"


def plan_destinations(args: argparse.Namespace, operation: str, project: Path) -> dict[str, Any]:
    """Derive the same destinations the real apply path (install_project) would write.

    Read-only: computes paths from the same inputs/flags as the apply path so the
    dry-run plan never diverges from what `apply` actually does.
    """
    claude = project / ".claude"
    destinations = [str(claude)]
    # Primary MCP surface; the apply path falls back to a versioned name only if
    # the primary already exists on disk.
    mcp_primary = project / ".mcp.example.json"
    mcp_alt = project / f".mcp.founderos-{SERIES}.example.json"
    destinations.append(str(mcp_alt if mcp_primary.is_file() else mcp_primary))
    layers = ["repository (.claude)"]
    if getattr(args, "workspace", None):
        workspace = Path(args.workspace)
        destinations.append(str(workspace / ".claude"))
        layers.append("workspace context")
    if getattr(args, "install_global", False):
        home = Path(os.environ.get("HOME")).expanduser().resolve() if os.environ.get("HOME") else Path.home()
        destinations.append(str(home / ".claude"))
        destinations.append(str(home / ".claude" / "MADVENTURES.md"))
        destinations.append(str(home / ".claude" / "madventures-statusline.mjs"))
        destinations.append(str(home / ".claude" / "examples" / f"madventures-{SERIES}"))
        layers.append("global managed baseline")
    if getattr(args, "install_managed", False):
        managed_dir = Path(args.managed_dir).expanduser() if args.managed_dir else default_managed_dir()
        destinations.append(str(managed_dir.resolve() / "managed-settings.d" / "20-madventures-baseline.json"))
        layers.append("managed hard-deny baseline")
    if getattr(args, "install_python_control_plane", False):
        install_home = Path(os.environ.get("MADCLAUDE_HOME", str(Path.home() / ".madclaude"))).expanduser().resolve()
        dest = install_home / "app"
        destinations.append(str(dest / "bin" / "madclaude.py"))
        destinations.append(str(dest / "src" / "madclaude"))
        destinations.append(str(dest / "schemas"))
        wrapper = Path(os.environ.get("MADCLAUDE_BIN_DIR", str(Path.home() / ".local" / "bin"))).expanduser().resolve()
        wrapper_name = "madclaude.cmd" if os.name == "nt" else "madclaude"
        destinations.append(str(wrapper / wrapper_name))
        layers.append("python control-plane engine")
    return {"layers": layers, "destinations": destinations}


def build_plan(
    *,
    operation: str,
    project: Path,
    profile: str,
    args: argparse.Namespace,
    backup: Path,
    validation: str,
) -> dict[str, Any]:
    """Build a read-only, human-readable lifecycle plan for a dry run.

    No filesystem mutation occurs; this only describes what `apply` would do,
    using the exact destination logic from install_project.
    """
    derived = plan_destinations(args, operation, project)
    managed_components = [
        "agents", "skills", "hooks (adapter + statusline)", "rules", "cloud",
        "control-plane (Python engine)", "FOUNDEROS.md", "MODEL_REGISTRY.md",
        "profiles", "examples", "settings.json", "PROJECT_PROFILE.md",
    ]
    if getattr(args, "install_python_control_plane", False):
        managed_components.append("python-control-plane engine under ~/.madclaude/app/bin")
    return {
        "status": "dry-run",
        "operation": operation,
        "project": str(project),
        "profile": profile,
        "affectedLayers": derived["layers"],
        "destinations": derived["destinations"],
        "managedComponents": managed_components,
        "backupIntent": str(backup),
        "validationMode": validation,
        "settingsStrategy": "replace" if getattr(args, "force_settings", False) else "deterministic-merge",
        "writesOccur": False,
        "confirmation": "NO writes will be performed (dry-run).",
    }


def render_plan(payload: dict[str, Any]) -> str:
    """Render a dry-run plan for human reading."""
    lines = [
        f"MAD Ventures lifecycle dry-run: {payload.get('operation')}",
        f"  Target project : {payload.get('project')}",
        f"  Profile         : {payload.get('profile')}",
        f"  Affected layers : {', '.join(payload.get('affectedLayers', []))}",
        f"  Destinations    : {', '.join(payload.get('destinations', []))}",
        f"  Managed files   : {', '.join(payload.get('managedComponents', []))}",
        f"  Settings        : {payload.get('settingsStrategy')}",
        f"  Backup intent   : {payload.get('backupIntent')}",
        f"  Validation mode : {payload.get('validationMode')}",
        f"  Writes          : {'NONE (dry-run)' if not payload.get('writesOccur') else 'yes'}",
        f"  Confirmation    : {payload.get('confirmation')}",
    ]
    return "\n".join(lines)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def validate_project_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == Path(resolved.anchor) or resolved == Path.home().resolve():
        raise LifecycleError(f"refusing broad lifecycle target: {resolved}")
    if not resolved.is_dir():
        raise LifecycleError(f"project directory does not exist: {resolved}")
    claude = resolved / ".claude"
    if claude.is_symlink():
        raise LifecycleError("refusing symlinked .claude lifecycle target")
    for name in (*PACKAGE_DIRS, "workflows", "control-plane"):
        if (claude / name).is_symlink():
            raise LifecycleError(f"refusing symlinked managed directory: .claude/{name}")
    return resolved


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source: Path, destination: Path) -> set[Path]:
    copied: set[Path] = set()
    if not source.is_dir():
        return copied
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        copy_file(path, target)
        copied.add(target)
    return copied


def command_version(command: str, *args: str) -> tuple[bool, str]:
    executable = shutil.which(command)
    if not executable:
        return False, "not found"
    proc = subprocess.run([executable, *args], capture_output=True, text=True)
    value = (proc.stdout or proc.stderr).strip().splitlines()
    return proc.returncode == 0, value[0] if value else f"exit {proc.returncode}"


def major_version(value: str) -> int | None:
    match = re.search(r"(?:^|\s|v)(\d+)(?:\.|$)", value)
    return int(match.group(1)) if match else None


def runtime_status() -> dict[str, dict[str, Any]]:
    python_ok = sys.version_info >= (3, 10)
    node_ok, node_value = command_version("node", "--version")
    git_ok, git_value = command_version("git", "--version")
    claude_ok, claude_value = command_version("claude", "--version")
    node_major = major_version(node_value) if node_ok else None
    claude_match = re.search(r"(\d+)\.(\d+)\.(\d+)", claude_value) if claude_ok else None
    claude_supported = bool(claude_match and tuple(map(int, claude_match.groups())) >= (2, 1, 223))
    return {
        "python": {"ok": python_ok, "version": ".".join(map(str, sys.version_info[:3])), "required": ">=3.10"},
        "node": {"ok": node_ok and node_major is not None and node_major >= 18, "version": node_value, "required": ">=18"},
        "git": {"ok": git_ok, "version": git_value, "required": True},
        "claude": {"ok": claude_ok and claude_supported, "version": claude_value, "required": ">=2.1.223"},
    }


def require_runtime() -> dict[str, dict[str, Any]]:
    result = runtime_status()
    failed = [name for name, item in result.items() if not item["ok"]]
    if failed:
        details = ", ".join(f"{name} ({result[name]['version']}; required {result[name]['required']})" for name in failed)
        raise LifecycleError(f"required runtime preflight failed: {details}")
    return result


def package_identity() -> str:
    manifest = ROOT / "MANIFEST.json"
    return sha256_file(manifest) if manifest.is_file() else hashlib.sha256(VERSION.encode()).hexdigest()


def preflight_package() -> None:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).is_file()]
    missing.extend(f"project/.claude/{name}/" for name in PACKAGE_DIRS if not (ROOT / "project/.claude" / name).is_dir())
    if missing:
        raise LifecycleError(f"package preflight failed; missing: {', '.join(missing)}")
    settings = json.loads((ROOT / "project/.claude/settings.json").read_text(encoding="utf-8"))
    serialized = json.dumps(settings)
    if "hook-adapter.mjs" not in serialized:
        raise LifecycleError("package settings do not register the Python hook adapter")


def run_package_validation(full: bool) -> None:
    script = ROOT / "scripts" / ("validate-config.py" if full else "quick-validate.py")
    command = [sys.executable, str(script)]
    if full:
        command.append("--no-report")
    subprocess.run(command, cwd=ROOT, check=True)


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def snapshot(project: Path, label: str = "install") -> Path:
    backup = project / ".claude-backups" / f"{timestamp()}-{label}"
    backup.mkdir(parents=True)
    targets = [Path(".claude"), Path(".gitignore"), Path(".mcp.example.json")]
    targets.extend(path.relative_to(project) for path in sorted(project.glob(".mcp.founderos-v*.example.json")))
    metadata: dict[str, Any] = {"project": str(project), "createdAt": timestamp(), "targets": {}}
    for relative in targets:
        source = project / relative
        metadata["targets"][relative.as_posix()] = {"existed": source.exists() or source.is_symlink()}
        if source.is_dir():
            shutil.copytree(source, backup / relative, symlinks=True)
        elif source.exists() or source.is_symlink():
            copy_file(source, backup / relative)
    write_json(backup / "backup-state.json", metadata)
    return backup


def restore_snapshot(project: Path, backup: Path) -> None:
    metadata_path = backup / "backup-state.json"
    if not metadata_path.is_file():
        raise LifecycleError(f"backup metadata missing: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if Path(metadata.get("project", "")).resolve() != project.resolve():
        raise LifecycleError("backup belongs to a different project")
    recorded = {Path(value) for value in metadata["targets"]}
    current_mcp = {path.relative_to(project) for path in project.glob(".mcp.founderos-v*.example.json")}
    for relative in sorted(recorded | current_mcp, key=lambda item: len(item.parts), reverse=True):
        target = project / relative
        if target.exists() or target.is_symlink():
            remove_path(target)
        source = backup / relative
        if source.is_dir():
            shutil.copytree(source, target, symlinks=True)
        elif source.exists() or source.is_symlink():
            copy_file(source, target)


def load_state(project: Path) -> dict[str, Any] | None:
    path = project / STATE_REL
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError(f"invalid installation state: {exc}") from exc


def choose_profile(project: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    name = project.name.lower()
    if (project / "04-agents/role-registry.md").is_file() and (project / "00-system/scripts/path-audit.sh").is_file():
        return "doctrine"
    if "founder-os-console" in name:
        return "console"
    if "founder-os-telegram" in name or "founderos-runtime" in name:
        return "runtime"
    return "generic"


def merge_unique(left: list[Any], right: list[Any]) -> list[Any]:
    result = list(left)
    for value in right:
        if value not in result:
            result.append(value)
    return result


def without_legacy_hooks(value: Any) -> Any:
    if isinstance(value, list):
        result = []
        for item in value:
            cleaned = without_legacy_hooks(item)
            if isinstance(cleaned, dict):
                command = str(cleaned.get("command", ""))
                if any(marker in command for marker in LEGACY_HOOK_COMMANDS):
                    continue
                hooks = cleaned.get("hooks")
                if isinstance(hooks, list) and not hooks:
                    continue
            result.append(cleaned)
        return result
    if isinstance(value, dict):
        return {key: without_legacy_hooks(item) for key, item in value.items()}
    return value


def merge_settings(existing: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    result = without_legacy_hooks(existing)
    for key, value in package.items():
        if key == "hooks":
            current = result.setdefault("hooks", {})
            for event, entries in value.items():
                current[event] = merge_unique(current.get(event, []), entries)
        elif key == "permissions":
            current = result.setdefault("permissions", {})
            for permission_key, permission_value in value.items():
                if isinstance(permission_value, list):
                    current[permission_key] = merge_unique(current.get(permission_key, []), permission_value)
                elif permission_key not in current:
                    current[permission_key] = permission_value
        elif key == "env":
            current = result.setdefault("env", {})
            for env_key, env_value in value.items():
                current.setdefault(env_key, env_value)
        elif key not in result:
            result[key] = value
    return result


def add_import(path: Path, imported: str, heading: str) -> None:
    line = f"@{imported}"
    if path.is_file() and any(value.strip() == line for value in path.read_text(encoding="utf-8").splitlines()):
        return
    content = path.read_text(encoding="utf-8") if path.is_file() else f"# {heading}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + f"\n\n<!-- MAD Ventures Claude Code Operating Environment -->\n{line}\n", encoding="utf-8")


def update_marked_block(path: Path, fragment: str) -> None:
    content = path.read_text(encoding="utf-8") if path.is_file() else ""
    pattern = re.compile(
        r"\n?# >>> MAD Ventures Claude Code Environment(?: v[0-9.]+)? >>>.*?"
        r"# <<< MAD Ventures Claude Code Environment <<<\n?",
        re.DOTALL,
    )
    content = pattern.sub("\n", content).rstrip()
    path.write_text(content + f"\n\n{MARKER_BEGIN}\n{fragment.rstrip()}\n{MARKER_END}\n", encoding="utf-8")


def retire_legacy(project: Path) -> None:
    for name in LEGACY_WORKFLOWS:
        path = project / ".claude/workflows" / name
        if path.exists():
            path.unlink()
    for name in LEGACY_HOOKS:
        path = project / ".claude/hooks" / name
        if path.exists():
            path.unlink()


def check_invariants(project: Path) -> list[str]:
    failures: list[str] = []
    workflows = sorted((project / ".claude/workflows").glob("*.js"))
    if workflows:
        failures.append("executable JavaScript workflows remain: " + ", ".join(path.name for path in workflows))
    scripts = sorted(
        path.name for path in (project / ".claude/hooks").iterdir()
        if path.is_file() and path.suffix in {".js", ".mjs"}
    ) if (project / ".claude/hooks").is_dir() else []
    if scripts != ["hook-adapter.mjs", "madventures-statusline.mjs"]:
        failures.append(f"expected the two governed JavaScript hooks, found {scripts}")
    settings_path = project / ".claude/settings.json"
    try:
        settings_text = settings_path.read_text(encoding="utf-8")
        json.loads(settings_text)
        if "hook-adapter.mjs" not in settings_text:
            failures.append("active settings do not register hook-adapter.mjs")
        if any(marker in settings_text for marker in LEGACY_HOOK_COMMANDS):
            failures.append("active settings still register a legacy hook")
    except (OSError, json.JSONDecodeError) as exc:
        failures.append(f"active settings are invalid: {exc}")
    return failures


def run_installed_checks(project: Path, *, full: bool = True) -> None:
    failures = check_invariants(project)
    if failures:
        raise LifecycleError("; ".join(failures))
    adapter = project / ".claude/hooks/hook-adapter.mjs"
    subprocess.run([shutil.which("node") or "node", "--check", str(adapter)], check=True)
    control = project / ".claude/control-plane/bin/madclaude.py"
    # -I: isolated mode (ignore PYTHONPATH, user-site, and PYTHON* env vars
    # from the host environment — prevents the Hermes Python 3.11 venv or any
    # other host Python from contaminating the installed control-plane run).
    # -B: don't write .pyc files.
    subprocess.run([sys.executable, "-I", "-B", str(control), "--version"], cwd=project, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "-I", "-B", str(control), "routes", "--json"], cwd=project, check=True, stdout=subprocess.DEVNULL)
    if full:
        # Sanitized environment: remove PYTHONPATH, PYTHONHOME, VIRTUAL_ENV,
        # and PIP_TARGET so the child process inherits only the host PATH and
        # OS-level vars, not Python-environment overrides.  -I on the
        # interpreter also prevents PYTHON* env vars and user-site from
        # loading foreign packages (pydantic_core, mcp, etc.) from the wrong
        # Python installation.  MCP SDK verification is the responsibility of
        # the isolated MCP release-venv target gate, not this installed-copy
        # smoke check.
        run_tests = project / ".claude/control-plane/run-tests.py"
        clean_env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PIP_TARGET")
        }
        clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
        subprocess.run(
            [sys.executable, "-I", "-B", str(run_tests), "--installed"],
            cwd=project,
            check=True,
            env=clean_env,
        )


def installed_files(paths: set[Path], project: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(paths):
        if path.is_file():
            result[path.relative_to(project).as_posix()] = sha256_file(path)
    return result


def install_workspace(workspace: Path) -> dict[str, Any]:
    workspace = validate_project_path(workspace)
    source = ROOT / "workspace/.claude/MADVENTURES_WORKSPACE.md"
    if not source.is_file():
        raise LifecycleError("workspace doctrine asset is missing")
    destination = workspace / ".claude/MADVENTURES_WORKSPACE.md"
    copy_file(source, destination)
    add_import(workspace / ".claude/CLAUDE.md", "MADVENTURES_WORKSPACE.md", "MAD Ventures workspace instructions")
    state = {"version": VERSION, "packageIdentity": package_identity(), "installedAt": timestamp(), "managedFiles": {destination.relative_to(workspace).as_posix(): sha256_file(destination)}}
    write_json(workspace / ".claude/WORKSPACE_INSTALLATION_STATE.json", state)
    return state


def install_global(home: Path) -> dict[str, Any]:
    claude_home = home / ".claude"
    examples = claude_home / "examples" / f"madventures-{SERIES}"
    doctrine = claude_home / "MADVENTURES.md"
    statusline = claude_home / "madventures-statusline.mjs"
    copy_file(ROOT / "global/CLAUDE.md.append", doctrine)
    copy_file(ROOT / "global/madventures-statusline.mjs", statusline)
    copy_file(ROOT / "global/settings.json.fragment", examples / "settings.json.fragment")
    copy_file(ROOT / "global/claude.json.fragment", examples / "claude.json.fragment")
    add_import(claude_home / "CLAUDE.md", "MADVENTURES.md", "User Claude Code instructions")
    paths = {doctrine, statusline, examples / "settings.json.fragment", examples / "claude.json.fragment"}
    state = {"version": VERSION, "packageIdentity": package_identity(), "installedAt": timestamp(), "managedFiles": {path.relative_to(home).as_posix(): sha256_file(path) for path in paths}}
    write_json(claude_home / "MADVENTURES_INSTALLATION_STATE.json", state)
    return state


def install_managed(managed_dir: Path) -> Path:
    destination = managed_dir.resolve() / "managed-settings.d/20-madventures-baseline.json"
    copy_file(ROOT / "managed/20-madventures-baseline.json", destination)
    return destination


def install_project(args: argparse.Namespace, operation: str) -> dict[str, Any]:
    project = validate_project_path(Path(args.project))
    preflight_package()
    runtime = require_runtime()
    if not args.skip_validation:
        run_package_validation(args.full_validation)
    old_state = load_state(project)
    if operation == "update" and old_state is None and not (project / ".claude").is_dir():
        raise LifecycleError("update requires an installed or legacy .claude environment; use install")
    profile = choose_profile(project, args.profile)
    if args.dry_run:
        return build_plan(
            operation=operation,
            project=project,
            profile=profile,
            args=args,
            backup=snapshot_path(project, operation),
            validation="exhaustive" if args.full_validation else ("skipped" if args.skip_validation else "default"),
        )

    backup = snapshot(project, operation)
    workspace_backup: Path | None = None
    global_backup: Path | None = None
    managed_destination: Path | None = None
    managed_previous: Path | None = None
    workspace = validate_project_path(Path(args.workspace)) if args.workspace else None
    home_value = os.environ.get("HOME")
    if args.install_global and not home_value:
        raise LifecycleError("HOME is required for --install-global")
    home = Path(home_value).expanduser().resolve() if args.install_global and home_value else None
    if workspace:
        workspace_backup = snapshot(workspace, "workspace")
    if home:
        global_backup = snapshot(home, "global")
    if args.install_managed:
        managed_dir = Path(args.managed_dir).expanduser() if args.managed_dir else default_managed_dir()
        managed_destination = managed_dir.resolve() / "managed-settings.d/20-madventures-baseline.json"
        if managed_destination.is_file():
            managed_previous = backup / "managed-baseline.previous.json"
            copy_file(managed_destination, managed_previous)
    baseline = old_state.get("baselineBackup") if old_state else str(backup)
    managed: set[Path] = set()

    try:
        claude = project / ".claude"
        claude.mkdir(parents=True, exist_ok=True)
        retire_legacy(project)
        for name in PACKAGE_DIRS:
            managed |= copy_tree(ROOT / "project/.claude" / name, claude / name)
        (claude / "workflows").mkdir(parents=True, exist_ok=True)

        control = claude / "control-plane"
        if control.exists():
            remove_path(control)
        managed |= copy_tree(ROOT / "python-control-plane", control)
        for cache in control.rglob("__pycache__"):
            if cache.is_dir():
                shutil.rmtree(cache)

        for name in ("FOUNDEROS.md", "MODEL_REGISTRY.md"):
            destination = claude / name
            copy_file(ROOT / "project/.claude" / name, destination)
            managed.add(destination)
        managed |= copy_tree(ROOT / "project/profiles", claude / "profiles")
        managed |= copy_tree(ROOT / "examples", claude / "examples")
        destination = claude / "settings.local.example.json"
        copy_file(ROOT / "project/settings.local.example.json", destination)
        managed.add(destination)

        profile_destination = claude / "PROJECT_PROFILE.md"
        if not profile_destination.exists():
            profile_source = ROOT / "project/.claude/PROJECT_PROFILE.md"
            if profile != "generic":
                profile_source = ROOT / "project/profiles" / f"founderos-{profile}.PROJECT_PROFILE.md"
            copy_file(profile_source, profile_destination)
            managed.add(profile_destination)

        add_import(claude / "CLAUDE.md", "FOUNDEROS.md", "Repository Claude Code instructions")
        managed.add(claude / "CLAUDE.md")
        package_settings = json.loads((ROOT / "project/.claude/settings.json").read_text(encoding="utf-8"))
        settings_path = claude / "settings.json"
        existing_settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.is_file() else {}
        if not isinstance(existing_settings, dict):
            raise LifecycleError("existing .claude/settings.json must contain a JSON object")
        settings = package_settings if args.force_settings else merge_settings(existing_settings, package_settings)
        write_json(settings_path, settings)
        managed.add(settings_path)
        candidate = claude / f"settings.founderos-{SERIES}.example.json"
        write_json(candidate, package_settings)
        managed.add(candidate)

        mcp_source = ROOT / "project/.mcp.example.json"
        mcp_destination = project / ".mcp.example.json"
        if mcp_destination.exists():
            mcp_destination = project / f".mcp.founderos-{SERIES}.example.json"
        copy_file(mcp_source, mcp_destination)
        managed.add(mcp_destination)
        gitignore = project / ".gitignore"
        update_marked_block(gitignore, (ROOT / "project/.gitignore.fragment").read_text(encoding="utf-8"))
        managed.add(gitignore)

        desired = {path.relative_to(project).as_posix() for path in managed}
        if old_state:
            for relative, expected_hash in old_state.get("managedFiles", {}).items():
                if relative in desired or relative in {STATE_REL.as_posix(), RECORD_REL.as_posix()}:
                    continue
                obsolete = project / relative
                if not obsolete.is_file():
                    continue
                if sha256_file(obsolete) != expected_hash:
                    raise LifecycleError(f"obsolete managed file changed locally; refusing removal: {relative}")
                obsolete.unlink()

        if os.environ.get("MADVENTURES_TEST_FAIL_AFTER_APPLY") == "1":
            raise LifecycleError("injected post-apply failure")
        run_installed_checks(project, full=os.environ.get("MADVENTURES_LIFECYCLE_TEST_FAST") != "1")

        state: dict[str, Any] = {
            "schemaVersion": 1,
            "status": "installed",
            "version": VERSION,
            "packageIdentity": package_identity(),
            "installedAt": timestamp(),
            "operation": operation,
            "profile": profile,
            "project": str(project),
            "backup": str(backup),
            "baselineBackup": baseline,
            "managedFiles": installed_files(managed, project),
            "settingsStrategy": "replace" if args.force_settings else "deterministic-merge",
            "runtime": runtime,
            "workspace": str(workspace) if workspace else None,
            "globalInstalled": bool(home),
            "managedBaseline": None,
        }
        if workspace:
            install_workspace(workspace)
        if home:
            install_global(home)
        if args.install_managed:
            assert managed_destination is not None
            state["managedBaseline"] = str(install_managed(managed_destination.parents[1]))
        write_json(project / STATE_REL, state)
        record = (
            "# MAD Ventures Claude Code environment installation\n\n"
            f"- Package version: `{VERSION}`\n- Installed (UTC): `{state['installedAt']}`\n"
            f"- Operation: `{operation}`\n- Selected profile: `{profile}`\n"
            f"- Package identity: `{state['packageIdentity']}`\n- Backup: `{backup}`\n"
            f"- Settings strategy: `{state['settingsStrategy']}`\n"
            f"- Workspace layer: `{state['workspace'] or 'not configured'}`\n"
            f"- Managed global baseline: `{state['managedBaseline'] or 'not configured'}`\n\n"
            "Installation and readiness are separate. Run `./scripts/install.sh doctor <repo>` and inspect every reported layer and integration.\n"
        )
        (project / RECORD_REL).write_text(record, encoding="utf-8")
        state["managedFiles"][RECORD_REL.as_posix()] = sha256_file(project / RECORD_REL)
        write_json(project / STATE_REL, state)

        if args.install_python_control_plane or args.with_python_sdk:
            command = ["bash", str(ROOT / "scripts/install-python-control-plane.sh")]
            if args.with_python_sdk:
                command.append("--with-sdk")
            subprocess.run(command, check=True)
        return state
    except BaseException:
        restore_snapshot(project, backup)
        if workspace and workspace_backup:
            restore_snapshot(workspace, workspace_backup)
        if home and global_backup:
            restore_snapshot(home, global_backup)
        if managed_destination:
            if managed_previous and managed_previous.is_file():
                copy_file(managed_previous, managed_destination)
            elif managed_destination.exists():
                managed_destination.unlink()
        raise


def default_managed_dir() -> Path:
    if sys.platform == "darwin":
        return Path("/Library/Application Support/ClaudeCode")
    if os.name == "nt":
        return Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "ClaudeCode"
    return Path("/etc/claude-code")


def integration_status() -> dict[str, dict[str, str]]:
    codex = shutil.which("codex")
    hermes = shutil.which("hermes") or shutil.which("hermes-local-code")
    return {
        "fable": {"status": "unknown", "reason": "model entitlement must be verified in the active Claude account"},
        "grok": {"status": "unknown", "reason": "route/provider identity requires an approved live check"},
        "codex": {"status": "verified" if codex else "not_configured", "reason": codex or "codex executable not found"},
        "hermes": {"status": "verified" if hermes else "not_configured", "reason": hermes or "Hermes executable not found"},
    }


def scope_state_ok(root: Path, state_relative: Path) -> bool:
    state_path = root / state_relative
    if not state_path.is_file():
        return False
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("packageIdentity") != package_identity():
            return False
        for relative, expected in state.get("managedFiles", {}).items():
            path = root / relative
            if not path.is_file() or sha256_file(path) != expected:
                return False
        return True
    except (OSError, json.JSONDecodeError):
        return False


def has_import(path: Path, name: str) -> bool:
    return path.is_file() and any(line.strip() == f"@{name}" for line in path.read_text(encoding="utf-8").splitlines())


def status_project(args: argparse.Namespace, run_checks: bool = False) -> dict[str, Any]:
    project = validate_project_path(Path(args.project))
    state = load_state(project)
    runtime = runtime_status()
    failures = check_invariants(project) if (project / ".claude").is_dir() else [".claude environment is missing"]
    package_match = bool(state and state.get("packageIdentity") == package_identity())
    managed_path = Path(state["managedBaseline"]) if state and state.get("managedBaseline") else None
    managed_ok = bool(managed_path and managed_path.is_file() and sha256_file(managed_path) == sha256_file(ROOT / "managed/20-madventures-baseline.json"))
    workspace_path = Path(state["workspace"]) if state and state.get("workspace") else None
    workspace_ok = bool(
        workspace_path
        and scope_state_ok(workspace_path, Path(".claude/WORKSPACE_INSTALLATION_STATE.json"))
        and has_import(workspace_path / ".claude/CLAUDE.md", "MADVENTURES_WORKSPACE.md")
    )
    global_ok = bool(
        state and state.get("globalInstalled")
        and scope_state_ok(Path.home(), Path(".claude/MADVENTURES_INSTALLATION_STATE.json"))
        and has_import(Path.home() / ".claude/CLAUDE.md", "MADVENTURES.md")
    )
    checks_error: str | None = None
    if run_checks and not failures:
        try:
            run_installed_checks(project)
        except (LifecycleError, OSError, subprocess.CalledProcessError) as exc:
            checks_error = str(exc)
            failures.append(f"installed-copy checks failed: {exc}")
    result = {
        "installed": bool(state),
        "ready": bool(state) and package_match and not failures and all(item["ok"] for item in runtime.values()),
        "project": str(project),
        "version": state.get("version") if state else None,
        "packageIdentityMatches": package_match,
        "runtime": runtime,
        "invariants": {"ok": not failures, "failures": failures},
        "layers": {
            "managedGlobal": "verified" if managed_ok else "not_configured",
            "userGlobal": "verified" if global_ok else "not_configured",
            "workspace": "verified" if workspace_ok else "not_configured",
            "repository": "verified" if state and not failures else "failed",
            "task": "available" if (project / ".claude/control-plane/schemas/plan.schema.json").is_file() else "missing",
        },
        "integrations": integration_status(),
        "installedChecksError": checks_error,
    }
    return result


def uninstall_project(args: argparse.Namespace) -> dict[str, Any]:
    project = validate_project_path(Path(args.project))
    state = load_state(project)
    if not state:
        return {"status": "not-installed", "project": str(project), "managedFiles": 0}
    managed_files: dict[str, str] = state.get("managedFiles", {})
    drift = []
    for relative, expected in managed_files.items():
        path = project / relative
        if path.is_file() and sha256_file(path) != expected:
            drift.append(relative)
    if drift and not args.force:
        raise LifecycleError("managed files changed; refusing uninstall without --force: " + ", ".join(drift))
    if args.dry_run:
        return build_plan(
            operation="uninstall",
            project=project,
            profile="n/a",
            args=args,
            backup=snapshot_path(project, "pre-uninstall"),
            validation="none (dry-run inspects managed-file inventory)",
        )
    before = snapshot(project, "pre-uninstall")
    baseline = Path(state["baselineBackup"])
    metadata = json.loads((baseline / "backup-state.json").read_text(encoding="utf-8"))
    try:
        for relative in sorted(managed_files, key=lambda item: len(Path(item).parts), reverse=True):
            target = project / relative
            source = baseline / relative
            if target.exists() or target.is_symlink():
                remove_path(target)
            if source.is_file():
                copy_file(source, target)
        for directory in sorted((project / ".claude").rglob("*"), key=lambda path: len(path.parts), reverse=True):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        for relative in (STATE_REL, RECORD_REL):
            path = project / relative
            if path.exists():
                path.unlink()
        return {"status": "uninstalled", "project": str(project), "safetyBackup": str(before), "baseline": str(baseline), "baselineTargets": metadata["targets"]}
    except BaseException:
        restore_snapshot(project, before)
        raise


def restore_command(args: argparse.Namespace) -> dict[str, Any]:
    project = validate_project_path(Path(args.project))
    backup = Path(args.backup).expanduser().resolve()
    if project / ".claude-backups" not in backup.parents:
        raise LifecycleError("backup must be inside this project's .claude-backups directory")
    if args.dry_run:
        return build_plan(
            operation="restore",
            project=project,
            profile="n/a",
            args=args,
            backup=backup,
            validation="none (dry-run previews restore source)",
        )
    safety = snapshot(project, "pre-restore")
    try:
        restore_snapshot(project, backup)
        return {"status": "restored", "project": str(project), "backup": str(backup), "safetyBackup": str(safety)}
    except BaseException:
        restore_snapshot(project, safety)
        raise


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("project")
    parser.add_argument("--profile", choices=("auto", "generic", "doctrine", "runtime", "console"), default="auto")
    parser.add_argument("--force-settings", action="store_true")
    parser.add_argument("--workspace")
    parser.add_argument("--install-global", action="store_true")
    parser.add_argument("--install-managed", action="store_true")
    parser.add_argument("--managed-dir")
    parser.add_argument("--install-python-control-plane", action="store_true")
    parser.add_argument("--with-python-sdk", action="store_true")
    parser.add_argument("--full-validation", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    for name in ("install", "update"):
        add_common(sub.add_parser(name))
    for name in ("status", "doctor"):
        item = sub.add_parser(name)
        item.add_argument("project")
        item.add_argument("--json", action="store_true")
    uninstall = sub.add_parser("uninstall")
    uninstall.add_argument("project")
    uninstall.add_argument("--force", action="store_true")
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.add_argument("--json", action="store_true")
    restore = sub.add_parser("restore")
    restore.add_argument("project")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--dry-run", action="store_true")
    restore.add_argument("--json", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command in {"install", "update"}:
            payload = install_project(args, args.command)
        elif args.command == "status":
            payload = status_project(args)
        elif args.command == "doctor":
            payload = status_project(args, run_checks=True)
        elif args.command == "uninstall":
            payload = uninstall_project(args)
        else:
            payload = restore_command(args)
    except (LifecycleError, OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"[MAD-ENV] ERROR: {exc}", file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif payload.get("status") == "dry-run":
        print(render_plan(payload))
    else:
        status = payload.get("status") or ("ready" if payload.get("ready") else "not ready")
        log(f"{args.command}: {status}")
        if args.command in {"status", "doctor"}:
            log(json.dumps(payload, sort_keys=True))
    return 0 if payload.get("ready", True) or args.command not in {"status", "doctor"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
