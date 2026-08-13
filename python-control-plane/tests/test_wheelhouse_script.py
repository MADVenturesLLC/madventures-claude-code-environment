"""U7: unit tests for scripts/mcp-wheelhouse.py (B1 Stage 1).

Uses fabricated wheel fixtures; no network access.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_wheelhouse_script():
    spec = importlib.util.spec_from_file_location("mcp_wheelhouse", ROOT / "scripts" / "mcp-wheelhouse.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


WHEELHOUSE = _load_wheelhouse_script()
WheelhouseError = WHEELHOUSE.WheelhouseError


def make_wheel(directory: Path, name: str, version: str, *, metadata_name: str | None = None,
               metadata_version: str | None = None) -> Path:
    normalized = name.replace("-", "_")
    path = directory / f"{normalized}-{version}-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        # Fixed timestamp: wheel bytes must be deterministic across calls so
        # merge tests exercise the intended conflict path, not a hash
        # mismatch caused by same-second vs cross-second zip timestamps.
        info = zipfile.ZipInfo(f"{normalized}-{version}.dist-info/METADATA", date_time=(2026, 1, 1, 0, 0, 0))
        archive.writestr(
            info,
            f"Metadata-Version: 2.1\nName: {metadata_name or name}\nVersion: {metadata_version or version}\n",
        )
        archive.writestr(f"{normalized}/__init__.py", "")
    return path


class WheelhouseScriptTests(unittest.TestCase):
    def _wheelhouse(self, temp: str) -> Path:
        wheelhouse = Path(temp) / "wheelhouse"
        wheelhouse.mkdir()
        make_wheel(wheelhouse, "mcp", "2.0.0")
        make_wheel(wheelhouse, "pydantic", "2.12.0")
        make_wheel(wheelhouse, "typing-extensions", "4.15.0")
        return wheelhouse

    def test_lock_formatting_sorted_pinned_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            wheelhouse = self._wheelhouse(temp)
            result = WHEELHOUSE.finalize(wheelhouse, arch="arm64")
            lines = result["lock"].read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, sorted(lines))
            for line in lines:
                name_version, _, hash_part = line.partition(" --hash=")
                name, _, version = name_version.partition("==")
                self.assertTrue(name and version)
                self.assertRegex(hash_part, r"^sha256:[0-9a-f]{64}$")
            self.assertIn("mcp==2.0.0", lines[0] + lines[1] + lines[2])
            pinned = [line for line in lines if line.startswith("mcp==")]
            self.assertEqual(len(pinned), 1)
            self.assertTrue(pinned[0].startswith("mcp==2.0.0 --hash=sha256:"))

    def test_hash_emission_matches_wheel_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            wheelhouse = self._wheelhouse(temp)
            result = WHEELHOUSE.finalize(wheelhouse, arch="arm64")
            for entry in result["wheels"]:
                actual = hashlib.sha256((wheelhouse / entry["filename"]).read_bytes()).hexdigest()
                self.assertEqual(entry["sha256"], actual)
                self.assertEqual(entry["size"], (wheelhouse / entry["filename"]).stat().st_size)

    def test_manifest_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            wheelhouse = self._wheelhouse(temp)
            result = WHEELHOUSE.finalize(wheelhouse, arch="x86_64")
            manifest = json.loads(result["manifest"].read_text(encoding="utf-8"))
            self.assertEqual(manifest["package"], "mcp==2.0.0")
            self.assertEqual(manifest["targetTriple"], "cp314-macos-x86_64")
            self.assertIn("generatedAt", manifest)
            self.assertIn("executable", manifest["interpreter"])
            self.assertIn("version", manifest["interpreter"])
            for wheel in manifest["wheels"]:
                for field in ("filename", "size", "sha256", "name", "version"):
                    self.assertIn(field, wheel)

    def test_sdist_rejected_without_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            wheelhouse = self._wheelhouse(temp)
            (wheelhouse / "mcp-2.0.0.tar.gz").write_bytes(b"sdist")
            with self.assertRaises(WheelhouseError):
                WHEELHOUSE.finalize(wheelhouse, arch="arm64")
            self.assertFalse(list(wheelhouse.glob("requirements-*.lock")))
            self.assertFalse((wheelhouse / "WHEELHOUSE_MANIFEST.json").exists())

    def test_duplicate_distribution_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            wheelhouse = self._wheelhouse(temp)
            make_wheel(wheelhouse, "pydantic", "2.11.0")
            with self.assertRaisesRegex(WheelhouseError, "Duplicate distribution"):
                WHEELHOUSE.finalize(wheelhouse, arch="arm64")

    def test_empty_download_dir_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            wheelhouse = Path(temp) / "empty"
            wheelhouse.mkdir()
            with self.assertRaisesRegex(WheelhouseError, "empty"):
                WHEELHOUSE.finalize(wheelhouse, arch="arm64")

    def test_metadata_mismatch_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            wheelhouse = self._wheelhouse(temp)
            make_wheel(wheelhouse, "anyio", "4.0.0", metadata_version="3.9.9")
            with self.assertRaisesRegex(WheelhouseError, "identity mismatch"):
                WHEELHOUSE.finalize(wheelhouse, arch="arm64")

    def test_mcp_pin_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            wheelhouse = Path(temp) / "wheelhouse"
            wheelhouse.mkdir()
            make_wheel(wheelhouse, "mcp", "1.9.9")
            with self.assertRaisesRegex(WheelhouseError, "mcp==2.0.0"):
                WHEELHOUSE.finalize(wheelhouse, arch="arm64")


def make_tagged_wheel(directory: Path, name: str, version: str, platform_tag: str) -> Path:
    normalized = name.replace("-", "_")
    path = directory / f"{normalized}-{version}-cp314-cp314-{platform_tag}.whl"
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo(f"{normalized}-{version}.dist-info/METADATA", date_time=(2026, 1, 1, 0, 0, 0))
        archive.writestr(
            info,
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n",
        )
        archive.writestr(f"{normalized}/__init__.py", f"# {platform_tag}\n")
    return path


def _arch_wheelhouse(base: Path, arch: str, *, binary_version: str = "2.7.0") -> Path:
    """A finalized per-target wheelhouse: shared pure wheels plus one
    arch-specific binary wheel (the pydantic-core pattern)."""
    wheelhouse = base / f"wheelhouse-{arch}"
    wheelhouse.mkdir()
    make_wheel(wheelhouse, "mcp", "2.0.0")
    make_wheel(wheelhouse, "pydantic", "2.12.0")
    make_tagged_wheel(wheelhouse, "pydantic-core", binary_version, f"macosx_11_0_{arch}")
    WHEELHOUSE.finalize(wheelhouse, arch=arch)
    return wheelhouse


class WheelhouseMergeTests(unittest.TestCase):
    def test_merge_deterministic_and_per_target_locks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = _arch_wheelhouse(base, "arm64")
            x86_64 = _arch_wheelhouse(base, "x86_64")
            first = base / "merged-1"
            second = base / "merged-2"
            result = WHEELHOUSE.merge_wheelhouses([(arm64, "arm64"), (x86_64, "x86_64")], first)
            WHEELHOUSE.merge_wheelhouses([(x86_64, "x86_64"), (arm64, "arm64")], second)
            # Determinism: input order and re-runs never change output bytes.
            for name in (
                "requirements-cp314-macos-arm64.lock",
                "requirements-cp314-macos-x86_64.lock",
                "MERGED_WHEELHOUSE_MANIFEST.json",
            ):
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(), name)
            arm_lock = (first / "requirements-cp314-macos-arm64.lock").read_text(encoding="utf-8")
            x86_lock = (first / "requirements-cp314-macos-x86_64.lock").read_text(encoding="utf-8")
            # Pure wheels carry one hash; the binary distribution carries
            # exactly its target-compatible hash on each lock.
            arm_binary = [line for line in arm_lock.splitlines() if line.startswith("pydantic-core==")][0]
            x86_binary = [line for line in x86_lock.splitlines() if line.startswith("pydantic-core==")][0]
            self.assertEqual(arm_binary.count("--hash="), 1)
            self.assertEqual(x86_binary.count("--hash="), 1)
            self.assertNotEqual(arm_binary, x86_binary)
            pure = [line for line in arm_lock.splitlines() if line.startswith("pydantic==")][0]
            self.assertIn(pure, x86_lock)
            self.assertIn("mcp==2.0.0 --hash=sha256:", arm_lock)
            self.assertEqual(result["distributions"], ["mcp", "pydantic", "pydantic-core"])
            # Merged output contains the union of wheel files.
            self.assertTrue((first / "pydantic_core-2.7.0-cp314-cp314-macosx_11_0_arm64.whl").is_file())
            self.assertTrue((first / "pydantic_core-2.7.0-cp314-cp314-macosx_11_0_x86_64.whl").is_file())

    def test_merge_version_conflict_aborts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = _arch_wheelhouse(base, "arm64", binary_version="2.7.0")
            x86_64 = _arch_wheelhouse(base, "x86_64", binary_version="2.8.0")
            with self.assertRaisesRegex(WheelhouseError, "Version conflict"):
                WHEELHOUSE.merge_wheelhouses([(arm64, "arm64"), (x86_64, "x86_64")], base / "out")

    def test_merge_rejects_unfinalized_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = _arch_wheelhouse(base, "arm64")
            raw = base / "raw"
            raw.mkdir()
            make_wheel(raw, "mcp", "2.0.0")
            with self.assertRaisesRegex(WheelhouseError, "not a finalized wheelhouse"):
                WHEELHOUSE.merge_wheelhouses([(arm64, "arm64"), (raw, "x86_64")], base / "out")

    def test_merge_rejects_unknown_or_duplicate_arch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = _arch_wheelhouse(base, "arm64")
            with self.assertRaisesRegex(WheelhouseError, "architectures|one wheelhouse per"):
                WHEELHOUSE.merge_wheelhouses([(arm64, "arm64"), (arm64, "arm64")], base / "out")

    def test_merge_rejects_single_architecture(self) -> None:
        # R6-06: exactly one arm64 and one x86_64 input are required.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = _arch_wheelhouse(base, "arm64")
            with self.assertRaisesRegex(WheelhouseError, "exactly one reviewed arm64"):
                WHEELHOUSE.merge_wheelhouses([(arm64, "arm64")], base / "out")

    def test_merge_rejects_extra_architecture_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = _arch_wheelhouse(base, "arm64")
            x86_64 = _arch_wheelhouse(base, "x86_64")
            with self.assertRaisesRegex(WheelhouseError, "exactly one reviewed arm64|architectures"):
                WHEELHOUSE.merge_wheelhouses(
                    [(arm64, "arm64"), (x86_64, "x86_64"), (arm64, "riscv64")], base / "out"
                )

    def test_merge_rejects_mislabeled_architecture(self) -> None:
        # R6-06: each input manifest's target triple must match the
        # architecture it is declared as.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = _arch_wheelhouse(base, "arm64")
            x86_64 = _arch_wheelhouse(base, "x86_64")
            # Swapped labels: each declared architecture is present once, but
            # each manifest's triple betrays the mislabel.
            with self.assertRaisesRegex(WheelhouseError, "does not match its declared architecture"):
                WHEELHOUSE.merge_wheelhouses([(x86_64, "arm64"), (arm64, "x86_64")], base / "out")
            # A manifest whose recorded triple was altered after finalize.
            manifest_path = arm64 / "WHEELHOUSE_MANIFEST.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["targetTriple"] = "cp314-macos-x86_64"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(WheelhouseError, "does not match its declared architecture"):
                WHEELHOUSE.merge_wheelhouses([(arm64, "arm64"), (x86_64, "x86_64")], base / "out")

    def test_universal2_wheel_serves_both_locks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = base / "wheelhouse-arm64"
            arm64.mkdir()
            make_wheel(arm64, "mcp", "2.0.0")
            make_tagged_wheel(arm64, "pydantic-core", "2.7.0", "macosx_10_13_universal2")
            WHEELHOUSE.finalize(arm64, arch="arm64")
            x86_64 = base / "wheelhouse-x86_64"
            x86_64.mkdir()
            make_wheel(x86_64, "mcp", "2.0.0")
            make_tagged_wheel(x86_64, "pydantic-core", "2.7.0", "macosx_10_13_universal2")
            WHEELHOUSE.finalize(x86_64, arch="x86_64")
            out = base / "merged"
            WHEELHOUSE.merge_wheelhouses([(arm64, "arm64"), (x86_64, "x86_64")], out)
            arm_lock = (out / "requirements-cp314-macos-arm64.lock").read_text(encoding="utf-8")
            x86_lock = (out / "requirements-cp314-macos-x86_64.lock").read_text(encoding="utf-8")
            self.assertEqual(arm_lock, x86_lock)

    def test_merge_rejects_distribution_missing_from_one_target(self) -> None:
        # R6-06: a distribution present in only one reviewed target manifest
        # must fail closed.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = _arch_wheelhouse(base, "arm64")
            x86_64 = _arch_wheelhouse(base, "x86_64")
            # Drop pydantic from the x86_64 manifest (and its wheel file).
            manifest_path = x86_64 / "WHEELHOUSE_MANIFEST.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["wheels"] = [w for w in manifest["wheels"] if w["name"] != "pydantic"]
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            for wheel in x86_64.glob("pydantic-*.whl"):
                wheel.unlink()
            with self.assertRaisesRegex(WheelhouseError, "Distribution sets differ across targets"):
                WHEELHOUSE.merge_wheelhouses([(arm64, "arm64"), (x86_64, "x86_64")], base / "out")

    def test_merge_rejects_pure_wheel_in_only_one_manifest(self) -> None:
        # R6-06: a pure/universal wheel appearing in only one reviewed target
        # manifest must fail closed.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = _arch_wheelhouse(base, "arm64")
            x86_64 = _arch_wheelhouse(base, "x86_64")
            # Add a pure wheel to the arm64 manifest only.
            make_wheel(arm64, "pureonly", "1.0.0")
            WHEELHOUSE.finalize(arm64, arch="arm64")
            with self.assertRaisesRegex(WheelhouseError, "Distribution sets differ across targets"):
                WHEELHOUSE.merge_wheelhouses([(arm64, "arm64"), (x86_64, "x86_64")], base / "out")

    def test_merge_rejects_version_difference_across_targets(self) -> None:
        # R6-06: identical distribution sets with a version difference must
        # fail closed.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = _arch_wheelhouse(base, "arm64")
            x86_64 = _arch_wheelhouse(base, "x86_64")
            # Bump pydantic's version in the x86_64 manifest only.
            manifest_path = x86_64 / "WHEELHOUSE_MANIFEST.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for w in manifest["wheels"]:
                if w["name"] == "pydantic":
                    w["version"] = "2.13.0"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(WheelhouseError, "Version conflict for pydantic"):
                WHEELHOUSE.merge_wheelhouses([(arm64, "arm64"), (x86_64, "x86_64")], base / "out")

    def test_merge_rejects_swapped_target_labels(self) -> None:
        # R6-06: swapped target labels must fail closed via the triple check.
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            arm64 = _arch_wheelhouse(base, "arm64")
            x86_64 = _arch_wheelhouse(base, "x86_64")
            with self.assertRaisesRegex(WheelhouseError, "does not match its declared architecture"):
                WHEELHOUSE.merge_wheelhouses([(x86_64, "arm64"), (arm64, "x86_64")], base / "out")


if __name__ == "__main__":
    unittest.main()
