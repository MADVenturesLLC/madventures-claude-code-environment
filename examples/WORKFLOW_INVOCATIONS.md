# Saved workflow invocation examples

These commands are JSON-oriented examples. Replace placeholders with exact repository evidence. Inspect the raw workflow script and its generated launch plan before the first run in any repository.

## Planning and analysis

```text
/founder-plan {"goal":"Implement the approved feature","scope":"app/components","acceptanceCriteria":["..."],"constraints":["..."]}
/founder-repository-audit {"scope":"current repository","question":"What blocks the next governed milestone?","axes":["architecture","security","governance","tests"]}
/founder-docs-drift {"scope":"README, runbooks, architecture docs, current code and tests"}
```

## Review and verification

```text
/founder-changed-files-review {"base":"BASE_SHA","head":"HEAD_SHA","maxFiles":12,"focus":["correctness","security","governance"]}
/founder-verify {"goal":"Verify Slice B","target":"HEAD_SHA","acceptanceCriteria":["..."],"checks":["lint","typecheck","unit","build"]}
/founder-test-gap-analysis {"target":"BASE_SHA...HEAD_SHA","acceptanceCriteria":["authorization failures are denied","audit events are durable"]}
/founder-tier2-evidence {"repository":"MADVenturesLLC/FounderOS","pr":195,"baseSha":"BASE_SHA","headSha":"HEAD_SHA","contract":"WF-13 / DEC-..."}
```

`founder-tier2-evidence` prepares an evidence pack. It does not replace the canonical edit-less `independent-reviewer` or issue a governed Tier-2 disposition.

## Specialist audits

```text
/founder-security-audit {"target":"authentication and approval execution paths","constraints":["no destructive tests"]}
/founder-performance-audit {"target":"Command Center route","workload":"initial load plus focus transition","environment":"local production build"}
/founder-incident-root-cause {"symptom":"runtime events stopped persisting after deployment","timeWindow":"2026-08-06T14:00Z/2026-08-06T16:00Z","evidence":["deployment SHA","logs","metrics"]}
/founder-ui-review {"surface":"Command Center","route":"/","references":["approved design specification"],"focus":"runtime truth, reduced motion, cinematic depth"}
/founder-release-readiness {"target":"FULL_SHA","environment":"production candidate","activationRequested":false}
```

## Intentionally mutating workflows

`founder-build` requires an explicit structured approval packet with an inspectable `approvalReference`. A plan file, an unreferenced prior chat approval, a bare boolean, or a technical review is not sufficient by itself.

```text
/founder-build {"goal":"Implement the approved approval-count correction","approvedPlan":"docs/plans/approval-count.md","founderApproved":true,"approvalReference":"Founder message 2026-08-06: approved this exact plan and scope","allowedScope":"app/components/approvals and tests only","acceptanceCriteria":["proposed/deferred only"],"verificationCommands":["npm test","npm run build"]}
/founder-fix-until-green {"command":"npm run typecheck","goal":"Restore the type gate","maxRounds":4,"noProgressLimit":2,"allowedScope":"src/ and tests/ only"}
```

Both mutating workflows prohibit commit, push, merge, deploy, activation, credential writes, protected-authority changes, and verification weakening. The other 12 workflows are evidence-only in intent, but workflow-spawned agents still run with edit acceptance; intent is not a hard read-only boundary.
