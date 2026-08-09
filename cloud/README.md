# MAD Ventures Claude Code cloud environment

These assets configure the Anthropic-managed cloud VM separately from the repository-local Claude Code control plane.

## Create the environment

1. Open the cloud environment selector at `claude.ai/code`.
2. Add a personal or organization-shared environment named `MAD Ventures — Governed Build`.
3. Start with **Trusted** network access. Use a Custom allowlist only after confirming every required registry and API domain.
4. Paste `environment.env.example` into the environment variables field after reviewing it.
5. Paste `setup.sh` into the Setup script field.
6. Save the environment, then select it locally with `/remote-env`.

Do not add API keys, database URLs, signing keys, personal access tokens, or other secrets to cloud environment variables. The cloud environment UI is not a dedicated secret store.

## What the setup script does

- installs the GitHub CLI and ShellCheck;
- leaves language runtimes and repository dependencies alone;
- creates `mad-cloud-doctor` for a quick environment check;
- writes no credentials and performs no repository mutation.

## Optional repository dependency bootstrap

The installer places `.claude/cloud/session-start.sh` in the repository, but does **not** activate it automatically. To enable it:

1. review `project/profiles/cloud-session-start.settings.fragment.json`;
2. merge its `SessionStart` entry into `.claude/settings.json`;
3. set `MADVENTURES_CLOUD_INSTALL_DEPS=true` in the cloud environment only after verifying the repository's lockfile and install policy.

The script exits immediately unless `CLAUDE_CODE_REMOTE=true`. It installs only from a recognized lockfile and uses immutable/frozen modes where supported.

## Cloud execution pattern

```bash
# Plan with the Founder in the loop.
claude --permission-mode plan --model fable --effort high

# Commit and push the approved plan, then execute in a separate cloud session.
claude --cloud "Execute docs/approved-plan.md. Do not merge, deploy, activate, or modify governance authority. Run all required checks and leave a review-ready branch."

# Monitor from the local CLI.
# Inside Claude Code: /tasks

# Pull a completed cloud session into a clean local checkout.
claude --teleport
```

Each cloud command creates an independent session. Use separate branches or non-overlapping task ownership to avoid merge collisions.
