#!/usr/bin/env python3
"""Exercise lifecycle gates from freshly extracted ZIP and TAR.GZ artifacts."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path


WORKFLOWS = (
    "founder-plan", "founder-build", "founder-verify", "founder-tier2-evidence",
    "founder-release-readiness", "founder-repository-audit", "founder-security-audit",
    "founder-ui-review", "founder-fix-until-green", "founder-changed-files-review",
    "founder-docs-drift", "founder-performance-audit", "founder-test-gap-analysis",
    "founder-incident-root-cause",
)
HOOKS = (
    "guard-authority-paths", "guard-control-plane", "guard-destructive",
    "guard-readonly-sql", "guard-secret-paths", "check-frontmatter",
    "guard-independent-review-shell", "hook-utils",
)


def safe_destination(root: Path, member: str) -> Path:
    destination = (root / member).resolve()
    if root.resolve() not in destination.parents and destination != root.resolve():
        raise ValueError(f"unsafe archive member: {member}")
    return destination


def extract(archive: Path, destination: Path) -> Path:
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                safe_destination(destination, info.filename)
            bundle.extractall(destination)
    else:
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                safe_destination(destination, member.name)
                if member.issym() or member.islnk():
                    raise ValueError(f"links are not permitted in release archive: {member.name}")
            bundle.extractall(destination)
    roots = [path for path in destination.iterdir() if path.is_dir()]
    if len(roots) != 1:
        raise ValueError(f"expected one archive root, found {roots}")
    return roots[0]


def run(*command: str, cwd: Path, env: dict[str, str] | None = None, expect: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True)
    if proc.returncode != expect:
        raise AssertionError(
            f"expected exit {expect}, got {proc.returncode}: {' '.join(command)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def fresh_install(package: Path, root: Path, label: str) -> tuple[Path, dict[str, object]]:
    repo = root / f"{label}-repo"
    workspace = root / f"{label}-MADVenturesOPs"
    managed = root / f"{label}-managed"
    repo.mkdir(); workspace.mkdir(); managed.mkdir()
    run("python3", "scripts/quick-validate.py", cwd=package)
    run(
        "bash", "scripts/install.sh", str(repo), "--workspace", str(workspace),
        "--install-managed", "--managed-dir", str(managed), "--skip-validation", cwd=package,
    )
    status = run("bash", "scripts/install.sh", "status", str(repo), "--json", cwd=package)
    payload = json.loads(status.stdout)
    assert payload["ready"] is True, payload
    assert payload["layers"]["managedGlobal"] == "verified", payload["layers"]
    assert payload["layers"]["workspace"] == "verified", payload["layers"]
    assert not list((repo / ".claude/workflows").glob("*.js"))
    assert sorted(path.name for path in (repo / ".claude/hooks").glob("*.mjs")) == ["hook-adapter.mjs", "madventures-statusline.mjs"]
    return repo, payload


def harness_integrity(package: Path) -> None:
    control = package / "python-control-plane"
    # Sanitized env: strip host Python-environment overrides (PYTHONPATH,
    # PYTHONHOME, VIRTUAL_ENV, PIP_TARGET) so the Hermes Python 3.11 venv or
    # any other host Python cannot contaminate the archive test run.  -I -B
    # on the interpreter also prevents user-site and PYTHON* env vars from
    # loading foreign packages (pydantic_core, mcp) from the wrong Python.
    clean_env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PIP_TARGET")
    }
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
    run("python3", "-I", "-B", "run-tests.py", cwd=control, env=clean_env)
    run("python3", "-I", "-B", "scripts/validate-config.py", "--skip-python-integration", cwd=package, env=clean_env)
    run("python3", "-I", "-B", "scripts/quick-validate.py", cwd=package, env=clean_env)
    # Audit 9 parity and lifecycle checks must also gate on fresh extractions.
    # Build on the sanitized env, adding only the archive's own src/tests.
    # -I is NOT used here because it would ignore the PYTHONPATH we set;
    # the sanitized env (stripped of host PYTHONPATH/HOME/VENV) is the
    # isolation mechanism for this subprocess.
    audit_env = dict(clean_env, PYTHONPATH=f"{control / 'src'}:{control / 'tests'}")
    run(
        "python3", "-B", "-m", "unittest",
        "test_plugin_parity", "test_mcp_release_install", "test_mcp_lifecycle",
        cwd=control / "tests", env=audit_env,
    )


def legacy_update(package: Path, root: Path) -> None:
    repo = root / "legacy-repo"
    hooks = repo / ".claude/hooks"
    workflows = repo / ".claude/workflows"
    hooks.mkdir(parents=True); workflows.mkdir()
    for name in WORKFLOWS:
        (workflows / f"{name}.js").write_text("export default {};\n", encoding="utf-8")
    for name in HOOKS:
        (hooks / f"{name}.mjs").write_text("#!/usr/bin/env node\n", encoding="utf-8")
    (repo / ".claude/custom.txt").write_text("KEEP\n", encoding="utf-8")
    (repo / ".claude/settings.json").write_text(
        '{"model":"haiku","hooks":{"PreToolUse":[{"hooks":[{"type":"command","command":"node .claude/hooks/guard-control-plane.mjs"}]}]}}\n',
        encoding="utf-8",
    )
    run(
        "bash", "scripts/install.sh", "update", str(repo), "--skip-validation", cwd=package,
        env=dict(os.environ, MADVENTURES_LIFECYCLE_TEST_FAST="1"),
    )
    assert not list(workflows.glob("*.js"))
    assert sorted(path.name for path in hooks.glob("*.mjs")) == ["hook-adapter.mjs", "madventures-statusline.mjs"]
    settings = json.loads((repo / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings["model"] == "haiku"
    assert "guard-control-plane" not in json.dumps(settings)
    assert "hook-adapter.mjs" in json.dumps(settings)
    assert (repo / ".claude/custom.txt").read_text(encoding="utf-8") == "KEEP\n"


def rollback(package: Path, root: Path) -> None:
    repo = root / "rollback-repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude/custom.txt").write_text("ORIGINAL\n", encoding="utf-8")
    (repo / ".claude/settings.json").write_text('{"model":"haiku"}\n', encoding="utf-8")
    before = {
        path.relative_to(repo).as_posix(): path.read_bytes()
        for path in repo.rglob("*") if path.is_file()
    }
    env = dict(os.environ, MADVENTURES_TEST_FAIL_AFTER_APPLY="1")
    run("bash", "scripts/install.sh", str(repo), "--skip-validation", cwd=package, env=env, expect=1)
    after = {
        path.relative_to(repo).as_posix(): path.read_bytes()
        for path in repo.rglob("*") if path.is_file() and ".claude-backups" not in path.parts
    }
    assert after == before, (before.keys(), after.keys())


def doctor_and_uninstall(package: Path, repo: Path) -> None:
    doctor = run("bash", "scripts/install.sh", "doctor", str(repo), "--json", cwd=package)
    assert json.loads(doctor.stdout)["ready"] is True
    (repo / ".claude/custom-after-install.txt").write_text("KEEP\n", encoding="utf-8")
    run("bash", "scripts/install.sh", "uninstall", str(repo), cwd=package)
    assert (repo / ".claude/custom-after-install.txt").read_text(encoding="utf-8") == "KEEP\n"
    assert not (repo / ".claude/INSTALLATION_STATE.json").exists()


def powershell_lifecycle(package: Path, root: Path) -> bool:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if not powershell:
        return False
    repo = root / "powershell-repo"
    workspace = root / "powershell-MADVenturesOPs"
    managed = root / "powershell-managed"
    repo.mkdir(); workspace.mkdir(); managed.mkdir()
    script = str(package / "scripts/install.ps1")
    env = dict(os.environ, MADVENTURES_LIFECYCLE_TEST_FAST="1")
    run(
        powershell, "-NoProfile", "-File", script, "-ProjectPath", str(repo),
        "-Action", "install", "-Workspace", str(workspace), "-InstallManaged",
        "-ManagedDir", str(managed), "-SkipValidation", cwd=package, env=env,
    )
    status = run(
        powershell, "-NoProfile", "-File", script, "-ProjectPath", str(repo),
        "-Action", "status", "-Json", cwd=package,
    )
    assert json.loads(status.stdout)["ready"] is True
    state = json.loads((repo / ".claude/INSTALLATION_STATE.json").read_text(encoding="utf-8"))
    run(
        powershell, "-NoProfile", "-File", script, "-ProjectPath", str(repo),
        "-Action", "restore", "-Backup", state["backup"], "-DryRun", cwd=package,
    )
    run(
        powershell, "-NoProfile", "-File", script, "-ProjectPath", str(repo),
        "-Action", "update", "-SkipValidation", cwd=package, env=env,
    )
    run(
        powershell, "-NoProfile", "-File", script, "-ProjectPath", str(repo),
        "-Action", "uninstall", cwd=package,
    )
    run(
        powershell, "-NoProfile", "-File", script, "-ProjectPath", str(repo),
        "-Action", "uninstall", cwd=package,
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("tar", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="madventures-release-gates-") as temporary:
        root = Path(temporary)
        zip_package = extract(args.zip.resolve(), root / "zip")
        tar_package = extract(args.tar.resolve(), root / "tar")
        harness_integrity(zip_package)
        zip_repo, _ = fresh_install(zip_package, root, "zip")
        fresh_install(tar_package, root, "tar")
        legacy_update(zip_package, root)
        rollback(zip_package, root)
        doctor_and_uninstall(zip_package, zip_repo)
        powershell_checked = powershell_lifecycle(zip_package, root)
    suffix = "; PowerShell runtime lifecycle" if powershell_checked else "; PowerShell runtime unavailable"
    print("RELEASE LIFECYCLE GATES PASSED: clean-extraction harness/integrity; ZIP + TAR fresh install; migration; rollback; hierarchy; status/doctor/uninstall" + suffix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
