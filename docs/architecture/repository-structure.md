# Repository Structure

## Top Level

```text
Sentinel/
  apps/
    web/
    identity-service/
    inventory-service/
    relationship-service/
    change-intelligence-service/
    operations-service/
    audit-service/
    migration/
  packages/
    python/sentinel_common/
  contracts/
    openapi/
    asyncapi/
    schemas/
  database/
    alembic.ini
    migrations/
    schema.sql
  deploy/
    compose/
    kubernetes/
  docs/
    adrs/
    api/
    architecture/
    deployment/
    diagrams/
    runbooks/
  tests/
    api/
    integration/
    security/
    unit/
  tools/
```

## Service Structure

Python services are independently deployable bounded contexts. Their implementation
should converge on:

```text
service/
  Dockerfile
  src/<service_package>/
    domain/
    application/
    infrastructure/
    presentation/
    bootstrap/
  tests/
```

The current MVP has flatter packages in several services. Refactor toward these layers
only when implementation complexity warrants it; do not perform structural churn
without behavior or ownership benefit.

## Shared Packages

`packages/python/sentinel_common` contains technical platform primitives:

- configuration
- authentication context
- database unit of work
- health and correlation middleware
- audit events and outbox relay
- Key Vault secret provider

It must not become a shared domain-model or cross-service repository package.

## Contracts

OpenAPI and event schemas are source-controlled compatibility contracts. Breaking
changes require versioning. Services consume another bounded context through APIs,
events, projections, or generated exports, never direct cross-schema queries.

## Database Ownership

PostgreSQL uses service-owned schemas:

```text
identity
inventory
relationships
intelligence
operations
audit
platform
```

The migration image under `apps/migration` contains Alembic and the database migration
history. Runtime service identities receive only the DML rights needed by their
service.

## Deployment Ownership

`deploy/kubernetes` is the AKS deployment source of truth. It contains
ordered plain manifests for:

- namespaces and resource governance
- Workload Identity service accounts
- Key Vault CSI integration
- one-shot Alembic database migration Job
- web, APIs, workers, and ClusterIP Services
- NetworkPolicy
- Nginx gateway exposed through a Kubernetes LoadBalancer Service

Each service retains independent image, scaling, identity, resource, and rollout
settings. Environment-specific Azure values are explicit `REPLACE_ME_*` placeholders.
Application secrets are never committed to these manifests.

The database migration image remains under `apps/migration`. The current AKS
deployment runs it through `04-database-migration-job.yaml`, which reads the database
URL from the Key Vault-synchronized Identity runtime secret. The Job is recreated for
each schema release and must complete before application rollout.

`deploy/compose` remains the local/VM transition configuration and is not the AKS
source of truth.
