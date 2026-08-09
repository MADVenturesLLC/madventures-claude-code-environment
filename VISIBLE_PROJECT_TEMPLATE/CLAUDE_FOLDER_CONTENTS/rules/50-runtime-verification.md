---
paths:
  - "src/**"
  - "app/**"
  - "packages/**"
  - "services/**"
  - "tests/**"
  - "package.json"
  - "*.config.*"
---
# Runtime verification

Source presence is not runtime activation. Trace flags, configuration, persistence, queues, external calls, and deployment state. Run the real lint/typecheck/test/build/runtime gates and report exact commands. Do not weaken tests or infer production health from local success.
