---
name: incident-response
description: Run a controlled, evidence-preserving incident process from containment through root cause, correction, verification, and post-incident learning.
argument-hint: "<incident or symptom>"
---

# FounderOS incident response

## Immediate priorities
1. Protect people, data, financial integrity, and evidence.
2. Pin the affected environment, service, version/SHA, time window, and observed impact.
3. Separate confirmed facts, hypotheses, and unknowns.
4. Use existing rollback, kill switch, or containment authority; do not invent production access or authorization.
5. Preserve logs, traces, configuration, deployment records, and operator actions before destructive cleanup.

## Investigation
Build a timestamped timeline. Compare application, infrastructure, dependency, database, queue, network, configuration, authorization, and observability hypotheses. Prefer reversible experiments. Do not run destructive tests against production or expose sensitive data in transcripts.

Use `/founder-incident-root-cause` when independent hypothesis lanes and a repeatable synthesis are valuable. The workflow is evidence-only in intent and cannot accept mid-run Founder sign-off; run containment, correction, and release as separate controlled stages.

## Correction and verification
Require a bounded approved correction, regression tests for the causal mechanism, real environment verification, rollback criteria, and an independent review. Do not call the incident resolved until the affected behavior and operational signals are verified in the relevant environment.

## Output
Return severity, impact, current state, timeline, confirmed/likely root cause, contributing conditions, containment, correction, verification, residual risk, follow-up owners, and evidence links. Keep the postmortem blameless and distinguish prevention from detection and recovery improvements.
