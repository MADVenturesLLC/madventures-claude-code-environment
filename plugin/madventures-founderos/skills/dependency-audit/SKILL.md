---
name: dependency-audit
description: Audit direct and transitive dependencies for necessity, provenance, compatibility, licensing, vulnerability, update risk, and operational ownership.
argument-hint: "[package|workspace|repository]"
---

# Dependency audit

## Establish truth
Identify the package manager, lockfiles, workspaces, runtime versions, registries, update bots, build images, and deployment environment. Use the lockfile and resolved graph, not only manifest declarations.

## Evaluate each material dependency
- actual import/use and owning subsystem;
- direct versus transitive status;
- pinned/resolved version and integrity/provenance evidence;
- maintenance and compatibility with the current runtime/framework;
- known security advisories using approved current sources;
- license and distribution constraints;
- initialization side effects, bundle/runtime cost, and failure behavior;
- replacement/removal feasibility and migration/test requirements.

## Controlled update policy
Do not bulk-upgrade, rewrite lockfiles, or install packages during the audit. Group updates by compatibility boundary. Require an explicit plan for majors, security-sensitive packages, framework/toolchain changes, native modules, database clients, and authentication libraries.

## Output
Return blockers first, then a table of keep/update/replace/remove/investigate decisions with evidence, target version policy, blast radius, verification, rollback, and owner. Distinguish confirmed vulnerabilities from scanner-only or unreachable findings.
