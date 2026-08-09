# Security and governance boundaries

The package is defense in depth. It combines instructions, allow/ask/deny settings, agent tool restrictions, deterministic hooks, Git isolation, model registration, and review policy. None of those controls alone is a complete security boundary.

## Authority model

FounderOS separates:

- planner;
- builder;
- verifier;
- independent reviewer;
- approver;
- merger;
- deployer;
- activator;
- Founder.

A capable model does not inherit authority from capability. Founder authorization is Founder-only.

Use lifecycle states precisely:

```text
proposed → approved → implemented → verified → merged → deployed → activated
```

`blocked` and `unknown` are valid outcomes. Unavailable evidence is not healthy state.

## Hard controls versus behavioral controls

### Harder package controls

- one fail-closed Python policy for destructive/force-push/merge/deploy commands, secrets, and authority paths;
- a transport-only cross-platform JavaScript adapter registered for tools and configuration changes;
- a scoped Python read-only SQL profile for `neon-reader`;
- blocking completion hooks that require a current manifested verification bundle for dirty trees;
- no edit/write/delegation tools for the project `independent-reviewer`;
- bypass-permissions mode disabled in shared settings;
- worktree isolation for independent editors;
- inactive MCP configuration by default;
- no bundled credentials.

### Behavioral controls

- “do not edit” in a normal prompt;
- evidence-only workflow instructions;
- builder promises not to merge/deploy;
- advisor guidance;
- model-generated plans and stop conditions.

Behavioral controls are important but are not equivalent to denied tools, scoped credentials, sandboxing, branch protection, or human approval.

## Workflow boundary

Dynamic workflow scripts run in a restricted orchestration runtime, but their spawned agents run in edit-acceptance mode and inherit the session tool allowlist. A parent plan-mode session does not make workflow workers hard read-only.

Therefore:

- inspect raw workflow JavaScript and phase plans before launch;
- keep shared tool allowlists narrow;
- run evidence workflows on a clean/controlled branch;
- do not expose mutating MCP tools unnecessarily;
- use the canonical edit-less `independent-reviewer` for exact-SHA Tier-2 review;
- split Founder approvals into separate sessions/workflows because workflows cannot pause for ordinary mid-run user input.

## Advisor boundary

The advisor receives the full session and returns guidance to the same main agent. It is not:

- independent context;
- a fresh exact-SHA review;
- a security sandbox;
- approval authority;
- a replacement for Fable/Opus independent review.

The optional advisor profile remains inactive by default. The advisor is provider- and account-gated and currently does not offer Fable as the advisor.

## Subagent and background boundaries

A subagent can isolate context and narrow tools, but:

- it normally shares the parent working tree;
- its edits may not be restored by the parent checkpoint;
- a model prompt cannot create organizational independence by itself;
- background sessions can outlive the foreground terminal but still need an active local/cloud host;
- parallel editors require worktrees or non-overlapping ownership.

Use `isolation: worktree` or a dedicated worktree session for independent mutations.

## Exact-SHA review

The project `independent-reviewer`:

- receives immutable base/head SHA;
- has read/search evidence only; deterministic commands run through the exact-SHA Python route;
- cannot edit, write, delegate, merge, deploy, or activate;
- reports findings with severity, file/line, evidence, impact, and disposition;
- becomes stale on every new head SHA.

The portable plugin version is also shell- and mutation-free. For high-risk FounderOS review, use the full project environment and its exact-SHA Python route.

## Secrets

Never place secrets in:

- `CLAUDE.md`, skills, agents, workflows, prompts, or handoffs;
- committed settings or MCP examples;
- cloud environment examples;
- debug logs or validation artifacts;
- PR comments or shared sessions.

The package denies common `.env`, key, certificate, and credential paths, but filename controls are incomplete. Use approved secret managers, scoped runtime injection, short-lived credentials, and repository/cloud IAM.

Debug logs can contain paths, commands, tool inputs, and outputs. Store them in a protected location and delete/archive them under policy.

## Python authentication and billing boundary

The Python control plane defaults to the user's Claude Code subscription login. A saved login is not
sufficient proof when an API key or provider credential is also present, because higher-precedence
environment or settings routes can change the active billing lane.

Before every model-backed Python route, the package:

- calls `claude auth status`;
- rejects API keys/tokens in subscription mode;
- rejects Bedrock, Vertex, and Foundry routes in subscription mode;
- rejects custom Anthropic/provider base URLs in subscription mode;
- inspects known settings files for `apiKeyHelper` or injected API credentials;
- refuses ambiguous authentication rather than guessing;
- strips higher-precedence routes from the child environment after a safe preflight; and
- writes only a redacted public authentication report.

Separate API billing requires `--billing-mode api --allow-api-billing` and a positive `--max-budget-usd`. The package never asks for,
prints, copies, stores, or creates the key. `--max-budget-usd` is a client-side estimate control, not
ledger-grade cost evidence.

The governed user-level install creates an isolated dependency-free Python environment. Native
`claude -p` is the default subscription route and every invocation receives an ephemeral policy
hook. The optional exactly pinned Agent SDK is installed only with `--with-sdk` / `-WithSdk` and
remains unavailable unless the caller also passes the explicit API-billing gates. Neither installer
alters credentials or account billing settings.

## MCP and external tools

The package installs `.mcp.example.json`, not an active `.mcp.json`.

The GitHub example uses:

- `https://api.githubcopilot.com/mcp/`;
- bounded `repos,pull_requests,actions` toolsets;
- `X-MCP-Readonly: true`;
- an environment-variable token reference.

Before activation:

1. verify the official server and transport;
2. narrow toolsets to the task;
3. use least-privilege, separately managed credentials;
4. inspect all mutating tools;
5. validate with `/mcp` and `/status`;
6. keep active local configuration uncommitted;
7. retain GitHub branch protection and required reviews.

A read-only MCP header is not a substitute for read-only repository credentials or provider-side enforcement.

## External model connectors

`.claude/MODEL_REGISTRY.md` records approved identities and roles. Registration does not bundle or authorize a connector.

For Grok, Hermes local code, Codex, Gemini, Cursor, or another model, record:

- exact model/version;
- role and independence relationship to the builder;
- repository/branch/base/head SHA;
- files or context sent;
- read/write/network/command permissions;
- files changed;
- commands and tests run;
- output/evidence location;
- review and Founder authorization state.

Stop before using an unregistered model or an unreviewed connector.

## Python workflow controls

Harder Python-enforced boundaries include:

- clean-tree precondition for approved builds;
- plan SHA-256 binding in the Founder approval document;
- exact goal match;
- non-empty allowed scopes, acceptance criteria, and verification commands;
- direct-command parsing without shell chaining or redirection;
- rejection of destructive and authority-changing commands;
- changed-file scope checks after every mutating stage;
- Python-executed verification rather than builder self-attestation;
- literal full SHA requirements for review/release routes;
- detached temporary review worktrees;
- schema validation and fail-closed exit codes;
- bounded repair rounds with repeated-failure/no-progress stops; and
- redacted evidence manifests.

These controls strengthen execution but do not replace external branch protection, CI, IAM, database
roles, production controls, or Founder authorization.

## Database boundary

`neon-reader` is included only in the full project environment and requires:

- a separately provisioned read-only database identity;
- approved MCP/CLI access;
- the agent-scoped Python SQL policy;
- no secrets in the package;
- explicit source/projection distinction.

The SQL guard is defense in depth, not a replacement for database privileges. The portable plugin excludes this agent because it cannot carry the same scoped enforcement safely.

## Cloud security

Claude Code cloud uses Anthropic-managed infrastructure and a saved cloud environment. Review:

- repository access method;
- network mode and allowed domains;
- setup scripts;
- environment variables;
- package-manager install behavior;
- session sharing visibility;
- branch and PR permissions.

Do not assume local user configuration or credentials exist in cloud. Do not put secrets in the package cloud environment template. Project hooks fire in cloud, but environment-specific availability and credentials still govern what they can do.

## Remote Control security

Remote Control exposes a local Claude Code session through web/mobile while execution remains local. Before enabling:

- verify the repository and working tree;
- inspect active local MCP servers and connectors;
- use a named session;
- confirm permission mode and allowed tools;
- keep the machine physically and logically secured;
- prefer worktree spawning for concurrent sessions;
- stop remote access when no longer needed.

Remote Control is a control surface, not an authority escalation. It is the appropriate route for local-only Hermes access, but it does not make Hermes independent or grant merge/deploy rights.

## Hooks and settings limitations

The baseline hook parses tool inputs and blocks known high-risk paths and commands before execution.
It is defense in depth, not a shell sandbox: an external operator can disable project hooks, and a
script can hide behavior that is not visible in the command string. Governed mutation therefore
runs through Python scope checks and Python-executed verification. `PostToolUse` is not used as an
authority gate because it cannot undo a completed action.

Project settings can be overridden or constrained by managed settings, provider hosts, environment variables, and user/local settings according to precedence. Always inspect `/status` and organization policy in the actual deployment.

## Required external controls

Maintain outside this package:

- GitHub branch protection and required reviews;
- least-privilege repository/app tokens;
- cloud IAM and network policy;
- database read-only roles;
- secret management and rotation;
- CI verification and protected environments;
- deployment approvals and rollback controls;
- production observability and audit logging;
- Founder governance records.

## Incident response

On suspected unsafe behavior:

1. stop the workflow/background/remote session;
2. disconnect Remote Control or cloud access as appropriate;
3. preserve logs and Git state without exposing secrets;
4. rotate potentially exposed credentials;
5. inspect diff, branches, PR actions, MCP calls, database/audit logs, deployment events, and cloud session sharing;
6. restore through Git/provider controls, not blind checkpoint assumptions;
7. run `/incident-response` and independent review;
8. document root cause, affected authority boundary, correction, verification, and prevention.
