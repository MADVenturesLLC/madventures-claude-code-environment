---
name: security-audit
description: Perform a read-only threat-driven security audit of a pinned scope and return exploitable findings, evidence, and remediation priorities.
argument-hint: "<scope, sha, or threat boundary>"
disable-model-invocation: true
---

# Threat-driven security audit

Pin the repository state and define assets, trust boundaries, identities, data sensitivity, external systems, and attacker capabilities.

Review authentication, authorization, tenant isolation, input validation, injection, SSRF, file/path handling, secrets, cryptography, session/token lifecycle, supply chain, logging/privacy, rate limiting, webhooks, database policy, CI/CD, and privileged operations as applicable.

For each finding provide:
- severity and confidence;
- affected path/line and reachable attack path;
- prerequisites;
- concrete impact;
- evidence or safe proof-of-concept reasoning;
- smallest robust remediation;
- regression test or verification.

Distinguish exploitable defects from defense-in-depth improvements and speculative concerns. Do not expose real secrets, run destructive payloads, alter production, or weaken controls to prove a point. Escalate governance-impacting remediation to the Founder.

End with a prioritized remediation plan, positive controls verified, and explicit coverage gaps.
