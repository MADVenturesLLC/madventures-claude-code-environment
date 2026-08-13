from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import safe_read
from .errors import EvidenceError, SafeReadError
from .secrets_patterns import REDACTION_PATTERNS

SECRET_KEYS = re.compile(r"(?:api[_-]?key|auth[_-]?token|oauth[_-]?token|password|secret|credential|private[_-]?key)", re.I)
# A10-A: replacement-safe redaction patterns derived from the canonical
# primitive registry (secrets_patterns.REGISTRY). Anchored boundaries keep
# benign text unscrubbed while every audit-confirmed secret shape is
# replaced with a clean [REDACTED] substitution.
SECRET_VALUES = REDACTION_PATTERNS


def redact(value: Any, key: str | None = None) -> Any:
    if key and SECRET_KEYS.search(key):
        return "[REDACTED]"
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        text = value
        for pattern in SECRET_VALUES:
            text = pattern.sub("[REDACTED]", text)
        return text
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# B3 governance constant: evidence sources larger than this are never hashed;
# their declared manifest hash is reported as unchecked instead.
EVIDENCE_SOURCE_CAP_BYTES = 1_048_576
_DECLARED_HASH = re.compile(r"^[0-9a-f]{64}$")


def read_evidence_source(
    root_fd: int, relative_path: str, declared_sha256: str | None
) -> tuple[dict[str, Any], bytes | None]:
    """B3 evidence-hash truth table for sources[] emitters.

    Opens the target exactly once through the B4 descriptor reader, fstats the
    open descriptor, and reads bounded to EVIDENCE_SOURCE_CAP_BYTES + 1 bytes.
    Returns (row, buffer): the row carries exactly five fields —
    source_sha256, declared_manifest_sha256, hash_provenance, target_match,
    verified — and buffer is the single read buffer the hash was computed
    from (None when oversized). `verified` is True only when a computed
    physical hash matched a present expected hash; computing alone is never
    verification, and declared manifest values are never presented as
    computed. Consumers that return content must decode it from the returned
    buffer, never from a second read.
    """
    if declared_sha256 is not None and not _DECLARED_HASH.fullmatch(declared_sha256):
        raise EvidenceError(
            f"Declared evidence hash is malformed (expected 64 lowercase hex): {declared_sha256!r}"
        )
    try:
        descriptor = safe_read.open_leaf(root_fd, relative_path)
    except SafeReadError as exc:
        raise EvidenceError(f"Evidence source is unreadable: {relative_path!r}: {exc}") from exc
    assert descriptor is not None  # leaf_required=True never returns None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise EvidenceError(f"Evidence source is not a regular file: {relative_path!r}")
        data: bytes | None = None
        if info.st_size <= EVIDENCE_SOURCE_CAP_BYTES:
            chunks: list[bytes] = []
            total = 0
            try:
                while True:
                    chunk = os.read(descriptor, min(1024 * 1024, EVIDENCE_SOURCE_CAP_BYTES + 1 - total))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > EVIDENCE_SOURCE_CAP_BYTES:
                        break
            except OSError as exc:
                raise EvidenceError(f"Evidence source is unreadable: {relative_path!r}: {exc}") from exc
            if total <= EVIDENCE_SOURCE_CAP_BYTES:
                data = b"".join(chunks)
        if data is None:
            # Oversized (per fstat, or it grew past the cap mid-read): never
            # streamed past cap + 1, and never hashed from a partial buffer.
            return {
                "source_sha256": None,
                "declared_manifest_sha256": declared_sha256,
                "hash_provenance": "manifest_declared" if declared_sha256 is not None else "none",
                "target_match": "not_checked",
                "verified": False,
            }, None
    finally:
        os.close(descriptor)
    computed = hashlib.sha256(data).hexdigest()
    if declared_sha256 is None:
        return {
            "source_sha256": computed,
            "declared_manifest_sha256": None,
            "hash_provenance": "computed",
            "target_match": "no_target",
            "verified": False,
        }, data
    match = computed == declared_sha256
    return {
        "source_sha256": computed,
        "declared_manifest_sha256": declared_sha256,
        "hash_provenance": "computed",
        "target_match": "match" if match else "mismatch",
        "verified": match,
    }, data


def hash_evidence_source(root_fd: int, relative_path: str, declared_sha256: str | None) -> dict[str, Any]:
    """Row-only form of read_evidence_source for sources[] emitters that do
    not return content."""
    return read_evidence_source(root_fd, relative_path, declared_sha256)[0]


def _chmod(path: Path, mode: int) -> None:
    if os.name != "nt":
        path.chmod(mode)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _chmod(path.parent, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    temp_path = Path(temporary)
    try:
        _chmod(temp_path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
        _chmod(path, 0o600)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


class EvidenceBundle:
    def __init__(self, root: Path, route: str) -> None:
        root.mkdir(parents=True, exist_ok=True)
        _chmod(root, 0o700)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = uuid.uuid4().hex[:8]
        self.path = root / f"{timestamp}-{route}-{suffix}"
        self.path.mkdir(parents=True, exist_ok=False)
        _chmod(self.path, 0o700)
        self.route = route
        self.write_json(
            "bundle.json",
            {
                "schemaVersion": 1,
                "route": route,
                "evidenceSource": "local_evidence",
                "createdAt": datetime.now(timezone.utc).isoformat(),
            },
        )

    def write_json(self, name: str, value: Any) -> Path:
        path = self.path / name
        try:
            content = json.dumps(redact(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            _atomic_write(path, content)
        except Exception as exc:
            raise EvidenceError(f"Could not write evidence {name}: {exc}") from exc
        return path

    def write_text(self, name: str, value: str) -> Path:
        path = self.path / name
        try:
            _atomic_write(path, str(redact(value)))
        except Exception as exc:
            raise EvidenceError(f"Could not write evidence {name}: {exc}") from exc
        return path

    def finalize(self, status: str) -> Path:
        entries: list[dict[str, Any]] = []
        for path in sorted(self.path.rglob("*")):
            if path.is_file() and path.name != "MANIFEST.json":
                entries.append(
                    {
                        "path": path.relative_to(self.path).as_posix(),
                        "size": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
        manifest = {
            "schemaVersion": 1,
            "route": self.route,
            "evidenceSource": "local_evidence",
            "status": status,
            "finalizedAt": datetime.now(timezone.utc).isoformat(),
            "files": entries,
        }
        return self.write_json("MANIFEST.json", manifest)


def write_immutable_record(path: Path, value: Any) -> Path:
    """A10-C (Q2.4): write one immutable, redacted JSON record.

    Write-once by construction: the target file is created with O_EXCL so a
    collision refuses instead of overwriting, and the content is redacted
    through the A10-A registry before write (Q2.3). Parent directory is
    created 0700, record file 0600 (evidence._chmod conventions). Raises
    EvidenceError on any failure — callers must fail closed (Q5).
    """
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _chmod(target.parent, 0o700)
        descriptor = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError as exc:
        raise EvidenceError(f"immutable record could not be written: {target.name}") from exc
    try:
        content = json.dumps(redact(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        _chmod(target, 0o600)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target
