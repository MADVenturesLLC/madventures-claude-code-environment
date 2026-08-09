from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from madclaude.errors import RepositoryError
from madclaude.git import (assert_ancestor, detached_worktree, diff_files, get_state, require_clean, require_unchanged, resolve_full_sha, working_tree_fingerprint)
from support import make_git_repo


class GitTests(unittest.TestCase):
    def test_exact_sha_ancestry_and_detached_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            base = resolve_full_sha(repo, subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(), require_literal=True)
            (repo / "src.txt").write_text("hello\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "src.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "add"], check=True)
            head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
            assert_ancestor(repo, base, head)
            self.assertEqual(diff_files(repo, base, head), ("src.txt",))
            with detached_worktree(repo, head) as worktree:
                before = get_state(worktree)
                self.assertEqual(before.head_sha, head)
                self.assertTrue((worktree / "src.txt").is_file())
                require_unchanged(before, get_state(worktree), "test")
            with self.assertRaises(RepositoryError):
                resolve_full_sha(repo, "HEAD", require_literal=True)

    def test_clean_tree_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            require_clean(repo)
            (repo / "dirty.txt").write_text("dirty", encoding="utf-8")
            with self.assertRaises(RepositoryError):
                require_clean(repo)


    def test_working_tree_fingerprint_detects_same_path_content_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = make_git_repo(Path(temp) / "repo")
            target = repo / "README.md"
            target.write_text("first change\n", encoding="utf-8")
            first = working_tree_fingerprint(repo)
            target.write_text("second change\n", encoding="utf-8")
            second = working_tree_fingerprint(repo)
            self.assertNotEqual(first, second)
            self.assertEqual(second, working_tree_fingerprint(repo))


if __name__ == "__main__":
    unittest.main()
