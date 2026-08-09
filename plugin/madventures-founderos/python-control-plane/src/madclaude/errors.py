class MadClaudeError(RuntimeError):
    """Base error for the MAD Ventures Claude control plane."""


class AuthPreflightError(MadClaudeError):
    """Selected authentication or billing lane cannot be proven safe."""


class RepositoryError(MadClaudeError):
    """Repository evidence or Git state is invalid."""


class PolicyViolation(MadClaudeError):
    """A deterministic governance or tool policy was violated."""


class AgentRunError(MadClaudeError):
    """A Claude run failed or returned invalid structured output."""


class EvidenceError(MadClaudeError):
    """Evidence could not be written or verified."""


class SafeReadError(PolicyViolation):
    """A TOCTOU-safe governed read failed or was rejected."""
