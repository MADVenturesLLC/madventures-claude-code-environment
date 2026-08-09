# Audit 9 Release Record — MADVentures Claude Code Environment v4.4.1

**Status:** CLOSED — FOUNDER APPROVED  
**Recorded (UTC):** 2026-08-09  
**Package version:** 4.4.1  
**Permanent release root:**  
`/Users/michaeldaley/MADVenturesOPs/releases/Audit9-v4.4.1-20260809`

---

## 1. Founder approval

**FOUNDER DECISION: AUDIT 9 APPROVED**

Audit 9 is approved based on final cross-architecture evidence. The approved release baseline is the three artifact SHA-256 values listed in §2. This record closes Audit 9. Installation, activation, deletion of prior environments, and removal of ambient MCP installations are **not** authorized by this approval and require separate Founder authorization.

---

## 2. Approved artifact identities

| Artifact | Path (under release root) | Size (bytes) | SHA-256 |
|---|---|---|---|
| Full ZIP | `artifacts/MADVentures-Claude-Code-Environment-v4.4.1.zip` | 619105 | `a33fdbeddb7bc1eceede374ca094c9d4014712a5706d53b840716183c4a64d77` |
| Full TAR.GZ | `artifacts/MADVentures-Claude-Code-Environment-v4.4.1.tar.gz` | 441112 | `acd4789da9b978dd069f044d0b69110cd6a5e5ec6e6ba540ada09b1489d9d335` |
| Portable plugin | `artifacts/MADVentures-FounderOS-Claude-Code-Plugin-v4.4.1.zip` | 78448 | `c34cd6ea63b89c81fdd8449ba918866a42f176bcbeb47fedad769f4e5803f98e` |

Post-copy recomputation confirmed each hash matches the Founder-approved values exactly. Sidecar `.sha256` files under `artifacts/` also verify OK.

Release inventory checksums for all copied files: `SHA256SUMS.txt` (relative paths).

---

## 3. Merged wheelhouse identity

| Item | Path | SHA-256 |
|---|---|---|
| Merged wheelhouse directory | `wheelhouse/merged/` | (31 wheels + 2 locks + merged manifest) |
| Merged manifest | `wheelhouse/merged/MERGED_WHEELHOUSE_MANIFEST.json` | `d0b3d2e7753ba0f5d834c70f0ad049fd8ca8888bbe90ee7d15fb48eae622b865` |
| arm64 lock (in merged) | `wheelhouse/merged/requirements-cp314-macos-arm64.lock` | `cde78a524a39fd52882baa6338d935838132283fb8a6743842f9875a6396cde6` |
| x86_64 lock (in merged) | `wheelhouse/merged/requirements-cp314-macos-x86_64.lock` | `a534ffcb4579d0cbdebeccd0c7517ae39d51330390ae53023fde6872ec0a6fdd` |

**Merge verification at approval time:**
- 28 distributions on each target
- Package/version set identical across arm64 and x86_64
- 31 wheels on disk (arch-specific wheels for cffi, pydantic-core, rpds-py)
- `mcp==2.0.0` pinned; `cryptography==48.0.1` on both targets

Per-arch source locks/manifests preserved at:
- `wheelhouse/arm64/requirements-cp314-macos-arm64.lock` + `WHEELHOUSE_MANIFEST.json`
- `wheelhouse/x86_64/requirements-cp314-macos-x86_64.lock` + `WHEELHOUSE_MANIFEST.json`

---

## 4. Native gate evidence identities

| Evidence | Path | SHA-256 of JSON file |
|---|---|---|
| arm64 final target gate | `evidence/audit9-target-gate-arm64.json` | `f6033d66e1d1aee6ba591252ad1b3b7b32797fd00b38463ffddb00e5160a1bb9` |
| x86_64 final target gate | `evidence/audit9-target-gate-x86_64.json` | `4c0c21710818a51d72c53d5c98faf47ff66729249d05817912c43ffe35c6cd4a` |

### arm64 evidence content (verified)

| Field | Value |
|---|---|
| `artifactSha256` | `a33fdbeddb7bc1eceede374ca094c9d4014712a5706d53b840716183c4a64d77` |
| `architecture` / `platformMachine` | `arm64` / `arm64` |
| `pythonVersion` | `3.14.6` |
| `evidenceClass` | `release-target` |
| `releaseEvidence` | `true` |
| installed `mcp` | `2.0.0` (from hash-locked arm64 wheelhouse) |
| All 10 steps | exit 0 |

### x86_64 evidence content (verified)

| Field | Value |
|---|---|
| `artifactSha256` | `a33fdbeddb7bc1eceede374ca094c9d4014712a5706d53b840716183c4a64d77` |
| `architecture` / `platformMachine` | `x86_64` / `x86_64` |
| `pythonVersion` | `3.14.6` |
| `evidenceClass` | `release-target` |
| `releaseEvidence` | `true` |
| installed `mcp` | `2.0.0` (from hash-locked x86_64 wheelhouse) |
| All 10 steps | exit 0 |

Both evidence records identify the **same** final ZIP SHA. No architecture simulation was used.

Gate steps (both machines, all exit 0):  
`local-harness` · `wheelhouse-lock-generation` · `offline-release-install` · `staged-launcher-self-test` · `atomic-enable` · `protocol-roundtrip` · `fastmcp-stdio-roundtrip` · `verb-cycle-disable` · `verb-cycle-re-enable` · `verb-cycle-status`

---

## 5. Test totals and validator result

| Gate | Result |
|---|---|
| Source-tree / archive default suite | **275 tests OK** |
| Installed-layout suite (`run-tests.py --installed`) | **163 tests OK** (16 modules; 6 source-only modules not selected) |
| Exhaustive validator | **62 pass, 1 warning, 0 fail** (PowerShell absent on macOS — expected/acceptable) |
| Release verification | **349 manifest files**; portable plugin **19 agents, 31 skills, 0 executable workflows** |
| Clean-extraction lifecycle | ZIP + TAR fresh install, migration, rollback, hierarchy, status/doctor/uninstall — **PASSED** |

### Dependency-free suite (no MCP in venv; normal PATH; Python contamination vars stripped)

```
Ran 275 tests
OK (skipped=5)
```

**Known five skips (not failures):**

1. `yarn run test` — yarn not on PATH  
2. `yarn test` — yarn not on PATH  
3. `bun run test` — bun not on PATH  
4. `bun test` — bun not on PATH  
5. `test_mcp_sdk_registration_matches_locked_surface` — `"mcp package exists only inside the release venv on targets"`

---

## 6. Ambient MCP note (truthful)

During the Audit 9 session, `mcp==2.0.0` was installed into the MacBook system Python 3.14 site-packages via `uv pip install --system`. That ambient installation was **not** removed. A pre-existing Hermes venv also holds `mcp==1.28.1`.

**Correct statement for this release:**  
No production MCP was activated. Final gates did **not** rely on ambient installations; they installed `mcp==2.0.0` into isolated release venvs from the hash-locked native wheelhouses. Ambient MCP removal requires separate Founder authorization.

---

## 7. Preserved governance boundaries

This approved package preserves:

1. **Python is the authoritative deterministic engine.**  
2. **One thin JavaScript adapter** for hooks; **zero executable JavaScript workflows.**  
3. **Local-first operation** — no remote authority for control-plane decisions.  
4. **SHA-bound evidence** — computed vs declared hashes never conflated; B3/B4-style provenance.  
5. **Fail-closed enforcement** — guard allowlists, schema keyword coverage, safe_read TOCTOU protection, MCP non-authoritative stamping.  
6. **No self-granted approval** — Founder approval is external to the package; the control plane cannot authorize itself.

---

## 8. Explicit non-actions (out of scope of this close-out)

This close-out did **not**:

- Install or activate the release into any project or global environment  
- Delete previous environments or prior Audit 8b baselines  
- Remove ambient system or Hermes MCP installations  
- Rebuild artifacts (copy-only from verified temp paths)

Those require separate Founder authorization.

---

## 9. Ready state

Audit 9 is **closed**. The approved package at this release root is ready for:

- the next audit, or  
- a separately authorized installation.

**Approved baseline SHAs (repeat):**

- Full ZIP: `a33fdbeddb7bc1eceede374ca094c9d4014712a5706d53b840716183c4a64d77`  
- Full TAR.GZ: `acd4789da9b978dd069f044d0b69110cd6a5e5ec6e6ba540ada09b1489d9d335`  
- Portable plugin: `c34cd6ea63b89c81fdd8449ba918866a42f176bcbeb47fedad769f4e5803f98e`  
