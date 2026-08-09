---
name: path-audit
description: Trace a file, symbol, route, event, or configuration value through definitions, callers, tests, build output, and runtime state.
argument-hint: "<path|symbol|route|config key>"
---

# Path and symbol audit

Locate the target definition, exports, imports, callers, writers, readers, tests, mocks, generated outputs, feature flags, and deployment/config references. Follow aliases and re-exports. Identify dead paths, duplicate implementations, and documentation that points to non-existent files.

Return a compact graph:
`source → transformation → persistence/transport → projection → UI/consumer → verification`.

For configuration, show default, override hierarchy, environment exposure, and failure behavior. For state, distinguish authoritative source from cache or projection. Cite exact paths and line ranges. Do not infer runtime activation from source presence.
