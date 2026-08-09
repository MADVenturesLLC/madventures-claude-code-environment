# Project profile — MADVenturesLLC/FounderOS doctrine repository

## Identity
- Project name: `FounderOS`
- Repository type: `doctrine`
- Purpose: Canonical governance, roles, decisions, workflows, and evidence for FounderOS.
- Default branch: Verify from the live remote before work.
- Primary owner/approver: Founder.

## Mandatory verification
- Path audit: `bash 00-system/scripts/path-audit.sh`
- Attribution-shape check: `bash 00-system/scripts/attribution-shape-check.sh`
- CI authorities: `.github/workflows/path-audit.yml` and `.github/workflows/attribution-shape.yml`
- Additional checks: Discover from current CI and root `CLAUDE.md`; do not invent.

## Architecture and authority
- Root execution contract: `CLAUDE.md`
- Canonical role registry: `04-agents/role-registry.md`
- Constitutional authority: `01-constitution/`
- Canonical decision log: `07-decisions/decision-log.md`
- File writes: local Git only; no GitHub API content writes.
- Merge authorization: Founder-controlled and SHA-specific; a technical review never substitutes for it.

## Current focus
- Approved objective: Complete from the current Founder instruction.
- Acceptance criteria: Complete from the governing DEC/workflow and current instruction.
- Known blockers/unknowns: Re-evaluate from the live repository at session start.
