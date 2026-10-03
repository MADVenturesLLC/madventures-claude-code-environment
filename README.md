# MADVentures Claude Code Environment

**Version:** 4.4.2 (release candidate — record filed, pending Founder approval)  
**Audit 9 status:** Founder-approved release baseline  
**Main since Audit 9:** post-release hardening (A10-A secret-pattern registry + deny-unknown baseline, A10-C runtime-state enforcement, A10-D schema extras + tier classifier, lean CI gates, env-identity statusline, release build-tooling fixes), packaged as the 4.4.2 candidate with a filed release record **pending Founder approval** — see the "Release status" note below.

## Approved artifact SHAs (Audit 9)

| Artifact | SHA-256 |
|---|---|
| Full ZIP | `a33fdbeddb7bc1eceede374ca094c9d4014712a5706d53b840716183c4a64d77` |
| Full TAR.GZ | `acd4789da9b978dd069f044d0b69110cd6a5e5ec6e6ba540ada09b1489d9d335` |
| Portable plugin | `c34cd6ea63b89c81fdd8449ba918866a42f176bcbeb47fedad769f4e5803f98e` |

## Layout

- Repository root = the environment source tree for v4.4.2 (release candidate; the last Founder-approved installable baseline is the Audit 9 artifact set below)
- `releases/Audit9-v4.4.1-20260809/` = permanent Audit 9 release record, artifacts, merged wheelhouse, and native gate evidence

See `releases/Audit9-v4.4.1-20260809/AUDIT9_RELEASE_RECORD.md` for Founder approval, test totals, and governance boundaries.

## Release status

The **Founder-approved installable artifacts remain the Audit 9 three** (SHAs above). The 4.4.2 candidate is **filed but not approved**: the release record at `releases/v4.4.2-20261003/RELEASE_RECORD.md` and its artifact set are prepared and pending Founder approval; the native arm64 target gate has been re-run and passed, the native x86_64 gate is pending the Intel iMac run. A fresh clone of `main` is **not** an approved artifact. Approval of the record (and completion of the open gates it lists) is the pending Founder action.

## Install

Installation requires separate Founder authorization. Do not treat clone as an automatic install into a project or global environment.

## Governance (locked)

- Python is the authoritative deterministic engine
- One thin JavaScript hook adapter; zero executable JavaScript workflows
- Local-first, SHA-bound evidence, fail-closed enforcement
- No self-granted approval
