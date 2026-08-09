#!/usr/bin/env python3
"""Audit 9 machine-gate orchestrator (Section 6 steps 1-8 evidence).

Runs the native target gates on ONE machine and emits a per-machine evidence
JSON: architecture recorded from platform.machine() of the RUNNING
interpreter (caller-supplied or metadata arch strings are never accepted),
CPython version, artifact SHA-256, every step's command + exit code, the lock
file used, installed inventory, launcher self-test and protocol-test results.
Evidence sources are reported with B3-conformant sources[] entries (computed
hashes are never presented as declared, and vice versa).

--self-check performs host-neutral dry validation of the gate definition and
evidence writer without running any step.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "python-control-plane" / "src"
TESTS = ROOT / "python-control-plane" / "tests"

STEP_HARNESS = "local-harness"
STEP_WHEELHOUSE = "wheelhouse-lock-generation"
STEP_INSTALL = "offline-release-install"
STEP_ENABLE = "atomic-enable"
STEP_SELF_TEST = "staged-launcher-self-test"
STEP_PROTOCOL = "protocol-roundtrip"
STEP_STDIO = "fastmcp-stdio-roundtrip"
STEP_VERB_CYCLE = "verb-cycle"


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _b3_source(path: Path) -> dict:
    """B3-conformant sources[] entry: computed physical hash, no declared target."""
    return {
        "path": str(path),
        "source_sha256": _sha256_path(path),
        "declared_manifest_sha256": None,
        "hash_provenance": "computed",
        "target_match": "no_target",
        "verified": False,
    }


def _run_step(name: str, command: list[str], *, cwd: Path, env: dict[str, str] | None = None,
              timeout: int = 900) -> dict:
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    return {
        "step": name,
        "command": command,
        "exitCode": completed.returncode,
        "stdoutTail": completed.stdout[-2000:],
        "stderrTail": completed.stderr[-2000:],
    }


def build_evidence(*, machine: str, steps: list[dict], extra: dict, sources: list[dict]) -> dict:
    return {
        "schemaVersion": 1,
        "gate": "audit9-target-gate",
        "machine": machine,
        "platformMachine": platform.machine(),  # recorded from the running interpreter, never from arguments
        "pythonVersion": platform.python_version(),
        "pythonImplementation": platform.python_implementation(),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
        "sources": sources,
        **extra,
    }


def self_check() -> int:
    """Host-neutral dry validation: gate structure, arch provenance, evidence writer."""
    problems = []
    for step in (
        STEP_HARNESS, STEP_WHEELHOUSE, STEP_INSTALL, STEP_ENABLE,
        STEP_SELF_TEST, STEP_PROTOCOL, STEP_STDIO, STEP_VERB_CYCLE,
    ):
        if not step:
            problems.append("empty step name")
    evidence = build_evidence(machine="self-check", steps=[], extra={}, sources=[])
    required = {"schemaVersion", "machine", "platformMachine", "pythonVersion", "steps", "sources"}
    missing = required - evidence.keys()
    if missing:
        problems.append(f"evidence schema missing keys: {sorted(missing)}")
    with tempfile.TemporaryDirectory() as temp:
        probe = Path(temp) / "probe.bin"
        probe.write_bytes(b"gate-probe\n")
        source = _b3_source(probe)
        if source["hash_provenance"] != "computed" or source["verified"] is not False:
            problems.append("B3 source entry is not computed/unverified for an undeclared target")
        out = Path(temp) / "evidence.json"
        out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if json.loads(out.read_text(encoding="utf-8"))["machine"] != "self-check":
            problems.append("evidence writer round trip failed")
    if problems:
        for problem in problems:
            print(f"SELF-CHECK FAILED: {problem}", file=sys.stderr)
        return 2
    print("audit9-target-gate self-check ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true", help="Host-neutral dry validation only.")
    parser.add_argument("--home", type=Path, help="Isolated MADCLAUDE_HOME test root (required unless --self-check).")
    parser.add_argument("--output", type=Path, help="Evidence JSON output path.")
    parser.add_argument("--artifact", type=Path, help="Built archive whose SHA-256 is recorded in evidence.")
    parser.add_argument("--skip-download", action="store_true", help="Finalize an existing wheelhouse (offline).")
    parser.add_argument("--wheelhouse", type=Path, help="Reuse an existing wheelhouse directory.")
    parser.add_argument(
        "--test-only-fabricated-wheelhouse",
        action="store_true",
        help=(
            "TEST ONLY: permit the real mcp==2.0.0 SDK stdio step to skip when the wheelhouse "
            "is fabricated. The emitted evidence is marked evidenceClass=test-only-fabricated-"
            "wheelhouse and releaseEvidence=false. Without this flag a release-target run FAILS "
            "when the real SDK stdio roundtrip cannot run."
        ),
    )
    args = parser.parse_args(argv)
    if args.self_check:
        return self_check()
    if not args.home:
        print("--home is required (isolated MADCLAUDE_HOME test root)", file=sys.stderr)
        return 2

    arch = platform.machine()  # native execution evidence; never from arguments
    home = args.home.expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True)
    wheelhouse = (args.wheelhouse or (home / "wheelhouse")).resolve()
    # Sanitized env: strip host Python-environment overrides so the Hermes
    # Python 3.11 venv or any other host Python cannot contaminate the gate.
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PIP_TARGET")
    }
    env["MADCLAUDE_HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cli_env = {**env, "PYTHONPATH": str(SRC)}
    steps: list[dict] = []

    # Base control-plane launcher shim for the externally verified launch path
    # (in a real install this is the stable madclaude launcher; here it execs
    # the source-tree CLI). The wrapper must never fall back to a host install.
    shim = home / "bin" / "madclaude"
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(
        "#!/bin/sh\n"
        f"PYTHONPATH='{SRC}' MADCLAUDE_HOME='{home}' "
        f"exec '{sys.executable}' -m madclaude.cli \"$@\"\n",
        encoding="utf-8",
    )
    shim.chmod(0o700)

    steps.append(_run_step(STEP_HARNESS, [sys.executable, "-I", "-B", "python-control-plane/run-tests.py"], cwd=ROOT, env=env))
    wheelhouse_command = [
        sys.executable, "scripts/mcp-wheelhouse.py",
        "--wheelhouse", str(wheelhouse), "--arch", arch,
    ]
    if args.skip_download:
        wheelhouse_command.append("--no-download")
    steps.append(_run_step(STEP_WHEELHOUSE, wheelhouse_command, cwd=ROOT, env=env))

    lock = wheelhouse / f"requirements-cp314-macos-{arch}.lock"
    failed = next((step for step in steps if step["exitCode"] != 0), None)
    release = None
    if failed is None:
        install = _run_step(
            STEP_INSTALL,
            [sys.executable, "-m", "madclaude.cli", "mcp", "install",
             "--wheelhouse", str(wheelhouse), "--lock", str(lock), "--arch", arch, "--home", str(home), "--json"],
            cwd=ROOT, env=cli_env,
        )
        steps.append(install)
        if install["exitCode"] == 0:
            try:
                release = json.loads(install["stdoutTail"])["release"]
            except (json.JSONDecodeError, KeyError) as exc:
                steps.append({
                    "step": STEP_INSTALL + "-parse",
                    "command": ["<parse install stdout>"],
                    "exitCode": 1,
                    "stdoutTail": "",
                    "stderrTail": f"could not parse release from install output: {exc}",
                })
                release = None
        if release:
            # Pre-activation: base-orchestrated staged self-test (the base
            # verifies the staged release before its interpreter runs).
            steps.append(_run_step(
                STEP_SELF_TEST,
                [sys.executable, "-m", "madclaude.cli", "mcp", "self-test",
                 "--release", release, "--home", str(home), "--json"],
                cwd=ROOT, env=cli_env,
            ))
            steps.append(_run_step(
                STEP_ENABLE,
                [sys.executable, "-m", "madclaude.cli", "mcp", "enable", "--release", release, "--home", str(home), "--json"],
                cwd=ROOT, env=cli_env,
            ))
            steps.append(_run_step(
                STEP_PROTOCOL,
                [sys.executable, "-c", _PROTOCOL_PROBE, release, str(home)],
                cwd=ROOT, env=cli_env,
            ))
            steps.append(_run_step(
                STEP_STDIO,
                [sys.executable, "-c", _STDIO_PROBE, str(home), release,
                 "allow-fabricated" if args.test_only_fabricated_wheelhouse else "require-real-sdk"],
                cwd=ROOT, env=cli_env,
                timeout=120,
            ))
            for verb in ("disable", "re-enable", "status"):
                verb_command = [sys.executable, "-m", "madclaude.cli", "mcp", verb, "--home", str(home), "--json"]
                if verb == "status":
                    verb_command.insert(-3, "--deep")
                steps.append(_run_step(STEP_VERB_CYCLE + f"-{verb}", verb_command, cwd=ROOT, env=cli_env))

    inventory = {}
    if release:
        integrity = json.loads((Path(release) / "RELEASE_INTEGRITY.json").read_text(encoding="utf-8"))
        inventory = integrity.get("installed_inventory", {})
    sources = [_b3_source(lock)] if lock.is_file() else []
    if args.artifact and args.artifact.is_file():
        sources.append(_b3_source(args.artifact))
    extra = {
        "architecture": arch,
        "evidenceClass": (
            "test-only-fabricated-wheelhouse" if args.test_only_fabricated_wheelhouse else "release-target"
        ),
        "releaseEvidence": not args.test_only_fabricated_wheelhouse,
        "artifactSha256": _sha256_path(args.artifact) if args.artifact and args.artifact.is_file() else None,
        "lockFile": str(lock) if lock.is_file() else None,
        "installedInventory": inventory,
        "release": release,
    }
    evidence = build_evidence(machine=platform.node() or "unknown", steps=steps, extra=extra, sources=sources)
    output = args.output or (home / f"audit9-target-gate-{arch}.json")
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    failures = [step["step"] for step in steps if step["exitCode"] != 0]
    if failures:
        print(f"gate failed at: {', '.join(failures)}", file=sys.stderr)
        return 1
    print(f"audit9 target gate passed natively on {arch}")
    return 0


_PROTOCOL_PROBE = """
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "app"))
from madclaude.mcp_server import ServerContext, handle_jsonrpc
context = ServerContext(home=Path(sys.argv[2]), release_dir=Path(sys.argv[1]))
init = handle_jsonrpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, context)
listed = handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, context)
tools = [tool["name"] for tool in listed["result"]["tools"]]
expected = ["control_plane_status", "routes_list", "evidence_index", "evidence_read", "request_verification"]
if tools != expected:
    raise SystemExit(f"protocol roundtrip FAILED: tools list mismatch: {tools!r}")
if init["result"]["serverInfo"]["authority"] != "non-authoritative":
    raise SystemExit(f"protocol roundtrip FAILED: server authority is not non-authoritative: {init!r}")
called = handle_jsonrpc(
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "control_plane_status", "arguments": {}}},
    context,
)
if called["result"]["structuredContent"]["authority"] != "non-authoritative":
    raise SystemExit(f"protocol roundtrip FAILED: tools/call authority is not non-authoritative: {called!r}")
print("protocol roundtrip ok: initialize/tools-list/tools-call with non-authoritative authority")
"""


_STDIO_PROBE = """
import json, selectors, subprocess, sys, time
from pathlib import Path

home = Path(sys.argv[1])
release = Path(sys.argv[2])
mode = sys.argv[3]
venv_python = release / "venv" / "bin" / "python"

check = subprocess.run(
    [str(venv_python), "-c", "import importlib.util; print(importlib.util.find_spec('mcp.server.mcpserver') is not None)"],
    capture_output=True, text=True, check=False,
)
if check.stdout.strip() != "True":
    if mode == "allow-fabricated":
        print("fastmcp-stdio: SKIPPED (TEST ONLY, non-release evidence) — fabricated wheelhouse without "
              "the real mcp SDK (no mcp.server.mcpserver)")
        raise SystemExit(0)
    print("fastmcp-stdio: FAILED — the real mcp==2.0.0 SDK stdio roundtrip cannot run against this "
          "wheelhouse; release-target evidence requires it (fail closed, no false green)", file=sys.stderr)
    raise SystemExit(2)

wrapper = home / "bin" / "madclaude-mcp-server"
proc = subprocess.Popen(
    ["/bin/sh", str(wrapper)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.PIPE, text=True, bufsize=1,
)
selector = selectors.DefaultSelector()
selector.register(proc.stdout, selectors.EVENT_READ)

def send(payload):
    proc.stdin.write(json.dumps(payload) + "\\n")
    proc.stdin.flush()

def recv(timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events = selector.select(deadline - time.monotonic())
        if events:
            line = proc.stdout.readline()
            if line:
                return json.loads(line)
    raise SystemExit("fastmcp-stdio: timed out waiting for the server")

try:
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                     "clientInfo": {"name": "audit9-gate", "version": "0"}}})
    init = recv()
    if init.get("result", {}).get("serverInfo", {}).get("name") != "madclaude-local-control-plane":
        raise SystemExit(f"fastmcp-stdio FAILED: unexpected serverInfo: {init!r}")
    send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    listed = recv()
    tools = sorted(tool["name"] for tool in listed["result"]["tools"])
    expected_tools = sorted(["control_plane_status", "routes_list", "evidence_index",
                             "evidence_read", "request_verification"])
    if tools != expected_tools:
        raise SystemExit(f"fastmcp-stdio FAILED: tools list mismatch: {tools!r}")
    send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
          "params": {"name": "control_plane_status", "arguments": {}}})
    called = recv()
    content = called["result"]["structuredContent"]
    if content["authority"] != "non-authoritative":
        raise SystemExit(f"fastmcp-stdio FAILED: authority is not non-authoritative: {content!r}")
    print("real-mcp-stdio ok: real mcp 2.0.0 SDK stdio roundtrip through the stable wrapper")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
"""


if __name__ == "__main__":
    raise SystemExit(main())
