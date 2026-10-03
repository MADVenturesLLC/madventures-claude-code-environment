# MADVentures Claude Code Environment

**Version:** 4.4.2 (Founder-approved 2026-10-03)  
**Audit 9 status:** prior approved release baseline  
**Main since Audit 9:** post-release hardening (A10-A secret-pattern registry + deny-unknown baseline, A10-C runtime-state enforcement, A10-D schema extras + tier classifier, lean CI gates, env-identity statusline, release build-tooling fixes), packaged as 4.4.2 with a **Founder-approved** release record — see the "Release status" note below.

## Previously approved artifact SHAs (Audit 9)

| Artifact | SHA-256 |
|---|---|
| Full ZIP | `a33fdbeddb7bc1eceede374ca094c9d4014712a5706d53b840716183c4a64d77` |
| Full TAR.GZ | `acd4789da9b978dd069f044d0b69110cd6a5e5ec6e6ba540ada09b1489d9d335` |
| Portable plugin | `c34cd6ea63b89c81fdd8449ba918866a42f176bcbeb47fedad769f4e5803f98e` |

## Layout

- Repository root = the environment source tree for v4.4.2 (Founder-approved 2026-10-03; see "Release status" below)
- `releases/Audit9-v4.4.1-20260809/` = permanent Audit 9 release record, artifacts, merged wheelhouse, and native gate evidence

See `releases/Audit9-v4.4.1-20260809/AUDIT9_RELEASE_RECORD.md` for Founder approval, test totals, and governance boundaries.

## Release status

The current **Founder-approved installable artifacts are the v4.4.2 three**:

| Artifact | SHA-256 |
|---|---|
| Full ZIP | `121723bd2b9ae4bd3e20a79666e4504980a42ec6861df1541ce2d241f8526f55` |
| Full TAR.GZ | `af8bfd665046d4626fe0c534c81e594906d24326e2d9defa2c713aa63a3f8dd3` |
| Portable plugin | `e2c3d5c459a7e96792e0bd5c7aeec4a30d06a1dd7aacd9be043262bb3dd68326` |

The record at `releases/v4.4.2-20261003/RELEASE_RECORD.md` is **Founder-approved (2026-10-03)** with all Audit 9 gate classes re-run and passed for this cut: native arm64 and x86_64 target gates (one host per architecture, pinned via the shared constraints file), the merged wheelhouse rebuild, and the MCP release-install re-proof on both architectures. A byte-exact custody copy of the approved record is preserved at `releases/v4.4.2-20261003/evidence/founder-approval/`. The Audit 9 artifact set above remains the prior approved baseline. A fresh clone of `main` is **not** an approved artifact; installation of v4.4.2 is a separately authorized act.

## Install

Installation requires separate Founder authorization. Do not treat clone as an automatic install into a project or global environment.

## Governance (locked)

- Python is the authoritative deterministic engine
- One thin JavaScript hook adapter; zero executable JavaScript workflows
- Local-first, SHA-bound evidence, fail-closed enforcement
- No self-granted approval
