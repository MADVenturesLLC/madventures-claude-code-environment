# MADVentures Claude Code Environment

**Version:** 4.4.1  
**Audit 9 status:** Founder-approved release baseline  

## Approved artifact SHAs (Audit 9)

| Artifact | SHA-256 |
|---|---|
| Full ZIP | `a33fdbeddb7bc1eceede374ca094c9d4014712a5706d53b840716183c4a64d77` |
| Full TAR.GZ | `acd4789da9b978dd069f044d0b69110cd6a5e5ec6e6ba540ada09b1489d9d335` |
| Portable plugin | `c34cd6ea63b89c81fdd8449ba918866a42f176bcbeb47fedad769f4e5803f98e` |

## Layout

- Repository root = unpacked approved environment package (v4.4.1)
- `releases/Audit9-v4.4.1-20260809/` = permanent Audit 9 release record, artifacts, merged wheelhouse, and native gate evidence

See `releases/Audit9-v4.4.1-20260809/AUDIT9_RELEASE_RECORD.md` for Founder approval, test totals, and governance boundaries.

## Install

Installation requires separate Founder authorization. Do not treat clone as an automatic install into a project or global environment.

## Governance (locked)

- Python is the authoritative deterministic engine
- One thin JavaScript hook adapter; zero executable JavaScript workflows
- Local-first, SHA-bound evidence, fail-closed enforcement
- No self-granted approval
