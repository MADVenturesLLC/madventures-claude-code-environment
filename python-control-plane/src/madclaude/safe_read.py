"""TOCTOU-safe governed reads (B4).

All governance input files (plans, approvals, evidence manifests, execution
records, canonical artifacts, MCP release manifests) are read through
descriptors rooted at a trusted directory instead of pathname opens, so a
symlink planted or swapped anywhere inside the governed tree cannot redirect
a read outside the trusted root.

Two kernel strategies, probed at import:

- ``nofollow_any`` (macOS, CPython 3.13+): a single
  ``os.open(relpath, O_RDONLY | O_NOFOLLOW_ANY | O_CLOEXEC, dir_fd=root_fd)``.
  The kernel rejects a symlink at any depth of the relative path.
- ``component_walk`` (portable POSIX): each parent component is opened with
  ``O_RDONLY | O_NOFOLLOW | O_DIRECTORY | O_CLOEXEC`` relative to the previous
  descriptor; the final component with ``O_RDONLY | O_NOFOLLOW | O_CLOEXEC``.

When neither primitive is available the module fails closed by raising
SafeReadError; there is deliberately no silent fallback to pathname reads.

Trust assumptions: the trusted root itself (verified repository root, evidence
root, or mcp-releases root) is a trusted input supplied by the caller, as is
the host interpreter. This module does not protect against a malicious local
account owner or a root-level attacker.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .errors import SafeReadError

DEFAULT_MAX_BYTES = 16 * 1024 * 1024

# Capability probe at import. Module-level so tests can force strategies.
HAS_NOFOLLOW_ANY = hasattr(os, "O_NOFOLLOW_ANY")
HAS_COMPONENT_WALK = (
    os.open in os.supports_dir_fd
    and hasattr(os, "O_NOFOLLOW")
    and hasattr(os, "O_DIRECTORY")
)

_COMMON_FLAGS = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)


def _strategy() -> str:
    if HAS_NOFOLLOW_ANY:
        return "nofollow_any"
    if HAS_COMPONENT_WALK:
        return "component_walk"
    raise SafeReadError(
        "TOCTOU-safe governed reads require O_NOFOLLOW_ANY or dir_fd+O_NOFOLLOW+O_DIRECTORY; "
        "neither is available on this platform."
    )


def _components(relpath: str) -> tuple[str, ...]:
    if not isinstance(relpath, str) or not relpath:
        raise SafeReadError("Governed read requires a non-empty relative path.")
    if "\0" in relpath:
        raise SafeReadError(f"Governed read path contains a NUL byte: {relpath!r}")
    if "\\" in relpath:
        raise SafeReadError(f"Governed read path contains an alternate separator: {relpath!r}")
    if relpath.startswith("/"):
        raise SafeReadError(f"Governed read path must be relative to the trusted root: {relpath!r}")
    parts = tuple(relpath.split("/"))
    for part in parts:
        if part in ("", ".", ".."):
            raise SafeReadError(f"Governed read path has an illegal component {part!r}: {relpath!r}")
    return parts


def validate_component(name: str) -> str:
    """Validate a single path component (e.g. an evidence-bundle directory
    name supplied as a tool argument). Any separator, NUL, or dot-component
    fails closed so the name cannot escape or redirect within its parent."""
    if not isinstance(name, str) or not name:
        raise SafeReadError("Governed path component cannot be empty.")
    if name in (".", "..") or "/" in name or "\\" in name or "\0" in name:
        raise SafeReadError(f"Illegal governed path component: {name!r}")
    return name


def open_root(root: Path) -> int:
    """Open the trusted root directory once; the caller owns closing it.

    A symlinked root is rejected when O_NOFOLLOW is available: callers must
    pass the real, verified root directory."""
    flags = _COMMON_FLAGS | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(str(root), flags)
    except OSError as exc:
        raise SafeReadError(f"Could not open trusted root {root}: {exc}") from exc


def _open_nofollow_any(root_fd: int, relpath: str) -> int:
    flags = _COMMON_FLAGS | os.O_NOFOLLOW_ANY
    try:
        return os.open(relpath, flags, dir_fd=root_fd)
    except OSError as exc:
        raise SafeReadError(f"Governed read rejected for {relpath!r}: {exc}") from exc


def _open_component_walk(root_fd: int, parts: tuple[str, ...], *, leaf_required: bool) -> int | None:
    nofollow = os.O_NOFOLLOW
    directory = os.O_DIRECTORY
    current = root_fd
    owned = False
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, _COMMON_FLAGS | nofollow | directory, dir_fd=current)
            if owned:
                os.close(current)
            current, owned = next_fd, True
        try:
            leaf_fd = os.open(parts[-1], _COMMON_FLAGS | nofollow, dir_fd=current)
        except FileNotFoundError:
            if not leaf_required:
                return None
            raise SafeReadError(f"Governed read target is missing: {'/'.join(parts)!r}") from None
        except OSError as exc:
            raise SafeReadError(f"Governed read rejected for {'/'.join(parts)!r}: {exc}") from exc
        return leaf_fd
    except SafeReadError:
        raise
    except OSError as exc:
        raise SafeReadError(f"Governed read rejected for {'/'.join(parts)!r}: {exc}") from exc
    finally:
        if owned:
            os.close(current)


def _open_leaf(root_fd: int, relpath: str, *, leaf_required: bool) -> int | None:
    parts = _components(relpath)
    if _strategy() == "nofollow_any":
        try:
            return _open_nofollow_any(root_fd, relpath)
        except SafeReadError as exc:
            if not leaf_required and isinstance(exc.__cause__, FileNotFoundError):
                return None
            raise
    return _open_component_walk(root_fd, parts, leaf_required=leaf_required)


def open_leaf(root_fd: int, relpath: str) -> int:
    """Open an existing regular-file target beneath the trusted root and return
    its descriptor. The caller owns closing it and must fstat/read from this
    descriptor only. Missing targets raise SafeReadError (fail closed)."""
    leaf_fd = _open_leaf(root_fd, relpath, leaf_required=True)
    assert leaf_fd is not None  # leaf_required=True never returns None
    return leaf_fd


def open_verified_leaf(
    root_fd: int, relpath: str, *, max_bytes: int = DEFAULT_MAX_BYTES
) -> tuple[bytes, os.stat_result]:
    """Open the target once, fstat the open descriptor, and read the content
    exactly once. Callers that hash, parse, and return content must derive all
    three from the returned buffer so a content swap between separate opens
    cannot desynchronize the hash from the parsed/returned content."""
    leaf_fd = _open_leaf(root_fd, relpath, leaf_required=True)
    assert leaf_fd is not None  # leaf_required=True never returns None
    try:
        info = os.fstat(leaf_fd)
        if not stat.S_ISREG(info.st_mode):
            raise SafeReadError(f"Governed read target is not a regular file: {relpath!r}")
        if info.st_size > max_bytes:
            raise SafeReadError(
                f"Governed read target exceeds the {max_bytes}-byte cap: {relpath!r} ({info.st_size} bytes)"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(leaf_fd, min(1024 * 1024, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise SafeReadError(f"Governed read target grew past the {max_bytes}-byte cap: {relpath!r}")
        return b"".join(chunks), info
    finally:
        os.close(leaf_fd)


def read_bytes(root_fd: int, relpath: str, *, max_bytes: int = DEFAULT_MAX_BYTES) -> bytes:
    """Read a regular file below the trusted root, symlink-free, size-bounded."""
    return open_verified_leaf(root_fd, relpath, max_bytes=max_bytes)[0]


def read_text(root_fd: int, relpath: str, *, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    try:
        return read_bytes(root_fd, relpath, max_bytes=max_bytes).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SafeReadError(f"Governed read target is not valid UTF-8: {relpath!r}: {exc}") from exc


def audit_path(root_fd: int, relpath: str) -> os.stat_result | None:
    """Mutation-audit mode: parents must exist and be symlink-free; an absent
    final leaf is valid (returns None) for deletion/rename evidence."""
    leaf_fd = _open_leaf(root_fd, relpath, leaf_required=False)
    if leaf_fd is None:
        return None
    try:
        return os.fstat(leaf_fd)
    finally:
        os.close(leaf_fd)
