# V4.4.1 Delivery Correction

## Finding

The V4.4 package data was intact, but the delivery experience was not acceptable:

1. The primary repository template was stored under `project/.claude`, which Finder hides by default.
2. The package did not provide an obvious Finder-visible installer at its root.
3. The installer invoked the exhaustive release validator by default. That validator intentionally runs broad tests and can appear stalled during a normal installation.
4. Multiple similarly named V4.4 artifacts made it unclear which file was authoritative.

## Correction

V4.4.1 provides one clearly named complete release, a visible inspection mirror, top-level launchers, fast install-time validation, a complete file index, and both ZIP and TAR.GZ delivery formats.

## Authority

V4.4.1 supersedes V4.4 for packaging and installation. The underlying FounderOS engineering controls remain V4.4 architecture with a patch-level delivery correction.
