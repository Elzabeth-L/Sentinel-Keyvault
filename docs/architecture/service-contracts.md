# Service Contracts

## Common Contract

All services expose:

- `GET /health/live`
- `GET /health/ready`
- `GET /version`
- versioned business APIs under `/api/v1`
- RFC 9457-compatible `application/problem+json` errors
- W3C `traceparent` propagation and `X-Correlation-ID`
- idempotency via `Idempotency-Key` on command endpoints

No service trusts tenant IDs supplied only in a path, body, or header. The authenticated
tenant claim is resolved to an internal tenant ID and compared with requested scope.

## Identity Service

**Owns:** tenant, user, membership, role, permission, onboarding state.

**Commands**

- Synchronize authenticated user
- Invite/disable membership
- Assign/revoke role
- Register customer automation identity metadata

**Queries**

- Current profile, roles, effective permissions
- Tenant onboarding and consent status

**Publishes**

- `identity.tenant-onboarded.v1`
- `identity.user-synchronized.v1`
- `identity.role-assignment-changed.v1`

**Consumes**

- None for core authorization; it must fail closed if dependencies are unavailable.

The service validates Entra access tokens locally using cached OpenID metadata/JWKS.
It does not call Microsoft Graph on every request.

## Inventory Service

**Owns:** registered subscriptions, resources, discovery jobs, snapshots.

**Commands**

- Register/unregister subscription
- Start full or incremental discovery
- Refresh one resource

**Queries**

- List/filter resources
- Get resource details
- List subscriptions and resource groups

**Publishes**

- `inventory.sync-requested.v1`
- `inventory.resource-upserted.v1`
- `inventory.resource-missing.v1`
- `inventory.sync-completed.v1`
- `inventory.sync-failed.v1`

**Consumes**

- `identity.tenant-onboarded.v1`

ARG is used for broad discovery. ARM `GET` calls enrich fields unavailable in ARG.
Azure SDK calls use bounded concurrency, retry with jitter, ARM throttling awareness,
and per-tenant circuit breakers.

## Relationship Service

**Owns:** typed edges, extraction runs, graph snapshots, traversal projections.

**Commands**

- Rebuild relationships for resource/snapshot
- Generate bounded graph snapshot

**Queries**

- Direct relationships
- Upstream/downstream graph traversal
- Impact subgraph by resource and maximum depth

**Publishes**

- `relationships.edge-upserted.v1`
- `relationships.graph-snapshot-created.v1`
- `relationships.extraction-completed.v1`

**Consumes**

- `inventory.resource-upserted.v1`
- `inventory.resource-missing.v1`
- `inventory.sync-completed.v1`

Extractors are versioned plugins selected by Azure resource type. Unknown resource
types remain valid inventory nodes without fabricated edges.

## Change Intelligence Service

**Owns:** change assessments, deterministic rule sets, findings, impact reports.

**Commands**

- Create assessment
- Reassess expired/stale assessment
- Cancel assessment

**Queries**

- Assessment status and report
- Risk summary and findings

**Publishes**

- `intelligence.assessment-requested.v1`
- `intelligence.assessment-completed.v1`
- `intelligence.assessment-failed.v1`

**Consumes**

- Relationship graph snapshot availability
- Inventory lifecycle events for assessment invalidation

Risk is a deterministic result of action hazard, resource criticality, dependency
blast radius, environment, recoverability, maintenance window, and policy overrides.
The service returns both a numeric score (0-100) and label:

- `LOW`: 0-29
- `MEDIUM`: 30-69
- `HIGH`: 70-100

Rules and thresholds are versioned. Findings include evidence and remediation, not
only a score.

## Operations Service

**Owns:** operation intent, approval workflow, execution attempts, idempotency state.

**Commands**

- Create operation from a valid assessment
- Approve/reject
- Execute/cancel/retry

**Queries**

- Operation state, timeline, result
- Pending approvals
- Supported action catalog

**Publishes**

- `operations.created.v1`
- `operations.approval-requested.v1`
- `operations.approved.v1`
- `operations.started.v1`
- `operations.succeeded.v1`
- `operations.failed.v1`

**Consumes**

- `intelligence.assessment-completed.v1`

Executors implement an explicit allow-list. Each action defines input schema,
preconditions, required Azure permissions, timeout, retry semantics, compensability,
and verification. There is no arbitrary ARM method/path or shell execution facility.

Initial action catalog:

- VM start, stop, restart
- App Service scale and restart
- Kubernetes Deployment restart and scale
- supported Key Vault secret rotation workflow
- resource tag patch

Destructive actions such as Key Vault deletion remain analysis-only until recovery,
soft-delete/purge-protection checks, and approval policies are fully implemented.

## Audit Service

**Owns:** append-only audit logs, user/system activity events, export batches.

**Commands**

- Ingest signed internal audit event
- Create compliance export

**Queries**

- Search audit events
- Operation timeline
- Export status

**Publishes**

- `audit.export-completed.v1`
- `audit.integrity-check-failed.v1`

**Consumes**

- All business-domain events through a dedicated subscription

Business services write a local outbox entry in the same transaction as state changes.
The audit service is therefore not a synchronous availability dependency for normal
commands.

## Event Delivery Contract

- Azure Service Bus topics with one subscription per consumer.
- At-least-once delivery; consumers must be idempotent.
- CloudEvents 1.0 envelope encoded as JSON.
- `event_id`, `event_type`, `subject`, `tenant_id`, `occurred_at`, `traceparent`,
  `producer`, `schema_version`, and `data`.
- Partition/session key is `tenant_id` when ordering is required.
- Inbox deduplication precedes side effects.
- Poison messages move to DLQ and create an operational alert.
- Breaking event changes require a new event type version.

