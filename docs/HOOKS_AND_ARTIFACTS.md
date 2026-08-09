# Hooks and canonical artifacts

## Authoritative boundary

JavaScript transports Claude Code hook events. Python makes every policy decision. Models, agents,
plugins, MCP tools, and hook output cannot grant approval or manufacture governed truth.

The environment contains one hook module:

```text
.claude/hooks/hook-adapter.mjs
```

It validates JSON, locates Python 3 on macOS/Linux/Windows, invokes `madclaude.hook_cli`, and fails
closed when input or the Python engine is unavailable. Policy lives in `madclaude/hook_policy.py`.

## Registered gates

| Event | Python profile | Enforced result |
|---|---|---|
| `PreToolUse` | `baseline` | Blocks secret paths, protected authority paths, unsafe shell operations, database clients outside `neon-reader`, and governed-route scope/tool escapes |
| `ConfigChange` | `baseline` | Requires the explicit Founder configuration gate; managed policy remains externally controlled |
| `Stop` | `completion` | A dirty tree cannot stop without current manifested verification |
| `TaskCompleted` | `completion` | A dirty task cannot be marked complete without the same evidence |
| `neon-reader` `PreToolUse` | `sql` | Allows one inspectable read-only statement and blocks interactive, write, lock, administrative, and multi-statement SQL |

The independent reviewer has no shell or mutation tools. Exact-SHA commands are executed by Python in
a detached worktree, so a lexical reviewer shell allowlist is unnecessary.

## Completion evidence

A dirty tree may complete only when one bundle under
`.claude/evidence/python-control-plane/` proves all of the following:

1. `MANIFEST.json` is completed, source-classified, complete, and every listed size/hash matches.
2. `EXECUTION_RECORD.json` is completed and bound to the current literal HEAD SHA.
3. `VERIFICATION.json` matches the current working-tree fingerprint and contains at least one passed command with no failed or skipped commands.
4. `VERIFICATION.md` has a valid canonical envelope, exact SHA, passed status, matching payload, and payload hash.

Generated evidence is excluded from the source fingerprint so finalizing a bundle does not stale its
own proof. Source changes made after verification do stale it.

## Canonical artifact contract

Python emits inspectable Markdown companions with mandatory metadata and a hashed JSON payload:

```text
PLAN.md
HANDOFF.md
VERIFICATION.md
REVIEW.md
TIER2_REVIEW.md
ACCEPTANCE.md
DECISION_PROPOSAL.md
```

Each envelope records artifact type, schema version, workflow/task identity, repository, route/stage,
literal base/head SHAs, status, `local_evidence`, timestamp, and payload SHA-256. The bundle manifest
binds every emitted file. Local evidence remains evidence, not Founder approval, merge/deploy
authority, production truth, or a ratified governance record.

## External boundary

Project hooks can be disabled by an external operator and cannot reveal hidden behavior inside an
opaque script. Branch protection, CI, read-only database identities, IAM, secret management, and
Founder approval remain required outside the package.
