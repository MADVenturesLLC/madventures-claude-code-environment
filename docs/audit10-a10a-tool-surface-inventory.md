# A10-A Tool Surface Inventory — Audit 10 Build Commission Evidence

**Status:** Working-tree evidence for the A10-A build commission (UNCOMMITTED).
**Baseline:** `MADVenturesLLC/madventures-claude-code-environment` `main` @ `4352dd2`.
**Recorded:** 2026-08-12. Read-only enumeration; no mutations.
**Governed by:** DEC-20260812-01 (active), Package A10-A, deliverable: supported-tool policy matrix.

This inventory is the live-tool ground truth the A10-A supported-tool policy
matrix ratifies against before the `hook_policy.py:99-100` flip from
allow-unknown to deny-unknown. Every family in the DEC's starting-point matrix
carries a live evidence line here.

---

## 1. Route-governed tools (`python-control-plane/src/madclaude/config.py` `ROUTES`)

Eleven routes. Union of route tool tuples: `{Read, Grep, Glob, Agent, Edit, Write}` —
the complete governed tool set today.

| Route | Tools |
|---|---|
| `plan` | Read, Grep, Glob, Agent |
| `build` | Read, Grep, Glob, Edit, Write |
| `verify` | Read, Grep, Glob |
| `review` | Read, Grep, Glob |
| `tier1-review` | Read, Grep, Glob |
| `release-readiness` | Read, Grep, Glob |
| `repo-audit` | Read, Grep, Glob, Agent |
| `security-audit` | Read, Grep, Glob, Agent |
| `ui-review` | Read, Grep, Glob, Agent |
| `fix-until-green` | Read, Grep, Glob, Edit, Write |
| `architecture-validation` | Read, Grep, Glob |

## 2. Enforcement-layer tool sets

| Set | Members | Location |
|---|---|---|
| `FILE_TOOLS` | Read, Edit, Write, NotebookEdit, MultiEdit, Grep, Glob | `hook_policy.py:18` |
| `MUTATION_TOOLS` | Edit, Write, NotebookEdit, MultiEdit | `hook_policy.py:19`, `guard.py:13` |
| `SHELL_TOOLS` | Bash, PowerShell | `guard.py:15` |
| `WEB_TOOLS` | WebFetch, WebSearch | `guard.py:14` — **defined but never consulted in any decision path: falls through → allow (the hole)** |
| `ALIASES` | Task → Agent | `guard.py:16` |

## 3. Hook coverage

- `plugin/madventures-founderos/hooks/hooks.json` — `PreToolUse` matcher `"*"`
  (every tool) → `hook-adapter.mjs baseline`, timeout 10. Same for `ConfigChange`.
- Baseline decision (`hook_policy.py:94-100`): `ALIASES.get(tool_name)`;
  Bash/PowerShell → `_baseline_shell`; FILE_TOOLS → `evaluate_tool_call`;
  **everything else → `return True, "allowed"`** (the A10-2 hole).

## 4. Installed surfaces with live tool use

| Surface | Content | Tool families exercised |
|---|---|---|
| Skills | 31 skills × 3 mirrors (`VISIBLE_PROJECT_TEMPLATE/CLAUDE_FOLDER_CONTENTS/skills`, `plugin/madventures-founderos/skills`, `project/.claude/skills`) | Skill family live |
| Subagents | 19 agents (`plugin/madventures-founderos/agents/`) | Agent/Task delegation live |
| Plugin | `madventures-founderos` v4.4.1 (`plugin.json`: name, version, hooks) | All of the above |

## 5. Tool vocabulary observed in the wild (grep counts, source + plugin + project)

Read(84) Grep(58) Glob(58) Edit(42) Write(43) NotebookEdit(28) MultiEdit(19)
Bash(74) PowerShell(24) WebFetch(11) WebSearch(4) Agent(101) Task(10) Skill(9)
— plus proposal-named meta tools (TaskCreate/Update, ExitPlanMode, TodoWrite)
and `mcp__*` (control-plane denies; baseline falls through).

## 6. Matrix implications (sharpened cells)

1. **Web (WebFetch/WebSearch)** — `WEB_TOOLS` is dead code (defined, never
   consulted). Matrix must disposition explicitly (DEC starting point: deny at
   baseline) and the build must either wire a governed route or confirm denial.
2. **Skill** — 31 live skills × 3 mirrors ⇒ real, used family; explicit
   disposition required (allow vs. governed).
3. **Delegation (Agent/Task)** — 19 subagents + 6 routes ⇒ governed route with
   subagent allowlist (matches control-plane stance).
4. **`mcp__*`** — control-plane denies, baseline falls through ⇒ deny at
   baseline closes a real gap.

## 7. Verification to re-run at build time

- Re-enumerate the live tool set (routes + installed plugin/skill surfaces)
  on the build branch before ratifying the matrix — surfaces may drift from
  this baseline.
- Run `python-control-plane/tests/` (source suite 275) and the installed
  suite (163) after the flip; parity via `test_plugin_parity.py`.

*End of inventory. Uncommitted working-tree evidence; becomes the matrix's
evidence appendix when the A10-A branch opens.*
