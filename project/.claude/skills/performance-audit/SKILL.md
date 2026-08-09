---
name: performance-audit
description: Diagnose performance with measurements, isolate bottlenecks, propose bounded optimizations, and require before/after evidence.
argument-hint: "<route, service, command, or workload>"
disable-model-invocation: true
---

# Evidence-based performance audit

1. Define workload, environment, data size, concurrency, latency/throughput objective, and user-visible symptom.
2. Establish a reproducible baseline. Record command/tool, sample count, warmup, median/tail values, resource use, and variance.
3. Trace the critical path across client, network, server, database, queues, external providers, serialization, rendering, and caching.
4. Rank suspected bottlenecks by evidence and expected impact. Avoid optimizing code that is not on the measured path.
5. Propose the smallest changes with tradeoffs: correctness, complexity, cache invalidation, cost, and observability.
6. Re-measure with the same workload. Report absolute and percentage change plus confidence and regressions.

Do not claim improvement from code inspection alone. Preserve data truth and failure semantics; faster incorrect state is not an optimization.
