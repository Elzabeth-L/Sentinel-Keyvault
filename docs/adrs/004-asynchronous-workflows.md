# ADR 004: Asynchronous Workflows

Status: Accepted

## Context

Azure discovery, graph extraction, analysis, and operations can exceed HTTP timeouts
and encounter provider throttling or transient faults.

## Decision

Use Azure Service Bus Premium with CloudEvents, at-least-once delivery, duplicate
detection where useful, service-owned outbox/inbox records, dead-letter queues, and
idempotent workers. HTTP command endpoints persist intent and return `202`.

## Consequences

Work survives process restarts and scales independently. Clients must understand job
states, and event compatibility and poison-message operations require discipline.

