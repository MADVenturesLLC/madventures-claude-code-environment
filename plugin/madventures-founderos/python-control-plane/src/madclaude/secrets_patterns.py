"""A10-A: canonical secret-pattern primitive registry.

DEC-20260812-01 Package A10-A requires ONE authoritative registry of
secret-pattern primitives consumed by both the detection path
(``guard.contains_sensitive_material``, recall-optimized) and the safe
replacement path (``evidence.redact``, anchored and non-lossy). The two
consumers compose the SAME primitives with job-appropriate regex forms:

- *detection* regexes are recall-optimized: they flag anything that could
  be a secret, tolerate false positives, and never replace text.
- *redaction* regexes are replacement-safe: they produce clean
  ``[REDACTED]`` substitutions with anchored boundaries so benign text
  survives.

A primitive is a named (detection, redaction) pair. Where the two jobs
need the same shape, both forms are identical; where they differ (e.g.
PEM headers vs full PEM blocks, token length floors), each job gets its
own form derived from the same named primitive. A test asserts there is
no divergent second copy of any primitive outside this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SecretPrimitive:
    """A named secret shape with its two consumer forms."""

    name: str
    detection: str
    redaction: str


# Audit-confirmed shapes (DEC-20260812-01 A10-A scope item 2):
#   ghp_/gho_/ghu_/ghs_/ghr_ (GitHub), AKIA (AWS), sk-proj- (OpenAI),
#   ://user:pass@host URL userinfo — added to the existing sk-ant-,
#   Anthropic/Claude env assigns, Bearer, and PEM coverage.
REGISTRY: tuple[SecretPrimitive, ...] = (
    SecretPrimitive(
        name="sk_ant",
        # Detection keeps the existing 12-char floor (guard.py baseline);
        # redaction has no floor so even short fragments are scrubbed.
        detection=r"\bsk-ant-[A-Za-z0-9_-]{12,}\b",
        redaction=r"sk-ant-[A-Za-z0-9_-]+",
    ),
    SecretPrimitive(
        name="sk_proj",
        detection=r"\bsk-proj-[A-Za-z0-9_-]{8,}\b",
        redaction=r"sk-proj-[A-Za-z0-9_-]+",
    ),
    SecretPrimitive(
        name="github_token",
        # GitHub fine-grained (ghp_), OAuth (gho_), user (ghu_),
        # server-to-server (ghs_), refresh (ghr_).
        detection=r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
        redaction=r"gh[pousr]_[A-Za-z0-9]+",
    ),
    SecretPrimitive(
        name="aws_access_key",
        detection=r"\bAKIA[0-9A-Z]{16}\b",
        redaction=r"AKIA[0-9A-Z]{16}",
    ),
    SecretPrimitive(
        name="claude_env_assign",
        detection=(
            r"(?i)(?:ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|CLAUDE_CODE_OAUTH_TOKEN)"
            r"\s*[=:]\s*[^\s,;]+"
        ),
        redaction=(
            r"(?i)(?:ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|CLAUDE_CODE_OAUTH_TOKEN)"
            r"\s*[=:]\s*[^\s,;]+"
        ),
    ),
    SecretPrimitive(
        name="bearer",
        # Detection: 8-char floor so prose like "bearer scheme" (6 chars)
        # is not flagged; real tokens are longer.
        detection=r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}",
        # Redaction: require a non-alphanumeric char (JWT dots, base64url
        # -_=) or 20+ length, so "bearer scheme"/"bearer documentation"
        # prose survives unscrubbed while real tokens are replaced.
        redaction=(
            r"(?i)\bBearer\s+(?:[A-Za-z0-9._~+/=-]*[._~+/=-][A-Za-z0-9._~+/=-]*"
            r"|[A-Za-z0-9._~+/=-]{20,})"
        ),
    ),
    SecretPrimitive(
        name="pem_private_key",
        # Detection needs only the header (recall); redaction must scrub the
        # whole block (replacement safety).
        detection=r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        redaction=(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?"
            r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
    ),
    SecretPrimitive(
        name="url_userinfo",
        # scheme://user:pass@host — detection includes the scheme prefix;
        # redaction uses a lookbehind so the replacement keeps the scheme
        # readable: postgres://[REDACTED]@host.
        detection=r"://[^\s:/@]+:[^\s@/]+@",
        redaction=r"(?<=://)[^\s:/@]+:[^\s@/]+(?=@)",
    ),
)


def _compile_detection() -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p.detection) for p in REGISTRY)


def _compile_redaction() -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p.redaction) for p in REGISTRY)


DETECTION_PATTERNS: tuple[re.Pattern[str], ...] = _compile_detection()
REDACTION_PATTERNS: tuple[re.Pattern[str], ...] = _compile_redaction()
