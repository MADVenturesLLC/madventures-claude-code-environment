# Validation report

**Generated:** 2026-10-03T13:20:54+00:00
**Package:** MADVentures-Claude-Code-Environment-v4.4.2
**Result:** PASSED
**Summary:** 62 pass, 1 warning, 0 fail

## Checks

- **PASS** — package version is 4.4.2
- **PASS** — required documentation present (29 files)
- **PASS** — Finder-visible mirror, top-level launchers, package index, and fast integrity preflight validated
- **PASS** — cross-platform installers use fast validation by default and preserve exhaustive opt-in validation
- **PASS** — expected agents count: 20
- **PASS** — expected skills count: 31
- **PASS** — expected workflows count: 0
- **PASS** — expected rules count: 8
- **PASS** — expected hooks count: 2
- **PASS** — agent names, frontmatter, tools, routing, and special guards validated
- **PASS** — skill names and frontmatter validated
- **PASS** — all 104 JSON configuration files parse
- **PASS** — project settings: no ineffective path-scoped Write/NotebookEdit/Glob/MultiEdit rules
- **PASS** — project settings: Read deny paths have matching Edit deny protection
- **PASS** — project settings hook references resolve (1 unique)
- **PASS** — ~/.claude.json-only keys are separated into the global fragment
- **PASS** — review-only settings profile combines plan mode with complete edit and shell denials
- **PASS** — FOUNDEROS.md imports the repository profile and model registry
- **PASS** — Founder-approved Claude and external model registry validated
- **PASS** — opt-in Opus advisor profile validated
- **PASS** — local Markdown links resolve
- **PASS** — Python build route requires SHA-bound, source-classified Founder approval evidence
- **PASS** — AUTHORITATIVE ENGINE VALIDATION PASSED (14 capabilities, 0 executable JavaScript workflows)
- **PASS** — all hook, test, and status-line JavaScript modules compile
- **PASS** — HOOK/STATUSLINE TESTS PASSED
- **PASS** — Bash installer, route launcher, release, cloud, and test scripts pass syntax validation
- **PASS** — MODEL ROUTE LAUNCHER TEST PASSED
- **PASS** — CLOUD SESSION TEST PASSED
- **PASS** — Python build and release scripts compile
- **WARN** — PowerShell not found; static PowerShell parse skipped
- **PASS** — release pipeline rebuilds the plugin and runs official validation when Claude CLI is available
- **PASS** — no credential-shaped values detected
- **PASS** — MCP configuration remains inactive by filename
- **PASS** — GitHub MCP example uses bounded header-based read-only configuration
- **PASS** — Python control-plane canonical source, policy hooks, installers, and dedicated test harness are present
- **PASS** — Python control plane has one canonical package source
- **PASS** — Python package is dependency-free by default and pins the optional API SDK extra exactly
- **PASS** — ten Python structured-output schemas parse
- **PASS** — all 55 Python control-plane modules/tests compile without cache files
- **PASS** — Python CLI defaults to native claude -p under the authenticated subscription lane
- **PASS** — native claude -p backend injects structured output, ephemeral policy hooks, strict MCP isolation, and API-only dollar caps
- **PASS** — optional Agent SDK adapter is API-only and retains Claude Code preset, strict MCP, checkpoint, and PreToolUse controls
- **PASS** — read-only fan-out is constrained to route-specific subagents while mutation routes remain single-builder
- **PASS** — subscription credential precedence, model-entitlement caveat, usage-credit gate, and explicit API-billing gates validated
- **PASS** — one Python-backed adapter enforces baseline, configuration, and completion policy
- **PASS** — eleven governed Python routes load with constrained read-only fan-out and single-builder mutation lanes
- **PASS** — Python control-plane integration rerun skipped for nested installation smoke; full release validation runs it separately
- **PASS** — Python installers are dependency-free by default and make the API SDK an exact, explicit opt-in
- **PASS** — V4.4 documentation consistently describes native CLI subscription default and API-only optional SDK
- **PASS** — release tree contains no Python bytecode/cache artifacts
- **PASS** — portable plugin manifest identity and version validated
- **PASS** — portable plugin component counts validated (19 agents, 31 skills, 0 executable workflows)
- **PASS** — portable plugin intentionally excludes only neon-reader
- **PASS** — plugin skills are synchronized with project skills
- **PASS** — plugin workflows are synchronized with project workflows
- **PASS** — plugin hook references resolve (1 unique)
- **PASS** — plugin ships one thin adapter backed by the shared Python policy modules
- **PASS** — plugin Python policy modules are byte-identical to the canonical source
- **PASS** — plugin policy modules cover the hook import closure (10 modules)
- **PASS** — cloud environment assets present (7 files)
- **PASS** — cloud SessionStart dependency installation is remote-scoped and opt-in
- **PASS** — cloud environment example contains non-secret controls only
- **PASS** — cloud SessionStart hook is supplied as an explicit opt-in fragment

## Interpretation

Static validation proves package shape, syntax, references, guard placement, and installer behavior that can be tested locally. It does not prove account-specific model availability, organization policy, MCP authentication, live repository commands, or production behavior. Run `claude doctor` and the repository's real verification commands after deployment.
