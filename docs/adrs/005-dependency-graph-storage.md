# ADR 005: Dependency Graph Storage

Status: Accepted

## Context

Dependency traversal is a flagship feature, but introducing a graph database adds an
additional persistence and operational platform before workload scale is known.

## Decision

Store canonical nodes in Inventory and typed adjacency edges in PostgreSQL. Use indexed
recursive CTEs and bounded graph snapshots. Measure depth, node count, latency, and
write volume before considering a dedicated graph store.

## Consequences

Phase 1 has fewer moving parts and transactional consistency. Complex graph algorithms
are limited; migration criteria must be based on measured production-like workloads.

