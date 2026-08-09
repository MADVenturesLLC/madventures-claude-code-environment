from __future__ import annotations

import hashlib
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .guard import validate_verification_command


@dataclass(frozen=True)
class VerificationResult:
    command: str
    argv: tuple[str, ...]
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def compact(self, max_chars: int = 12_000) -> dict[str, object]:
        output = (self.stdout + ("\n" if self.stdout and self.stderr else "") + self.stderr).strip()
        if len(output) > max_chars:
            output = output[:max_chars] + "\n[OUTPUT TRUNCATED]"
        return {
            "command": self.command,
            "status": self.status,
            "exit_code": self.exit_code,
            "evidence": output or "Command produced no output.",
        }


def validate_commands(commands: list[str]) -> list[tuple[str, list[str]]]:
    return [(command, validate_verification_command(command)) for command in commands]


def run_command(repo: Path, command: str, timeout_seconds: int) -> VerificationResult:
    argv = validate_verification_command(command)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(repo),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        duration = int((time.monotonic() - started) * 1000)
        return VerificationResult(
            command=command,
            argv=tuple(argv),
            status="passed" if completed.returncode == 0 else "failed",
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_ms=duration,
        )
    except subprocess.TimeoutExpired as exc:
        duration = int((time.monotonic() - started) * 1000)
        return VerificationResult(
            command=command,
            argv=tuple(argv),
            status="failed",
            exit_code=None,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=((exc.stderr or "") if isinstance(exc.stderr, str) else "") + "\nCommand timed out.",
            duration_ms=duration,
            timed_out=True,
        )


def run_commands(repo: Path, commands: list[str], timeout_seconds: int) -> list[VerificationResult]:
    validate_commands(commands)
    return [run_command(repo, command, timeout_seconds) for command in commands]


def failure_fingerprint(results: list[VerificationResult]) -> str:
    material = "\n".join(
        f"{item.command}\0{item.exit_code}\0{item.stdout[-4000:]}\0{item.stderr[-4000:]}"
        for item in results
        if item.status != "passed"
    )
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()
