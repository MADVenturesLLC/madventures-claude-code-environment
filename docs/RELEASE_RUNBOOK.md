# Release runbook — MADVentures Claude Code Environment

How a release of this environment is cut, step by step. This is the sequence
proven by the v4.4.2 cut (2026-10-03); follow it in order — each rule below
exists because the naive version of it failed at least once.

## Invariants (do not negotiate)

1. **The Founder's approval is external and separate.** The record is filed as
   `PREPARED — PENDING FOUNDER APPROVAL`. Agents never edit the Status line and
   never self-approve. Approval is the Founder's own edit of the record.
2. **Native target gates run one host per architecture, never simulated.** The
   gate records `platform.machine()` of the running interpreter; the release
   standard forbids architecture simulation — no Rosetta, no cross-arch runners,
   no caller-supplied arch strings. arm64 → Apple-Silicon machine; x86_64 →
   Intel iMac.
3. **The final build comes from an unchanged tree.** No edits while the build
   runs; commit the frozen outputs deliberately afterwards.
4. **Builds, suites, and gates run on the clean auth lane.** Without it the
   subscription-first suites fail closed on the host's global proxy lane.
   Strip the full watched set (API, subscription, cloud-route, and routing
   variables — the fail-closed list in `docs/AUTHENTICATION_AND_BILLING.md`),
   not just a couple of names:

   ```bash
   env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN \
       -u CLAUDE_CODE_OAUTH_TOKEN -u CLAUDE_CODE_OAUTH_REFRESH_TOKEN -u CLAUDE_CODE_OAUTH_SCOPES \
       -u CLAUDE_CODE_USE_BEDROCK -u CLAUDE_CODE_USE_VERTEX -u CLAUDE_CODE_USE_FOUNDRY -u CLAUDE_CODE_USE_ANTHROPIC_AWS \
       -u ANTHROPIC_BASE_URL -u ANTHROPIC_BEDROCK_BASE_URL -u ANTHROPIC_VERTEX_BASE_URL -u ANTHROPIC_FOUNDRY_BASE_URL -u ANTHROPIC_CUSTOM_HEADERS \
     CLAUDE_CONFIG_DIR=$HOME/.claude-control-plane <command>
   ```

   On hosts whose normal shell carries a proxy lane, a small wrapper that
   exports the config dir and unsets this set before exec'ing the command is
   the durable shape.

5. **One canonical runner per job.** When a paste-ready command is superseded,
   say so and delete the stale copy — a stale paste once hard-reset a clone to a
   SHA from before the tooling existed and wiped local uncommitted edits.

## Preconditions

- Clone: `~/MADVenturesOPs/madventures-claude-code-environment` (origin:
  `MADVenturesLLC/madventures-claude-code-environment`).
- arm64 host: Apple-Silicon machine, clean lane configured
  (`~/.claude-control-plane`, one-time `claude auth login` inside it).
- x86_64 host: Intel iMac, repo cloned, PyPI reachable, CPython 3.14.x.
- Founder authorization for the cut — a release cut is a Founder-authorized act.

## 1. Version sweep

```bash
python3 scripts/bump-version.py --list          # sweep set + current VERSION
python3 scripts/bump-version.py X.Y.Z           # dry run: per-file replacement counts
python3 scripts/bump-version.py X.Y.Z --apply   # write the replacements
```

Then by hand: the `CHANGELOG.md` top section (curated — never auto-swept), and
the canonical regeneration order (index → manifest → validate, §2). The
`test_version_consistency` tripwire must pass; it fails loudly on a partial bump.

Generated files (`MANIFEST.json`, `PACKAGE_CONTENTS.txt`, `SHA256SUMS.txt`,
`docs/VALIDATION_REPORT.md`) are deliberately excluded from the sweep — they are
regenerated, not edited.

## 2. Freeze and build

Build from the frozen tree, on the clean lane, editing nothing while it runs:

```bash
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN \
    -u CLAUDE_CODE_OAUTH_TOKEN -u CLAUDE_CODE_OAUTH_REFRESH_TOKEN -u CLAUDE_CODE_OAUTH_SCOPES \
    -u CLAUDE_CODE_USE_BEDROCK -u CLAUDE_CODE_USE_VERTEX -u CLAUDE_CODE_USE_FOUNDRY -u CLAUDE_CODE_USE_ANTHROPIC_AWS \
    -u ANTHROPIC_BASE_URL -u ANTHROPIC_BEDROCK_BASE_URL -u ANTHROPIC_VERTEX_BASE_URL -u ANTHROPIC_FOUNDRY_BASE_URL -u ANTHROPIC_CUSTOM_HEADERS \
  CLAUDE_CONFIG_DIR=$HOME/.claude-control-plane \
  bash scripts/build-release.sh <zip> <plugin-zip> <tar.gz>
```

(≈8–12 min; runs the source suite, validator, both archives' lifecycle gates,
and plugin verification.) On exit 0, commit the files it regenerated as the
freeze commit. Copy artifacts + `.sha256` sidecars out of scratch **immediately**
into `releases/<version>-<date>/artifacts/`, re-hashing the copies to prove
equality.

## 3. File the record and mirror

Write `releases/<version>-<date>/RELEASE_RECORD.md`:

- status `PREPARED — PENDING FOUNDER APPROVAL`; approval section `NOT YET ISSUED`;
- §2: proposed artifact SHA-256 values;
- §3: source commit identity;
- §4: per-gate evidence — or an explicit open-gates list; never hide an open gate;
- §8: the approval procedure + hash-ripple note (approval edits the record, so
  the release-root `SHA256SUMS.txt` must be regenerated after approval).

Generate the release-root `SHA256SUMS.txt` (over the folder minus itself) and
mirror byte-identical to `~/MADVenturesOPs/releases/<same-name>/`; verify both
with `shasum -a 256 -c`.

## 4. Native target gates

One host per architecture. The canonical runner ships in the repo
(`scripts/run-native-target-gate.sh`):

```bash
# on the ARM64 host:
bash scripts/run-native-target-gate.sh --arch arm64 \
  --release-dir releases/<version>-<date> --branch <gate-branch> --commit-and-push

# on the x86_64 host — same command, different arch:
bash scripts/run-native-target-gate.sh --arch x86_64 \
  --release-dir releases/<version>-<date> --branch <gate-branch> --commit-and-push
```

The runner refuses (exit 2) on the wrong hardware, under Rosetta, or on a
non-macOS host (the contract is macOS `cp314` wheels); refuses (exit 3) a clone
with uncommitted changes or a local gate branch carrying unpushed commits;
refuses (exit 6) a non-CPython-3.14 interpreter or an unsafe `--home`/`--output`
target (`--home` must stay under `$HOME/.hermes/cache/scratch`; `--output` must
be a `.json` path inside the repository). It fetches the gate branch BEFORE
resolving prerequisites — so `--branch` can bootstrap a branch that does not
exist locally yet; never a hard reset — wires the constraints file, and
prints/commits the evidence JSON. Use `--dry-run` to see the resolved plan
without running.

**Constraint pinning.** The constraints file
(`releases/<version>-<date>/evidence/wheelhouse-constraints-cp314-macos.txt`)
pins the exact distribution set for both gates. Build it from the first gate's
resolved lock: copy each `name==version` line from
`requirements-cp314-macos-<arch>.lock`; where a pinned distribution has no wheel
for the second architecture (e.g. `cryptography` 50.0.2 ships arm64-only for
macOS), step back to the newest release that ships wheels for BOTH architectures
and pin that. Why: the deterministic wheelhouse merge fails closed on
cross-target divergence, so an unpinned second gate can silently resolve a
different set.

**Cross-target agreement check** (cheap, proven): rebuild the second gate's lock
independently on the first host (`mcp-wheelhouse.py --wheelhouse <dir> --arch
<arch> --no-download`) and `shasum -a 256` it — it must equal the lock recorded
in the second host's evidence JSON. That proves both targets resolved the
identical distribution set without shipping the whole wheelhouse across.

## 5. Wheelhouse merge

```bash
python3 scripts/mcp-wheelhouse.py merge \
  --input <arm64-wheelhouse>:arm64 \
  --input <x86_64-wheelhouse>:x86_64 \
  --output releases/<version>-<date>/wheelhouse/merged
```

Preserve per-arch manifests under `wheelhouse/{arm64,x86_64}/`; update the
record (§1/§4 tables) with the merged manifest + both locks; regenerate the
release-root `SHA256SUMS.txt`; mirror and verify again.

## 6. Founder approval → carry-in (one pass)

1. The Founder edits the record's Status line — his edit may land in either copy
   (the repo record or the `~/MADVenturesOPs/releases/…` mirror); `diff` the two
   to locate the signed revision.
2. Preserve his byte-exact file as custody inside the release root:
   `evidence/founder-approval/<record>.as-approved-<date>.md` + a `.sha256`
   sidecar; re-hash to prove the copies match.
3. Carry the approval into the canonical record in ONE pass: Status line
   verbatim, §2 `Proposed` → `Approved`, every `NOT YET ISSUED` becomes the
   approval with its date, and any forward-looking footnote that has come true
   (e.g. "will become canonical once the release PR lands") is rewritten to the
   fact.
4. Regenerate the release-root `SHA256SUMS.txt` (the approved edit changed the
   record's hash — §8's ripple), mirror, verify, commit, open the
   record-approval PR.

## 7. Install (separately authorized)

Installing is a separate act from cutting. Install **from the approved
artifact**: verify the ZIP's SHA-256 against the record, unpack it, and run
*its* `scripts/install.sh` — never the working clone, so the installed bytes are
the approved bytes. For an existing seat, `update` with the seat's existing
profile (`.claude/INSTALLATION_STATE.json` → `--profile …`) plus
`--install-python-control-plane`; `--dry-run` first prints the affected layers
and backup path. Verify afterwards: `INSTALLATION_STATE.json`
version/operation/backup; the installed CLI and the seat control-plane
versions; `madclaude auth-check` → `safe: true` on the clean lane. (Doctor's
`clean: false` is the repo's dirty worktree, not an install defect.)

## Pitfalls

- **Dirty-clone guard exists because of a real incident.** A stale paste ran
  `git reset --hard <sha>` in the iMac clone and wiped local uncommitted edits.
  Never put a hard reset in a paste destined for another machine; the runner
  refuses dirty clones for exactly this reason.
- **Heredoc trap.** Shell heredocs containing backticks can silently produce
  empty files. Write to a tempfile with a quoted delimiter, move into place, and
  verify `wc -c` + `tail` after any sensitive write.
- **`releases/` is excluded from the delivery index and manifest**, so release
  records need no regeneration — but any change to shipped files (docs,
  scripts, `.github`) does; regenerate index → manifest → validate in the same
  commit or `quick-validate` (a CI merge gate) fails.
- **A merge-authorization naming an older head is void.** Any rebase or
  force-push moves the head — hand the Founder a fresh authorization block for
  the new head.
- **Release dirs are history.** The 4.4.2 cut's runner
  (`releases/v4.4.2-20261003/RUN-X86_64-GATE-ON-IMAC.sh`) stays in place as
  part of that approved release's record; future cuts use
  `scripts/run-native-target-gate.sh`. Never edit or delete files inside an
  approved release root.
