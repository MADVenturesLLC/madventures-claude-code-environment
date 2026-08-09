"""R6-04: installed-layout package-identity manifest contract.

Proves the CLI resolves exactly one explicit manifest location that exists in
both layouts, that the installer places it deliberately, and that a fresh
installed copy of the control plane (real deployed directory shape, no
source-tree PYTHONPATH) uses the INSTALLED $MADCLAUDE_HOME/MANIFEST.json when
running `madclaude mcp install`.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from madclaude import __version__
from madclaude.cli import _validate_identity_manifest
from madclaude.errors import MadClaudeError
from test_mcp_release_install import NATIVE_ARCH, WHEELHOUSE, make_wheel

ROOT = Path(__file__).resolve().parents[2]


def shutil_which_bash() -> bool:
    import shutil

    return shutil.which("bash") is not None


class IdentityManifestValidationTests(unittest.TestCase):
    def _write(self, directory: Path, payload: object) -> Path:
        candidate = directory / "MANIFEST.json"
        candidate.write_text(json.dumps(payload), encoding="utf-8")
        return candidate

    def _valid_doc(self) -> dict:
        return {
            "package": f"MADVentures-Claude-Code-Environment-v{__version__}",
            "version": __version__,
            "algorithm": "SHA-256",
            "fileCount": 0,
            "files": [],
        }

    def test_valid_manifest_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate = self._write(Path(temp), self._valid_doc())
            self.assertEqual(_validate_identity_manifest(candidate), candidate)

    def test_missing_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(MadClaudeError, "missing"):
                _validate_identity_manifest(Path(temp) / "MANIFEST.json")

    def test_invalid_json_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp) / "MANIFEST.json"
            candidate.write_text("{not json", encoding="utf-8")
            with self.assertRaisesRegex(MadClaudeError, "invalid JSON"):
                _validate_identity_manifest(candidate)

    def test_unrelated_package_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            doc = self._valid_doc()
            doc["package"] = "some-other-package"
            with self.assertRaisesRegex(MadClaudeError, "unrelated package"):
                _validate_identity_manifest(self._write(Path(temp), doc))

    def test_version_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            doc = self._valid_doc()
            doc["version"] = "0.0.0"
            with self.assertRaisesRegex(MadClaudeError, "version"):
                _validate_identity_manifest(self._write(Path(temp), doc))

    def test_malformed_schema_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            for mutation in (
                {"algorithm": "SHA-1"},
                {"fileCount": 3},  # disagrees with files: []
                {"files": {}},
            ):
                with self.subTest(mutation=mutation):
                    doc = self._valid_doc()
                    doc.update(mutation)
                    with self.assertRaisesRegex(MadClaudeError, "schema"):
                        _validate_identity_manifest(self._write(Path(temp), doc))


class InstalledCopyInstallTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix" and shutil_which_bash(), "Bash installer test requires POSIX bash")
    def test_installed_copy_mcp_install_uses_installed_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / "madclaude-home"
            bin_dir = base / "bin"
            wheelhouse = base / "wheelhouse"
            wheelhouse.mkdir()
            make_wheel(wheelhouse, "mcp", "2.0.0")
            make_wheel(wheelhouse, "sampledep", "1.0.0")
            result = WHEELHOUSE.finalize(wheelhouse, arch=NATIVE_ARCH)
            # No source-tree PYTHONPATH anywhere in the child environment.
            env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            install = subprocess.run(
                [
                    "bash",
                    str(ROOT / "scripts" / "install-python-control-plane.sh"),
                    "--home", str(home),
                    "--bin-dir", str(bin_dir),
                    "--python", sys.executable,
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(install.returncode, 0, install.stderr + install.stdout)
            installed_manifest = home / "MANIFEST.json"
            self.assertTrue(installed_manifest.is_file())
            # The deployed app/ tree holds no manifest; the single explicit
            # resolvable location is $MADCLAUDE_HOME/MANIFEST.json.
            self.assertFalse((home / "app" / "MANIFEST.json").exists())
            # Perturb ONLY the installed manifest (the schema stays valid), so
            # the derived release identity proves which physical file was read.
            doc = json.loads(installed_manifest.read_text(encoding="utf-8"))
            doc["installedCopyMarker"] = "installed-not-source"
            installed_manifest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            expected_sha = hashlib.sha256(installed_manifest.read_bytes()).hexdigest()
            source_sha = hashlib.sha256((ROOT / "MANIFEST.json").read_bytes()).hexdigest()
            self.assertNotEqual(expected_sha, source_sha)
            wrapper = bin_dir / "madclaude"
            self.assertTrue(wrapper.is_file())
            completed = subprocess.run(
                [
                    str(wrapper),
                    "mcp", "install",
                    "--wheelhouse", str(wheelhouse),
                    "--lock", str(result["lock"]),
                    "--arch", NATIVE_ARCH,
                    "--home", str(home),
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            payload = json.loads(completed.stdout)
            self.assertTrue(
                payload["identity"].endswith(f"-{expected_sha[:12]}"),
                f"identity {payload['identity']!r} was not derived from the installed manifest",
            )


if __name__ == "__main__":
    unittest.main()
