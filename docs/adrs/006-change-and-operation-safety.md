# ADR 006: Change and Operation Safety

Status: Accepted

## Context

An approval is unsafe if target state or requested parameters change after analysis.
An unrestricted cloud API proxy would make least privilege and risk reasoning
impossible.

## Decision

Bind approvals and execution to an immutable hash of action, parameters, target state,
inventory/graph snapshots, and rule-set version. Expose only versioned, typed,
allow-listed executors with explicit permissions, preconditions, verification, and
retry semantics.

## Consequences

Execution is explainable and governable. New actions require engineering and review;
Sentinel intentionally cannot execute arbitrary ARM requests or scripts.

