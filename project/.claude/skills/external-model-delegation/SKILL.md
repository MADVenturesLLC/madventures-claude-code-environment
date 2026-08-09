---
name: external-model-delegation
description: Prepare a governed file-based delegation to Grok, Hermes Local Code, Codex, Gemini, or another registered external model.
argument-hint: "<registered model> <task>"
disable-model-invocation: true
---

# External model delegation

Read `.claude/MODEL_REGISTRY.md` first. Use only Founder-approved, registered models and the permissions granted to that model. Confirm whether the model may read local files, write files, execute commands, access the network, or review independently.

Create a task packet containing goal, scope, authority, pinned Git state, allowed paths/tools, prohibited actions, acceptance criteria, verification commands, output contract, and handback location. Share the minimum files required; never include secrets or unrestricted credentials.

The receiving model must label uncertainty, preserve role separation, and stop at its authority boundary. A builder cannot act as its own independent reviewer. On return, verify the actual diff and commands locally rather than trusting the handoff claim.

Record registry ID, exact model identity/version when known, connector, role, permissions, start/end SHA, files touched, commands run, and evidence produced for auditability. A connector being installed does not itself authorize use; an unregistered model must stop for Founder approval.
