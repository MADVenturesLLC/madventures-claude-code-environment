from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from madclaude import safe_read
from madclaude.errors import SafeReadError

POSIX = os.name == "posix"
NOFOLLOW_ANY = hasattr(os, "O_NOFOLLOW_ANY")
COMPONENT_WALK = (
    os.open in os.supports_dir_fd
    and hasattr(os, "O_NOFOLLOW")
    and hasattr(os, "O_DIRECTORY")
)


class FDTracker:
    def __init__(self) -> None:
        self.opens = 0
        self.closes = 0
        self._real_open = os.open
        self._real_close = os.close

    def open(self, *args, **kwargs):
        fd = self._real_open(*args, **kwargs)
        self.opens += 1
        return fd

    def close(self, fd) -> None:
        self.closes += 1
        self._real_close(fd)

    def __enter__(self) -> "FDTracker":
        self._patches = [
            mock.patch.object(safe_read.os, "open", self.open),
            mock.patch.object(safe_read.os, "close", self.close),
        ]
        for patch in self._patches:
            patch.start()
        return self

    def __exit__(self, *exc) -> None:
        for patch in self._patches:
            patch.stop()
        assert self.opens == self.closes, f"leaked descriptors: {self.opens} opens vs {self.closes} closes"


def strategies() -> list[str]:
    available = []
    if NOFOLLOW_ANY:
        available.append("nofollow_any")
    if COMPONENT_WALK:
        available.append("component_walk")
    return available


@unittest.skipUnless(POSIX, "descriptor-based governed reads require POSIX")
class SafeReadTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name).resolve()
        (self.root / "sub").mkdir()
        (self.root / "sub" / "file.txt").write_text("governed-content\n", encoding="utf-8")
        (self.root / "top.txt").write_text("top-level\n", encoding="utf-8")
        self._patches = []

    def tearDown(self) -> None:
        for patch in self._patches:
            patch.stop()
        self._temp.cleanup()

    def _force(self, strategy: str) -> None:
        self._patches.append(
            mock.patch.object(safe_read, "HAS_NOFOLLOW_ANY", strategy == "nofollow_any")
        )
        self._patches.append(
            mock.patch.object(safe_read, "HAS_COMPONENT_WALK", strategy == "component_walk")
        )
        self._patches[-1].start()
        self._patches[-2].start()

    def _root_fd(self) -> int:
        return safe_read.open_root(self.root)

    # --- positive ---

    def test_read_mode_success_both_strategies(self) -> None:
        for strategy in strategies():
            with self.subTest(strategy=strategy):
                self._force(strategy)
                fd = self._root_fd()
                try:
                    self.assertEqual(
                        safe_read.read_bytes(fd, "sub/file.txt"), b"governed-content\n"
                    )
                finally:
                    os.close(fd)
                self.tearDown_patches()

    def tearDown_patches(self) -> None:
        for patch in self._patches:
            patch.stop()
        self._patches = []

    def test_mutation_audit_absent_leaf_ok(self) -> None:
        fd = self._root_fd()
        try:
            self.assertIsNone(safe_read.audit_path(fd, "sub/deleted.txt"))
            self.assertIsNone(safe_read.audit_path(fd, "renamed-away.txt"))
        finally:
            os.close(fd)

    def test_content_and_size_returned(self) -> None:
        fd = self._root_fd()
        try:
            info = safe_read.audit_path(fd, "sub/file.txt")
            self.assertIsNotNone(info)
            assert info is not None
            self.assertTrue(stat.S_ISREG(info.st_mode))
            self.assertEqual(info.st_size, len(b"governed-content\n"))
            self.assertEqual(safe_read.read_text(fd, "top.txt"), "top-level\n")
        finally:
            os.close(fd)

    # --- lexical validation ---

    def test_lexical_components_rejected(self) -> None:
        fd = self._root_fd()
        try:
            for bad in ("../outside.txt", "sub/../../x", "/etc/passwd", "", "sub//file.txt",
                        "sub/./file.txt", "sub\\file.txt", "sub\0file.txt", "."):
                with self.subTest(path=bad):
                    with self.assertRaises(SafeReadError):
                        safe_read.read_bytes(fd, bad)
        finally:
            os.close(fd)

    # --- symlink adversarial cases ---

    def _assert_rejected_both_strategies(self, relpath: str) -> None:
        for strategy in strategies():
            with self.subTest(strategy=strategy, path=relpath):
                self._force(strategy)
                fd = self._root_fd()
                try:
                    with self.assertRaises(SafeReadError):
                        safe_read.read_bytes(fd, relpath)
                finally:
                    os.close(fd)
                self.tearDown_patches()

    def test_symlinked_dot_claude_rejected(self) -> None:
        outside = Path(self._temp.name) / "outside"
        outside.mkdir(exist_ok=True)
        (outside / "settings.json").write_text("{}", encoding="utf-8")
        os.symlink(str(outside), self.root / ".claude")
        self._assert_rejected_both_strategies(".claude/settings.json")

    def test_symlinked_evidence_root_rejected(self) -> None:
        real = Path(self._temp.name) / "real-evidence"
        real.mkdir(exist_ok=True)
        link = Path(self._temp.name) / "evidence-link"
        os.symlink(str(real), link)
        with self.assertRaises(SafeReadError):
            safe_read.open_root(link)

    def test_in_root_symlink_rejected(self) -> None:
        os.symlink("sub", self.root / "alias")
        self._assert_rejected_both_strategies("alias/file.txt")

    def test_out_of_root_symlink_rejected(self) -> None:
        secret = Path(self._temp.name) / "secret.txt"
        secret.write_text("outside-the-root\n", encoding="utf-8")
        os.symlink(str(secret), self.root / "escape.txt")
        self._assert_rejected_both_strategies("escape.txt")

    def test_symlinked_bundle_rejected(self) -> None:
        real_bundle = Path(self._temp.name) / "bundle-real"
        real_bundle.mkdir(exist_ok=True)
        link = Path(self._temp.name) / "bundle-link"
        os.symlink(str(real_bundle), link)
        with self.assertRaises(SafeReadError):
            safe_read.open_root(link)

    def test_symlinked_final_artifact_rejected(self) -> None:
        os.symlink("file.txt", self.root / "sub" / "artifact-link.txt")
        self._assert_rejected_both_strategies("sub/artifact-link.txt")

    def test_preplanted_symlink_swap_rejected(self) -> None:
        # Simulates the check-then-use race: a directory that would pass lexical
        # validation is replaced by a symlink before the open. The descriptor
        # walk makes the race structurally unwinnable — the open itself rejects.
        for strategy in strategies():
            with self.subTest(strategy=strategy):
                self._force(strategy)
                swap = self.root / "swapdir"
                swap.mkdir(exist_ok=True)
                (swap / "file.txt").write_text("original\n", encoding="utf-8")
                # Attacker swaps the validated component for a symlink pre-open.
                (swap / "file.txt").unlink()
                swap.rmdir()
                os.symlink("sub", swap)
                fd = self._root_fd()
                try:
                    with self.assertRaises(SafeReadError):
                        safe_read.read_bytes(fd, "swapdir/file.txt")
                finally:
                    os.close(fd)
                swap.unlink()
                self.tearDown_patches()

    def test_symlinked_parent_rejected_in_audit_mode(self) -> None:
        os.symlink("sub", self.root / "audit-alias")
        fd = self._root_fd()
        try:
            with self.assertRaises(SafeReadError):
                safe_read.audit_path(fd, "audit-alias/file.txt")
        finally:
            os.close(fd)

    # --- failure modes ---

    def test_missing_final_target_read_mode(self) -> None:
        for strategy in strategies():
            with self.subTest(strategy=strategy):
                self._force(strategy)
                fd = self._root_fd()
                try:
                    with self.assertRaises(SafeReadError):
                        safe_read.read_bytes(fd, "sub/missing.txt")
                finally:
                    os.close(fd)
                self.tearDown_patches()

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO test requires os.mkfifo")
    def test_non_regular_final_rejected(self) -> None:
        import threading

        os.mkfifo(self.root / "pipe")
        # Opening a FIFO for reading blocks until a writer arrives; pair a
        # writer thread so the descriptor open completes and fstat can reject
        # the non-regular target.
        writer_error: list[OSError] = []

        def _writer() -> None:
            try:
                wfd = os.open(self.root / "pipe", os.O_WRONLY)
                os.close(wfd)
            except OSError as exc:
                writer_error.append(exc)

        thread = threading.Thread(target=_writer, daemon=True)
        thread.start()
        fd = self._root_fd()
        try:
            with self.assertRaises(SafeReadError):
                safe_read.read_bytes(fd, "pipe")
        finally:
            os.close(fd)
            thread.join(timeout=5)
        self.assertEqual(writer_error, [])

    def test_oversized_file_rejected(self) -> None:
        big = self.root / "big.bin"
        big.write_bytes(b"x" * 1024)
        fd = self._root_fd()
        try:
            with self.assertRaises(SafeReadError):
                safe_read.read_bytes(fd, "big.bin", max_bytes=512)
        finally:
            os.close(fd)

    def test_fail_closed_without_primitives(self) -> None:
        self._patches.append(mock.patch.object(safe_read, "HAS_NOFOLLOW_ANY", False))
        self._patches.append(mock.patch.object(safe_read, "HAS_COMPONENT_WALK", False))
        for patch in self._patches:
            patch.start()
        fd = self._root_fd()
        try:
            with self.assertRaises(SafeReadError):
                safe_read.read_bytes(fd, "sub/file.txt")
        finally:
            os.close(fd)

    # --- descriptor-count audit after injected failures ---

    def test_descriptor_cleanup_on_injected_failures(self) -> None:
        os.symlink("sub", self.root / "leak-alias")
        failures = [
            lambda fd: safe_read.read_bytes(fd, "leak-alias/file.txt"),
            lambda fd: safe_read.read_bytes(fd, "sub/missing.txt"),
            lambda fd: safe_read.read_bytes(fd, "../escape"),
            lambda fd: safe_read.read_bytes(fd, "sub", max_bytes=4),
            lambda fd: safe_read.audit_path(fd, "leak-alias/file.txt"),
        ]
        with FDTracker():
            for failing in failures:
                with self.subTest(failing=failing):
                    fd = self._root_fd()
                    try:
                        with self.assertRaises(SafeReadError):
                            failing(fd)
                    finally:
                        os.close(fd)

    def test_descriptor_cleanup_on_success(self) -> None:
        with FDTracker():
            fd = self._root_fd()
            try:
                safe_read.read_bytes(fd, "sub/file.txt")
                safe_read.audit_path(fd, "sub/file.txt")
                safe_read.audit_path(fd, "absent.txt")
            finally:
                os.close(fd)


if __name__ == "__main__":
    unittest.main()
