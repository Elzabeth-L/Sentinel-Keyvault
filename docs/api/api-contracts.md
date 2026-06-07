# API Contracts

This document defines the Phase 1 HTTP surface. Formal OpenAPI documents will be
generated service-by-service during implementation and validated in CI.

## Conventions

Base path: `/api/v1`

Required request headers:

| Header | Requirement |
|---|---|
| `Authorization: Bearer <token>` | All business endpoints |
| `X-Correlation-ID` | Optional from client; generated if absent |
| `Idempotency-Key` | Required for commands that create or execute work |
| `If-Match` | Required for concurrency-sensitive mutations |

Collection responses use cursor pagination:

```json
{
  "items": [],
  "page": {
    "next_cursor": null,
    "limit": 50
  }
}
```

Asynchronous commands return `202 Accepted` with a durable job/operation resource and
`Location` header. Resource creation that completes transactionally returns `201`.

Errors use:

```json
{
  "type": "https://sentinel.example/problems/forbidden",
  "title": "Permission denied",
  "status": 403,
  "detail": "The actor lacks operations.execute.",
  "instance": "/api/v1/operations/019...",
  "code": "SENTINEL_AUTHZ_DENIED",
  "correlation_id": "019..."
}
```

## Identity Service

### `GET /auth/login?tenant={entraTenantId}`

Creates PKCE state/verifier cookies and returns the Microsoft authorization URL. The
tenant ID is optional; omitting it uses the multi-tenant `common` authority.
The Entra application must accept organizational and personal Microsoft accounts.
Personal users do not need an invitation to an external organization; Azure RBAC
determines which subscriptions and resources are returned.

### `GET /auth/callback`

Microsoft redirect target. Exchanges the code, validates the ID token, synchronizes
tenant/user/RBAC state, encrypts the refresh token, and issues the HTTP-only Sentinel
session.

### `POST /auth/logout`

Expires the Sentinel session cookie.

### `GET /auth/profile`

Returns synchronized user, active tenant, membership state, and effective permissions.

### `GET /auth/roles`

Permission: `identity.roles.read`.

### `GET /auth/permissions`

Returns the permission catalog or current effective permissions.

### `POST /tenants/onboarding`

Starts tenant onboarding and returns admin-consent requirements. Permission:
`tenant.onboarding.manage`.

## Inventory Service

### `GET /inventory/resources`

Filters: `subscription_id`, `resource_group`, `resource_type`, `location`, `state`,
`tag[key]`, `search`, `cursor`, `limit`.

### `GET /inventory/resources/{resource_id}`

The route identifier is Sentinel's UUID, not a raw ARM ID.

### `GET /inventory/subscriptions`

Returns only subscriptions registered and visible to the actor.

### `POST /inventory/subscriptions/discover`

Uses the authenticated customer's configured automation identity to enumerate
accessible subscriptions and upsert the tenant-scoped registration projection.
Permission: `inventory.sync.execute`.

### `GET /inventory/resource-groups`

Aggregated from the current inventory snapshot.

### `POST /inventory/sync-jobs`

```json
{
  "scope": {
    "subscription_ids": ["00000000-0000-0000-0000-000000000000"]
  },
  "mode": "incremental"
}
```

Returns `202` and a sync job. Permission: `inventory.sync.execute`.

## Relationship Service

### `GET /relationships`

Filters: `resource_id`, `direction`, `relationship_type`, `minimum_confidence`.

### `POST /relationships/graph-queries`

```json
{
  "root_resource_id": "019...",
  "direction": "downstream",
  "max_depth": 4,
  "max_nodes": 500,
  "relationship_types": []
}
```

Returns an inline graph when bounded work completes quickly, otherwise `202` and a
graph snapshot job.

### `POST /relationships/graph`

Compatibility alias for `/relationships/graph-queries`. It accepts the same bounded
query and never permits an unbounded full-tenant graph response.

### `GET /relationships/graphs/{graph_snapshot_id}`

Returns React Flow-compatible nodes/edges plus canonical graph metadata. UI-specific
position is optional and never part of dependency semantics.

## Change Intelligence Service

### `POST /analysis/assessments`

```json
{
  "action_type": "azure.keyvault.delete",
  "target_resource_id": "019...",
  "parameters": {},
  "requested_execution_window": {
    "starts_at": "2026-06-06T20:00:00Z",
    "ends_at": "2026-06-06T22:00:00Z"
  }
}
```

Returns `202`.

### `GET /analysis/assessments/{assessment_id}`

Returns state, score, label, findings, blast radius, evidence versions, approval
requirement, expiration, and canonical input hash.

### `POST /analysis/impact`

Compatibility endpoint that creates an assessment and returns `202`. It will not
perform an untracked synchronous analysis.

### `POST /analysis/risk`

Same lifecycle as impact analysis; both are views of one assessment aggregate.

## Operations Service

### `GET /operations/action-catalog`

Returns supported operations, parameter schemas, required permissions, and whether
the action is enabled for the tenant.

### `POST /operations`

```json
{
  "assessment_id": "019...",
  "assessment_input_hash": "sha256:...",
  "reason": "Approved maintenance CHG001234"
}
```

Creates an operation only from a completed, unexpired assessment.

### `POST /operations/{operation_id}/approvals`

```json
{
  "decision": "approve",
  "comment": "Validated maintenance window and recovery plan."
}
```

Self-approval is denied when separation-of-duties policy applies.

### `POST /operations/{operation_id}/execute`

Requires an approved and unchanged assessment, `Idempotency-Key`, permission
`operations.execute`, and satisfied Azure preconditions. Returns `202`.

### `POST /operations/execute`

Compatibility command accepting `operation_id` and `assessment_input_hash`. It applies
the same authorization, idempotency, staleness, and approval checks as the
operation-resource route and returns `202`.

### `GET /operations/{operation_id}`

Returns the operation state machine, attempts, approval summary, and sanitized result.

## Audit Service

### `GET /audit/events`

Filters: time range, actor, action, entity type/ID, outcome, correlation ID. Audit
search permissions are separate from operation permissions.

### `GET /audit/operations/{operation_id}`

Returns a merged immutable timeline for assessment, approval, and execution.

### `POST /audit/exports`

Creates an asynchronous compliance export to an authorized storage destination.

## Authorization Permission Names

Permission strings are stable contracts:

```text
tenant.onboarding.manage
identity.roles.read
identity.roles.assign
inventory.resources.read
inventory.sync.execute
relationships.read
analysis.create
analysis.read
operations.create
operations.approve
operations.execute
operations.cancel
audit.read
audit.export
settings.manage
```

Default roles are `TenantAdministrator`, `PlatformEngineer`, `ChangeApprover`,
`Operator`, `Auditor`, and `Reader`. Roles are permission bundles; code authorizes
permissions, not role names.
