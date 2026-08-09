---
name: handoff-create
description: Create an evidence-preserving agent or session handoff that pins state, decisions, changed files, verification, risks, and next action.
argument-hint: "[recipient role or model]"
---

# Create a durable handoff

A receiving agent must be able to continue without replaying the entire conversation or guessing current repository state.

Include:
- goal and done condition;
- repository, branch, remote, base SHA, current head SHA, and working-tree status;
- Founder approvals and authority constraints;
- observed architecture and key paths;
- changes made, by file, and why;
- exact commands run and results;
- review findings/dispositions;
- unresolved risks and unknowns;
- prohibited actions;
- next concrete step and expected verifier.

Keep evidence separate from interpretation. Do not claim files were committed, pushed, merged, deployed, or activated unless verified. Avoid secrets and large raw dumps. End with a concise `RECEIVER CHECKLIST`.
