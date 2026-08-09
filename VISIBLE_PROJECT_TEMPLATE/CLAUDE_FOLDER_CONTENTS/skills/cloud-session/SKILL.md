---
name: cloud-session
description: Choose between Claude Code cloud execution and Remote Control, then prepare, launch, monitor, retrieve, and verify the governed session without losing branch, authority, dependency, or evidence boundaries.
argument-hint: "<route|plan|launch|monitor|teleport|remote-control> <task>"
disable-model-invocation: true
---

# Governed remote-session protocol

## Choose the execution host first
- **Claude Code cloud:** use when work should run on Anthropic-managed infrastructure, persist after the local machine closes, and start from committed/pushed or bundled repository state.
- **Remote Control:** use when Claude must remain on the local machine with access to its local filesystem, MCP servers, tools, and approved local-only connectors while the Founder steers it from web or mobile.
- **Background local session:** use when remote steering is unnecessary but the task should keep running independently on the local machine.

Do not describe Remote Control as cloud execution. The browser/mobile interface is only a control surface; commands and file access remain local.

## Preflight
Verify repository identity, current branch, clean/known working tree, remote URL, pushed commits or bundle state, task ownership, acceptance criteria, and execution host. Record whether the local machine must remain online.

## Cloud launch contract
The cloud prompt must state:
- goal and completion verifier;
- approved plan path or bounded scope;
- allowed and prohibited mutations;
- required checks;
- branch/PR expectation;
- no merge, deployment, activation, authority change, credential access, or destructive recovery without Founder approval.

Use `/remote-env` to select the approved environment and `claude --cloud "..."` to create a new session. Independent tasks require separate branches and non-overlapping ownership.

## Remote Control contract
Start with `claude remote-control`, `claude --remote-control`, or `/remote-control` only after confirming the local session's tools, permissions, repository, and connectors are appropriate. The local machine must remain awake and connected. Remote steering does not widen permissions or convert a local connector into an approved authority.

## Monitoring
Use `/tasks`, `claude agents`, agent view, or the web/mobile session view. Intervene when scope changes, a permission or authority gate appears, verification cannot be completed, or a task no longer matches its assigned branch.

## Retrieval and closeout
For cloud work, use `claude --teleport` only from a clean checkout of the same repository and account. After retrieval, verify branch, SHA, diff, commands, and evidence before relying on the cloud narrative. For Remote Control, verify local Git state directly because no cloud branch transfer occurred.

## Output
Return the selected route, why the alternatives were rejected, a copy-pasteable launch command, preflight checklist, ownership boundary, expected artifacts, stop conditions, and post-session verification steps.
