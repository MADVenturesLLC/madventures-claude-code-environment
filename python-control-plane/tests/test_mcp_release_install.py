"""U8: release build, offline install, and integrity generation (B1/B2).

Integration tests build real venvs from fabricated wheels and install fully
offline (PIP_NO_INDEX=1, no proxy variables). No network is used anywhere.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from madclaude.errors import PolicyViolation
from madclaude.mcp_lifecycle import (
    install_release,
    release_identity,
    verify_record_level,
    verify_release_prelaunch,
)

ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = ROOT / "python-control-plane" / "src" / "madclaude"
NATIVE_ARCH = platform.machine()


def _load_wheelhouse_script():
    spec = importlib.util.spec_from_file_location("mcp_wheelhouse", ROOT / "scripts" / "mcp-wheelhouse.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


WHEELHOUSE = _load_wheelhouse_script()


def _wheel_record_row(relative: str, data: bytes) -> str:
    """A real wheel RECORD row: pip preserves these hashes in the installed
    RECORD, so fixtures must carry them like real wheels do."""
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii").rstrip("=")
    return f"{relative},sha256={digest},{len(data)}"


def make_wheel(directory: Path, name: str, version: str, *, tag: str = "py3-none-any",
               requires: tuple[str, ...] = (), extra: dict[str, str] | None = None) -> Path:
    normalized = name.replace("-", "_")
    path = directory / f"{normalized}-{version}-{tag}.whl"
    requires_lines = "".join(f"Requires-Dist: {dep}\n" for dep in requires)
    extra = extra or {}
    payload: dict[str, bytes] = {
        f"{normalized}/__init__.py": f'"""fake {name} for offline install tests"""\n'.encode("utf-8"),
        **{relative: content.encode("utf-8") for relative, content in sorted(extra.items())},
        f"{normalized}-{version}.dist-info/METADATA": (
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n{requires_lines}"
        ).encode("utf-8"),
        f"{normalized}-{version}.dist-info/WHEEL": (
            f"Wheel-Version: 1.0\nGenerator: audit9-tests\nRoot-Is-Purelib: true\nTag: {tag}\n"
        ).encode("utf-8"),
    }
    record = "\n".join(
        _wheel_record_row(relative, data) for relative, data in sorted(payload.items())
    ) + f"\n{normalized}-{version}.dist-info/RECORD,,\n"
    with zipfile.ZipFile(path, "w") as archive:
        for relative, data in sorted(payload.items()):
            archive.writestr(relative, data)
        archive.writestr(f"{normalized}-{version}.dist-info/RECORD", record)
    return path


class Fixture:
    def __init__(self, base: Path, wheel_extra: dict[str, str] | None = None) -> None:
        self.home = base / "home"
        self.home.mkdir()
        # Hermetic base-launcher shim: the externally verified launch path
        # must never fall back to a real `madclaude` on the host PATH.
        shim = self.home / "bin" / "madclaude"
        shim.parent.mkdir()
        shim.write_text("#!/bin/sh\nexec echo base-launcher-shim-not-executable-for-tests\n", encoding="utf-8")
        shim.chmod(0o700)
        self.wheelhouse = base / "wheelhouse"
        self.wheelhouse.mkdir()
        make_wheel(self.wheelhouse, "mcp", "2.0.0", extra=wheel_extra)
        make_wheel(self.wheelhouse, "sampledep", "1.0.0")
        result = WHEELHOUSE.finalize(self.wheelhouse, arch=NATIVE_ARCH)
        self.lock = result["lock"]
        self.source_manifest = base / "MANIFEST.json"
        self.source_manifest.write_text('{"files": []}\n', encoding="utf-8")

    def install(self, **overrides) -> Path:
        values = dict(
            home=self.home,
            app_source=APP_SOURCE,
            wheelhouse=self.wheelhouse,
            lock_file=self.lock,
            architecture=NATIVE_ARCH,
            python=sys.executable,
            package_version="4.4.1",
            source_manifest=self.source_manifest,
        )
        values.update(overrides)
        return install_release(**values)


def _sneak_wheelhouse(base: Path) -> tuple[Path, Path]:
    """Fresh wheelhouse where mcp depends on a package absent from the lock."""
    wheelhouse = base / f"sneak-wheelhouse-{len(list(base.glob('sneak-wheelhouse-*')))}"
    wheelhouse.mkdir()
    make_wheel(wheelhouse, "mcp", "2.0.0", requires=("sneak",))
    make_wheel(wheelhouse, "sampledep", "1.0.0")
    make_wheel(wheelhouse, "sneak", "0.1.0")
    result = WHEELHOUSE.finalize(wheelhouse, arch=NATIVE_ARCH)
    lines = [l for l in result["lock"].read_text(encoding="utf-8").splitlines() if not l.startswith("sneak==")]
    result["lock"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return wheelhouse, result["lock"]


class ReleaseInstallTests(unittest.TestCase):
    def test_release_layout_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            expected_identity = release_identity("4.4.1", __import__("hashlib").sha256(b'{"files": []}\n').hexdigest())
            self.assertEqual(release.name, expected_identity)
            self.assertTrue(release.name.startswith("mcp-2.0.0-4.4.1-"))
            for entry in (
                "app",
                "venv",
                "launcher",
                f"requirements-cp314-macos-{NATIVE_ARCH}.lock",
                "WHEELHOUSE_MANIFEST.json",
                "APP_MANIFEST.json",
                "RELEASE_INTEGRITY.json",
                "RELEASE_IDENTITY.json",
            ):
                self.assertTrue((release / entry).exists(), entry)
            self.assertTrue(os.access(release / "launcher" / "mcp-server", os.X_OK))

    def test_integrity_covers_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            integrity = json.loads((release / "RELEASE_INTEGRITY.json").read_text(encoding="utf-8"))
            for key in (
                "identity", "packageVersion", "mcpVersion", "architecture", "sourceSha256",
                "app_manifest", "hashes", "lock_file", "wheelhouse_manifest_sha256",
                "installed_inventory", "installed_records", "interpreter",
            ):
                self.assertIn(key, integrity)
            self.assertEqual(integrity["installed_inventory"], {"mcp": "2.0.0", "sampledep": "1.0.0"})
            self.assertEqual(integrity["interpreter"]["python_version"], sys.version.split()[0])
            records = integrity["installed_records"]
            for name in ("mcp", "sampledep"):
                self.assertIn("record_sha256", records[name])
                self.assertTrue(any(row.startswith("sha256=") for row in records[name]["files"].values()))
            self.assertEqual(verify_record_level(release), [])

    def test_reuse_requires_exact_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            first = fixture.install()
            second = fixture.install()
            self.assertEqual(first, second)
            # Identical reuse leaves no staging residue.
            self.assertFalse(list((fixture.home / "mcp-releases").glob(".staging.*")))
            app_manifest = first / "APP_MANIFEST.json"
            doc = json.loads(app_manifest.read_text(encoding="utf-8"))
            doc["files"] = []
            app_manifest.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "exact manifest match"):
                fixture.install()

    def test_equivalent_installs_produce_identical_pyvenv_cfg_evidence(self) -> None:
        # Two equivalent installations must anchor the SAME normalized
        # pyvenv.cfg SHA-256 (the informational `command =` line is stripped
        # at venv creation), so reuse succeeds and the anchored hash stays
        # deterministic and authenticated.
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            first = fixture.install()
            second = fixture.install()
            self.assertEqual(first, second)  # reuse path succeeded
            int1 = json.loads((first / "RELEASE_INTEGRITY.json").read_text(encoding="utf-8"))
            int2 = json.loads((second / "RELEASE_INTEGRITY.json").read_text(encoding="utf-8"))
            self.assertEqual(int1["pyvenv_cfg_sha256"], int2["pyvenv_cfg_sha256"])
            # The normalized file must not contain the per-install command line.
            cfg = (first / "venv" / "pyvenv.cfg").read_text(encoding="utf-8")
            self.assertNotIn("command =", cfg)
            # Security-relevant fields are preserved.
            self.assertIn("home =", cfg)
            self.assertIn("include-system-site-packages =", cfg)
            self.assertIn("version =", cfg)
            self.assertIn("executable =", cfg)
            # The anchored hash matches the on-disk normalized bytes.
            import hashlib
            self.assertEqual(int1["pyvenv_cfg_sha256"], hashlib.sha256(cfg.encode("utf-8")).hexdigest())

    def test_wrong_target_lock_fails_pre_activation(self) -> None:
        import platform

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture = Fixture(base)
            foreign = "x86_64" if platform.machine() == "arm64" else "arm64"
            other = base / f"wheelhouse-{foreign}"
            other.mkdir()
            make_wheel(other, "mcp", "2.0.0", tag=f"py3-none-macosx_10_9_{foreign}")
            result = WHEELHOUSE.finalize(other, arch=foreign)
            # Native arch, foreign-target lock/wheels: must fail before activation.
            with self.assertRaises(PolicyViolation):
                fixture.install(wheelhouse=other, lock_file=result["lock"], architecture=NATIVE_ARCH)
            releases = fixture.home / "mcp-releases"
            remaining = [p.name for p in releases.iterdir()] if releases.is_dir() else []
            self.assertEqual(remaining, [])

    def test_non_native_arch_rejected(self) -> None:
        import platform

        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            foreign = "x86_64" if platform.machine() == "arm64" else "arm64"
            with self.assertRaisesRegex(PolicyViolation, "natively per target"):
                fixture.install(architecture=foreign)

    def test_missing_hash_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            broken = Path(temp) / "broken.lock"
            broken.write_text("mcp==2.0.0\n", encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "hashed exact pin"):
                fixture.install(lock_file=broken)

    def test_offline_install_fails_with_empty_wheelhouse(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture = Fixture(base)
            empty = base / "empty-wheelhouse"
            empty.mkdir()
            # Present but empty wheelhouse: pip has nothing to resolve from and
            # PIP_NO_INDEX=1 forbids any network fallback.
            (empty / "WHEELHOUSE_MANIFEST.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "offline release install failed"):
                fixture.install(wheelhouse=empty)

    def test_undeclared_distribution_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture = Fixture(base)
            wheelhouse, lock = _sneak_wheelhouse(base)
            # pip itself aborts under --require-hashes because the transitive
            # dependency is not pinned+hashed; the inventory equality check is
            # the second layer if install ever succeeded with extra content.
            with self.assertRaisesRegex(PolicyViolation, "pinned with ==|undeclared or missing"):
                fixture.install(wheelhouse=wheelhouse, lock_file=lock)

    def test_extra_app_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            (release / "app" / "smuggled.py").write_text("# extra\n", encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "membership"):
                verify_release_prelaunch(release, home=fixture.home)

    def test_tampered_integrity_fails_prelaunch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            integrity_path = release / "RELEASE_INTEGRITY.json"
            doc = json.loads(integrity_path.read_text(encoding="utf-8"))
            doc["hashes"]["APP_MANIFEST.json"] = "0" * 64
            integrity_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
            # The mutable in-release document diverges from its external anchor.
            with self.assertRaisesRegex(PolicyViolation, "external anchor"):
                verify_release_prelaunch(release, home=fixture.home)

    def test_tampered_release_file_fails_prelaunch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            # Tamper a file the (untampered) integrity document records: the
            # anchor matches, so the per-file hash check must fire.
            (release / "APP_MANIFEST.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "hash mismatch"):
                verify_release_prelaunch(release, home=fixture.home)

    def test_missing_external_anchor_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            state_path = fixture.home / "mcp-installation-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["integrityAnchors"] = {}
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "No external integrity anchor"):
                verify_release_prelaunch(release, home=fixture.home)

    def test_failure_preserves_prior_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture = Fixture(base)
            release = fixture.install()
            wheelhouse, lock = _sneak_wheelhouse(base)
            with self.assertRaises(PolicyViolation):
                fixture.install(wheelhouse=wheelhouse, lock_file=lock)
            # The prior release is untouched and still verifies.
            self.assertTrue(release.exists())
            verify_release_prelaunch(release, home=fixture.home)
            self.assertFalse(list((fixture.home / "mcp-releases").glob(".staging.*")))


class ReleaseIdentityAuthenticationTests(unittest.TestCase):
    """R6-02: the release identity is authenticated BEFORE any release-owned
    document is parsed, and identity substitution fails closed."""

    def _two_releases(self, base: Path) -> tuple[Fixture, Path, Path]:
        fixture = Fixture(base)
        first = fixture.install()
        second_manifest = base / "MANIFEST.v2.json"
        second_manifest.write_text('{"files": ["v2"]}\n', encoding="utf-8")
        second = fixture.install(source_manifest=second_manifest)
        return fixture, first, second

    def test_substituted_release_payload_fails_at_anchor(self) -> None:
        # Release B's internally consistent payload and integrity document,
        # copied under release A's directory name, must NOT authenticate: the
        # anchor for A's trusted directory name is compared against the
        # physical bytes BEFORE parsing, so B's self-consistent document can
        # never select its own anchor.
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            b_integrity = (second / "RELEASE_INTEGRITY.json").read_bytes()
            doc = json.loads(b_integrity.decode("utf-8"))
            self.assertEqual(doc["identity"], second.name)  # B is internally consistent
            shutil.rmtree(first)
            shutil.copytree(second, first)
            self.assertTrue((first / "RELEASE_INTEGRITY.json").is_file())
            with self.assertRaisesRegex(PolicyViolation, "external anchor"):
                verify_release_prelaunch(first, home=fixture.home)
            # B itself still verifies under its own trusted name.
            verify_release_prelaunch(second, home=fixture.home)

    def test_anchor_matched_but_identity_field_mismatch_fails(self) -> None:
        # Second layer: even if the anchor for A's name somehow matches the
        # substituted bytes, the parsed identity must equal release_dir.name.
        with tempfile.TemporaryDirectory() as temp:
            import hashlib

            fixture, first, second = self._two_releases(Path(temp))
            b_bytes = (second / "RELEASE_INTEGRITY.json").read_bytes()
            shutil.rmtree(first)
            shutil.copytree(second, first)
            state_path = fixture.home / "mcp-installation-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["integrityAnchors"][first.name] = hashlib.sha256(b_bytes).hexdigest()
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "trusted directory identity"):
                verify_release_prelaunch(first, home=fixture.home)

    def test_unowned_identity_fails_closed(self) -> None:
        # Ownership: the trusted directory identity must be recorded in the
        # installation-state record, independently of the anchor match.
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            state_path = fixture.home / "mcp-installation-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["releases"] = [name for name in state["releases"] if name != release.name]
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "not owned"):
                verify_release_prelaunch(release, home=fixture.home)


class PreExecutionDependencyVerificationTests(unittest.TestCase):
    """R6-03: executable dependency bytes verify BEFORE the release
    interpreter runs; tampered or unrecorded payload never executes."""

    def _purelib(self, release: Path) -> Path:
        integrity = json.loads((release / "RELEASE_INTEGRITY.json").read_text(encoding="utf-8"))
        return release / "venv" / integrity["purelib"]

    def test_modified_sitecustomize_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            marker = base / "EXECUTED_MARKER"
            fixture = Fixture(base, wheel_extra={"sitecustomize.py": '"""reviewed sitecustomize"""\n'})
            release = fixture.install()
            purelib = self._purelib(release)
            self.assertTrue((purelib / "sitecustomize.py").is_file())
            payload = f"import pathlib; pathlib.Path({str(marker)!r}).write_text('ran')\n"
            (purelib / "sitecustomize.py").write_text(payload, encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "fail closed before any release-owned Python runs"):
                verify_release_prelaunch(release, home=fixture.home)
            self.assertFalse(marker.exists())  # the tampered payload never executed

    def test_dropped_unrecorded_sitecustomize_rejected_before_execution(self) -> None:
        # A sitecustomize.py absent from every RECORD would execute on ANY
        # venv interpreter start; membership verification must catch it first.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            marker = base / "EXECUTED_MARKER"
            fixture = Fixture(base)
            release = fixture.install()
            purelib = self._purelib(release)
            payload = f"import pathlib; pathlib.Path({str(marker)!r}).write_text('ran')\n"
            (purelib / "sitecustomize.py").write_text(payload, encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "unrecorded interpreter-consumed payload"):
                verify_release_prelaunch(release, home=fixture.home)
            self.assertFalse(marker.exists())

    def test_modified_installed_payload_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            marker = base / "EXECUTED_MARKER"
            fixture = Fixture(base)
            release = fixture.install()
            purelib = self._purelib(release)
            target = purelib / "sampledep" / "__init__.py"
            self.assertTrue(target.is_file())
            target.write_text(
                f"import pathlib; pathlib.Path({str(marker)!r}).write_text('ran')\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(PolicyViolation, "hash drift"):
                verify_release_prelaunch(release, home=fixture.home)
            self.assertFalse(marker.exists())

    def test_venv_interpreter_relationship_change_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            venv_python = release / "venv" / "bin" / "python"
            self.assertTrue(venv_python.exists())
            venv_python.unlink()
            os.symlink("/bin/sh", venv_python)
            with self.assertRaisesRegex(PolicyViolation, "interpreter/symlink relationship"):
                verify_release_prelaunch(release, home=fixture.home)

    def test_missing_pyvenv_cfg_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            (release / "venv" / "pyvenv.cfg").unlink()
            with self.assertRaisesRegex(PolicyViolation, "pyvenv.cfg"):
                verify_release_prelaunch(release, home=fixture.home)


if __name__ == "__main__":
    unittest.main()
