"""U9: activation lifecycle verbs and the ownership record (clarifications 1-11)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from madclaude import mcp_lifecycle
from madclaude.errors import PolicyViolation
from madclaude.mcp_lifecycle import (
    disable,
    enable,
    releases_root,
    reenable,
    remove,
    rollback,
    status,
    verify_release_prelaunch,
    wrapper_path,
)
from test_mcp_release_install import Fixture


class LifecycleTests(unittest.TestCase):
    def _two_releases(self, base: Path) -> tuple[Fixture, Path, Path]:
        fixture = Fixture(base)
        first = fixture.install()
        # A second, distinct release identity (different source manifest).
        second_manifest = base / "MANIFEST.v2.json"
        second_manifest.write_text('{"files": ["v2"]}\n', encoding="utf-8")
        second = fixture.install(source_manifest=second_manifest)
        return fixture, first, second

    def test_full_verb_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            self.assertEqual(status(home)["identity"], first.name)
            disable(home)
            self.assertEqual(status(home)["state"], "disabled")
            reenable(home)
            self.assertEqual(status(home)["identity"], first.name)
            rollback(home, second.name)
            self.assertEqual(status(home)["identity"], second.name)
            report = remove(home, first.name)
            self.assertEqual(report["removed"], [first.name])
            self.assertFalse(first.exists())
            self.assertTrue(second.exists())

    def test_atomic_symlink_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            current = releases_root(home) / "current"
            self.assertTrue(current.is_symlink())
            self.assertEqual(os.readlink(current), first.name)  # relative target
            enable(home, second)
            self.assertEqual(os.readlink(current), second.name)
            self.assertFalse(list(releases_root(home).glob("current.tmp.*")))

    def test_no_delete_before_move(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            real_unlink = os.unlink

            def guarded_unlink(path, *args, **kwargs):
                if Path(path).name == "current":
                    raise AssertionError("activation must not unlink current")
                return real_unlink(path, *args, **kwargs)

            with mock.patch.object(mcp_lifecycle.os, "unlink", guarded_unlink):
                enable(home, second)
            self.assertEqual(os.readlink(releases_root(home) / "current"), second.name)

    def test_injected_failure_leaves_no_partial_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            with mock.patch.object(mcp_lifecycle.os, "replace", side_effect=OSError("injected crash")):
                with self.assertRaises(OSError):
                    enable(home, second)
            current = releases_root(home) / "current"
            self.assertEqual(os.readlink(current), first.name)
            self.assertFalse(list(releases_root(home).glob("current.tmp.*")))

    def test_disable_preserves_wrapper_and_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, _ = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            wrapper = wrapper_path(home)
            self.assertTrue(wrapper.is_file())
            disable(home)
            self.assertFalse((releases_root(home) / "current").exists())
            self.assertTrue(wrapper.is_file())
            self.assertTrue(first.exists())
            completed = subprocess.run(["/bin/sh", str(wrapper)], capture_output=True, text=True, check=False)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("madclaude mcp re-enable", completed.stderr)

    def test_reenable_verifies_before_pointing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, _ = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            disable(home)
            integrity_path = first / "RELEASE_INTEGRITY.json"
            doc = json.loads(integrity_path.read_text(encoding="utf-8"))
            doc["hashes"]["APP_MANIFEST.json"] = "0" * 64
            integrity_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
            with self.assertRaises(PolicyViolation):
                reenable(home)
            self.assertFalse((releases_root(home) / "current").exists())

    def test_ownership_record_survives_disable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, _ = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            disable(home)
            state = json.loads((home / "mcp-installation-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["schemaVersion"], 2)
            self.assertIn(first.name, state["releases"])
            self.assertEqual(state["lastEnabled"], first.name)
            self.assertIn("wrapper", state)
            self.assertIn(first.name, state["integrityAnchors"])
            self.assertIn("baseLauncher", state)

    def test_remove_only_owned(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, _ = self._two_releases(Path(temp))
            home = fixture.home
            squat = releases_root(home) / "mcp-2.0.0-4.4.1-deadbeefdead"
            squat.mkdir()
            report = remove(home, squat.name)
            self.assertEqual(report["removed"], [])
            self.assertTrue(squat.exists())
            self.assertIn("not owned", report["leftInPlace"][0])
            enable(home, first)
            with self.assertRaisesRegex(PolicyViolation, "active"):
                remove(home, first.name)
            disable(home)
            report = remove(home, first.name)
            self.assertEqual(report["removed"], [first.name])

    def test_identity_includes_source_sha12(self) -> None:
        import hashlib

        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            expected = hashlib.sha256(b'{"files": []}\n').hexdigest()[:12]
            self.assertTrue(release.name.endswith(f"-{expected}"))

    def test_activation_failure_never_moves_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            integrity_path = second / "RELEASE_INTEGRITY.json"
            doc = json.loads(integrity_path.read_text(encoding="utf-8"))
            doc["installed_inventory"] = {}
            integrity_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
            with self.assertRaises(PolicyViolation):
                enable(home, second)
            self.assertEqual(os.readlink(releases_root(home) / "current"), first.name)

    def test_dangling_current_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, _ = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            current = releases_root(home) / "current"
            current.unlink()
            os.symlink("mcp-2.0.0-4.4.1-missing", current)
            with self.assertRaises(PolicyViolation):
                status(home)

    def test_status_reports_drift_not_prevention(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, _ = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            report = status(home, deep=True)
            self.assertEqual(report["recordLevel"], "verified")
            integrity = json.loads((first / "RELEASE_INTEGRITY.json").read_text(encoding="utf-8"))
            purelib = first / "venv" / integrity["purelib"]
            target = purelib / "mcp-2.0.0.dist-info" / "REQUESTED"
            target.write_text("tampered\n", encoding="utf-8")
            # R6-03: prelaunch now authenticates ALL RECORD-covered files
            # (not just *.py), so a tampered REQUESTED file is caught by
            # prelaunch as a PolicyViolation, not as deep-check drift.
            with self.assertRaises(PolicyViolation):
                status(home, deep=True)

    def test_record_level_missing_installed_file_is_drift(self) -> None:
        # A deleted payload file must surface as drift through the descriptor
        # reader's failure path (not as an unhandled error).  R6-03: prelaunch
        # now catches this as a PolicyViolation, so test verify_record_level
        # directly to verify the drift-reporting path still works.
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            enable(fixture.home, release)
            integrity = json.loads((release / "RELEASE_INTEGRITY.json").read_text(encoding="utf-8"))
            purelib = release / "venv" / integrity["purelib"]
            victim = purelib / "sampledep-2.0.0.dist-info" / "INSTALLER"
            if not victim.is_file():
                victim = purelib / "sampledep-1.0.0.dist-info" / "INSTALLER"
            self.assertTrue(victim.is_file())
            victim.unlink()
            drift = mcp_lifecycle.verify_record_level(release)
            self.assertTrue(any("sampledep" in entry for entry in drift))

    def test_record_level_out_of_purelib_rows_are_skipped(self) -> None:
        # RECORD rows for venv scaffolding outside purelib (entry-point
        # scripts under bin/) stay out of drift scope.
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            integrity_path = release / "RELEASE_INTEGRITY.json"
            doc = json.loads(integrity_path.read_text(encoding="utf-8"))
            doc["installed_records"]["sampledep"]["files"]["../../../bin/sampledep-script"] = (
                "sha256=" + "0" * 43
            )
            integrity_path.write_text(json.dumps(doc), encoding="utf-8")
            self.assertEqual(mcp_lifecycle.verify_record_level(release), [])

    def test_no_durability_claim_in_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, _ = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            text = json.dumps(status(home, deep=True)).lower()
            for word in ("durable", "durability", "crash-proof", "power-loss safe"):
                self.assertNotIn(word, text)

    def test_wrapper_launches_base_not_release(self) -> None:
        # R3: the sanctioned launch path execs the BASE control plane's
        # `mcp serve`; release-owned code runs only after externally anchored
        # verification inside that base process.
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, _ = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            content = wrapper_path(home).read_text(encoding="utf-8")
            self.assertIn("mcp serve", content)
            self.assertIn(str(home / "bin" / "madclaude"), content)
            self.assertNotIn("launcher/mcp-server", content)
            state = json.loads((home / "mcp-installation-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["baseLauncher"], str((home / "bin" / "madclaude").resolve()))

    def test_remove_refuses_symlinked_release_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, _ = self._two_releases(Path(temp))
            home = fixture.home
            state = json.loads((home / "mcp-installation-state.json").read_text(encoding="utf-8"))
            state["releases"].append("linked-release")
            (home / "mcp-installation-state.json").write_text(json.dumps(state), encoding="utf-8")
            os.symlink(first, releases_root(home) / "linked-release")
            with self.assertRaisesRegex(PolicyViolation, "symlinked"):
                remove(home, "linked-release")
            self.assertTrue(first.exists())

    def test_remove_race_restores_release(self) -> None:
        # If the release becomes active between the trash rename and the
        # re-check, removal aborts and the directory is restored untouched.
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, second)
            calls = {"count": 0}
            real_readlink = os.readlink

            def raced_readlink(path, *args, **kwargs):
                if Path(path).name == "current":
                    calls["count"] += 1
                    if calls["count"] > 1:
                        return first.name  # simulated concurrent activation of first
                return real_readlink(path, *args, **kwargs)

            with mock.patch.object(mcp_lifecycle.os, "readlink", raced_readlink):
                with self.assertRaisesRegex(PolicyViolation, "became active during removal"):
                    remove(home, first.name)
            self.assertTrue((first / "RELEASE_INTEGRITY.json").is_file())
            self.assertFalse(list(releases_root(home).glob(".trash.*")))
            self.assertEqual(os.readlink(releases_root(home) / "current"), second.name)

    def test_staged_self_test_pre_activation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            # No enable, no current pointer: the base-orchestrated staged
            # self-test still runs the install-tier verification first.
            before = {p.relative_to(release).as_posix() for p in release.rglob("*")}
            mcp_lifecycle.staged_self_test(fixture.home, release)
            after = {p.relative_to(release).as_posix() for p in release.rglob("*")}
            self.assertEqual(before, after)  # the self-test must not dirty the byte-frozen payload
            with self.assertRaisesRegex(PolicyViolation, "disabled"):
                mcp_lifecycle.serve(fixture.home, [])

    def test_enable_fails_closed_without_base_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, _ = self._two_releases(Path(temp))
            home = fixture.home
            (home / "bin" / "madclaude").unlink()
            env = {k: v for k, v in os.environ.items() if k != "MADCLAUDE_BASE_LAUNCHER"}
            with mock.patch.object(mcp_lifecycle.shutil, "which", return_value=None):
                with mock.patch.dict(os.environ, env, clear=True):
                    with self.assertRaisesRegex(PolicyViolation, "base control-plane launcher"):
                        enable(home, first)
            self.assertFalse((releases_root(home) / "current").exists())


class TransactionalLifecycleTests(unittest.TestCase):
    """R6-05: shared lifecycle lock, compensating rollback of current, and
    cleanup limited to uniquely owned assets under fault injection."""

    def _two_releases(self, base: Path) -> tuple[Fixture, Path, Path]:
        fixture = Fixture(base)
        first = fixture.install()
        second_manifest = base / "MANIFEST.v2.json"
        second_manifest.write_text('{"files": ["v2"]}\n', encoding="utf-8")
        second = fixture.install(source_manifest=second_manifest)
        return fixture, first, second

    def test_enable_state_write_failure_restores_prior_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            with mock.patch.object(mcp_lifecycle, "_write_state", side_effect=OSError("injected state failure")):
                with self.assertRaises(OSError):
                    enable(home, second)
            current = releases_root(home) / "current"
            self.assertEqual(os.readlink(current), first.name)  # prior current restored
            self.assertEqual(status(home)["identity"], first.name)
            verify_release_prelaunch(first, home=home)  # prior active release still valid
            state = json.loads((home / "mcp-installation-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["lastEnabled"], first.name)  # prior state bytes intact

    def test_enable_state_write_failure_without_prior_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            release = fixture.install()
            with mock.patch.object(mcp_lifecycle, "_write_state", side_effect=OSError("injected state failure")):
                with self.assertRaises(OSError):
                    enable(fixture.home, release)
            current = releases_root(fixture.home) / "current"
            self.assertFalse(current.is_symlink() or current.exists())  # pointer removed, not left moved

    def test_rollback_state_write_failure_restores_prior_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, first)
            enable(home, second)
            with mock.patch.object(mcp_lifecycle, "_write_state", side_effect=OSError("injected rollback failure")):
                with self.assertRaises(OSError):
                    rollback(home, first.name)
            current = releases_root(home) / "current"
            self.assertEqual(os.readlink(current), second.name)  # prior current restored
            self.assertEqual(status(home)["identity"], second.name)
            verify_release_prelaunch(second, home=home)  # prior active release still valid
            state = json.loads((home / "mcp-installation-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["lastEnabled"], second.name)

    def test_install_ownership_failure_leaves_no_orphaned_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture = Fixture(base)
            first = fixture.install()
            enable(fixture.home, first)
            second_manifest = base / "MANIFEST.v2.json"
            second_manifest.write_text('{"files": ["v2"]}\n', encoding="utf-8")
            with mock.patch.object(mcp_lifecycle, "_write_state", side_effect=OSError("injected ownership failure")):
                with self.assertRaises(OSError):
                    fixture.install(source_manifest=second_manifest)
            root = releases_root(fixture.home)
            self.assertEqual([entry.name for entry in root.iterdir() if entry.name != "current"], [first.name])
            self.assertFalse(list(root.glob(".staging.*")))
            self.assertEqual(os.readlink(root / "current"), first.name)
            verify_release_prelaunch(first, home=fixture.home)  # prior release untouched and valid
            state = json.loads((fixture.home / "mcp-installation-state.json").read_text(encoding="utf-8"))
            self.assertNotIn("v2", json.dumps(state["releases"]))

    def test_install_reuse_ownership_failure_preserves_prior_release(self) -> None:
        # The reuse path re-records ownership of an EXISTING release; a failed
        # write there must never remove it.
        with tempfile.TemporaryDirectory() as temp:
            fixture = Fixture(Path(temp))
            first = fixture.install()
            with mock.patch.object(mcp_lifecycle, "_write_state", side_effect=OSError("injected ownership failure")):
                with self.assertRaises(OSError):
                    fixture.install()
            self.assertTrue((first / "RELEASE_INTEGRITY.json").is_file())
            verify_release_prelaunch(first, home=fixture.home)

    def test_lifecycle_lock_contention_blocks_second_opener(self) -> None:
        import fcntl
        import threading

        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            home.mkdir()
            with mcp_lifecycle._lifecycle_lock(home):
                outcomes: list[bool] = []

                def contender() -> None:
                    fd = os.open(home / mcp_lifecycle.LIFECYCLE_LOCK_NAME, os.O_RDWR)
                    try:
                        try:
                            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            outcomes.append(True)
                        except BlockingIOError:
                            outcomes.append(False)
                    finally:
                        os.close(fd)

                thread = threading.Thread(target=contender)
                thread.start()
                thread.join(timeout=30)
            self.assertEqual(outcomes, [False])  # held lock excludes any second opener

    def test_remove_serializes_with_activation(self) -> None:
        # With the lifecycle lock held, a concurrent remove cannot interleave
        # between any active check and deletion; it waits for the lock and
        # only then completes against the final state.
        import threading
        import time

        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, second)
            with mcp_lifecycle._lifecycle_lock(home):
                reports: list[dict] = []

                def contender() -> None:
                    reports.append(remove(home, first.name))

                thread = threading.Thread(target=contender)
                thread.start()
                time.sleep(0.5)
                self.assertEqual(reports, [])  # blocked on the shared lock
                self.assertTrue((first / "RELEASE_INTEGRITY.json").is_file())
            thread.join(timeout=60)
            self.assertEqual(reports[0]["removed"], [first.name])
            self.assertFalse(first.exists())
            self.assertEqual(os.readlink(releases_root(home) / "current"), second.name)
            verify_release_prelaunch(second, home=home)

    def test_remove_state_write_failure_restores_release(self) -> None:
        # R6-05: a failed state write during remove must restore the release
        # from trash — never a missing owned release, never stale ownership.
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, second)
            with mock.patch.object(mcp_lifecycle, "_write_state", side_effect=OSError("injected state failure")):
                with self.assertRaises(OSError):
                    remove(home, first.name)
            # Release restored untouched.
            self.assertTrue((first / "RELEASE_INTEGRITY.json").is_file())
            # No trash residue.
            self.assertFalse(list(releases_root(home).glob(".trash.*")))
            # State still records ownership (unchanged).
            state = json.loads((home / "mcp-installation-state.json").read_text(encoding="utf-8"))
            self.assertIn(first.name, state["releases"])
            self.assertIn(first.name, state["integrityAnchors"])
            # Prior active release untouched and valid.
            self.assertEqual(os.readlink(releases_root(home) / "current"), second.name)
            verify_release_prelaunch(second, home=home)

    def test_remove_trash_cleanup_failure_leaves_recoverable_trash(self) -> None:
        # R6-05: a failed trash deletion surfaces loudly and leaves only the
        # uniquely named recoverable trash — state already records removal,
        # so there is no stale ownership and no missing owned release.
        with tempfile.TemporaryDirectory() as temp:
            fixture, first, second = self._two_releases(Path(temp))
            home = fixture.home
            enable(home, second)
            with mock.patch.object(mcp_lifecycle.shutil, "rmtree", side_effect=OSError("injected cleanup failure")):
                with self.assertRaises(OSError):
                    remove(home, first.name)
            # State records removal (no stale ownership).
            state = json.loads((home / "mcp-installation-state.json").read_text(encoding="utf-8"))
            self.assertNotIn(first.name, state["releases"])
            self.assertNotIn(first.name, state["integrityAnchors"])
            # The release is gone from its owned path; exactly one uniquely
            # named recoverable trash remains.
            self.assertFalse(first.exists())
            trashes = list(releases_root(home).glob(".trash.*"))
            self.assertEqual(len(trashes), 1)
            self.assertTrue((trashes[0] / "RELEASE_INTEGRITY.json").is_file())
            # Prior active release untouched and valid.
            self.assertEqual(os.readlink(releases_root(home) / "current"), second.name)
            verify_release_prelaunch(second, home=home)


class PreExecutionDependencyAuthTests(unittest.TestCase):
    """R6-03 (P0): every interpreter-consumed dependency file must be
    authenticated BEFORE release Python executes.  Tests tamper with
    .so/.pth/pyvenv.cfg/sitecustomize/bytecode and prove prelaunch rejects
    the release."""

    def _make_release(self, base: Path) -> tuple[Fixture, Path]:
        fixture = Fixture(base)
        release = fixture.install()
        return fixture, release

    def _purelib(self, release: Path) -> Path:
        integrity = json.loads((release / "RELEASE_INTEGRITY.json").read_text(encoding="utf-8"))
        return release / "venv" / integrity["purelib"]

    def _integrity(self, release: Path) -> dict:
        return json.loads((release / "RELEASE_INTEGRITY.json").read_text(encoding="utf-8"))

    def test_modified_native_so_rejected(self) -> None:
        # Tamper with a .so file if one exists, or add a fake one.
        with tempfile.TemporaryDirectory() as temp:
            fixture, release = self._make_release(Path(temp))
            purelib = self._purelib(release)
            # Find an existing .so or create a fake one that the RECORD covers.
            so_files = list(purelib.rglob("*.so"))
            if so_files:
                target = so_files[0]
                target.write_bytes(b"tampered-native-module")
            else:
                # No .so in fabricated wheels — inject one into a dist-info RECORD
                # and onto disk, then verify prelaunch catches the hash mismatch.
                target = purelib / "sampledep" / "_native.so"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"fake-native-module")
                # Add it to the RECORD so it's "in scope" but with a wrong hash.
                integrity = self._integrity(release)
                for name, record in integrity["installed_records"].items():
                    if name == "sampledep":
                        record["files"]["sampledep/_native.so"] = "sha256=" + "0" * 43
                        break
                (release / "RELEASE_INTEGRITY.json").write_text(
                    json.dumps(integrity, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
            with self.assertRaisesRegex(PolicyViolation, "diverges|drift|mismatch|fail closed"):
                verify_release_prelaunch(release, home=fixture.home, require_anchor=False)

    def test_added_pth_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, release = self._make_release(Path(temp))
            purelib = self._purelib(release)
            (purelib / "evil.pth").write_text("import os; os.system('id')\n", encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "diverges|drift|unrecorded|membership|fail closed"):
                verify_release_prelaunch(release, home=fixture.home, require_anchor=False)

    def test_modified_pyvenv_cfg_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, release = self._make_release(Path(temp))
            cfg = release / "venv" / "pyvenv.cfg"
            original = cfg.read_bytes()
            cfg.write_bytes(original + b"\nevil = true\n")
            with self.assertRaisesRegex(PolicyViolation, "pyvenv|diverg|mismatch|fail closed"):
                verify_release_prelaunch(release, home=fixture.home, require_anchor=False)

    def test_added_sitecustomize_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fixture, release = self._make_release(Path(temp))
            purelib = self._purelib(release)
            (purelib / "sitecustomize.py").write_text("import os; os.system('id')\n", encoding="utf-8")
            with self.assertRaisesRegex(PolicyViolation, "diverges|drift|unrecorded|membership|fail closed"):
                verify_release_prelaunch(release, home=fixture.home, require_anchor=False)

    def test_modified_sitecustomize_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            fixture = Fixture(base, wheel_extra={"sitecustomize.py": '"""reviewed sitecustomize"""\n'})
            release = fixture.install()
            purelib = self._purelib(release)
            target = purelib / "sitecustomize.py"
            self.assertTrue(target.is_file())
            original = target.read_bytes()
            target.write_bytes(original + b"\n# tampered\n")
            with self.assertRaisesRegex(PolicyViolation, "diverges|drift|mismatch|fail closed"):
                verify_release_prelaunch(release, home=fixture.home, require_anchor=False)

    def test_added_pyc_rejected(self) -> None:
        # A .pyc bytecode payload that isn't in the RECORD must fail closed.
        with tempfile.TemporaryDirectory() as temp:
            fixture, release = self._make_release(Path(temp))
            purelib = self._purelib(release)
            cache_dir = purelib / "__pycache__"
            cache_dir.mkdir(exist_ok=True)
            (cache_dir / "evil.cpython-314.pyc").write_bytes(b"\x00" * 16)
            with self.assertRaisesRegex(PolicyViolation, "diverges|drift|unrecorded|membership|fail closed|__pycache__"):
                verify_release_prelaunch(release, home=fixture.home, require_anchor=False)


if __name__ == "__main__":
    unittest.main()
