"""Optional MCP release lifecycle (B1 Stage 2 + B2).

Builds an isolated, versioned MCP release under $MADCLAUDE_HOME/mcp-releases/
from reviewed wheelhouse inputs, fully offline, and generates the integrity
manifests. Approved truthful description of the result:

    Versioned, self-contained application payload with an isolated dependency
    environment; the verified host CPython 3.14 interpreter remains an external
    runtime dependency.

External verification anchor (Audit 9 remediation): the SHA-256 of every
release's RELEASE_INTEGRITY.json is recorded in the installation-state record,
which lives OUTSIDE the versioned release. The sanctioned launch path is
stable wrapper -> base control plane `mcp serve` -> externally anchored
prelaunch verification -> only then exec of release-owned code. No
release-owned launcher, shell, Python module, or mutable integrity document
executes before that externally anchored verification succeeds.

Durability claim: atomic visibility only. Parent-directory fsync is not
implemented, so no crash/power-loss durability claim is made anywhere.

Trusted bootstrap assumption: the stable wrapper, the base control plane, the
installation-state record, and the host interpreter are trusted inputs. This
module does not protect against a malicious local account owner or a
root-level attacker, and claims no OS-enforced immutability.
"""

from __future__ import annotations

import base64
import contextlib
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

# macOS-only scope (Audit 9): the POSIX lifecycle lock is loaded lazily
# inside the supported MCP lifecycle path, never unconditionally at import.
# Importing this module on an unsupported platform must not crash unrelated
# CLI operations.
try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - non-POSIX platforms
    _fcntl = None

from . import safe_read
from .errors import PolicyViolation, SafeReadError
from .evidence import _atomic_write

MCP_VERSION = "2.0.0"
PYTHON_TAG = "cp314"
_RELEASE_PREFIX = f"mcp-{MCP_VERSION}"

# Release dependency verification read cap.  The default safe_read cap
# (16 MiB) is a DoS guard for governance reads; real native wheels routinely
# ship .so payloads far larger (e.g. cryptography's _rust.abi3.so is ~23 MiB).
# The bytes read here are verified against externally anchored RECORD hashes,
# so a larger cap is not a security boundary — it is the size of the payload
# being authenticated.
RELEASE_VERIFY_MAX_BYTES = 512 * 1024 * 1024

# Distributions a fresh venv provides before the lock is installed. The
# installed inventory contract is bootstrap PLUS lock, exact equality both
# ways: anything beyond the lock that is not a recorded bootstrap
# distribution fails closed, at install and at every prelaunch.
BOOTSTRAP_DISTRIBUTIONS = frozenset({"pip"})

_VENV_PROBE = """
import importlib.metadata as metadata
import json
import os
import platform
import sys
import sysconfig
dists = sorted(
    (dist.metadata["Name"], dist.version)
    for dist in metadata.distributions()
    if dist.metadata["Name"]
)
print(json.dumps({
    "dists": dists,
    "purelib": sysconfig.get_paths()["purelib"],
    "base_prefix": os.path.realpath(sys.base_prefix),
    "base_executable": os.path.realpath(sys._base_executable),
    "python_version": platform.python_version(),
}))
"""


def _split_inventory(dists: list[list[str]]) -> tuple[dict[str, str], dict[str, str]]:
    """Split a probed inventory into (installed, bootstrap): bootstrap holds
    exactly BOOTSTRAP_DISTRIBUTIONS, installed holds everything else."""
    inventory = {_normalize(name): version for name, version in dists}
    bootstrap = {name: version for name, version in inventory.items() if name in BOOTSTRAP_DISTRIBUTIONS}
    installed = {name: version for name, version in inventory.items() if name not in BOOTSTRAP_DISTRIBUTIONS}
    return installed, bootstrap


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def release_identity(package_version: str, source_sha256: str) -> str:
    return f"{_RELEASE_PREFIX}-{package_version}-{source_sha256[:12]}"


def releases_root(home: Path) -> Path:
    return home / "mcp-releases"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_lock(lock_file: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in lock_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(
            r"^([A-Za-z0-9_.-]+)==([^\s]+)((?:\s+--hash=sha256:[0-9a-f]{64})+)$", line
        )
        if not match:
            raise PolicyViolation(
                f"Lock file line is not a hashed exact pin (required under --require-hashes): {line!r}"
            )
        name = _normalize(match.group(1))
        if name in entries:
            raise PolicyViolation(f"Lock file pins the same distribution twice: {name}")
        entries[name] = match.group(2)
    if not entries:
        raise PolicyViolation(f"Lock file contains no pinned distributions: {lock_file}")
    if entries.get("mcp") != MCP_VERSION:
        raise PolicyViolation(f"Lock file must pin mcp=={MCP_VERSION}: {lock_file}")
    return entries


def _offline_env(home: Path) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_REQUIRE_HASHES": "1",
        # The app payload is byte-frozen for integrity; nothing under the
        # release may ever write bytecode into it.
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    for passthrough in ("TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL"):
        if os.environ.get(passthrough):
            env[passthrough] = os.environ[passthrough]
    # Offline enforcement: no proxy variables, ever.
    for name in list(env):
        if name.lower().endswith("_proxy"):
            del env[name]
    return env


def _run(command: list[str], *, env: dict[str, str], description: str) -> subprocess.CompletedProcess:
    completed = subprocess.run(command, env=env, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:400]
        raise PolicyViolation(f"{description} failed (exit {completed.returncode}): {detail}")
    return completed


def _venv_python(venv: Path) -> Path:
    return venv / "bin" / "python"


def _probe_venv(venv: Path, home: Path) -> dict[str, Any]:
    completed = _run(
        [str(_venv_python(venv)), "-c", _VENV_PROBE], env=_offline_env(home), description="release venv probe"
    )
    return json.loads(completed.stdout)


def _clean_bytecode(venv_root: Path) -> None:
    """Remove __pycache__ directories and *.pyc files from the venv so the
    byte-frozen release payload carries no bytecode artifacts."""
    for path in venv_root.rglob("__pycache__"):
        shutil.rmtree(path, ignore_errors=True)
    for path in venv_root.rglob("*.pyc"):
        path.unlink(missing_ok=True)


def _normalize_pyvenv_cfg(cfg_path: Path) -> None:
    """Strip the informational `command =` line from pyvenv.cfg so its bytes
    are deterministic across equivalent installations.

    The `command` key records the exact venv-creation argv, which embeds the
    unique staging path — inherently per-install.  Every security-relevant
    field (home, include-system-site-packages, version, executable) is
    preserved.  The normalized bytes are what the release anchors and
    authenticates at prelaunch, so a tampered pyvenv.cfg still fails closed
    while two equivalent installs produce identical integrity evidence."""
    if not cfg_path.is_file():
        return
    lines = cfg_path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not line.strip().lower().startswith("command =")]
    cfg_path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _copy_app(app_source: Path, staging: Path) -> None:
    destination = staging / "app" / "madclaude"
    destination.mkdir(parents=True)
    for path in sorted(app_source.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            relative = path.relative_to(app_source)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


def _app_manifest(app_dir: Path) -> dict[str, Any]:
    root_fd = safe_read.open_root(app_dir)
    try:
        files = []
        for path in sorted(app_dir.rglob("*")):
            if path.is_file() and not path.is_symlink():
                relative = path.relative_to(app_dir).as_posix()
                data = safe_read.read_bytes(root_fd, relative)
                files.append({"path": relative, "size": len(data), "sha256": _sha256_bytes(data)})
        return {"schemaVersion": 1, "files": files}
    finally:
        os.close(root_fd)


def _write_launcher(staging: Path) -> Path:
    launcher_dir = staging / "launcher"
    launcher_dir.mkdir()
    launcher = launcher_dir / "mcp-server"
    content = (
        "#!/bin/sh\n"
        "# MCP release launcher: stdio transport only, integrity-gated.\n"
        "# The app payload is byte-frozen for integrity; never write bytecode into it.\n"
        "export PYTHONDONTWRITEBYTECODE=1\n"
        'RELEASE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"\n'
        'exec "$RELEASE_DIR/venv/bin/python" -c \'import sys; sys.path.insert(0, sys.argv[1]); '
        'from madclaude.mcp_server import main; raise SystemExit(main())\' "$RELEASE_DIR/app" "$@"\n'
    )
    launcher.write_text(content, encoding="utf-8")
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return launcher


def _parse_record_rows(data: bytes) -> dict[str, str]:
    """Parse a dist-info RECORD into its in-scope rows. Rows outside purelib
    (entry-point scripts under bin/) are venv scaffolding, not distribution
    payload: out of scope for verification, and install-layout-dependent, so
    they are excluded."""
    rows: dict[str, str] = {}
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        parts = next(csv.reader([line]))
        relative = parts[0]
        row_parts = PurePosixPath(relative).parts
        if any(part in ("", ".", "..") for part in row_parts) or "\\" in relative:
            continue
        rows[relative] = parts[1] if len(parts) > 1 else ""
    return rows


def _canonical_record_hash(rows: dict[str, str]) -> str:
    """Deterministic evidence hash over the in-scope RECORD rows, independent
    of the install layout (generated entry-point script rows are excluded)."""
    return _sha256_bytes("\n".join(f"{key},{value}" for key, value in sorted(rows.items())).encode("utf-8"))


def _record_evidence(purelib: Path, lock_entries: dict[str, str]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for name, version in sorted(lock_entries.items()):
        dist_info = purelib / f"{name.replace('-', '_')}-{version}.dist-info"
        record = dist_info / "RECORD"
        if not record.is_file():
            raise PolicyViolation(f"Installed distribution is missing dist-info RECORD evidence: {name}")
        record_rows = _parse_record_rows(record.read_bytes())
        evidence[name] = {
            "version": version,
            "record": str(record.relative_to(purelib)),
            "record_sha256": _canonical_record_hash(record_rows),
            "files": record_rows,
        }
    return evidence


def _record_hash(data: bytes) -> str:
    """Wheel RECORD hash format: sha256=<urlsafe-base64-nopad>."""
    return "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii").rstrip("=")


def _validated_purelib_relative(integrity: dict[str, Any]) -> str:
    purelib_relative = integrity["purelib"]
    purelib_parts = PurePosixPath(purelib_relative).parts
    if (
        PurePosixPath(purelib_relative).is_absolute()
        or any(part in ("", ".", "..") for part in purelib_parts)
        or "\\" in purelib_relative
    ):
        raise PolicyViolation(f"Release purelib layout is not a clean relative path: {purelib_relative!r}")
    return purelib_relative


def _record_level_drift(release_dir: Path, integrity: dict[str, Any], *, executable_only: bool) -> list[str]:
    """Shared RECORD-level verification core.

    executable_only=False (status --deep): every in-scope hashed RECORD row is
    re-verified; divergence is reported as drift (remedy: reinstall).
    executable_only=True (R6-03 pre-execution tier): ALL RECORD-covered files
    are hash-verified (not just *.py), PLUS complete membership — every
    regular file beneath purelib (including .so, .pth, .pyc, sitecustomize.py)
    must be a recorded RECORD row, so any dropped or added interpreter-consumed
    payload is caught before the release interpreter runs.
    Declared hashes come from the externally anchored integrity document,
    never from the mutable on-disk RECORD; the physical RECORD file itself is
    re-hashed against its recorded evidence hash. Reads are descriptor-relative
    beneath the venv root."""
    venv_root = release_dir / "venv"
    purelib_relative = _validated_purelib_relative(integrity)
    records = dict(integrity.get("bootstrap_records", {}))
    records.update(integrity["installed_records"])
    venv_fd = safe_read.open_root(venv_root)
    try:
        drift: list[str] = []
        declared_files: set[str] = set()
        for name, record in sorted(records.items()):
            try:
                record_data = safe_read.read_bytes(
                    venv_fd, f"{purelib_relative}/{record['record']}", max_bytes=RELEASE_VERIFY_MAX_BYTES
                )
            except SafeReadError:
                drift.append(f"{name}: dist-info RECORD evidence is missing, symlinked, or not a regular file")
                continue
            if _canonical_record_hash(_parse_record_rows(record_data)) != record["record_sha256"]:
                drift.append(f"{name}: dist-info RECORD evidence diverges from the anchored integrity record")
            for relative, declared in sorted(record["files"].items()):
                relative_parts = PurePosixPath(relative).parts
                if any(part in ("", ".", "..") for part in relative_parts) or "\\" in relative:
                    # RECORD rows outside purelib (e.g. ../../bin/ entry-point
                    # scripts) are venv scaffolding, not distribution payload;
                    # they are out of this check's scope, as before.
                    continue
                declared_files.add(relative)
                if not declared.startswith("sha256="):
                    continue
                try:
                    data = safe_read.read_bytes(
                        venv_fd, f"{purelib_relative}/{relative}", max_bytes=RELEASE_VERIFY_MAX_BYTES
                    )
                except SafeReadError:
                    drift.append(f"{name}: missing, symlinked, or non-regular installed file {relative}")
                    continue
                if _record_hash(data) != declared:
                    drift.append(f"{name}: installed file hash drift at {relative}")
        if executable_only:
            # P0: complete membership — every regular file beneath purelib must
            # be a recorded RECORD row.  This catches .so, .pth, .pyc,
            # sitecustomize.py, and any other interpreter-consumed payload
            # that was dropped in but not in the RECORD.
            purelib = venv_root / purelib_relative
            for path in sorted(purelib.rglob("*")) if purelib.is_dir() else []:
                if not path.is_file() or path.is_symlink():
                    continue
                if "__pycache__" in path.parts:
                    drift.append(f"unrecorded bytecode cache beneath purelib: {path.relative_to(purelib).as_posix()}")
                    continue
                relative = path.relative_to(purelib).as_posix()
                if relative not in declared_files:
                    drift.append(f"unrecorded interpreter-consumed payload beneath purelib: {relative}")
        return drift
    finally:
        os.close(venv_fd)


def verify_record_level(release_dir: Path) -> list[str]:
    """Re-verify every installed distribution file against its RECORD hashes.
    Returns a list of drift descriptions (empty means verified). Venv content
    divergence found this way is drift detection, not prevention; the remedy
    is reinstall. Reads are descriptor-relative beneath the venv root."""
    integrity = _load_integrity(release_dir)
    return _record_level_drift(release_dir, integrity, executable_only=False)


def _verify_dependency_bytes(release_dir: Path, integrity: dict[str, Any]) -> None:
    """R6-03: base-owned verification of the release's dependency bytes BEFORE
    the release interpreter is ever invoked. Uses the externally anchored
    integrity record and descriptor-relative reads to verify the recorded
    relative purelib location, the installed RECORD evidence, every in-scope
    executable distribution file and hash (plus membership, so unrecorded
    executable payload such as a dropped sitecustomize.py fails closed), the
    venv interpreter/symlink relationship, and the external base-interpreter
    identity and SHA-256. The release interpreter is never used to establish
    its own trust; only after this succeeds may it run."""
    venv_root = release_dir / "venv"
    purelib_relative = _validated_purelib_relative(integrity)
    if not (venv_root / purelib_relative).is_dir():
        raise PolicyViolation(f"Release purelib is missing beneath the venv: {purelib_relative}")
    drift = _record_level_drift(release_dir, integrity, executable_only=True)
    if drift:
        raise PolicyViolation(
            "Executable dependency payload diverges from the externally anchored RECORD evidence "
            f"(fail closed before any release-owned Python runs; remedy: reinstall): {'; '.join(drift[:5])}"
        )
    interpreter = integrity["interpreter"]
    venv_python = _venv_python(venv_root)
    if not venv_python.is_file():
        raise PolicyViolation("Release venv interpreter entry is missing")
    actual_base = os.path.realpath(venv_python)
    if actual_base != interpreter["base_executable"]:
        raise PolicyViolation(
            "Release venv interpreter/symlink relationship changed: the venv entry point no "
            "longer resolves to the recorded external base interpreter"
        )
    if _sha256_path(Path(actual_base)) != interpreter["base_executable_sha256"]:
        raise PolicyViolation("Release base interpreter binary changed")
    venv_fd = safe_read.open_root(venv_root)
    try:
        try:
            cfg = safe_read.read_bytes(venv_fd, "pyvenv.cfg")
        except SafeReadError:
            raise PolicyViolation("Release venv is missing a regular pyvenv.cfg") from None
    finally:
        os.close(venv_fd)
    # P0: authenticate the EXACT pyvenv.cfg bytes, not just the presence of
    # a 'home' key.  A modified pyvenv.cfg can redirect the interpreter or
    # inject settings that change execution behavior.
    expected_cfg_sha = integrity.get("pyvenv_cfg_sha256")
    if expected_cfg_sha is None:
        raise PolicyViolation("Release integrity record is missing pyvenv.cfg SHA-256")
    if _sha256_bytes(cfg) != expected_cfg_sha:
        raise PolicyViolation("Release venv pyvenv.cfg diverges from its anchored integrity hash")


def _parse_integrity(data: bytes) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PolicyViolation(f"Release integrity file is invalid: {exc}") from exc
    if not isinstance(value, dict):
        raise PolicyViolation("Release integrity file must contain an object.")
    missing = sorted(
        {"hashes", "app_manifest", "installed_inventory", "bootstrap_inventory", "interpreter", "identity"}
        - value.keys()
    )
    if missing:
        raise PolicyViolation(f"Release integrity file is missing required sections {missing}")
    return value


def _read_integrity_buffer(root_fd: int) -> tuple[dict[str, Any], bytes]:
    """Read RELEASE_INTEGRITY.json once; parse from the single buffer the
    caller may also hash for the external anchor check."""
    try:
        data, _info = safe_read.open_verified_leaf(root_fd, "RELEASE_INTEGRITY.json")
    except SafeReadError as exc:
        raise PolicyViolation(f"Release integrity file is missing or unreadable: {exc}") from exc
    return _parse_integrity(data), data


def _load_integrity(release_dir: Path) -> dict[str, Any]:
    root_fd = safe_read.open_root(release_dir)
    try:
        return _read_integrity_buffer(root_fd)[0]
    finally:
        os.close(root_fd)


def verify_release_prelaunch(
    release_dir: Path, *, home: Path | None = None, require_anchor: bool = True
) -> dict[str, Any]:
    """Fail-closed pre-launch verification tier.

    R6-02 ordering: the trusted release identity is release_dir.name — an
    identity read from release-owned content is NEVER used to select the
    external anchor. The physical RELEASE_INTEGRITY.json bytes are
    descriptor-read exactly once, hashed, and compared with the externally
    stored anchor BEFORE any JSON parsing; only after the anchor matches is
    the document parsed, and then it must satisfy integrity["identity"] ==
    release_dir.name, state ownership of that same identity, and (when the
    current pointer names it) resolution to this same release. Every mismatch
    fails closed.

    R6-03 ordering: after the recorded app/launcher/lock hashes and app
    membership are re-verified against disk, the executable dependency payload
    and the venv/base-interpreter relationship are verified by base-owned code
    BEFORE the release interpreter is invoked for the inventory probe.

    require_anchor=False exists only for the install-time staging check and
    the base-orchestrated staged self-test, where no anchor can exist yet;
    every launch path requires the anchor."""
    home = home or release_dir.parent.parent
    root = releases_root(home)
    resolved = release_dir.resolve()
    root_fd = safe_read.open_root(release_dir)
    try:
        # Trusted identity: the directory name beneath mcp-releases/.
        safe_read.validate_component(release_dir.name)
        identity = release_dir.name
        if require_anchor and resolved.parent != root.resolve():
            raise PolicyViolation(f"Release directory is not an owned entry beneath {root}: {release_dir.name!r}")
        # Descriptor-read the physical bytes once; the same buffer is hashed
        # for the anchor check and (only afterwards) parsed.
        try:
            integrity_bytes, _info = safe_read.open_verified_leaf(root_fd, "RELEASE_INTEGRITY.json")
        except SafeReadError as exc:
            raise PolicyViolation(f"Release integrity file is missing or unreadable: {exc}") from exc
        state = _load_state(home) if require_anchor else None
        if require_anchor:
            if state is None:
                raise PolicyViolation("Installation-state record could not be loaded for anchored verification.")
            anchors = state.get("integrityAnchors")
            anchor = anchors.get(identity) if isinstance(anchors, dict) else None
            if not isinstance(anchor, str):
                raise PolicyViolation(
                    f"No external integrity anchor is recorded for {identity!r}; reinstall the release."
                )
            if _sha256_bytes(integrity_bytes) != anchor:
                raise PolicyViolation(
                    f"Release integrity document diverges from its external anchor for {identity!r} "
                    "(fail closed; the mutable in-release document is never trusted on its own)"
                )
        integrity = _parse_integrity(integrity_bytes)
        if require_anchor:
            if state is None:
                raise PolicyViolation("Installation-state record could not be loaded for anchored verification.")
            if integrity["identity"] != identity:
                raise PolicyViolation(
                    f"Release integrity identity {integrity['identity']!r} does not match the trusted "
                    f"directory identity {identity!r} (fail closed)"
                )
            if identity not in state["releases"]:
                raise PolicyViolation(f"Release {identity!r} is not owned by the installation-state record.")
            current = root / "current"
            if current.is_symlink() and os.readlink(current) == identity and current.resolve() != resolved:
                raise PolicyViolation(
                    f"MCP current pointer names {identity!r} but resolves elsewhere (fail closed)"
                )
        for relative in sorted(integrity["hashes"]):
            data = safe_read.read_bytes(root_fd, relative)
            if _sha256_bytes(data) != integrity["hashes"][relative]:
                raise PolicyViolation(f"Release file hash mismatch: {relative}")
    finally:
        os.close(root_fd)
    # app membership: files present but absent from APP_MANIFEST.json fail closed
    app_dir = release_dir / "app"
    app_fd = safe_read.open_root(app_dir)
    try:
        manifest = integrity["app_manifest"]
        expected = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
        actual_files = {
            path.relative_to(app_dir).as_posix()
            for path in app_dir.rglob("*")
            if path.is_file() and not path.is_symlink()
        }
        if set(expected) != actual_files:
            raise PolicyViolation("Release app/ membership diverges from APP_MANIFEST.json (fail closed)")
        for relative, declared in expected.items():
            if _sha256_bytes(safe_read.read_bytes(app_fd, relative)) != declared:
                raise PolicyViolation(f"Release app file hash mismatch: {relative}")
    finally:
        os.close(app_fd)
    # R6-03: executable dependency bytes and the venv/base-interpreter
    # relationship verify BEFORE the release interpreter runs below.
    _verify_dependency_bytes(release_dir, integrity)
    probe = _probe_venv(release_dir / "venv", home)
    installed, bootstrap = _split_inventory(probe["dists"])
    if installed != integrity["installed_inventory"]:
        raise PolicyViolation(
            f"Installed distribution inventory diverges from the release lock: "
            f"expected {integrity['installed_inventory']!r}, found {installed!r}"
        )
    if bootstrap != integrity["bootstrap_inventory"]:
        raise PolicyViolation(
            f"Bootstrap distribution inventory diverges from the release record: "
            f"expected {integrity['bootstrap_inventory']!r}, found {bootstrap!r}"
        )
    interpreter = integrity["interpreter"]
    if probe["base_prefix"] != interpreter["base_prefix"]:
        raise PolicyViolation("Release base interpreter prefix changed")
    if probe["python_version"] != interpreter["python_version"]:
        raise PolicyViolation("Release interpreter version changed")
    if _sha256_path(Path(probe["base_executable"])) != interpreter["base_executable_sha256"]:
        raise PolicyViolation("Release base interpreter binary changed")
    return integrity


def install_release(
    *,
    home: Path,
    app_source: Path,
    wheelhouse: Path,
    lock_file: Path,
    architecture: str,
    python: str,
    package_version: str,
    source_manifest: Path,
) -> Path:
    """B1 Stage 2 + B2: offline build of mcp-releases/<identity>/ from reviewed
    inputs. Any failure removes only the uniquely-named staging directory; a
    prior active release is never touched."""
    lock_entries = _parse_lock(lock_file)
    if architecture != platform.machine():
        raise PolicyViolation(
            f"Release installs run natively per target: --arch {architecture} does not match "
            f"this interpreter's platform.machine() {platform.machine()}"
        )
    expected_lock_name = f"requirements-{PYTHON_TAG}-macos-{architecture}.lock"
    if lock_file.name != expected_lock_name:
        raise PolicyViolation(
            f"Target lock file must be named {expected_lock_name!r} for this target: {lock_file.name!r}"
        )
    wheelhouse_manifest_path = wheelhouse / "WHEELHOUSE_MANIFEST.json"
    if not wheelhouse_manifest_path.is_file():
        merged_manifest = wheelhouse / "MERGED_WHEELHOUSE_MANIFEST.json"
        if merged_manifest.is_file():
            wheelhouse_manifest_path = merged_manifest
        else:
            raise PolicyViolation(f"Wheelhouse manifest is missing: {wheelhouse_manifest_path}")
    source_sha256 = _sha256_path(source_manifest)
    identity = release_identity(package_version, source_sha256)
    root = releases_root(home)
    staging = root / f".staging.{uuid.uuid4().hex}"
    final = root / identity
    published = False
    with _lifecycle_lock(home):
        root.mkdir(parents=True, exist_ok=True)
        try:
            staging.mkdir()
            _copy_app(app_source, staging)
            _run([python, "-m", "venv", str(staging / "venv")], env=_offline_env(home), description="venv creation")
            # Normalize pyvenv.cfg: strip the informational `command =` line
            # (it embeds the unique staging path, so it is inherently
            # per-install).  All security-relevant fields (home,
            # include-system-site-packages, version, executable) are
            # preserved, and the normalized bytes are what gets anchored and
            # authenticated at prelaunch — so two equivalent installations
            # produce identical pyvenv.cfg integrity evidence.
            _normalize_pyvenv_cfg(staging / "venv" / "pyvenv.cfg")
            venv_python = str(_venv_python(staging / "venv"))
            _run(
                [
                    venv_python, "-m", "pip", "install",
                    "--no-index",
                    "--find-links", str(wheelhouse),
                    "--only-binary=:all:",
                    "--require-hashes",
                    "-r", str(lock_file),
                ],
                env=_offline_env(home),
                description="offline release install",
            )
            _run([venv_python, "-m", "pip", "check"], env=_offline_env(home), description="pip check")
            # Clean any __pycache__/*.pyc that pip or the venv probe may have
            # created — the release payload is byte-frozen and must not carry
            # bytecode artifacts that would trip the pre-execution membership
            # check.
            _clean_bytecode(staging / "venv")
            probe = _probe_venv(staging / "venv", home)
            # The probe runs the venv interpreter; clean again so the
            # byte-frozen payload has no __pycache__ artifacts.
            _clean_bytecode(staging / "venv")
            if not probe["python_version"].startswith("3.14."):
                raise PolicyViolation(
                    f"Release requires the verified CPython 3.14 interpreter; venv reports {probe['python_version']}"
                )
            installed, bootstrap = _split_inventory(probe["dists"])
            if installed != lock_entries:
                undeclared = sorted(set(installed) ^ set(lock_entries))
                raise PolicyViolation(
                    f"Installed inventory diverges from the lock (undeclared or missing distributions): {undeclared}"
                )
            unexpected_bootstrap = sorted(set(bootstrap) - BOOTSTRAP_DISTRIBUTIONS)
            if unexpected_bootstrap:
                raise PolicyViolation(f"Unexpected bootstrap distributions in the release venv: {unexpected_bootstrap}")
            records = _record_evidence(Path(probe["purelib"]), lock_entries)
            # R6-03: bootstrap distributions (pip) are recorded with the same
            # RECORD evidence so executable-payload membership can cover every
            # *.py beneath purelib without trusting the release interpreter.
            bootstrap_records = _record_evidence(Path(probe["purelib"]), bootstrap)
            launcher = _write_launcher(staging)
            shutil.copyfile(lock_file, staging / lock_file.name)
            wheelhouse_manifest_name = wheelhouse_manifest_path.name
            shutil.copyfile(wheelhouse_manifest_path, staging / wheelhouse_manifest_name)
            app_manifest = _app_manifest(staging / "app")
            _atomic_write(staging / "APP_MANIFEST.json", json.dumps(app_manifest, indent=2, sort_keys=True) + "\n")
            identity_doc = {
                "schemaVersion": 1,
                "identity": identity,
                "packageVersion": package_version,
                "mcpVersion": MCP_VERSION,
                "architecture": architecture,
                "pythonTag": PYTHON_TAG,
                "sourceManifestSha256": source_sha256,
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            _atomic_write(staging / "RELEASE_IDENTITY.json", json.dumps(identity_doc, indent=2, sort_keys=True) + "\n")
            hashes = {
                "APP_MANIFEST.json": _sha256_path(staging / "APP_MANIFEST.json"),
                "RELEASE_IDENTITY.json": _sha256_path(staging / "RELEASE_IDENTITY.json"),
                lock_file.name: _sha256_path(staging / lock_file.name),
                wheelhouse_manifest_name: _sha256_path(staging / wheelhouse_manifest_name),
                "launcher/mcp-server": _sha256_path(launcher),
            }
            integrity = {
                "schemaVersion": 1,
                "identity": identity,
                "packageVersion": package_version,
                "mcpVersion": MCP_VERSION,
                "architecture": architecture,
                "pythonTag": PYTHON_TAG,
                "sourceSha256": source_sha256,
                "app_manifest": app_manifest,
                "hashes": hashes,
                "lock_file": {"name": lock_file.name, "sha256": hashes[lock_file.name]},
                "wheelhouse_manifest_sha256": hashes[wheelhouse_manifest_name],
                "installed_inventory": installed,
                "bootstrap_inventory": bootstrap,
                "installed_records": records,
                "bootstrap_records": bootstrap_records,
                "purelib": os.path.relpath(probe["purelib"], (staging / "venv").resolve()),
                "pyvenv_cfg_sha256": _sha256_path(staging / "venv" / "pyvenv.cfg"),
                "interpreter": {
                    "python_version": probe["python_version"],
                    "base_prefix": probe["base_prefix"],
                    "base_executable": probe["base_executable"],
                    "base_executable_sha256": _sha256_path(Path(probe["base_executable"])),
                },
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            _atomic_write(staging / "RELEASE_INTEGRITY.json", json.dumps(integrity, indent=2, sort_keys=True) + "\n")
            # Install-time staging check: no external anchor can exist yet.
            verify_release_prelaunch(staging, home=home, require_anchor=False)
            if final.exists():
                if _releases_equivalent(staging, final):
                    shutil.rmtree(staging)
                    # Reuse path: the release was published earlier; a failed
                    # ownership write must never remove it.
                    _record_release_ownership(home, final.name, _integrity_anchor(final))
                    return final
                raise PolicyViolation(
                    f"A different release already occupies {identity!r}; reuse requires an exact manifest match"
                )
            os.rename(staging, final)
            published = True
            try:
                _record_release_ownership(home, final.name, _integrity_anchor(final))
            except BaseException:
                # Transactional contract: a failed ownership/anchor write after
                # the staging-to-final rename removes ONLY the newly published
                # release; a prior release is never touched.
                shutil.rmtree(final, ignore_errors=True)
                raise
            return final
        except BaseException:
            if not published and staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            raise


def _integrity_anchor(release_dir: Path) -> str:
    """SHA-256 of the release's RELEASE_INTEGRITY.json, recorded externally in
    the installation-state record so the mutable in-release document is never
    trusted on its own."""
    root_fd = safe_read.open_root(release_dir)
    try:
        data, _info = safe_read.open_verified_leaf(root_fd, "RELEASE_INTEGRITY.json")
    finally:
        os.close(root_fd)
    return _sha256_bytes(data)


def _record_release_ownership(home: Path, identity: str, anchor: str) -> None:
    state = _load_state(home)
    if identity not in state["releases"]:
        state["releases"].append(identity)
        state["releases"].sort()
    state.setdefault("integrityAnchors", {})[identity] = anchor
    _write_state(home, state)


def _releases_equivalent(staging: Path, final: Path) -> bool:
    """Reuse is allowed only when identity and all manifests match exactly.
    Timestamps (and hashes of timestamped documents) are excluded; content is
    what identifies a release."""
    try:
        staged_identity = json.loads((staging / "RELEASE_IDENTITY.json").read_text(encoding="utf-8"))
        existing_identity = json.loads((final / "RELEASE_IDENTITY.json").read_text(encoding="utf-8"))
        for doc in (staged_identity, existing_identity):
            doc.pop("createdAt", None)
        if staged_identity != existing_identity:
            return False
        if json.loads((staging / "APP_MANIFEST.json").read_text(encoding="utf-8")) != json.loads(
            (final / "APP_MANIFEST.json").read_text(encoding="utf-8")
        ):
            return False
        staged_integrity = json.loads((staging / "RELEASE_INTEGRITY.json").read_text(encoding="utf-8"))
        existing_integrity = json.loads((final / "RELEASE_INTEGRITY.json").read_text(encoding="utf-8"))
        for doc in (staged_integrity, existing_integrity):
            doc.pop("createdAt", None)
            doc.get("hashes", {}).pop("RELEASE_IDENTITY.json", None)
        return staged_integrity == existing_integrity
    except (OSError, json.JSONDecodeError):
        return False


# --- Activation lifecycle (clarifications 1-11) ---
#
# Atomic visibility only; no durability claim is made. Every failure path
# removes only its own uniquely-named temporary assets; the previously active
# release is never touched. The ownership record survives disable. The
# installation-state record also carries the external integrity anchors and
# the base-launcher path that make verification independent of release-owned
# code and documents.
#
# Transactional contract (R6-05): every mutation verb (install, enable,
# disable, re-enable, rollback, remove) serializes on ONE shared stdlib
# macOS/POSIX lifecycle lock. Each verb preserves the prior current target
# before activation; a failure after activation restores it before the lock
# is released. A failed ownership/anchor write during install removes only
# the newly published release. State writes are atomic (temp + replace), so
# a failed write leaves the prior state bytes intact. No crash/power-loss
# durability is claimed: atomic visibility remains the approved contract.

STATE_VERSION = 2
WRAPPER_RELATIVE = Path("bin") / "madclaude-mcp-server"
LIFECYCLE_LOCK_NAME = ".mcp-lifecycle.lock"

_SERVE_BOOTSTRAP = (
    "import sys; sys.dont_write_bytecode = True; sys.path.insert(0, sys.argv[1]); "
    "from madclaude.mcp_server import main; raise SystemExit(main(sys.argv[2:]))"
)


def _state_path(home: Path) -> Path:
    return home / "mcp-installation-state.json"


def _load_state(home: Path) -> dict[str, Any]:
    path = _state_path(home)
    if not path.is_file():
        return {
            "schemaVersion": STATE_VERSION,
            "releases": [],
            "wrapper": None,
            "lastEnabled": None,
            "integrityAnchors": {},
            "baseLauncher": None,
        }
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyViolation(f"MCP installation-state record is invalid: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PolicyViolation(f"MCP installation-state record has an unsupported schema: {path}")
    version = value.get("schemaVersion")
    if version == 1:
        # v1 -> v2 migration: anchors are empty, so every pre-v2 release fails
        # closed at launch until reinstalled (which records its anchor).
        value["schemaVersion"] = STATE_VERSION
        value.setdefault("integrityAnchors", {})
        value.setdefault("baseLauncher", None)
    if value.get("schemaVersion") != STATE_VERSION:
        raise PolicyViolation(f"MCP installation-state record has an unsupported schema: {path}")
    if not isinstance(value.get("integrityAnchors"), dict):
        raise PolicyViolation(f"MCP installation-state record has corrupt integrity anchors: {path}")
    return value


def _write_state(home: Path, state: dict[str, Any]) -> None:
    state["updatedAt"] = datetime.now(timezone.utc).isoformat()
    state.setdefault("createdAt", state["updatedAt"])
    _atomic_write(_state_path(home), json.dumps(state, indent=2, sort_keys=True) + "\n")


def wrapper_path(home: Path) -> Path:
    return home / WRAPPER_RELATIVE


def _discover_base_launcher(home: Path) -> Path:
    """Locate the BASE control-plane launcher (outside mcp-releases/). The
    stable wrapper execs it, so externally anchored verification runs before
    any release-owned code."""
    override = os.environ.get("MADCLAUDE_BASE_LAUNCHER")
    candidates = [Path(override)] if override else []
    candidates.append(home / "bin" / "madclaude")
    found = shutil.which("madclaude")
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise PolicyViolation(
        "No base control-plane launcher found (MADCLAUDE_BASE_LAUNCHER, $MADCLAUDE_HOME/bin/madclaude, "
        "or madclaude on PATH); cannot create an externally verified MCP launch path."
    )


def _write_wrapper(home: Path, base_launcher: Path) -> Path:
    if "'" in str(home) or "'" in str(base_launcher):
        raise PolicyViolation(f"MADCLAUDE_HOME and the base launcher path must not contain a single quote: {home}")
    wrapper = wrapper_path(home)
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "#!/bin/sh\n"
        "# MAD Ventures MCP control-plane stable wrapper (owned asset).\n"
        "# Launch path: this wrapper -> BASE control plane `mcp serve`, which runs\n"
        "# externally anchored integrity verification BEFORE any release-owned\n"
        "# launcher, shell, Python module, or integrity document executes.\n"
        f"HOME_DIR='{home}'\n"
        'export MADCLAUDE_HOME="$HOME_DIR"\n'
        'CURRENT="$HOME_DIR/mcp-releases/current"\n'
        'if [ ! -e "$CURRENT" ]; then\n'
        '  echo "madclaude MCP control plane is disabled. Re-enable with: madclaude mcp re-enable --home \'$HOME_DIR\'" >&2\n'
        "  exit 3\n"
        "fi\n"
        f"exec '{base_launcher}' mcp serve --home \"$HOME_DIR\" -- \"$@\"\n"
    )
    _atomic_write(wrapper, content)
    wrapper.chmod(0o700)
    return wrapper


def _owned_release_dir(home: Path, identity: str) -> Path:
    safe_read.validate_component(identity)
    root = releases_root(home)
    entry = root / identity
    if entry.is_symlink():
        raise PolicyViolation(f"Refusing a symlinked MCP release entry: {identity!r}")
    candidate = entry.resolve()
    if candidate.parent != root.resolve() or not candidate.is_dir():
        raise PolicyViolation(f"Unknown or unowned MCP release identity: {identity!r}")
    return candidate


def _activate(home: Path, release_dir: Path) -> None:
    """Atomic visibility: relative symlink via same-directory os.replace.
    No rm/delete-before-move anywhere in activation."""
    root = releases_root(home)
    tmp = root / f"current.tmp.{os.getpid()}"
    current = root / "current"
    try:
        os.symlink(release_dir.name, tmp)
        os.replace(tmp, current)
    finally:
        if tmp.exists() or tmp.is_symlink():
            tmp.unlink()


@contextlib.contextmanager
def _lifecycle_lock(home: Path) -> Iterator[None]:
    """The one shared stdlib macOS/POSIX lifecycle lock (fcntl.flock on a
    dedicated lock file) serializing every mutation verb. Read-only verbs
    (serve/status) do not take it. The lock is non-recursive by design: no
    verb ever calls another verb.

    Audit 9 MCP lifecycle support is macOS arm64 and macOS x86_64 only. On
    an unsupported platform (no fcntl), every lifecycle verb fails closed
    with a typed, actionable error instead of crashing at import."""
    if _fcntl is None:
        raise PolicyViolation(
            "MCP lifecycle is supported on macOS arm64 and macOS x86_64 only; "
            "the POSIX lifecycle lock (fcntl) is unavailable on this platform."
        )
    home.mkdir(parents=True, exist_ok=True)
    fd = os.open(home / LIFECYCLE_LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _fcntl.flock(fd, _fcntl.LOCK_EX)
        yield
    finally:
        try:
            _fcntl.flock(fd, _fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _current_target(home: Path) -> str | None:
    current = releases_root(home) / "current"
    return os.readlink(current) if current.is_symlink() else None


def _restore_current(home: Path, target: str | None) -> None:
    """Compensating rollback for a failed post-activation write: re-point the
    current symlink to the preserved prior target (or remove the pointer when
    there was none) via the same atomic-replace mechanism. Never deletes or
    modifies any release directory."""
    root = releases_root(home)
    current = root / "current"
    if target is None:
        if current.is_symlink() or current.exists():
            current.unlink()
        return
    tmp = root / f"current.tmp.{os.getpid()}"
    try:
        os.symlink(target, tmp)
        os.replace(tmp, current)
    finally:
        if tmp.exists() or tmp.is_symlink():
            tmp.unlink()


def enable(home: Path, release_dir: Path) -> Path:
    root = releases_root(home)
    release_dir = release_dir.resolve()
    if release_dir.parent != root.resolve() or release_dir.name.startswith("."):
        raise PolicyViolation(f"MCP enable requires a release inside {root}")
    with _lifecycle_lock(home):
        verify_release_prelaunch(release_dir, home=home)
        base_launcher = _discover_base_launcher(home)
        wrapper = _write_wrapper(home, base_launcher)
        previous = _current_target(home)
        _activate(home, release_dir)
        try:
            state = _load_state(home)
            if release_dir.name not in state["releases"]:
                state["releases"].append(release_dir.name)
            state["releases"].sort()
            state["wrapper"] = str(wrapper)
            state["baseLauncher"] = str(base_launcher)
            state["lastEnabled"] = release_dir.name
            _write_state(home, state)
        except BaseException:
            # Transactional contract: a failed state write after activation
            # restores the previous current pointer before the lock releases.
            _restore_current(home, previous)
            raise
    return release_dir


def disable(home: Path) -> None:
    """Removes only the current pointer. The owned stable wrapper and all
    preserved releases remain; the ownership record survives."""
    with _lifecycle_lock(home):
        current = releases_root(home) / "current"
        if current.is_symlink() or current.exists():
            current.unlink()


def reenable(home: Path) -> Path:
    """Verifies the preserved release (prelaunch tier, externally anchored)
    before recreating only the atomic current pointer."""
    with _lifecycle_lock(home):
        state = _load_state(home)
        identity = state.get("lastEnabled")
        if not identity:
            raise PolicyViolation("No preserved MCP release to re-enable; run madclaude mcp install first.")
        release_dir = _owned_release_dir(home, identity)
        verify_release_prelaunch(release_dir, home=home)
        if not wrapper_path(home).is_file():
            _write_wrapper(home, _discover_base_launcher(home))
        _activate(home, release_dir)
        return release_dir


def rollback(home: Path, identity: str) -> Path:
    """Re-points current to a preserved prior release. The previously active
    release is never deleted by any failure path."""
    with _lifecycle_lock(home):
        state = _load_state(home)
        if identity not in state["releases"]:
            raise PolicyViolation(f"Rollback target is not a preserved owned release: {identity!r}")
        release_dir = _owned_release_dir(home, identity)
        verify_release_prelaunch(release_dir, home=home)
        if not wrapper_path(home).is_file():
            _write_wrapper(home, _discover_base_launcher(home))
        previous = _current_target(home)
        _activate(home, release_dir)
        try:
            state["lastEnabled"] = identity
            _write_state(home, state)
        except BaseException:
            # Transactional contract: a failed state write after activation
            # restores the previous current pointer before the lock releases.
            _restore_current(home, previous)
            raise
        return release_dir


def remove(home: Path, identity: str) -> dict[str, Any]:
    """Deletes only assets the ownership record proves are owned; anything
    else is reported and left in place. Removal is race-safe against a
    concurrent activation: the whole verb runs under the shared lifecycle
    lock, so no activation can interleave; the trash-rename + active re-check
    below remains as in-lock defense in depth, and a lost race restores the
    directory untouched."""
    with _lifecycle_lock(home):
        state = _load_state(home)
        report: dict[str, Any] = {"removed": [], "leftInPlace": []}
        root = releases_root(home)
        current = root / "current"

        def _active_is(candidate_identity: str) -> bool:
            return current.is_symlink() and os.readlink(current) == candidate_identity

        if _active_is(identity):
            raise PolicyViolation(f"Cannot remove the active MCP release {identity!r}; disable or roll back first.")
        if identity not in state["releases"]:
            report["leftInPlace"].append(f"{identity} (not owned by the installation-state record)")
            return report
        safe_read.validate_component(identity)
        candidate = root / identity
        if candidate.is_symlink():
            raise PolicyViolation(f"Refusing to remove a symlinked MCP release entry: {identity!r}")
        if candidate.exists():
            if candidate.resolve().parent != root.resolve():
                raise PolicyViolation(f"Refusing to remove a release outside {root}: {identity!r}")
            trash = root / f".trash.{uuid.uuid4().hex}"
            os.rename(candidate, trash)
            if _active_is(identity):
                os.rename(trash, candidate)  # lost the activation race; restore untouched
                raise PolicyViolation(f"MCP release {identity!r} became active during removal; removal aborted.")
            # Transactional contract (R6-05): persist the updated ownership
            # state BEFORE irreversible deletion.  A failed state write
            # restores the release from trash so disk and state stay
            # consistent (no missing owned release, no stale ownership).
            state["releases"] = [name for name in state["releases"] if name != identity]
            state.get("integrityAnchors", {}).pop(identity, None)
            if state.get("lastEnabled") == identity:
                state["lastEnabled"] = None
            try:
                _write_state(home, state)
            except BaseException:
                os.rename(trash, candidate)  # restore before releasing the lock
                raise
            # State persistence succeeded: only now delete the trash.  A
            # failed delete surfaces loudly and leaves only the uniquely
            # named recoverable trash — never stale ownership (state already
            # records removal) and never a missing owned release.
            try:
                shutil.rmtree(trash)
            except BaseException:
                raise
            report["removed"].append(identity)
        else:
            # Release directory already absent: still persist the ownership
            # update so state never records ownership of a missing release.
            state["releases"] = [name for name in state["releases"] if name != identity]
            state.get("integrityAnchors", {}).pop(identity, None)
            if state.get("lastEnabled") == identity:
                state["lastEnabled"] = None
            _write_state(home, state)
            report["removed"].append(identity)
        return report


def serve(home: Path, argv: list[str]) -> int:
    """Externally verified launch: runs from the BASE control plane, performs
    the externally anchored prelaunch verification, and only then execs the
    release venv interpreter on the release-owned server module."""
    root = releases_root(home)
    current = root / "current"
    if not current.is_symlink():
        raise PolicyViolation(
            "madclaude MCP control plane is disabled. Re-enable with: madclaude mcp re-enable"
        )
    release_dir = current.resolve()
    if release_dir.parent != root.resolve() or not release_dir.is_dir():
        raise PolicyViolation(f"MCP current pointer is dangling or points outside {root}")
    state = _load_state(home)
    if release_dir.name not in state["releases"]:
        raise PolicyViolation(f"MCP current points at an unowned release: {release_dir.name!r}")
    verify_release_prelaunch(release_dir, home=home)  # externally anchored, base-owned code
    venv_python = release_dir / "venv" / "bin" / "python"
    os.execve(
        str(venv_python),
        [str(venv_python), "-c", _SERVE_BOOTSTRAP, str(release_dir / "app"), *argv],
        {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    raise AssertionError("os.execve returned")  # pragma: no cover - unreachable


def staged_self_test(home: Path, release_dir: Path) -> None:
    """Pre-activation self-test, orchestrated by the BASE control plane: the
    staged release is verified (install-time tier, no anchor exists yet) by
    base-owned code, and only then is the release interpreter launched in
    --self-test --staged mode."""
    release_dir = release_dir.resolve()
    root = releases_root(home)
    if release_dir.parent != root.resolve() or release_dir.name.startswith("."):
        raise PolicyViolation(f"Staged self-test requires a release inside {root}")
    verify_release_prelaunch(release_dir, home=home, require_anchor=False)
    venv_python = release_dir / "venv" / "bin" / "python"
    _run(
        [str(venv_python), "-c", _SERVE_BOOTSTRAP, str(release_dir / "app"), "--self-test", "--staged"],
        env=_offline_env(home),
        description="staged launcher self-test",
    )


def status(home: Path, *, deep: bool = False) -> dict[str, Any]:
    """Verifies current resolves inside mcp-releases/ to an owned release and
    runs the prelaunch tier. --deep adds RECORD-level venv verification; venv
    divergence is drift detection (remedy: reinstall), not prevention."""
    state = _load_state(home)
    root = releases_root(home)
    current = root / "current"
    report: dict[str, Any] = {
        "enabled": False,
        "ownedReleases": list(state["releases"]),
        "wrapper": str(wrapper_path(home)),
        "wrapperPresent": wrapper_path(home).is_file(),
    }
    if not current.is_symlink():
        report["state"] = "disabled"
        return report
    target = os.readlink(current)
    resolved = current.resolve()
    if resolved.parent != root.resolve() or not resolved.is_dir():
        raise PolicyViolation(f"MCP current pointer is dangling or points outside {root}: {target!r}")
    if resolved.name not in state["releases"]:
        raise PolicyViolation(f"MCP current points at an unowned release: {resolved.name!r}")
    integrity = verify_release_prelaunch(resolved, home=home)
    report.update({"enabled": True, "state": "enabled", "identity": integrity["identity"], "prelaunch": "verified"})
    if deep:
        drift = verify_record_level(resolved)
        report["recordLevel"] = "verified" if not drift else "drift-detected"
        report["drift"] = drift
        if drift:
            report["remedy"] = "reinstall"
    return report
