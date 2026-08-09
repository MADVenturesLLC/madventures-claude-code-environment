# Claude cloud, Remote Control, and local background execution

These are different execution hosts. Choose the host before choosing the model or orchestration pattern.

## Decision table

| Surface | Where execution occurs | Local files/connectors | Survives local machine closing | Best use |
|---|---|---:|---:|---|
| Interactive local session | local machine | Yes | No | tight Founder-in-the-loop work |
| Local background session / agent view | local machine | Yes | No | independent local work that can run without the foreground terminal attached |
| Remote Control | local machine; web/mobile is a control window | Yes | No; reconnects when the machine returns | steering Hermes/local files/MCP/tools from another device |
| Claude Code cloud | Anthropic-managed infrastructure | Only cloned/bundled state and configured cloud services | Yes | persistent autonomous execution, parallel cloud tasks, web/mobile monitoring |

Neither cloud nor Remote Control expands repository, credential, governance, merge, deployment, activation, or Founder authority.

## Route selection

Choose **cloud** when:

- the task should continue after the laptop closes;
- the required state is committed/pushed or intentionally bundled;
- the cloud environment has the needed tools and approved network access;
- local-only connectors are not required.

Choose **Remote Control** when:

- execution must stay on the local machine;
- local repository state, MCP servers, tools, or approved local connectors such as `hermes-local-code` are needed;
- the Founder wants to steer from web/mobile;
- the machine can stay awake and connected.

Choose a **local background session** when:

- the task needs local state;
- remote steering is unnecessary;
- work can run independently and be monitored in `claude agents`.

## Cloud repository truth

`claude --cloud` creates a **new** cloud session. For a GitHub-backed repository it clones the current repository remote and branch. It does not upload arbitrary uncommitted local working-tree state.

Before launch:

```bash
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
git remote -v
git push
```

For complex changes:

1. plan locally in `--permission-mode plan`;
2. save the approved plan in the repository;
3. commit and push the plan and required inputs;
4. launch cloud execution against that exact branch;
5. require the cloud result to report its final SHA, diff, commands, and remaining uncertainty.

For a repository not available through GitHub, use Claude Code’s documented local-repository bundle route rather than pretending uncommitted files were transferred.

## Configure the cloud environment

Review:

```text
cloud/README.md
cloud/setup.sh
cloud/environment.env.example
cloud/allowed-domains.example.txt
```

Recommended setup:

1. Create a named environment such as `MAD Ventures — Governed Build`.
2. Begin with Trusted network access unless a stricter reviewed allowlist is ready.
3. Paste only reviewed **non-secret** values from `cloud/environment.env.example`.
4. Use `cloud/setup.sh` as the environment setup script after inspection.
5. Select the environment locally with `/remote-env`.
6. Start a narrow cloud task and run `mad-cloud-doctor`.
7. Confirm runtime/package-manager versions and repository install behavior before broad autonomy.

Cloud environment variables are not the package’s secret store. Use the approved Anthropic/cloud integration and repository secret-management path. Never place long-lived credentials in committed settings, example files, prompts, logs, or handoff documents.

## Optional project dependency bootstrap

The repository includes:

```text
.claude/cloud/session-start.sh
profiles/cloud-session-start.settings.fragment.json
```

The shared baseline intentionally does **not** activate this `SessionStart` hook. To opt in:

1. inspect the repository lockfile and package-manager policy;
2. merge the fragment into `.claude/settings.json`;
3. set `MADVENTURES_CLOUD_INSTALL_DEPS=true` in the cloud environment;
4. test in a disposable cloud session;
5. verify the hook runs only when `CLAUDE_CODE_REMOTE` indicates the cloud runtime.

Do not silently install dependencies from a generic package into every repository.

## Launch contract

Example:

```bash
claude --cloud "Execute docs/approved-plan.md on this branch. Allowed scope: app/auth/** and tests/auth/**. Run the profile verification commands. Do not change governance, credentials, shared Claude configuration, deployment, or activation state. Do not merge. Return final SHA, changed files, command results, blockers, and unknowns."
```

Every cloud task must state:

- goal and machine-verifiable completion condition;
- exact approved plan/reference;
- allowed files/subsystems;
- prohibited paths and actions;
- required tests/build/runtime checks;
- branch/PR expectations;
- stop conditions;
- no merge, deploy, activation, authority change, secret access, or destructive recovery without Founder approval.

Run independent tasks in separate cloud sessions and branches. Do not assign two sessions to the same files.

## Monitor cloud work

Use:

```text
/tasks
```

and the web/mobile session view. Intervene when:

- the task crosses its file/authority boundary;
- the plan proves incorrect;
- a required tool or network path is unavailable;
- acceptance criteria become ambiguous;
- verification cannot run;
- the session requests a permission or governance decision.

Cloud sessions persist independently of the local machine, but they still consume account usage and remain subject to environment expiry, organization policy, and provider limits.

## Cloud context behavior

Cloud sessions support:

```text
/context
/compact
```

They do not support `/clear`; start a new cloud session from the sidebar instead. Project `.claude` files committed with the repository travel to the cloud. Personal `~/.claude` configuration does not automatically become cloud project state, so critical doctrine is duplicated at the repository layer.

## Teleport cloud work locally

```bash
claude --teleport
claude --teleport <session-id>
```

Use the same claude.ai account and a clean checkout of the same repository. After teleporting:

1. record repository, branch, and HEAD;
2. inspect `git status` and the full diff;
3. compare the cloud narrative to actual files;
4. rerun verification locally;
5. run independent review on the resulting immutable SHA;
6. do not treat successful teleport as merge, deployment, or activation.

Terminal-to-web handoff is not symmetrical: `--cloud` creates a new cloud session; it does not push an existing local transcript to the web. The Desktop product may expose additional continuation UI, but this package does not rely on it.

## Remote Control

Start server mode:

```bash
cd /path/to/project
claude remote-control --name "FounderOS Console"
```

Start a normal interactive session with remote access:

```bash
claude --remote-control "FounderOS Console"
```

Enable it in an existing session:

```text
/remote-control FounderOS Console
```

For multiple independent Remote Control sessions:

```bash
claude remote-control --spawn worktree --capacity 4 --name "MAD Ventures Build Room"
```

Remote Control facts:

- code execution and filesystem access remain local;
- local MCP servers, project configuration, tools, subagents, and workflows remain available;
- attachments sent from another device are downloaded to the local machine;
- the local machine and Claude Code process must be available for live work;
- sleep/network interruption pauses connectivity and can reconnect later;
- eligibility requires an appropriate claude.ai login/account and is not available through every provider/proxy configuration;
- organization owners can restrict or disable it.

Remote Control is the preferred remote surface for Hermes/local-only model connectors, because those connectors do not exist inside Anthropic’s cloud unless separately and explicitly configured there.

## Remote security boundaries

### Cloud

- review network mode and allowed domains;
- never assume local credentials are present;
- treat setup scripts as privileged build infrastructure;
- limit repository and GitHub permissions;
- review sharing visibility before exposing a session;
- remember that public/shared sessions can expose private code or credentials if mishandled.

### Remote Control

- the local host remains the execution and secret boundary;
- remote viewers can exercise whatever the local session is allowed to do;
- review local MCP servers and connectors before enabling;
- use worktrees for concurrent edits;
- stop the server or `/remote-control` when remote access is no longer needed;
- Remote Control does not turn a local connector into an independent reviewer or authorized deployer.

## Closeout evidence

For either route, preserve:

- execution host;
- account/provider and active model;
- repository, branch, base/head SHA;
- prompt/approved plan;
- allowed scope;
- changed files;
- commands and results;
- open findings and unknowns;
- review state;
- Founder authorization state;
- whether work is merely implemented, verified, merged, deployed, or activated.
