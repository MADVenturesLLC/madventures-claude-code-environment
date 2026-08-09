from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

from .errors import RepositoryError

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class GitState:
    repository: str
    branch: str
    head_sha: str
    clean: bool
    changed_files: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_git(repo: Path, *args: str, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise RepositoryError(
            f"Git command failed ({' '.join(args)}): {(result.stderr or result.stdout).strip()}"
        )
    return result


def repository_root(repo: Path) -> Path:
    result = run_git(repo.resolve(), "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()).resolve()


def changed_files(repo: Path) -> tuple[str, ...]:
    result = run_git(repo, "status", "--porcelain=v1", "-z")
    records = result.stdout.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        path = record[3:] if len(record) >= 4 else record
        if record[:2].strip().startswith(("R", "C")) and index < len(records):
            path = records[index]
            index += 1
        paths.append(path.replace("\\", "/"))
    return tuple(sorted(set(paths)))


def working_tree_fingerprint(repo: Path) -> str:
    """Hash Git status plus changed working-tree content without persisting source text."""
    root = repository_root(repo)
    digest = hashlib.sha256()
    raw_status = run_git(root, "status", "--porcelain=v1", "-z").stdout.encode("utf-8", errors="surrogateescape")
    digest.update(b"status\0")
    digest.update(raw_status)

    def add_path(relative: str, path: Path) -> None:
        normalized = relative.replace("\\", "/")
        digest.update(b"path\0" + normalized.encode("utf-8", errors="surrogateescape") + b"\0")
        try:
            stat_result = path.lstat()
        except FileNotFoundError:
            digest.update(b"missing\0")
            return
        digest.update(f"mode:{stat_result.st_mode:o}\0".encode())
        if path.is_symlink():
            digest.update(b"symlink\0" + os.readlink(path).encode("utf-8", errors="surrogateescape") + b"\0")
        elif path.is_file():
            digest.update(b"file\0")
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        elif path.is_dir():
            digest.update(b"dir\0")
            for child in sorted((item for item in path.rglob("*") if ".git" not in item.parts), key=lambda item: item.as_posix()):
                add_path(child.relative_to(root).as_posix(), child)
        else:
            digest.update(b"other\0")

    for relative in changed_files(root):
        if relative == ".claude/evidence" or relative.startswith(".claude/evidence/"):
            continue
        add_path(relative, root / relative)
    return digest.hexdigest()


def get_state(repo: Path) -> GitState:
    root = repository_root(repo)
    branch_result = run_git(root, "symbolic-ref", "--short", "-q", "HEAD", check=False)
    branch = branch_result.stdout.strip() or "DETACHED"
    head = run_git(root, "rev-parse", "HEAD").stdout.strip().lower()
    changed = changed_files(root)
    return GitState(str(root), branch, head, not changed, changed)


def require_clean(repo: Path) -> GitState:
    state = get_state(repo)
    if not state.clean:
        raise RepositoryError(
            "Governed mutation requires a clean working tree. Commit, stash, or use a separate "
            "worktree first. Existing changes: " + ", ".join(state.changed_files)
        )
    return state


def require_unchanged(before: GitState, after: GitState, label: str) -> None:
    if before.head_sha != after.head_sha or before.changed_files != after.changed_files:
        raise RepositoryError(
            f"{label} was required to be read-only, but repository state changed. "
            f"Before={before.changed_files}; after={after.changed_files}."
        )


def resolve_full_sha(repo: Path, ref: str, *, require_literal: bool = False) -> str:
    candidate = ref.strip().lower()
    if require_literal and not FULL_SHA.fullmatch(candidate):
        raise RepositoryError(f"Exact-SHA workflow requires a full 40-character SHA, not {ref!r}.")
    resolved = run_git(repo, "rev-parse", f"{candidate}^{{commit}}").stdout.strip().lower()
    if not FULL_SHA.fullmatch(resolved):
        raise RepositoryError(f"Could not resolve a full commit SHA from {ref!r}.")
    if require_literal and resolved != candidate:
        raise RepositoryError(f"The supplied SHA does not resolve to itself: {ref!r}.")
    return resolved


def assert_ancestor(repo: Path, base_sha: str, head_sha: str) -> None:
    result = run_git(repo, "merge-base", "--is-ancestor", base_sha, head_sha, check=False)
    if result.returncode != 0:
        raise RepositoryError(f"Base SHA {base_sha} is not an ancestor of head SHA {head_sha}.")


def diff_files(repo: Path, base_sha: str, head_sha: str) -> tuple[str, ...]:
    result = run_git(repo, "diff", "--name-only", "--no-renames", base_sha, head_sha)
    return tuple(line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip())


def diff_text(repo: Path, base_sha: str, head_sha: str, *, max_chars: int = 240_000) -> tuple[str, bool]:
    result = run_git(
        repo,
        "diff",
        "--no-ext-diff",
        "--no-color",
        "--find-renames=50%",
        "--unified=40",
        base_sha,
        head_sha,
        timeout=180,
    )
    text = result.stdout
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n\n[DIFF TRUNCATED BY CONTROL PLANE]\n", True


@contextmanager
def detached_worktree(repo: Path, head_sha: str) -> Iterator[Path]:
    root = repository_root(repo)
    parent = Path(tempfile.mkdtemp(prefix="madclaude-review-"))
    worktree = parent / "worktree"
    run_git(root, "worktree", "add", "--detach", str(worktree), head_sha, timeout=180)
    try:
        yield worktree
    finally:
        run_git(root, "worktree", "remove", "--force", str(worktree), check=False, timeout=180)
        shutil.rmtree(parent, ignore_errors=True)
