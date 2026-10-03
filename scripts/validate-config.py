#!/usr/bin/env python3
"""Static validator for the MAD Ventures Claude Code Operating Environment."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 package floor
    tomllib = None  # type: ignore[assignment]
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = 'MADVentures-Claude-Code-Environment-v4.4.2'
PROJECT = ROOT / "project"
CLAUDE = PROJECT / ".claude"
PLUGIN = ROOT / "plugin" / "madventures-founderos"

EXPECTED = {
    "agents": 20,
    "skills": 31,
    "workflows": 0,
    "rules": 8,
    "hooks": 2,  # hook-adapter.mjs + madventures-statusline.mjs (env identity marker)
}

ALLOWED_AGENT_KEYS = {
    "name", "description", "tools", "disallowedTools", "model", "permissionMode",
    "maxTurns", "effort", "skills", "mcpServers", "hooks", "color", "memory",
    "background", "isolation",
}
PLUGIN_AGENT_KEYS = {
    "name", "description", "tools", "disallowedTools", "model", "maxTurns",
    "effort", "skills", "color", "memory", "background", "isolation",
}
ALLOWED_SKILL_KEYS = {
    "name", "description", "argument-hint", "disable-model-invocation", "user-invocable",
    "model", "context", "agent", "allowed-tools", "hooks", "when_to_use",
}
ALLOWED_TOOLS = {
    "Read", "Grep", "Glob", "Bash", "PowerShell", "Edit", "Write", "NotebookEdit",
    "WebFetch", "WebSearch", "Agent", "Skill", "AskUserQuestion", "Task", "TodoWrite",
}
ALLOWED_MODELS = {"default", "best", "fable", "sonnet", "opus", "haiku", "inherit"}
ALLOWED_EFFORT = {"low", "medium", "high", "xhigh", "max"}
ALLOWED_PERMISSION_MODES = {"default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions", "manual"}

KNOWN_SETTINGS_KEYS = {
    "$schema", "model", "fallbackModel", "effortLevel", "autoCompactEnabled",
    "autoMemoryEnabled", "fileCheckpointingEnabled", "fastModePerSessionOptIn",
    "workflowKeywordTriggerEnabled", "workflowSizeGuideline", "showClearContextOnPlanAccept",
    "skillListingBudgetFraction", "skillListingMaxDescChars", "env", "permissions", "hooks",
    "statusLine", "alwaysThinkingEnabled", "attribution", "sandbox", "mcpServers",
    "enabledPlugins", "disabledPlugins", "outputStyle", "cleanupPeriodDays", "respectGitignore",
    "modelOverrides", "availableModels", "enforceAvailableModels", "additionalDirectories",
    "advisorModel",
}
GLOBAL_ONLY_KEYS = {"teammateDefaultModel", "diffTool", "externalEditorContext", "autoConnectIde", "autoInstallIdeExtension"}


@dataclass
class Result:
    level: str
    message: str


results: list[Result] = []


def ok(message: str) -> None:
    results.append(Result("PASS", message))


def warn(message: str) -> None:
    results.append(Result("WARN", message))


def fail(message: str) -> None:
    results.append(Result("FAIL", message))


def frontmatter(text: str, path: Path) -> tuple[str, dict[str, str]] | None:
    match = re.match(r"^---\s*\n([\s\S]*?)\n---\s*\n", text)
    if not match:
        fail(f"{path.relative_to(ROOT)}: missing YAML frontmatter")
        return None
    raw = match.group(1)
    data: dict[str, str] = {}
    for line in raw.splitlines():
        if not line or line.startswith((" ", "\t", "#")):
            continue
        key_match = re.match(r"^([A-Za-z0-9_-]+):(?:\s*(.*))?$", line)
        if key_match:
            data[key_match.group(1)] = (key_match.group(2) or "").strip().strip('"').strip("'")
    return raw, data


def parse_tools(value: str) -> list[str]:
    return [part.strip() for part in value.strip("[]").split(",") if part.strip()]


def top_level_keys(raw: str) -> set[str]:
    return {
        match.group(1)
        for line in raw.splitlines()
        if (match := re.match(r"^([A-Za-z0-9_-]+):", line))
    }


def skill_refs(raw: str) -> list[str]:
    lines = raw.splitlines()
    refs: list[str] = []
    active = False
    for line in lines:
        if re.match(r"^skills:\s*$", line):
            active = True
            continue
        if active:
            m = re.match(r"^\s+-\s+([A-Za-z0-9_-]+)\s*$", line)
            if m:
                refs.append(m.group(1))
                continue
            if line and not line.startswith((" ", "\t")):
                active = False
    return refs


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        fail(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        return None


def validate_file_permission_rules(label: str, settings: object) -> None:
    """Reject path rules Claude Code accepts but never consults and pair secret reads with edit denial."""
    if not isinstance(settings, dict):
        return
    permissions = settings.get("permissions", {})
    if not isinstance(permissions, dict):
        return
    all_rules: list[str] = []
    for bucket in ("allow", "ask", "deny"):
        values = permissions.get(bucket, [])
        if isinstance(values, list):
            all_rules.extend(rule for rule in values if isinstance(rule, str))

    ineffective = sorted(
        rule for rule in all_rules
        if re.match(r"^(?:Write|NotebookEdit|Glob|MultiEdit)\(.+\)$", rule)
    )
    if ineffective:
        fail(f"{label}: ineffective path-scoped permission rule(s): {ineffective}; use Read(path) or Edit(path)")
    else:
        ok(f"{label}: no ineffective path-scoped Write/NotebookEdit/Glob/MultiEdit rules")

    deny = {
        rule for rule in permissions.get("deny", [])
        if isinstance(rule, str)
    }
    missing_edit: list[str] = []
    for rule in sorted(deny):
        match = re.fullmatch(r"Read\((.+)\)", rule)
        if match and f"Edit({match.group(1)})" not in deny:
            missing_edit.append(rule)
    if missing_edit:
        fail(f"{label}: Read deny path(s) missing matching Edit deny protection: {missing_edit}")
    elif any(rule.startswith("Read(") for rule in deny):
        ok(f"{label}: Read deny paths have matching Edit deny protection")


def validate_counts() -> None:
    actual = {
        "agents": len(list((CLAUDE / "agents").glob("*.md"))),
        "skills": len(list((CLAUDE / "skills").glob("*/SKILL.md"))),
        "workflows": len(list((CLAUDE / "workflows").glob("*.js"))),
        "rules": len(list((CLAUDE / "rules").glob("*.md"))),
        "hooks": len(list((CLAUDE / "hooks").glob("*.mjs"))),
    }
    for kind, expected in EXPECTED.items():
        if actual[kind] == expected:
            ok(f"expected {kind} count: {expected}")
        else:
            fail(f"expected {expected} {kind}, found {actual[kind]}")


def validate_agents() -> None:
    available_skills = {p.parent.name for p in (CLAUDE / "skills").glob("*/SKILL.md")}
    seen: set[str] = set()
    for path in sorted((CLAUDE / "agents").glob("*.md")):
        parsed = frontmatter(path.read_text(encoding="utf-8"), path)
        if not parsed:
            continue
        raw, data = parsed
        keys = top_level_keys(raw)
        unknown = keys - ALLOWED_AGENT_KEYS
        if unknown:
            fail(f"{path.relative_to(ROOT)}: unsupported agent frontmatter key(s): {sorted(unknown)}")
        for key in ("name", "description", "tools", "model", "permissionMode"):
            if not data.get(key):
                fail(f"{path.relative_to(ROOT)}: missing required '{key}'")
        name = data.get("name", "")
        if name != path.stem:
            fail(f"{path.relative_to(ROOT)}: name '{name}' does not match filename")
        if name in seen:
            fail(f"duplicate agent name: {name}")
        seen.add(name)
        if "permissions" in keys:
            fail(f"{path.relative_to(ROOT)}: unsupported permissions frontmatter")

        tools = parse_tools(data.get("tools", ""))
        for tool in tools:
            if "(" in tool or ")" in tool:
                fail(f"{path.relative_to(ROOT)}: granular pattern '{tool}' belongs in settings/hooks, not tools")
            elif tool not in ALLOWED_TOOLS and not tool.startswith("mcp__"):
                fail(f"{path.relative_to(ROOT)}: unknown tool name '{tool}'")

        model = data.get("model")
        if model and model not in ALLOWED_MODELS and not model.startswith("claude-"):
            fail(f"{path.relative_to(ROOT)}: unsupported model value '{model}'")
        effort = data.get("effort")
        if effort and effort not in ALLOWED_EFFORT:
            fail(f"{path.relative_to(ROOT)}: unsupported effort '{effort}'")
        if model == "haiku" and effort:
            fail(f"{path.relative_to(ROOT)}: Haiku must not declare an effort override")
        permission = data.get("permissionMode")
        if permission and permission not in ALLOWED_PERMISSION_MODES:
            fail(f"{path.relative_to(ROOT)}: unsupported permissionMode '{permission}'")

        for ref in skill_refs(raw):
            if ref not in available_skills:
                fail(f"{path.relative_to(ROOT)}: referenced skill '{ref}' does not exist")

        if name == "independent-reviewer":
            forbidden = {"Edit", "Write", "NotebookEdit", "Bash", "PowerShell", "Agent", "Skill"} & set(tools)
            if forbidden:
                fail(f"independent-reviewer exposes mutation/delegation tools: {sorted(forbidden)}")
            if permission != "plan":
                fail("independent-reviewer must use permissionMode plan")
        if name == "neon-reader" and not ("hook-adapter.mjs" in raw and " sql" in raw):
            fail("neon-reader is missing the Python read-only SQL policy")

    if len(seen) == EXPECTED["agents"]:
        ok("agent names, frontmatter, tools, routing, and special guards validated")


def validate_skills() -> None:
    seen: set[str] = set()
    for path in sorted((CLAUDE / "skills").glob("*/SKILL.md")):
        parsed = frontmatter(path.read_text(encoding="utf-8"), path)
        if not parsed:
            continue
        raw, data = parsed
        keys = top_level_keys(raw)
        unknown = keys - ALLOWED_SKILL_KEYS
        if unknown:
            fail(f"{path.relative_to(ROOT)}: unsupported skill frontmatter key(s): {sorted(unknown)}")
        name = data.get("name", "")
        if not name or not data.get("description"):
            fail(f"{path.relative_to(ROOT)}: skill requires name and description")
        if name != path.parent.name:
            fail(f"{path.relative_to(ROOT)}: skill name '{name}' must match directory")
        if name in seen:
            fail(f"duplicate skill name: {name}")
        seen.add(name)
    if len(seen) == EXPECTED["skills"]:
        ok("skill names and frontmatter validated")


def validate_json_and_settings() -> None:
    json_paths = sorted(p for p in ROOT.rglob("*.json") if "MANIFEST.json" not in str(p))
    loaded = {path: load_json(path) for path in json_paths}
    if all(value is not None for value in loaded.values()):
        ok(f"all {len(json_paths)} JSON configuration files parse")

    settings_path = CLAUDE / "settings.json"
    settings = loaded.get(settings_path)
    if not isinstance(settings, dict):
        return
    unknown = set(settings) - KNOWN_SETTINGS_KEYS
    if unknown:
        fail(f"project settings contain unrecognized package-level keys: {sorted(unknown)}")
    misplaced = set(settings) & GLOBAL_ONLY_KEYS
    if misplaced:
        fail(f"global-only keys placed in settings.json: {sorted(misplaced)}")
    if settings.get("model") != "sonnet":
        warn("project default model is not sonnet")
    if settings.get("workflowSizeGuideline") != "small":
        fail("workflowSizeGuideline must be 'small' in the shared baseline")
    if settings.get("fileCheckpointingEnabled") is not True:
        fail("fileCheckpointingEnabled must be true")
    if settings.get("fastModePerSessionOptIn") is not True:
        fail("fastModePerSessionOptIn must be true")
    env = settings.get("env", {})
    if env.get("FOUNDEROS_LIVE_ACCESS_ENABLED") != "false":
        fail("FOUNDEROS_LIVE_ACCESS_ENABLED must default to string 'false'")

    permissions = settings.get("permissions", {})
    if permissions.get("disableBypassPermissionsMode") != "disable":
        fail("permissions.disableBypassPermissionsMode must be 'disable'")
    rules = permissions.get("allow", []) + permissions.get("ask", []) + permissions.get("deny", [])
    for rule in rules:
        if rule.startswith("WebFetch(") and not re.fullmatch(r"WebFetch\(domain:[A-Za-z0-9.-]+\)", rule):
            fail(f"invalid WebFetch permission syntax: {rule}")
    if "hook-adapter.mjs" in json.dumps(settings.get("hooks", {})) and " sql" in json.dumps(settings.get("hooks", {})):
        fail("read-only SQL guard must be scoped to neon-reader, not global settings")

    validate_file_permission_rules("project settings", settings)

    hook_text = json.dumps(settings.get("hooks", {}))
    refs = re.findall(r"\.claude/hooks/([A-Za-z0-9._-]+\.mjs)", hook_text)
    for ref in refs:
        if not (CLAUDE / "hooks" / ref).exists():
            fail(f"settings hook references missing file: {ref}")
    if refs:
        ok(f"project settings hook references resolve ({len(set(refs))} unique)")

    global_json = load_json(ROOT / "global" / "claude.json.fragment")
    if isinstance(global_json, dict):
        wrong = set(global_json) - GLOBAL_ONLY_KEYS
        if wrong:
            warn(f"global claude.json fragment contains non-global-only keys: {sorted(wrong)}")
        else:
            ok("~/.claude.json-only keys are separated into the global fragment")

    global_settings = loaded.get(ROOT / "global" / "settings.json.fragment")
    validate_file_permission_rules("global settings fragment", global_settings)

    review_profile = loaded.get(PROJECT / "profiles" / "review-only.settings.json")
    if not isinstance(review_profile, dict):
        fail("review-only settings profile is missing or invalid")
    else:
        review_permissions = review_profile.get("permissions", {})
        review_denies = set(review_permissions.get("deny", [])) if isinstance(review_permissions, dict) else set()
        required_tool_denials = {"Edit", "Write", "NotebookEdit", "Bash", "PowerShell"}
        if review_permissions.get("defaultMode") != "plan":
            fail("review-only settings profile must use defaultMode plan")
        if not required_tool_denials.issubset(review_denies):
            fail(f"review-only settings profile missing tool-level denials: {sorted(required_tool_denials - review_denies)}")
        if required_tool_denials.issubset(review_denies):
            ok("review-only settings profile combines plan mode with complete edit and shell denials")


def validate_doctrine() -> None:
    doctrine = (CLAUDE / "FOUNDEROS.md").read_text(encoding="utf-8")
    imports = {"@PROJECT_PROFILE.md", "@MODEL_REGISTRY.md"}
    missing_imports = sorted(item for item in imports if item not in doctrine)
    if missing_imports:
        fail(f"FOUNDEROS.md missing import(s): {missing_imports}")
    else:
        ok("FOUNDEROS.md imports the repository profile and model registry")
    required = [
        "cheap fan-out, expensive judgment",
        "Founder authorization is Founder-only",
        "Python is the only authoritative orchestration engine",
        "An advisor may improve in-session judgment, but it is not an independent reviewer",
        "proposed", "activated", "unknown",
    ]
    for phrase in required:
        if phrase not in doctrine:
            fail(f"FOUNDEROS.md missing doctrine phrase: {phrase}")


def validate_model_registry() -> None:
    registry_path = CLAUDE / "MODEL_REGISTRY.md"
    if not registry_path.exists():
        fail("MODEL_REGISTRY.md is missing")
        return
    text = registry_path.read_text(encoding="utf-8")
    required_ids = {
        "fable", "opus", "sonnet", "haiku", "grok-4.5",
        "hermes-local-code", "deepseek-v4-flash", "codex", "gemini", "cursor",
    }
    missing = sorted(identifier for identifier in required_ids if f"`{identifier}`" not in text)
    if missing:
        fail(f"MODEL_REGISTRY.md missing registered identity/identities: {missing}")
    required_phrases = [
        "Registration does not grant credentials",
        "The advisor remains part of the same session and is not Tier-2 independence",
        "cannot review its own work independently",
        "A model or connector not listed here is unregistered",
    ]
    for phrase in required_phrases:
        if phrase not in text:
            fail(f"MODEL_REGISTRY.md missing governance phrase: {phrase}")
    if not missing and all(phrase in text for phrase in required_phrases):
        ok("Founder-approved Claude and external model registry validated")

    advisor_path = PROJECT / "profiles" / "advisor-opus.settings.fragment.json"
    if not advisor_path.exists():
        fail("advisor-opus settings fragment is missing")
        return
    advisor = load_json(advisor_path)
    base = load_json(CLAUDE / "settings.json")
    if isinstance(advisor, dict) and advisor.get("advisorModel") == "opus":
        ok("opt-in Opus advisor profile validated")
    else:
        fail("advisor-opus profile must set advisorModel to 'opus'")
    if isinstance(base, dict) and "advisorModel" in base:
        fail("advisorModel must remain opt-in and absent from shared project settings")


def validate_markdown_links() -> None:
    missing: list[str] = []
    pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for path in sorted(ROOT.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            target = match.group(1).split("#", 1)[0].strip()
            if not target or "://" in target or target.startswith(("mailto:", "#")):
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                continue
            if not resolved.exists():
                missing.append(f"{path.relative_to(ROOT)} -> {target}")
    if missing:
        fail(f"broken local Markdown link(s): {missing}")
    else:
        ok("local Markdown links resolve")


def validate_workflows() -> None:
    approval_path = ROOT / "python-control-plane" / "src" / "madclaude" / "approval.py"
    approval_source = approval_path.read_text(encoding="utf-8")
    required_approval_markers = ["approvalReference", "founderApproved", "planSha256", "evidenceSource"]
    missing_markers = [marker for marker in required_approval_markers if marker not in approval_source]
    if missing_markers:
        fail(f"Python approval gate is missing hardening markers: {missing_markers}")
    else:
        ok("Python build route requires SHA-bound, source-classified Founder approval evidence")

    node = shutil.which("node")
    if not node:
        warn("Node.js not found; skipped workflow and hook JavaScript compilation")
        return
    proc = subprocess.run([node, str(ROOT / "scripts" / "validate-workflows.mjs")], capture_output=True, text=True)
    if proc.returncode:
        fail("workflow compiler failed: " + (proc.stderr.strip() or proc.stdout.strip()))
    else:
        ok(proc.stdout.strip())
    for path in sorted((CLAUDE / "hooks").glob("*.mjs")) + [ROOT / "global" / "madventures-statusline.mjs", ROOT / "scripts" / "test-hooks.mjs"]:
        check = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
        if check.returncode:
            fail(f"{path.relative_to(ROOT)}: Node syntax error: {check.stderr.strip()}")
    if not any(r.level == "FAIL" and "Node syntax" in r.message for r in results):
        ok("all hook, test, and status-line JavaScript modules compile")
    runtime = subprocess.run([node, str(ROOT / "scripts" / "test-hooks.mjs")], capture_output=True, text=True)
    if runtime.returncode:
        fail("hook/status-line runtime tests failed: " + (runtime.stderr.strip() or runtime.stdout.strip()))
    else:
        ok(runtime.stdout.strip())


def validate_installers() -> None:
    bash = shutil.which("bash")
    install_sh = ROOT / "scripts" / "install.sh"
    smoke_sh = ROOT / "scripts" / "smoke-test-install.sh"
    if not install_sh.exists() or not smoke_sh.exists():
        fail("installer or smoke-test script is missing")
    elif bash:
        for path in (
            install_sh,
            smoke_sh,
            ROOT / "scripts" / "build-release.sh",
            ROOT / "scripts" / "run-native-target-gate.sh",
            ROOT / "scripts" / "start-claude-route.sh",
            ROOT / "scripts" / "test-route-launcher.sh",
            ROOT / "scripts" / "install-plugin.sh",
            ROOT / "scripts" / "install-python-control-plane.sh",
            ROOT / "scripts" / "test-cloud-session.sh",
            ROOT / "cloud" / "setup.sh",
            CLAUDE / "cloud" / "session-start.sh",
        ):
            proc = subprocess.run([bash, "-n", str(path)], capture_output=True, text=True)
            if proc.returncode:
                fail(f"{path.relative_to(ROOT)}: Bash syntax error: {proc.stderr.strip()}")
        if not any(r.level == "FAIL" and "Bash syntax" in r.message for r in results):
            ok("Bash installer, route launcher, release, cloud, and test scripts pass syntax validation")
        route_test = subprocess.run([bash, str(ROOT / "scripts" / "test-route-launcher.sh")], capture_output=True, text=True)
        if route_test.returncode:
            fail("model route launcher test failed: " + (route_test.stderr.strip() or route_test.stdout.strip()))
        else:
            ok(route_test.stdout.strip())
        cloud_test = subprocess.run([bash, str(ROOT / "scripts" / "test-cloud-session.sh")], capture_output=True, text=True)
        if cloud_test.returncode:
            fail("cloud SessionStart behavior test failed: " + (cloud_test.stderr.strip() or cloud_test.stdout.strip()))
        else:
            ok(cloud_test.stdout.strip())
    else:
        warn("Bash not found; skipped installer syntax check")

    for path in (
        ROOT / "scripts" / "build-plugin.py",
        ROOT / "scripts" / "create-zip.py",
        ROOT / "scripts" / "create-plugin-zip.py",
        ROOT / "scripts" / "generate-manifest.py",
        ROOT / "scripts" / "bump-version.py",
        ROOT / "scripts" / "environment-lifecycle.py",
        ROOT / "scripts" / "test-release-archives.py",
    ):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            fail(f"{path.relative_to(ROOT)}: Python syntax error: {exc}")
    if not any(r.level == "FAIL" and "Python syntax error" in r.message for r in results):
        ok("Python build and release scripts compile")

    ps = shutil.which("pwsh") or shutil.which("powershell")
    if ps:
        command = "& { [void][System.Management.Automation.Language.Parser]::ParseFile($args[0],[ref]$null,[ref]$null) }"
        for script in (
            ROOT / "scripts" / "install.ps1",
            ROOT / "scripts" / "install-plugin.ps1",
            ROOT / "scripts" / "install-python-control-plane.ps1",
            ROOT / "scripts" / "start-claude-route.ps1",
        ):
            proc = subprocess.run([ps, "-NoProfile", "-Command", command, str(script)], capture_output=True, text=True)
            if proc.returncode:
                fail(f"{script.relative_to(ROOT)}: PowerShell parse failed: {proc.stderr.strip()}")
        if not any(r.level == "FAIL" and "PowerShell parse failed" in r.message for r in results):
            ok("PowerShell installers parse")
    else:
        warn("PowerShell not found; static PowerShell parse skipped")

    release_text = (ROOT / "scripts" / "build-release.sh").read_text(encoding="utf-8")
    release_requirements = [
        "build-plugin.py", "claude plugin validate", "smoke-test-install.sh",
        "test-route-launcher.sh", "test-cloud-session.sh", "test-python-control-plane.sh",
        "test-release-archives.py",
    ]
    missing_release_steps = [item for item in release_requirements if item not in release_text]
    if missing_release_steps:
        fail(f"release pipeline is missing required step(s): {missing_release_steps}")
    else:
        ok("release pipeline rebuilds the plugin and runs official validation when Claude CLI is available")


def validate_secrets_and_mcp() -> None:
    token_patterns = {
        "Anthropic key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
        "GitHub classic token": re.compile(r"ghp_[A-Za-z0-9]{30,}"),
        "GitHub fine-grained token": re.compile(r"github_pat_[A-Za-z0-9_]{30,}"),
        "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
        "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    }
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name in {"MANIFEST.json", "SHA256SUMS.txt"}:
            continue
        # A10-A secret-pattern fixtures intentionally embed credential-shaped
        # strings to exercise the redactor; they are test data, not leaked
        # credentials, and are excluded from the release-tree secret scan.
        # Scoped to the EXACT path so a copy elsewhere cannot bypass the scan.
        if path.relative_to(ROOT) == Path("python-control-plane/tests/test_secrets_patterns.py"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in token_patterns.items():
            if pattern.search(text):
                fail(f"possible embedded {label} in {path.relative_to(ROOT)}")
    if not any(r.level == "FAIL" and "possible embedded" in r.message for r in results):
        ok("no credential-shaped values detected")

    active = [p for p in PROJECT.rglob(".mcp.json") if p.is_file()]
    if active:
        fail(f"active MCP configuration unexpectedly included: {[str(p.relative_to(ROOT)) for p in active]}")
    elif (PROJECT / ".mcp.example.json").exists():
        ok("MCP configuration remains inactive by filename")
        mcp = load_json(PROJECT / ".mcp.example.json")
        try:
            github = mcp["mcpServers"]["github-readonly"]
            headers = github["headers"]
            if github.get("url") != "https://api.githubcopilot.com/mcp/":
                fail("GitHub MCP example must use the current base remote URL")
            if headers.get("X-MCP-Readonly") != "true":
                fail("GitHub MCP example must enable header-based read-only mode")
            if not headers.get("X-MCP-Toolsets"):
                fail("GitHub MCP example must bound exposed toolsets")
            if "${GITHUB_PERSONAL_ACCESS_TOKEN}" not in headers.get("Authorization", ""):
                fail("GitHub MCP example must reference, not embed, the token")
            else:
                ok("GitHub MCP example uses bounded header-based read-only configuration")
        except (TypeError, KeyError):
            fail("GitHub MCP example has an unexpected structure")
    else:
        fail("inactive MCP example missing")


def validate_cloud_assets() -> None:
    required = [
        ROOT / "cloud" / "README.md",
        ROOT / "cloud" / "setup.sh",
        ROOT / "cloud" / "environment.env.example",
        ROOT / "cloud" / "allowed-domains.example.txt",
        CLAUDE / "cloud" / "session-start.sh",
        PROJECT / "profiles" / "cloud-session-start.settings.fragment.json",
        ROOT / "examples" / "CLOUD_TASKS.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        fail(f"missing cloud asset(s): {missing}")
        return
    ok(f"cloud environment assets present ({len(required)} files)")

    setup = (ROOT / "cloud" / "setup.sh").read_text(encoding="utf-8")
    session = (CLAUDE / "cloud" / "session-start.sh").read_text(encoding="utf-8")
    env_text = (ROOT / "cloud" / "environment.env.example").read_text(encoding="utf-8")
    if "CLAUDE_CODE_REMOTE" not in session or "MADVENTURES_CLOUD_INSTALL_DEPS" not in session:
        fail("cloud SessionStart script is missing remote and opt-in guards")
    else:
        ok("cloud SessionStart dependency installation is remote-scoped and opt-in")
    if "MADVENTURES_CLOUD_ENVIRONMENT_VERSION=4.4.2" not in setup:
        fail("cloud setup script version marker is stale")
    banned_env = {"ANTHROPIC_API_KEY", "GITHUB_PERSONAL_ACCESS_TOKEN", "GH_TOKEN", "DATABASE_URL", "AWS_SECRET_ACCESS_KEY"}
    declared = {
        line.split("=", 1)[0].strip()
        for line in env_text.splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    }
    exposed = sorted(banned_env & declared)
    if exposed:
        fail(f"cloud environment example must not declare secret-bearing keys: {exposed}")
    else:
        ok("cloud environment example contains non-secret controls only")

    base_settings = load_json(CLAUDE / "settings.json")
    fragment = load_json(PROJECT / "profiles" / "cloud-session-start.settings.fragment.json")
    if isinstance(base_settings, dict) and "SessionStart" in base_settings.get("hooks", {}):
        fail("cloud dependency bootstrap must not be active in the shared baseline")
    elif isinstance(fragment, dict) and "SessionStart" in fragment.get("hooks", {}):
        ok("cloud SessionStart hook is supplied as an explicit opt-in fragment")
    else:
        fail("cloud SessionStart opt-in fragment is malformed")


def validate_version_and_docs() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip() if (ROOT / "VERSION").exists() else ""
    if version != "4.4.2":
        fail(f"VERSION must be 4.4.2, found '{version}'")
    else:
        ok("package version is 4.4.2")
    required_docs = {
        "README.md", "START_HERE.md", "CHANGELOG.md", "docs/ARCHITECTURE.md", "docs/DEPLOYMENT.md",
        "docs/DYNAMIC_WORKFLOWS.md", "docs/SUBAGENT_REGISTRY.md", "docs/MODEL_ROUTING.md",
        "docs/SESSION_CONTEXT_CHECKPOINTS.md", "docs/CLI_DEBUG_REFERENCE.md",
        "docs/SECURITY_GOVERNANCE.md", "docs/UPGRADE_FROM_V4.md",
        "docs/OFFICIAL_SOURCE_AUDIT.md", "docs/OPERATIONAL_PLAYBOOK.md",
        "docs/CLOUD_ENVIRONMENT.md", "docs/PARALLELISM_AND_AUTONOMY.md",
        "docs/COMMAND_PALETTE.md", "docs/PERFORMANCE_AND_TROUBLESHOOTING.md",
        "docs/PLUGIN_DEPLOYMENT.md", "docs/CLAUDE_CODE_FIELD_REFERENCE.md",
        "docs/MODEL_ROUTE_PROFILES.md", "docs/AUTHENTICATION_AND_BILLING.md",
        "docs/PYTHON_CONTROL_PLANE.md", "docs/HOOKS_AND_ARTIFACTS.md", "docs/RELEASE_RUNBOOK.md",
        "python-control-plane/README.md",
        "cloud/README.md", "examples/CLOUD_TASKS.md",
        "examples/PYTHON_CONTROL_PLANE_INVOCATIONS.md", "examples/FOUNDER_APPROVAL.example.json",
    }
    missing = sorted(rel for rel in required_docs if not (ROOT / rel).exists())
    if missing:
        fail(f"missing required documentation: {missing}")
    else:
        ok(f"required documentation present ({len(required_docs)} files)")



def _policy_modules() -> tuple[str, ...]:
    spec = importlib.util.spec_from_file_location("mad_build_plugin", ROOT / "scripts" / "build-plugin.py")
    if spec is None or spec.loader is None:
        fail("could not load scripts/build-plugin.py for the policy module list")
        return ()
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return tuple(module.POLICY_MODULES)


def _policy_closure() -> frozenset[str]:
    spec = importlib.util.spec_from_file_location("mad_build_plugin", ROOT / "scripts" / "build-plugin.py")
    if spec is None or spec.loader is None:
        fail("could not load scripts/build-plugin.py for the policy closure")
        return frozenset()
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.policy_module_closure(ROOT / "python-control-plane" / "src" / "madclaude")


def plugin_policy_module_drift(root: Path) -> list[str]:
    """A9-04 byte-parity gate: exact-set plus SHA-256 comparison of every
    bundled plugin Python policy module against the canonical control-plane
    source. Returns a list of human-readable drift descriptions (empty when
    the plugin is in parity)."""
    source = root / "python-control-plane" / "src" / "madclaude"
    bundled = root / "plugin" / "madventures-founderos" / "python-control-plane" / "src" / "madclaude"
    expected = set(_policy_modules())
    actual = {path.name for path in bundled.glob("*.py")} if bundled.is_dir() else set()
    problems = [f"missing plugin policy module: {name}" for name in sorted(expected - actual)]
    problems.extend(f"extra plugin Python module: {name}" for name in sorted(actual - expected))
    for name in sorted(expected & actual):
        source_hash = hashlib.sha256((source / name).read_bytes()).hexdigest()
        bundled_hash = hashlib.sha256((bundled / name).read_bytes()).hexdigest()
        if source_hash != bundled_hash:
            problems.append(f"plugin policy module differs from canonical source: {name}")
    return problems


def validate_plugin() -> None:
    if not PLUGIN.exists():
        fail("portable plugin directory is missing")
        return

    manifest_path = PLUGIN / ".claude-plugin" / "plugin.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else None
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not isinstance(manifest, dict):
        fail("plugin manifest is missing or invalid")
    else:
        if manifest.get("name") != "madventures-founderos":
            fail("plugin manifest name must be madventures-founderos")
        if manifest.get("version") != version:
            fail(f"plugin version {manifest.get('version')!r} does not match package {version!r}")
        if manifest.get("$schema") != "https://json.schemastore.org/claude-code-plugin-manifest.json":
            warn("plugin manifest does not use the current SchemaStore plugin schema URL")
        else:
            ok("portable plugin manifest identity and version validated")

    plugin_counts = {
        "agents": len(list((PLUGIN / "agents").glob("*.md"))),
        "skills": len(list((PLUGIN / "skills").glob("*/SKILL.md"))),
        "workflows": len(list((PLUGIN / "workflows").glob("*.js"))),
    }
    expected = {"agents": 19, "skills": EXPECTED["skills"], "workflows": EXPECTED["workflows"]}
    for kind, count in expected.items():
        if plugin_counts[kind] != count:
            fail(f"portable plugin expected {count} {kind}, found {plugin_counts[kind]}")
    if plugin_counts == expected:
        ok(f"portable plugin component counts validated (19 agents, {EXPECTED['skills']} skills, 0 executable workflows)")

    project_agent_names = {p.stem for p in (CLAUDE / "agents").glob("*.md")}
    plugin_agent_names = {p.stem for p in (PLUGIN / "agents").glob("*.md")}
    expected_agents = project_agent_names - {"neon-reader"}
    if plugin_agent_names != expected_agents:
        fail(f"plugin agent set differs from project set minus neon-reader: {sorted(plugin_agent_names ^ expected_agents)}")
    elif "neon-reader" in plugin_agent_names:
        fail("plugin must not ship neon-reader without its scoped SQL guard")
    else:
        ok("portable plugin intentionally excludes only neon-reader")

    for path in sorted((PLUGIN / "agents").glob("*.md")):
        parsed = frontmatter(path.read_text(encoding="utf-8"), path)
        if not parsed:
            continue
        raw, data = parsed
        keys = top_level_keys(raw)
        unsupported = keys - PLUGIN_AGENT_KEYS
        if unsupported:
            fail(f"{path.relative_to(ROOT)}: unsupported plugin agent field(s): {sorted(unsupported)}")
        forbidden_fields = {"permissionMode", "hooks", "mcpServers"} & keys
        if forbidden_fields:
            fail(f"{path.relative_to(ROOT)}: plugin agents cannot enforce {sorted(forbidden_fields)}")
        for key in ("name", "description", "tools", "model"):
            if not data.get(key):
                fail(f"{path.relative_to(ROOT)}: missing required '{key}'")
        tools = set(parse_tools(data.get("tools", "")))
        if data.get("name") == "independent-reviewer":
            forbidden_tools = {"Bash", "PowerShell", "Edit", "Write", "NotebookEdit", "Agent", "Skill"} & tools
            if forbidden_tools:
                fail(f"plugin independent-reviewer exposes forbidden tools: {sorted(forbidden_tools)}")
            required_denials = {"Edit", "Write", "NotebookEdit", "Bash", "PowerShell"}
            denials = set(parse_tools(data.get("disallowedTools", "")))
            if not required_denials.issubset(denials):
                fail("plugin independent-reviewer is missing explicit disallowed tools")

    project_skills = {p.parent.name: p.read_bytes() for p in (CLAUDE / "skills").glob("*/SKILL.md")}
    plugin_skills = {p.parent.name: p.read_bytes() for p in (PLUGIN / "skills").glob("*/SKILL.md")}
    if project_skills != plugin_skills:
        fail("plugin skills are not byte-for-byte synchronized with project skills")
    else:
        ok("plugin skills are synchronized with project skills")

    project_workflows = {p.name: p.read_bytes() for p in (CLAUDE / "workflows").glob("*.js")}
    plugin_workflows = {p.name: p.read_bytes() for p in (PLUGIN / "workflows").glob("*.js")}
    if project_workflows != plugin_workflows:
        fail("plugin workflows are not byte-for-byte synchronized with project workflows")
    else:
        ok("plugin workflows are synchronized with project workflows")

    hook_config_path = PLUGIN / "hooks" / "hooks.json"
    hook_config = load_json(hook_config_path) if hook_config_path.exists() else None
    if not isinstance(hook_config, dict):
        fail("plugin hooks/hooks.json is missing or invalid")
    else:
        text = json.dumps(hook_config)
        if "${CLAUDE_PLUGIN_ROOT}" not in text:
            fail("plugin hook commands must resolve through CLAUDE_PLUGIN_ROOT")
        refs = re.findall(r"hooks/([A-Za-z0-9._-]+\.mjs)", text)
        for ref in refs:
            if not (PLUGIN / "hooks" / ref).exists():
                fail(f"plugin hook references missing file: {ref}")
        if refs:
            ok(f"plugin hook references resolve ({len(set(refs))} unique)")
        bundled_policy = PLUGIN / "python-control-plane" / "src" / "madclaude" / "hook_policy.py"
        forbidden_runtime = {"cli.py", "backend.py", "workflows.py", "approval.py", "execution.py"}
        bundled_names = {path.name for path in bundled_policy.parent.glob("*.py")} if bundled_policy.is_file() else set()
        if not bundled_policy.is_file() or set(refs) != {"hook-adapter.mjs"} or forbidden_runtime & bundled_names:
            fail("plugin must ship one thin hook adapter and its Python policy modules")
        else:
            ok("plugin ships one thin adapter backed by the shared Python policy modules")

    drift = plugin_policy_module_drift(ROOT)
    for problem in drift:
        fail(problem)
    if not drift:
        ok("plugin Python policy modules are byte-identical to the canonical source")

    closure = set(_policy_closure())
    shipped = set(_policy_modules())
    missing = sorted(closure - shipped)
    if missing:
        fail(f"plugin policy set does not cover the hook import closure: {missing}")
    else:
        ok(f"plugin policy modules cover the hook import closure ({len(closure)} modules)")

    for rel in ("README.md", "NOTICE.md"):
        if not (PLUGIN / rel).exists():
            fail(f"portable plugin missing {rel}")


def validate_python_control_plane(*, run_integration: bool = True) -> None:
    control = ROOT / "python-control-plane"
    required = [
        control / "pyproject.toml",
        control / "README.md",
        control / "bin/madclaude.py",
        control / "run-tests.py",
        control / "src" / "madclaude" / "cli.py",
        control / "src" / "madclaude" / "auth.py",
        control / "src" / "madclaude" / "backend.py",
        control / "src" / "madclaude" / "guard.py",
        control / "src" / "madclaude" / "hook_cli.py",
        control / "src" / "madclaude" / "workflows.py",
        ROOT / "scripts" / "install-python-control-plane.sh",
        ROOT / "scripts" / "install-python-control-plane.ps1",
        ROOT / "scripts" / "test-python-control-plane.sh",
        CLAUDE / "hooks" / "hook-adapter.mjs",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        fail(f"Python control-plane files missing: {missing}")
        return
    ok("Python control-plane canonical source, policy hooks, installers, and dedicated test harness are present")

    if (CLAUDE / "control-plane").exists():
        fail("stale duplicate project/.claude/control-plane source exists; canonical source must remain top-level")
    else:
        ok("Python control plane has one canonical package source")

    pyproject_path = control / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    project_data: dict[str, object] = {}
    optional_data: dict[str, object] = {}
    if tomllib is not None:
        parsed = tomllib.loads(pyproject_text)
        candidate = parsed.get("project", {}) if isinstance(parsed, dict) else {}
        project_data = candidate if isinstance(candidate, dict) else {}
        optional = project_data.get("optional-dependencies", {})
        optional_data = optional if isinstance(optional, dict) else {}
    else:
        version_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_text, re.M)
        python_match = re.search(r'^requires-python\s*=\s*"([^"]+)"', pyproject_text, re.M)
        dependency_match = re.search(r'^dependencies\s*=\s*\[(.*?)\]', pyproject_text, re.M | re.S)
        dependencies = re.findall(r'"([^"]+)"', dependency_match.group(1)) if dependency_match else []
        sdk_section = re.search(r'^\[project\.optional-dependencies\]\s*(.*?)(?=^\[|\Z)', pyproject_text, re.M | re.S)
        sdk_match = re.search(r'^sdk\s*=\s*\[(.*?)\]', sdk_section.group(1), re.M | re.S) if sdk_section else None
        sdk_dependencies = re.findall(r'"([^"]+)"', sdk_match.group(1)) if sdk_match else []
        project_data = {
            "version": version_match.group(1) if version_match else None,
            "requires-python": python_match.group(1) if python_match else None,
            "dependencies": dependencies,
        }
        optional_data = {"sdk": sdk_dependencies}
    version_ok = project_data.get("version") == "4.4.2"
    dependencies = project_data.get("dependencies")
    sdk_dependencies = optional_data.get("sdk")
    requires_python = str(project_data.get("requires-python") or "")
    if not version_ok:
        fail("Python control-plane package version is not 4.4.2")
    if dependencies != []:
        fail(f"subscription-first Python control plane must have no mandatory dependencies; got {dependencies!r}")
    if sdk_dependencies != ["claude-agent-sdk==0.2.131"]:
        fail(f"optional SDK extra must pin exactly claude-agent-sdk==0.2.131; got {sdk_dependencies!r}")
    if ">=3.10" not in requires_python:
        fail(f"Python control-plane package floor must be >=3.10; got {requires_python!r}")
    if version_ok and dependencies == [] and sdk_dependencies == ["claude-agent-sdk==0.2.131"] and ">=3.10" in requires_python:
        ok("Python package is dependency-free by default and pins the optional API SDK extra exactly")

    schemas = sorted((control / "schemas").glob("*.schema.json"))
    if len(schemas) != 10:
        fail(f"expected 10 Python structured-output schemas, found {len(schemas)}")
    elif all(load_json(path) is not None for path in schemas):
        ok("ten Python structured-output schemas parse")

    source_files = sorted(control.rglob("*.py"))
    compile_failures: list[str] = []
    for source in source_files:
        try:
            compile(source.read_text(encoding="utf-8"), str(source), "exec")
        except (OSError, SyntaxError, UnicodeError) as exc:
            compile_failures.append(f"{source.relative_to(ROOT)}: {exc}")
    if compile_failures:
        fail("Python control-plane compilation failed: " + "; ".join(compile_failures))
    else:
        ok(f"all {len(source_files)} Python control-plane modules/tests compile without cache files")

    backend = (control / "src" / "madclaude" / "backend.py").read_text(encoding="utf-8")
    auth = (control / "src" / "madclaude" / "auth.py").read_text(encoding="utf-8")
    cli = (control / "src" / "madclaude" / "cli.py").read_text(encoding="utf-8")
    guard = (control / "src" / "madclaude" / "guard.py").read_text(encoding="utf-8")
    hook_cli = (control / "src" / "madclaude" / "hook_cli.py").read_text(encoding="utf-8")
    workflows = (control / "src" / "madclaude" / "workflows.py").read_text(encoding="utf-8")
    config = (control / "src" / "madclaude" / "config.py").read_text(encoding="utf-8")

    if 'default="cli"' not in cli or 'default="subscription"' not in cli:
        fail("Python CLI must default to native claude -p plus subscription billing")
    else:
        ok("Python CLI defaults to native claude -p under the authenticated subscription lane")

    cli_markers = [
        '"-p"',
        '"--json-schema"',
        '"--settings"',
        '"--strict-mcp-config"',
        'MADCLAUDE_ALLOWED_SUBAGENTS_JSON',
        '_ephemeral_policy_settings()',
        'if request.billing_mode == "api"',
    ]
    missing_cli = [marker for marker in cli_markers if marker not in backend]
    if missing_cli:
        fail(f"native CLI backend hard-control marker(s) missing: {missing_cli}")
    else:
        ok("native claude -p backend injects structured output, ephemeral policy hooks, strict MCP isolation, and API-only dollar caps")

    sdk_markers = [
        'system_prompt={"type": "preset", "preset": "claude_code"',
        "strict_mcp_config=True",
        "mcp_servers={}",
        'hooks={"PreToolUse"',
        "enable_file_checkpointing=True",
        "setting_sources=list(request.setting_sources)",
        'if request.billing_mode != "api"',
    ]
    missing_sdk = [marker for marker in sdk_markers if marker not in backend]
    if missing_sdk:
        fail(f"optional Agent SDK hard-control marker(s) missing: {missing_sdk}")
    else:
        ok("optional Agent SDK adapter is API-only and retains Claude Code preset, strict MCP, checkpoint, and PreToolUse controls")

    if "allow_cli_fallback" in backend + cli + workflows or "--allow-cli-fallback" in backend + cli + workflows:
        fail("stale CLI-fallback architecture remains in Python source")
    if '"Skill"' in config:
        fail("Python governed routes must not expose Skill")
    elif 'tools=("Read", "Grep", "Glob", "Agent")' not in config:
        fail("read-only fan-out routes are missing explicit Agent delegation")
    elif "allowed_subagents=request.subagents" not in backend or "allowed_subagents" not in guard or "evaluate_input" not in hook_cli:
        fail("subagent registry or dynamic PreToolUse enforcement is incomplete")
    else:
        ok("read-only fan-out is constrained to route-specific subagents while mutation routes remain single-builder")

    if '"--bare"' in backend or "'--bare'" in backend:
        fail("Python CLI backend must not use --bare because subscription/settings loading is required")
    required_auth = [
        "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_USE_ANTHROPIC_AWS", "apiKeyHelper",
        "--allow-api-billing", "--max-budget-usd", "--allow-usage-credits", "usage credits",
        "model-specific plan entitlements",
    ]
    combined = auth + cli
    missing_auth = [item for item in required_auth if item not in combined]
    if missing_auth:
        fail(f"Python billing guard missing marker(s): {missing_auth}")
    else:
        ok("subscription credential precedence, model-entitlement caveat, usage-credit gate, and explicit API-billing gates validated")

    settings = load_json(CLAUDE / "settings.json")
    settings_text = json.dumps(settings) if isinstance(settings, dict) else ""
    required_hook_events = {"PreToolUse", "ConfigChange", "Stop", "TaskCompleted"}
    hook_events = set(settings.get("hooks", {})) if isinstance(settings, dict) else set()
    if "hook-adapter.mjs" not in settings_text or not required_hook_events.issubset(hook_events):
        fail("Python-backed baseline and completion hooks are not fully registered")
    else:
        ok("one Python-backed adapter enforces baseline, configuration, and completion policy")

    routes = subprocess.run(
        [sys.executable, str(control / "bin/madclaude.py"), "routes", "--json"],
        capture_output=True,
        text=True,
        cwd=control,
        env={**dict(__import__("os").environ), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if routes.returncode:
        fail("Python route registry launcher failed: " + (routes.stderr.strip() or routes.stdout.strip()))
    else:
        try:
            payload = json.loads(routes.stdout)
        except json.JSONDecodeError as exc:
            fail(f"Python route registry did not emit JSON: {exc}")
        else:
            route_error = None
            if len(payload) != 11:
                route_error = f"expected 11 Python routes, found {len(payload)}"
            elif payload.get("plan", {}).get("subagents") != ["founder-os-explorer", "dependency-mapper"]:
                route_error = "plan route does not expose the approved read-only explorer registry"
            elif "Agent" not in payload.get("plan", {}).get("tools", []):
                route_error = "plan route is missing Agent fan-out"
            elif payload.get("build", {}).get("subagents") != [] or "Agent" in payload.get("build", {}).get("tools", []):
                route_error = "build route must remain a single non-delegating mutation lane"
            elif any("Skill" in route.get("tools", []) for route in payload.values()):
                route_error = "Python routes must not expose Skill"
            elif any(("Agent" in route.get("tools", [])) != bool(route.get("subagents")) for route in payload.values()):
                route_error = "Agent tool availability does not match route subagent registries"
            if route_error:
                fail(route_error)
            else:
                ok("eleven governed Python routes load with constrained read-only fan-out and single-builder mutation lanes")

    if run_integration:
        shell_test = subprocess.run(
            ["bash", str(ROOT / "scripts" / "test-python-control-plane.sh")],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if shell_test.returncode:
            fail("Python control-plane integration tests failed: " + (shell_test.stderr.strip() or shell_test.stdout.strip()))
        else:
            ok("Python control-plane unit, policy, auth, dry-run, dependency-free installer, and evidence tests passed")
    else:
        ok("Python control-plane integration rerun skipped for nested installation smoke; full release validation runs it separately")

    install_sh = (ROOT / "scripts" / "install-python-control-plane.sh").read_text(encoding="utf-8")
    install_ps = (ROOT / "scripts" / "install-python-control-plane.ps1").read_text(encoding="utf-8")
    shell_markers = ["--with-sdk", 'SDK_VERSION="0.2.131"', 'claude-agent-sdk==$SDK_VERSION', "umask 077", "requires no Python dependencies"]
    ps_markers = ["[switch]$WithSdk", "$SdkVersion = '0.2.131'", 'claude-agent-sdk==$SdkVersion', "requires no Python dependencies"]
    missing_shell = [marker for marker in shell_markers if marker not in install_sh]
    missing_ps = [marker for marker in ps_markers if marker not in install_ps]
    if missing_shell:
        fail(f"Bash Python installer missing marker(s): {missing_shell}")
    if missing_ps:
        fail(f"PowerShell Python installer missing marker(s): {missing_ps}")
    if not missing_shell and not missing_ps:
        ok("Python installers are dependency-free by default and make the API SDK an exact, explicit opt-in")

    stale_markers = (
        "--allow-cli-fallback",
        "SDK is the governed default",
        "Agent SDK is the governed default",
        "Agent SDK default",
        "direct CLI compatibility lane",
    )
    stale_hits: list[str] = []
    doc_paths = [
        ROOT / "README.md", ROOT / "START_HERE.md", ROOT / "CHANGELOG.md",
        *sorted((ROOT / "docs").glob("*.md")), control / "README.md",
        CLAUDE / "skills" / "python-control-plane" / "SKILL.md",
        CLAUDE / "rules" / "70-python-control-plane.md",
    ]
    for path in doc_paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for marker in stale_markers:
            if marker in text:
                stale_hits.append(f"{path.relative_to(ROOT)}:{marker}")
    if stale_hits:
        fail(f"stale V4.4 Python architecture/billing guidance remains: {stale_hits}")
    else:
        ok("V4.4 documentation consistently describes native CLI subscription default and API-only optional SDK")

    caches = [path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*.pyc")]
    caches.extend(path.relative_to(ROOT).as_posix() for path in ROOT.rglob("__pycache__"))
    if caches:
        fail(f"Python cache artifacts remain in the release tree: {caches[:10]}")
    else:
        ok("release tree contains no Python bytecode/cache artifacts")



def validate_delivery_experience() -> None:
    required = [
        ROOT / "README_FIRST.txt",
        ROOT / "OPEN_ME_FIRST.md",
        ROOT / "DELIVERY_FIX.md",
        ROOT / "INSTALL_MAC.command",
        ROOT / "INSTALL_WINDOWS.ps1",
        ROOT / "VERIFY_PACKAGE.command",
        ROOT / "PACKAGE_CONTENTS.txt",
        ROOT / "VISIBLE_PROJECT_TEMPLATE" / "README_FIRST.txt",
        ROOT / "scripts" / "quick-validate.py",
        ROOT / "scripts" / "sync-visible-template.py",
        ROOT / "scripts" / "generate-delivery-index.py",
        ROOT / "scripts" / "create-tar.py",
        ROOT / "scripts" / "environment-lifecycle.py",
        ROOT / "scripts" / "test-release-archives.py",
        ROOT / "managed" / "20-madventures-baseline.json",
        ROOT / "workspace" / ".claude" / "MADVENTURES_WORKSPACE.md",
    ]
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    if missing:
        fail(f"delivery-correction assets missing: {missing}")
        return

    quick = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "quick-validate.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if quick.returncode:
        fail("fast delivery/integrity validation failed: " + (quick.stderr.strip() or quick.stdout.strip()))
    else:
        ok("Finder-visible mirror, top-level launchers, package index, and fast integrity preflight validated")

    install_sh = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    install_ps = (ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")
    lifecycle = (ROOT / "scripts" / "environment-lifecycle.py").read_text(encoding="utf-8")
    if "environment-lifecycle.py" not in install_sh or "--full-validation" not in lifecycle or "quick-validate.py" not in lifecycle:
        fail("Bash installer is not a thin launcher for the fast-default/full-opt-in lifecycle")
    elif "[switch]$FullValidation" not in install_ps or "environment-lifecycle.py" not in install_ps:
        fail("PowerShell installer is not a thin launcher for the shared lifecycle")
    else:
        ok("cross-platform installers use fast validation by default and preserve exhaustive opt-in validation")

def write_report(path: Path) -> None:
    failures = sum(r.level == "FAIL" for r in results)
    warnings = sum(r.level == "WARN" for r in results)
    passes = sum(r.level == "PASS" for r in results)
    status = "PASSED" if failures == 0 else "FAILED"
    lines = [
        "# Validation report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        f"**Package:** {PACKAGE_NAME}",
        f"**Result:** {status}",
        f"**Summary:** {passes} pass, {warnings} warning, {failures} fail",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- **{r.level}** — {r.message}" for r in results)
    lines += [
        "",
        "## Interpretation",
        "",
        "Static validation proves package shape, syntax, references, guard placement, and installer behavior that can be tested locally. It does not prove account-specific model availability, organization policy, MCP authentication, live repository commands, or production behavior. Run `claude doctor` and the repository's real verification commands after deployment.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", help="write a Markdown validation report to this path")
    parser.add_argument("--no-report", action="store_true", help="deprecated compatibility flag; validation is read-only by default")
    parser.add_argument(
        "--skip-python-integration",
        action="store_true",
        help="skip the separate Python integration subprocess (used only by nested installer smoke tests)",
    )
    args = parser.parse_args()

    validate_version_and_docs()
    validate_delivery_experience()
    validate_counts()
    validate_agents()
    validate_skills()
    validate_json_and_settings()
    validate_doctrine()
    validate_model_registry()
    validate_markdown_links()
    validate_workflows()
    validate_installers()
    validate_secrets_and_mcp()
    validate_python_control_plane(run_integration=not args.skip_python_integration)
    validate_plugin()
    validate_cloud_assets()

    for result in results:
        print(f"[{result.level}] {result.message}")
    failures = sum(r.level == "FAIL" for r in results)
    warnings = sum(r.level == "WARN" for r in results)
    passes = sum(r.level == "PASS" for r in results)
    print(f"\nVALIDATION {'PASSED' if failures == 0 else 'FAILED'}: {passes} pass, {warnings} warning, {failures} fail")

    if args.report and not args.no_report:
        write_report(Path(args.report))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
