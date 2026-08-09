# Authoritative workflow routing

Executable JavaScript workflows are retired. The runtime exposed only model orchestration primitives,
so a JavaScript adapter would still depend on prompt compliance and would compete with Python.

> **MCP is the interface layer. Python is the deterministic enforcement layer.**

The canonical mapping is machine-readable in
`python-control-plane/WORKFLOW_MIGRATION.json`. No model, plugin, workflow, or MCP surface can create
approval, verification, scope compliance, checkpoint integrity, or other governed truth.

## Capability mapping

| Former capability | Classification | Authoritative Python route |
|---|---|---|
| founder-plan | THIN-ADAPTER | `madclaude plan` |
| founder-build | THIN-ADAPTER | `madclaude build` |
| founder-verify | THIN-ADAPTER | `madclaude verify` |
| founder-tier2-evidence | THIN-ADAPTER | `madclaude tier2` |
| founder-release-readiness | THIN-ADAPTER | `madclaude release-readiness` |
| founder-repository-audit | THIN-ADAPTER | `madclaude repo-audit` |
| founder-security-audit | THIN-ADAPTER | `madclaude security-audit` |
| founder-ui-review | THIN-ADAPTER | `madclaude ui-review` |
| founder-fix-until-green | THIN-ADAPTER | `madclaude fix-until-green` |
| founder-changed-files-review | MERGE | `madclaude tier1` |
| founder-docs-drift | MERGE | `madclaude repo-audit --profile docs-drift` |
| founder-performance-audit | MERGE | `madclaude repo-audit --profile performance` |
| founder-test-gap-analysis | MERGE | `madclaude repo-audit --profile test-gap` |
| founder-incident-root-cause | MERGE | `madclaude repo-audit --profile incident` |

`madclaude architecture-validation` is an additional Opus/max, exact-SHA, read-only route. It validates
architecture invariants and remains separate from Tier-2 independence review.

## Engine boundary

Python owns route/model eligibility, one-builder mutation, approval SHA binding, scope enforcement,
command execution, exact-SHA worktrees, Tier-2 participant exclusion, evidence-source classification,
execution records, and bounded recovery. Models may inspect and interpret only within that envelope.

Tier-1 writes `REVIEW.json` plus its execution record. Tier-2 requires manifest-bound execution records
for planner, builder, verifier, and Tier-1, then selects the first eligible model that did not participate
earlier. It fails closed when a role is missing or no independent reviewer remains. The result is
review evidence only; it does not authorize merge, deploy, activation, or production writes.
