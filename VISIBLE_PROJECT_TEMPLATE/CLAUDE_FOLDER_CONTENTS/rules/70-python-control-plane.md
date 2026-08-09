# Python control-plane rules

> **MCP is the interface layer. Python is the deterministic enforcement layer.** Models, plugins,
> agents, and MCP tools may request, inspect, recommend, and explain; they cannot self-create
> verification, approval, checkpoint integrity, scope compliance, or any other governed truth.

Use `.claude/control-plane/madclaude.py` only when deterministic orchestration, structured evidence,
scope enforcement, bounded repair, or exact-SHA isolation adds material value over an interactive
Claude Code session.

1. Native `claude -p` is the governed Python default. It uses the authenticated Claude subscription
   lane and does not require an API key or Agent SDK.
2. Subscription mode stops before execution when an API key, bearer token, provider route, gateway,
   custom base URL, or API-key helper could supersede or obscure the subscription login.
3. API billing is never inferred. It requires `--billing-mode api --allow-api-billing` and a positive
   `--max-budget-usd` in the same invocation. Never request, print, or persist credential values.
4. The optional Agent SDK is an API-only adapter in this package and must be installed explicitly
   with `--with-sdk` / `-WithSdk`.
5. Every native CLI run receives an ephemeral Python-generated `PreToolUse` policy. Project policy
   hooks remain defense in depth, not the sole control.
6. Read-only planning and audit routes may spawn only their registered read-only subagents. Build and
   repair routes keep one accountable builder and expose no Agent tool.
7. A build requires an inspectable plan and Founder approval bound to the plan SHA-256, exact goal,
   allowed scopes, acceptance criteria, verification commands, and a non-cached evidence source.
8. Python-run verification is independent of builder prose. Report exact commands, exit status, and
   observed output.
9. Review and release-readiness routes require literal full Git SHAs and run in detached temporary
   worktrees. Any later commit invalidates the old verdict.
10. MCP, web, shell, Skill, nested delegation, credentials, and authority-path mutation remain denied
    inside controlled model routes.
11. Local evidence is not automatically a ratified governance record, merge/deploy authorization,
    production proof, or authoritative billing record.
12. Auth preflight proves the credential lane only; it cannot prove remaining plan allowance,
    account-level extra-usage settings, or the final invoice.
13. Executable JavaScript workflows are retired. All 14 former capabilities route to the single
    Python engine according to `WORKFLOW_MIGRATION.json`; prompt text is never an enforcement bridge.
14. Route model overrides must remain inside the Python-owned eligibility envelope. Tier-2 selection
    must read prior execution records, exclude every participating model, and fail closed when none
    remains.
15. Every evidence bundle declares `local_evidence`, `remote_verified_evidence`, or `cached_evidence`.
    Cached evidence may inform analysis but cannot establish approval or verification authority.
16. Every governed run writes an observable execution record with repository, immutable SHAs,
    participant role/model/stage, evidence path, and final status. Never store hidden reasoning.
17. `.claude/hooks/hook-adapter.mjs` is the only JavaScript hook module. It transports events to
    Python; it contains no governance decision logic.
18. A dirty-tree `Stop` or `TaskCompleted` event requires a completed evidence manifest whose hashes,
    exact HEAD, working-tree fingerprint, deterministic commands, and `VERIFICATION.md` envelope all
    validate. Stale, malformed, skipped, failed, or tampered evidence cannot authorize completion.
19. Governed mutation emits canonical `PLAN`, `HANDOFF`, `VERIFICATION`, and `ACCEPTANCE` artifacts
    as applicable. Exact-SHA review emits `REVIEW` or `TIER2_REVIEW`. Markdown frontmatter is an
    inspectable envelope; Python JSON evidence and manifest hashes remain authoritative.
