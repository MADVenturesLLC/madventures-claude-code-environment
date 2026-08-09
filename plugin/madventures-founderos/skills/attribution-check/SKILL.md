---
name: attribution-check
description: Verify that repository, commit, PR, model, agent, reviewer, and evidence attribution is accurate before publishing a status or review.
argument-hint: "<status, review, or artifact>"
---

# Attribution integrity check

Verify:
- repository and organization;
- branch, PR number, base/head SHA, and timestamp;
- author/builder versus reviewer roles;
- model/agent identity and declared effort where material;
- commands actually run versus suggested;
- local evidence versus remote/production evidence;
- ownership of decisions and Founder approval.

Flag ambiguous phrases such as “we deployed,” “approved,” “live,” “ledger-backed,” or “verified” when the underlying actor or evidence is missing. Correct the statement to the strongest state actually proven. Never attribute another agent’s finding, code, or approval to the current agent.
