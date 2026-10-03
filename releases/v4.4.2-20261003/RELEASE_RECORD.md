# Release Record — MADVentures Claude Code Environment v4.4.2

**Status:** PREPARED — PENDING FOUNDER APPROVAL (approval not yet issued; artifact SHA-256 values below are proposed, not approved)
**Recorded (UTC):** 2026-10-03
**Package version:** `4.4.2`
**Release root (repository):** `releases/v4.4.2-20261003`
**Permanent release root (on-disk target):**
`/Users/michaeldaley/MADVenturesOPs/releases/v4.4.2-20261003`

> On approval, the Founder replaces the Status line above and records the approval; only then do the artifact SHA-256 values below become the approved baseline. This record, as filed, does not approve anything.

---

## 1. Founder approval

**NOT YET ISSUED.**

Approval is external to this package (governance boundary 6: no self-granted approval). The exact tree, artifact identities, validation results, and open gates below are the inputs to the Founder's decision.

**Open gates a Founder decision should address (see §4):**
- Native arm64 target gate: **RE-RUN AND PASSED for this cut, pinned** — `evidence/audit442-target-gate-arm64.json` (SHA-256 `eb58baf96c75d84adb40729a0fdec20185976645b1b7fab8300b4a0624739458`); all 10 steps exit 0; artifact SHA matches the filed ZIP; wheelhouse resolved under `evidence/wheelhouse-constraints-cp314-macos.txt` (cryptography pinned to 48.0.1 — macOS universal2 — because 50.0.2 has no x86_64 build and the merge gate fails closed on cross-target divergence).
- Native x86_64 target gate: **RE-RUN AND PASSED for this cut, pinned** — `evidence/audit442-target-gate-x86_64.json` (SHA-256 `a1c00db7eff5b4d5c7a4d6fc210b517e03339499dc0a2ea35e3eaf6645ad2716`); all 10 steps exit 0 on `Michaels-iMac.local` (native Intel x86_64; no simulation), artifact SHA matches the filed ZIP, `cryptography==48.0.1` installed. Its lock file (`3bee6a9c…`) is byte-identical to an independently pinned cross-arch rebuild of the same wheelhouse on the arm64 host — the two target sets provably agree.
- Merged wheelhouse: **REBUILT for this cut** — `wheelhouse/merged/` (28 distributions; MERGED_WHEELHOUSE_MANIFEST.json `f3394499…`; locks `6f7df649…` arm64 / `3bee6a9c…` x86_64), deterministically merged from the two reviewed per-target wheelhouses. §3 below.
- MCP release-install surface: **RE-PROVEN on both architectures** — the A10-series `mcp_lifecycle.py`/`mcp_server.py` paths ran end-to-end inside both native gates (install, staged self-test, atomic enable, protocol roundtrip, real mcp 2.0.0 SDK stdio roundtrip, disable/re-enable/status cycle), 10/10 steps exit 0 on each.

No gate of the Audit 9 set remains open. The decision before the Founder is approval of the artifacts in §2 and the record as a whole.

---

## 2. Proposed artifact identities

| Artifact | Path (under release root) | Size (bytes) | SHA-256 |
|---|---|---|---|
| Full ZIP | `artifacts/MADVentures-Claude-Code-Environment-v4.4.2.zip` | 662698 | `121723bd2b9ae4bd3e20a79666e4504980a42ec6861df1541ce2d241f8526f55` |
| Full TAR.GZ | `artifacts/MADVentures-Claude-Code-Environment-v4.4.2.tar.gz` | 477979 | `af8bfd665046d4626fe0c534c81e594906d24326e2d9defa2c713aa63a3f8dd3` |
| Portable plugin | `artifacts/MADVentures-FounderOS-Claude-Code-Plugin-v4.4.2.zip` | 91041 | `e2c3d5c459a7e96792e0bd5c7aeec4a30d06a1dd7aacd9be043262bb3dd68326` |

Post-copy recomputation confirmed each hash matches the values above exactly. Sidecar `.sha256` files under `artifacts/` also verify OK.

Release inventory checksums for all files under this root (except `SHA256SUMS.txt` itself): `SHA256SUMS.txt` (relative paths).

---

## 3. Source identity

- **Built from repository:** `MADVenturesLLC/madventures-claude-code-environment`
- **Branch:** `release/4.4.2-prep`
- **Source tree commit (build input):** `4e79443ea2c31f3c771fe186c4665f62e1a14023`
- **Base:** `main` @ `f7588048308cd0fd556bde06e69d56e6de6428c9` (post-#7/#8/#9) plus the release-prep commit
- **Note:** this commit supersedes at merge; the merged `main` commit will become the canonical source identity once the release PR lands. Artifacts were built from the tree of `4e79443`; the artifact-internal `MANIFEST.json` was verified byte-identical to the working tree at build time.
- **Gate evidence branch:** `release/4.4.2-gates` (tip at evidence time: `22d23de33e132859ea30ab247b51764ae1216e67`; evidence committed from both machines: arm64 on the MacBook Pro, x86_64 from the iMac; merge + record finalization on the MacBook Pro; subsequent record commits advance the branch tip).

Superseded by this release: the Aug 13 candidate build archived on disk as `Audit10-v4.4.1-20260813` (v4.4.1-era hardening, no record, not in this repository).

---

## 4. Build and validation evidence (this cut)

Build host: macOS arm64 (Apple M2 Max), Python `3.14.6`, git `2.54.0 (Apple Git-157)`.
Build ran with a clean subscription lane (`CLAUDE_CONFIG_DIR` = dedicated clean config dir, watched `ANTHROPIC_*` variables absent).

| Gate | Result |
|---|---|
| Source-tree suite (release tree, `run-tests.py`) | **334 tests OK** |
| Installed-layout suite (`run-tests.py --installed`) | **220 tests OK** (19 modules) |
| Exhaustive validator (`validate-config.py`) | **62 pass, 1 warning, 0 fail** (PowerShell absent on macOS — expected/acceptable) |
| Release lifecycle gates | **PASSED** — clean-extraction harness/integrity; ZIP + TAR fresh install; migration; rollback; hierarchy; status/doctor/uninstall |
| Release verification (`verify-release.py`) | **PASSED** — full package 363 manifest files; portable plugin 19 agents, 31 skills, 0 workflows |
| Plugin byte parity + closure | PASSED (policy modules byte-identical; hook import closure covered) |
| Shell control-plane test (`test-python-control-plane.sh`) | **PASSED** (default install, dry-runs, wrapper self-checks, SDK opt-out, permissions) |

Environment note (found during this cut, fixed before the build): the release shell test's inline `claude` stub did not answer the `--version` probe introduced by the CLI version floor (#7); the build stopped after the source suite. Fixed in `bccb3f7b290fbd0f9f749c2c0c1696d047bb3f93` (stub now answers `--version`).

Known host quirk (not a package defect): when a shell carries `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_BASE_URL` injected by `~/.claude/settings.json`, the fail-closed preflight correctly refuses subscription mode and 15 installed-suite cases error. This is the designed fail-closed behavior; the release build and CI's clean runner do not carry those variables.

**Not re-run for this cut (see §1 open gates):** — none. All Audit 9 gate classes (native arm64 + x86_64 target gates, merged wheelhouse, MCP re-proof) were re-run and passed for this cut; see the two gate tables and §3.

### Native target gate — arm64 (RE-RUN, PASSED)

| Field | Value |
|---|---|
| Evidence file | `evidence/audit442-target-gate-arm64.json` |
| Evidence SHA-256 | `eb58baf96c75d84adb40729a0fdec20185976645b1b7fab8300b4a0624739458` |
| Machine / arch | `MikeMacBook.local` / `arm64` (native, from the running interpreter) |
| Python | CPython `3.14.6` |
| Artifact SHA recorded | `121723bd2b9ae4bd3e20a79666e4504980a42ec6861df1541ce2d241f8526f55` (matches the filed ZIP) |
| Evidence class | `release-target` / `releaseEvidence: true` |
| Steps | all **10/10 exit 0** — local-harness, wheelhouse-lock-generation, offline-release-install, staged-launcher-self-test, atomic-enable, protocol-roundtrip, fastmcp-stdio-roundtrip, verb-cycle-disable, verb-cycle-re-enable, verb-cycle-status |
| Installed inventory | 28 distributions incl. `mcp==2.0.0`, `cryptography==48.0.1` |
| Pins | `evidence/wheelhouse-constraints-cp314-macos.txt` (both target runs) |

### Native target gate — x86_64 (RE-RUN, PASSED)

| Field | Value |
|---|---|
| Evidence file | `evidence/audit442-target-gate-x86_64.json` |
| Evidence SHA-256 | `a1c00db7eff5b4d5c7a4d6fc210b517e03339499dc0a2ea35e3eaf6645ad2716` |
| Machine / arch | `Michaels-iMac.local` / `x86_64` (native Intel, from the running interpreter) |
| Python | CPython `3.14.7` |
| Artifact SHA recorded | `121723bd2b9ae4bd3e20a79666e4504980a42ec6861df1541ce2d241f8526f55` (matches the filed ZIP) |
| Evidence class | `release-target` / `releaseEvidence: true` |
| Steps | all **10/10 exit 0** (same gate sequence as arm64) |
| Installed inventory | 28 distributions incl. `mcp==2.0.0`, `cryptography==48.0.1` |
| Recorded lock SHA | `3bee6a9c3db40eb7bbc34826497859111473775215ddd7618a8df2588bdba706` |
| Cross-target agreement | the same pinned constraint set was independently resolved and finalized cross-arch on the arm64 host, producing a **byte-identical lock** (`3bee6a9c…`) — the two target sets provably agree |

### Merged wheelhouse (REBUILT for this cut)

Deterministic merge of the two reviewed per-target wheelhouses (`scripts/mcp-wheelhouse.py merge`), mirroring the Audit 9 layout:

| Item | Path | SHA-256 |
|---|---|---|
| Merged directory | `wheelhouse/merged/` | 28 distributions (shared pure wheels + per-arch wheels) |
| Merged manifest | `wheelhouse/merged/MERGED_WHEELHOUSE_MANIFEST.json` | `f339449958ea021a348e656a73d0464022db48a3efb83af11b9b186482c0ace9` |
| arm64 lock | `wheelhouse/merged/requirements-cp314-macos-arm64.lock` | `6f7df649ca77d034800617546998c4ea84846c305c3b86978d85b7ec09bd960e` |
| x86_64 lock | `wheelhouse/merged/requirements-cp314-macos-x86_64.lock` | `3bee6a9c3db40eb7bbc34826497859111473775215ddd7618a8df2588bdba706` |

Per-arch source manifests preserved: `wheelhouse/arm64/WHEELHOUSE_MANIFEST.json` (`5a9bdf2383ca6f4a719f4f2cf7fe3fc8a2391c8967ad7e0c5637684e1df5ee01`) and `wheelhouse/x86_64/WHEELHOUSE_MANIFEST.json` (`c2f02c96f12ffe3922ba7fe80469e01469bde42ea8bf4425fb6ce20d580dd8e6`).

---

## 5. What this release contains (vs Audit 9 approved baseline)

Everything merged on `main` after the Audit 9 artifacts (`4352dd2`):

- **A10-A** — secret-pattern registry, supported-tool matrix, baseline deny-unknown.
- **A10-C** — runtime-state enforcement: escalation journal, ceilings, terminal deny.
- **A10-D** — schema extras and mechanical tier classifier.
- **MAD_OS environment-identity marker** on the status line.
- **CI merge gates** — installed suite (asserted module/test counts) + plugin parity + `quick-validate.py` (mirror parity, delivery-index exactness, manifest integrity).
- **CLI version floor** — auth preflight fails closed below the documented `2.1.223` minimum, on probe failure, and on unparseable version output.
- **Version-identity tripwire** — `VERSION`, `pyproject.toml`, `plugin.json`, and both `madclaude/version.py` copies must agree.
- **Entry-point consolidation** — `README.md` + `START_HERE.md` canonical; `README_FIRST.txt`/`OPEN_ME_FIRST.md` are pointer stubs; `docs/README.md` indexes all shipped references.
- **Version sweep** — all toolchain/script/doc version literals moved to 4.4.2 in lockstep.

Full inventory: see `CHANGELOG.md` §4.4.2 in the source tree.

---

## 6. Governance boundaries preserved

1. **Python is the authoritative deterministic engine.**
2. **One thin JavaScript adapter** for hooks; **zero executable JavaScript workflows.**
3. **Local-first operation** — no remote authority for control-plane decisions.
4. **SHA-bound evidence** — computed vs declared hashes never conflated.
5. **Fail-closed enforcement** — guard allowlists, schema keyword coverage, safe_read TOCTOU protection, MCP non-authoritative stamping, CLI version floor.
6. **No self-granted approval** — Founder approval is external to the package; the control plane cannot authorize itself.

---

## 7. Explicit non-actions (out of scope of this cut)

This cut did **not**:

- install or activate the release into any project or global environment;
- delete previous environments, prior Audit 8b baselines, or the Aug 13 candidate artifacts;
- remove ambient system or Hermes MCP installations;
- modify any release artifact after hashing (copy-only from the verified build output).

Those require separate Founder authorization. (The native target gates and wheelhouse rebuild — previously listed as open in an earlier revision of this record — are **complete** for this cut; see §1 and §4.)

---

## 8. Ready state

**Prepared, not approved.** After Founder approval of the exact artifacts above and completion of any required open gates (§1):

- this record's Status line is updated by the Founder (and the date-of-approval recorded);
- because that edit changes this file's SHA-256, `SHA256SUMS.txt` in this root must be regenerated after approval (it currently hashes the record as filed);
- the release is ready for a separately authorized installation.

**Proposed baseline SHAs (repeat, pending approval):**

- Full ZIP: `121723bd2b9ae4bd3e20a79666e4504980a42ec6861df1541ce2d241f8526f55`
- Full TAR.GZ: `af8bfd665046d4626fe0c534c81e594906d24326e2d9defa2c713aa63a3f8dd3`
- Portable plugin: `e2c3d5c459a7e96792e0bd5c7aeec4a30d06a1dd7aacd9be043262bb3dd68326`
