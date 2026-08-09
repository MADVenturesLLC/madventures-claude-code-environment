---
name: context-handoff
description: Compress a long build or review into a structured context packet optimized for another Claude Code session or external model.
argument-hint: "[target agent/model and token budget]"
---

# Context handoff packet

Prioritize irreversible facts and current evidence over narrative. Use this order:

1. **Goal / done condition**
2. **Authority and approvals**
3. **Pinned repository state**
4. **Current architecture facts**
5. **Changes and rationale**
6. **Verification evidence**
7. **Findings and dispositions**
8. **Open risks/unknowns**
9. **Exact next action**
10. **Files to read first**

Keep direct quotes minimal. Preserve exact identifiers, names, SHAs, commands, dates, and state labels. Strip secrets and irrelevant conversation. Mark what must be re-verified after resume or compaction.
