from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from . import safe_read
from .artifacts import read_canonical_artifact
from .errors import EvidenceError, SafeReadError
from .escalation_state import DenialJournal
from .guard import ALIASES, evaluate_tool_call
from .git import get_state, working_tree_fingerprint


FILE_TOOLS = {"Read", "Edit", "Write", "NotebookEdit", "MultiEdit", "Grep", "Glob"}
MUTATION_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}

# A10-A: explicit supported-tool policy matrix (DEC-20260812-01 A10-A scope
# item 3). Before this package, the baseline hook fell through to
# `return True, "allowed"` for every non-file, non-shell tool (the A10-2
# hole at hook_policy.py:99-100). The flip below removes the default allow:
# every supported family has an explicit disposition, and any tool not in
# these sets fails closed. Rationale per family (ratified in the A10-A
# build commission; see docs/audit10-a10a-tool-surface-inventory.md):
#   - File read/mutate, Shell: existing governed routes (unchanged).
#   - Web (WebFetch/WebSearch): WEB_TOOLS in guard.py is dead code — never
#     consulted by any decision path; no governed route uses web tools.
#     Deny at baseline.
#   - Delegation (Agent/Task): governed by the control-plane route layer,
#     where MADCLAUDE_ALLOWED_SUBAGENTS_JSON supplies the allowlist and
#     unapproved subagents are denied. The plugin baseline hook has no
#     subagent registry and MUST defer to that layer — both hooks fire on
#     every tool call in the installed environment, and a baseline deny
#     would override a legitimate governed-route allow. The A10-2 hole for
#     delegation is closed at the governing layer (which is where the
#     allowlist data exists); the baseline defers by design, documented
#     here as the Delegation cell of the policy matrix.
#   - Skill: instruction-content loading with no authority or mutation
#     effect — the same class as the task/plan meta tools. The 31 shipped
#     skills must keep working in the installed environment, so Skill is
#     an EXPLICIT allow (it previously fell through to the default allow
#     as a silent hole; the matrix makes the disposition explicit rather
#     than flipping a live surface). A future route that needs Skill
#     beyond instruction loading must add a scope-guarded allow.
#   - Task/plan meta (TodoWrite, ExitPlanMode, TaskCreate, TaskUpdate):
#     model-internal bookkeeping, no repository or authority effect. Allow.
#   - MCP surfaces (mcp__*): denied by evaluate_tool_call in governed
#     routes; deny at baseline too (matches control-plane stance).
BASELINE_META_ALLOW = frozenset({"TodoWrite", "ExitPlanMode", "TaskCreate", "TaskUpdate"})
BASELINE_INSTRUCTION_ALLOW = frozenset({"Skill"})
BASELINE_DEFER = frozenset({"Agent"})  # Task normalizes to Agent via ALIASES
BASELINE_DENY = frozenset({"WebFetch", "WebSearch"})
DATABASE_CLIENT = re.compile(r"\b(?:psql|pgcli|mysql|mariadb|sqlite3|duckdb|sqlcmd)\b", re.I)
SHELL_SECRET = re.compile(
    r"(?:^|[\s'\"/\\])(?:\.env(?:\.[A-Za-z0-9_-]+)?|id_(?:rsa|ed25519|ecdsa)(?:\.pub)?|"
    r"[^\s'\"]+\.(?:pem|p12|pfx|key|keystore|jks|kdbx)|\.npmrc|\.netrc|\.pypirc|"
    r"credentials(?:\.[^\s'\"]*)?\.json|service[-_]?account(?:\.[^\s'\"]*)?\.json|"
    r"secrets?\.(?:json|ya?ml|toml))(?:$|[\s'\";&|])",
    re.I,
)
ALLOWED_ENV_TEMPLATE = re.compile(r"\.env\.(?:example|sample|template|defaults?)", re.I)
SHELL_AUTHORITY = re.compile(
    r"(?:^|[\s'\"/\\])(?:\.git(?:[/\\]|$)|CLAUDE\.md|\.claude[/\\](?:settings(?:\.local)?\.json|"
    r"FOUNDEROS\.md|MODEL_REGISTRY\.md|PROJECT_PROFILE\.md|INSTALLATION_RECORD\.md|rules(?:[/\\]|$)|"
    r"hooks(?:[/\\]|$)|control-plane(?:[/\\]|$)|evidence(?:[/\\]|$))|01-constitution(?:[/\\]|$)|"
    r"04-agents[/\\]role-registry\.md|07-decisions[/\\]decision-log\.md|decision-id-reservations\.md)",
    re.I,
)
SHELL_MUTATION = re.compile(
    r"(?:^|[;&|]\s*|\s)(?:sed\s+-[^\s]*i[^\s]*|tee|cp|mv|rm|touch|truncate|chmod|chown|install|"
    r"perl\s+-[^\s]*i|python(?:3)?\s+-c|node\s+-e|pwsh\s+-Command|powershell\s+-Command)(?:\s|$)|"
    r"(?:^|\s)(?:\d*>>?|&>)",
    re.I,
)
INLINE_AUTHORITY_GATE = re.compile(r"\b(?:FOUNDER_[A-Z0-9_]*_WRITE|FOUNDEROS_LIVE_ACCESS_ENABLED)\s*=", re.I)
DANGEROUS_SHELL = (
    re.compile(r"\bgit\b(?:\s+--?[A-Za-z][A-Za-z-]*(?:=\S+|\s+\S+))*\s+reset\s+--hard\b", re.I),
    re.compile(r"\bgit\b(?:\s+--?[A-Za-z][A-Za-z-]*(?:=\S+|\s+\S+))*\s+clean\s+-[^\s]*[fdx]", re.I),
    re.compile(r"\bgit\b[\s\S]*?\bpush\b[^\n]*(?:--force(?:-with-lease)?|(?:^|\s)-f(?:\s|$))", re.I),
    re.compile(r"\bgit\b[\s\S]*?\bbranch\s+(?:-D|--delete\s+--force)\b", re.I),
    re.compile(r"\bgit\b[\s\S]*?\b(?:checkout|restore)\s+(?:--\s+)?\.\s*(?:$|[;&|])", re.I),
    re.compile(r"\bgh\b[\s\S]*?\bpr\s+merge\b", re.I),
    re.compile(r"\bgh\b[\s\S]*?\bapi\b[\s\S]*?(?:-X|--method)\s*(?:POST|PUT|PATCH|DELETE)\b", re.I),
    re.compile(r"\bclaude\b[^\n]*(?:--dangerously-skip-permissions|--allow-dangerously-skip-permissions)\b", re.I),
    re.compile(r"\brm\s+-[^\s]*r[^\s]*f|\brm\s+-[^\s]*f[^\s]*r", re.I),
    re.compile(r"\b(?:mkfs(?:\.[A-Za-z0-9]+)?|fdisk|parted|shutdown|reboot|halt|poweroff)\b", re.I),
    re.compile(r"\bdd\s+[^\n]*\bof=(?:/dev/|\\\\\.\\PhysicalDrive)", re.I),
    re.compile(r"\b(?:wrangler|vercel|netlify|fly|heroku)\b[^\n]*\b(?:deploy|publish|release|promote)\b", re.I),
    re.compile(r"\b(?:kubectl\s+(?:apply|delete|replace)|terraform\s+(?:apply|destroy)|tofu\s+(?:apply|destroy))\b", re.I),
)

# A10-D (DEC-20260813-01 §2): mechanical risk-tier classifier.
# Deterministic pure function of (tool, target, route) — never model-supplied.
#   high:     authority/exfil tools on protected/secret/remote targets
#   moderate: the same tools on ordinary project targets
#   low:      read-only tools with no protected target
# A target matching no rule fails to 'moderate' (never 'unknown').
AUTHORITY_TOOLS = frozenset({"Edit", "Write", "NotebookEdit", "MultiEdit", "Bash", "PowerShell", "Agent"})
READONLY_TOOLS = frozenset({"Read", "Grep", "Glob"})
REMOTE_TARGET = re.compile(r"https?://|s3://|gs://|ftp://|ssh://", re.I)


def classify_risk_tier(tool_name: str, target: str, route: str = "") -> str:
    """A10-D: mechanical risk tier for a denial record.

    Pure function of (tool, target, route). The tier is a property of the
    action, never of model-supplied payload. Protected/secret targets reuse
    the A10-A SHELL_SECRET / SHELL_AUTHORITY patterns so the classifier and
    the deny rules agree on what is sensitive. A target that matches no
    rule fails to 'moderate' (never 'unknown').
    """
    name = ALIASES.get(str(tool_name or ""), str(tool_name or ""))
    target = str(target or "")
    if name in READONLY_TOOLS:
        if SHELL_SECRET.search(target) or SHELL_AUTHORITY.search(target):
            return "high"
        return "low"
    if name in AUTHORITY_TOOLS:
        if (
            SHELL_SECRET.search(target)
            or SHELL_AUTHORITY.search(target)
            or REMOTE_TARGET.search(target)
        ):
            return "high"
        return "moderate"
    # Unknown tool family: fail to moderate, never unknown.
    return "moderate"


def _tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("tool_input")
    return value if isinstance(value, dict) else {}


def _baseline_shell(payload: dict[str, Any]) -> tuple[bool, str]:
    command = str(_tool_input(payload).get("command") or _tool_input(payload).get("script") or "").strip()
    if not command:
        return False, "Shell hook input did not contain an inspectable command."
    if INLINE_AUTHORITY_GATE.search(command):
        return False, "A model shell command cannot enable Founder write or live-access gates."
    secret_scan = ALLOWED_ENV_TEMPLATE.sub("", command)
    if SHELL_SECRET.search(secret_scan):
        return False, "Shell access to credential- or secret-bearing paths is blocked."
    if any(pattern.search(command) for pattern in DANGEROUS_SHELL):
        return False, "Destructive, authority-changing, merge, deployment, or permission-bypass shell command blocked."
    if SHELL_AUTHORITY.search(command) and SHELL_MUTATION.search(command):
        return False, "Shell mutation of FounderOS authority or control-plane paths is blocked."
    if DATABASE_CLIENT.search(command) and str(payload.get("agent_type") or "") != "neon-reader":
        return False, "Database clients are restricted to the scoped neon-reader with a provider-enforced read-only identity."
    return True, "allowed"


def consult_escalation(repo: Path, payload: dict[str, Any]) -> tuple[bool, str]:
    """A10-C (Q1.3/Q3/Q4/Q5): objective/escalation consultation in the
    decision path.

    - No objective_id in scope -> allowed (baseline denials are
      un-governed; governed: false is recorded by the journal writer).
    - Malformed objective_id -> deny (Q1.3: validation on every governed
      action that consults it).
    - Unknown (well-formed but never Founder-minted) objective_id -> deny
      (Q1.1/Q1.3: ids are minted only by the Founder and must exist in the
      durable objective store).
    - Escalated objective -> deny (Q4.3: continuing past a ceiling
      requires a Founder disposition).
    - Closed objective (Founder deny disposition) -> deny, always: a deny
      disposition is a terminal ruling, never a continuation grant.
    - Dispositioned objective -> allow ONLY when the disposition is a
      continuation type (allow-with-conditions / modify-ceiling) bound to
      the exact ceiling event in this payload. A different ceiling event
      needs its own disposition.
    - Journal read failure -> deny (Q5: fail closed; the returned reason
      never exposes storage error details).
    """
    objective_id = str(
        payload.get("objective_id")
        or os.environ.get("MADCLAUDE_OBJECTIVE_ID")
        or ""
    ).strip()
    if not objective_id:
        return True, "no objective-bound escalation in scope"
    journal = DenialJournal(repo)
    if not journal.validate_objective_id(objective_id):
        return False, "Objective-bound escalation is denied: malformed objective_id."
    try:
        if journal.objective_record(objective_id) is None:
            return False, "Objective-bound escalation is denied: unknown objective_id (not Founder-minted)."
        state = journal.objective_state(objective_id)
        if state == "closed":
            return False, "Objective-bound escalation: this objective is closed by a Founder deny disposition."
        if state == "escalated":
            return False, "Objective-bound escalation is active: governed actions are denied pending a Founder disposition."
        if state == "dispositioned":
            ceiling_record_id = str(payload.get("ceiling_record_id") or "").strip()
            if ceiling_record_id and journal.disposition_permits(objective_id, ceiling_record_id):
                return True, "Founder disposition authorizes continuation past this ceiling event"
            return False, "Objective-bound escalation: continuation requires a Founder disposition bound to this exact ceiling event."
        # created / active
        return True, "objective is not escalated"
    except EvidenceError:
        return False, "Objective-bound escalation state is unavailable: action denied (fail closed)."


def evaluate_baseline(repo: Path, payload: dict[str, Any]) -> tuple[bool, str]:
    event = str(payload.get("hook_event_name") or "PreToolUse")
    if event == "ConfigChange":
        if str(payload.get("source") or "") == "policy_settings":
            return True, "managed policy settings are externally controlled"
        if os.environ.get("FOUNDER_CLAUDE_CONFIG_WRITE") == "1":
            return True, "Founder configuration gate is active"
        return False, "Claude configuration changes require explicit Founder approval and FOUNDER_CLAUDE_CONFIG_WRITE=1."
    if event != "PreToolUse":
        return False, f"Baseline hook received unsupported event {event or '[missing]'} and failed closed."

    name = ALIASES.get(str(payload.get("tool_name") or ""), str(payload.get("tool_name") or ""))
    if not name:
        return False, "PreToolUse payload did not identify a tool."
    # A10-C (Q1.3/Q3/Q4.3): objective/escalation consultation gates the
    # decision. Escalated objectives keep governed actions denied until a
    # Founder disposition for the exact ceiling event exists.
    if payload.get("objective_id") or os.environ.get("MADCLAUDE_OBJECTIVE_ID"):
        allowed, reason = consult_escalation(repo, payload)
        if not allowed:
            return False, reason
    if name in {"Bash", "PowerShell"}:
        return _baseline_shell(payload)
    if name not in FILE_TOOLS:
        # A10-A: supported-tool policy matrix — no default allow. Every
        # non-file, non-shell tool either has an explicit disposition or
        # fails closed as unrecognized.
        if name in BASELINE_META_ALLOW:
            return True, "task-management meta tool has no authority effect"
        if name in BASELINE_INSTRUCTION_ALLOW:
            return True, "Skill instruction-content loading has no authority or mutation effect"
        if name in BASELINE_DEFER:
            if os.environ.get("MADCLAUDE_CONTROL_PLANE_ACTIVE") == "1":
                return True, "delegation is governed by the control-plane route layer"
            return False, "Delegation (Agent/Task) is only permitted inside governed control-plane routes."
        if name in BASELINE_DENY or name.lower().startswith("mcp__"):
            return False, f"Tool {name} is not supported at baseline (policy matrix)."
        return False, f"Unrecognized tool {name} is denied at baseline (fail closed)."

    allowed, reason = evaluate_tool_call(
        repo=repo,
        tool_name=name,
        tool_input=_tool_input(payload),
        allowed_tools=(name,),
        mutates=True,
        scopes=("",),
    )
    if allowed:
        return True, reason
    if "authority" in reason.lower() or "protected" in reason.lower():
        if os.environ.get("FOUNDER_CLAUDE_CONFIG_WRITE") == "1":
            return True, "Founder configuration gate is active"
    return False, reason


def evaluate_sql(payload: dict[str, Any]) -> tuple[bool, str]:
    command = str(_tool_input(payload).get("command") or "").strip()
    if not command or not DATABASE_CLIENT.search(command):
        return True, "allowed"
    if re.search(r"(?:^|\s)(?:-f|--file)(?:=|\s)", command, re.I):
        return False, "SQL files are not inspectable by the read-only hook; use one bounded inline query."
    match = re.search(r"(?:^|\s)(?:-c|--command)(?:=|\s+)(['\"])([\s\S]*?)\1(?:\s|$)", command)
    if not match:
        return False, "Interactive or uninspectable database-client sessions are blocked."
    sql = re.sub(r"^\s*(?:(?:--[^\n]*\n)|(?:/\*[\s\S]*?\*/\s*))*", "", match.group(2)).strip()
    without_trailing = re.sub(r";\s*$", "", sql).strip()
    if ";" in without_trailing or re.search(r"\\[A-Za-z!]", without_trailing):
        return False, "Only one inline SQL statement without client meta-commands is allowed."
    if not re.match(r"^(?:select|with|explain|show|describe|desc|values|table|pragma)\b", without_trailing, re.I):
        return False, "The database investigator is read-only."
    forbidden = re.compile(
        r"\b(?:insert|update|delete|upsert|create|alter|drop|truncate|grant|revoke|merge|call|execute|copy|"
        r"vacuum|analyze|refresh|set|reset|lock|reindex|cluster|do|begin|commit|rollback|savepoint|release|"
        r"prepare|deallocate|listen|notify|load|comment|attach|detach)\b",
        re.I,
    )
    unsafe = re.compile(
        r"\bfor\s+(?:update|no\s+key\s+update|share|key\s+share)\b|\bselect\b[\s\S]*\binto\b|"
        r"\b(?:nextval|setval|pg_advisory_lock|pg_try_advisory_lock|pg_terminate_backend|pg_cancel_backend|"
        r"pg_reload_conf|pg_rotate_logfile|pg_create_restore_point|pg_switch_wal|pg_logical_emit_message|"
        r"dblink_exec|lo_import|lo_export|load_extension)\s*\(",
        re.I,
    )
    if forbidden.search(without_trailing) or unsafe.search(without_trailing):
        return False, "Write-capable, locking, administrative, or multi-effect SQL is blocked."
    if re.match(r"^pragma\b", without_trailing, re.I) and not re.match(
        r"^pragma\s+(?:table_info|table_xinfo|table_list|index_list|index_info|index_xinfo|foreign_key_list|"
        r"database_list|compile_options)(?:\s*\(|\s*$)",
        without_trailing,
        re.I,
    ):
        return False, "Only catalog-style read-only PRAGMA queries are allowed."
    return True, "allowed"


def evaluate_completion(repo: Path, payload: dict[str, Any]) -> tuple[bool, str]:
    if payload.get("stop_hook_active") is True:
        return True, "Reentrant Stop hook allowed to prevent a block loop."
    if os.environ.get("MADCLAUDE_CONTROL_PLANE_ACTIVE") == "1":
        return True, "Python control-plane child completion is validated by its parent route."
    state = get_state(repo)
    if state.clean:
        return True, "Repository is clean."
    evidence_root = repo / ".claude" / "evidence" / "python-control-plane"
    for manifest_path in sorted(evidence_root.glob("*/MANIFEST.json"), reverse=True):
        try:
            if _current_verification_bundle(manifest_path.parent, repo, state.head_sha):
                return True, f"Current manifested Python verification evidence: {manifest_path.parent.name}"
        except (EvidenceError, SafeReadError, OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return False, "Repository changes require current Python verification evidence before completion."


def _json_rooted(root_fd: int, relpath: str) -> dict[str, Any]:
    value = json.loads(safe_read.read_text(root_fd, relpath))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {relpath}")
    return value


def _current_verification_bundle(bundle: Path, repo: Path, head_sha: str) -> bool:
    repo_fd = safe_read.open_root(repo)
    try:
        bundle_rel = os.path.relpath(str(bundle), str(repo))
        bundle_stat = safe_read.audit_path(repo_fd, bundle_rel)
        if bundle_stat is None or not stat.S_ISDIR(bundle_stat.st_mode):
            return False
    finally:
        os.close(repo_fd)
    root_fd = safe_read.open_root(bundle)
    try:
        manifest = _json_rooted(root_fd, "MANIFEST.json")
        if manifest.get("status") != "completed" or manifest.get("evidenceSource") != "local_evidence":
            return False
        listed = manifest.get("files")
        if not isinstance(listed, list):
            return False
        expected: set[str] = set()
        for entry in listed:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                return False
            relative = entry["path"]
            data = safe_read.read_bytes(root_fd, relative)
            if entry.get("size") != len(data) or entry.get("sha256") != hashlib.sha256(data).hexdigest():
                return False
            expected.add(relative)
        record = _json_rooted(root_fd, "EXECUTION_RECORD.json")
        verification = _json_rooted(root_fd, "VERIFICATION.json")
    finally:
        os.close(root_fd)
    actual = {
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file() and not path.is_symlink() and path.name != "MANIFEST.json"
    }
    if actual != expected:
        return False

    if (
        record.get("finalStatus") != "completed"
        or record.get("finalSha") != head_sha
        or record.get("evidenceSource") != "local_evidence"
        or verification.get("headSha") != head_sha
        or verification.get("evidenceSource") != "local_evidence"
        or verification.get("workingTreeFingerprint") != working_tree_fingerprint(repo)
        or verification.get("failed")
        or verification.get("skipped")
    ):
        return False
    commands = verification.get("commands")
    if not isinstance(commands, list) or not commands or any(
        not isinstance(command, dict) or command.get("status") != "passed" for command in commands
    ):
        return False
    metadata, payload = read_canonical_artifact(bundle / "VERIFICATION.md")
    return metadata.get("head_sha") == head_sha and metadata.get("status") == "passed" and payload == verification


def evaluate_profile(repo: Path, payload: dict[str, Any], profile: str) -> tuple[bool, str]:
    if profile == "baseline":
        return evaluate_baseline(repo, payload)
    if profile == "sql":
        allowed, reason = evaluate_baseline(repo, payload)
        return evaluate_sql(payload) if allowed else (allowed, reason)
    if profile == "completion":
        return evaluate_completion(repo, payload)
    return False, f"Unknown hook profile {profile!r}."
