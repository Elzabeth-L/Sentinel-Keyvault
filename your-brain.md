# Sentinel Continuity File

Last updated: 2026-06-07

## Purpose

This file is the durable context for future Codex and engineering sessions. Read this
file, `README.md`, and the linked architecture documents before changing Sentinel.

## Business Context

Sentinel is a multi-tenant Azure Change Intelligence Platform. Its purpose is to help
cloud operators understand and govern operational change before execution:

1. Discover Azure resources in customer tenants.
2. Derive resource and runtime dependencies.
3. Assess the impact and risk of a proposed operation.
4. Require approval according to risk and tenant policy.
5. Execute only a supported, typed, authorized operation.
6. Preserve complete governance and audit evidence.

It is not a generic Azure resource portal, monitoring dashboard, FinOps product, or an
arbitrary ARM API proxy.

Primary users are cloud engineers, DevOps engineers, platform engineers, cloud
architects, and Azure administrators.

Phase 1 has no AI. Phase 2 may add Azure AI Foundry as an advisory layer, but AI output
must never directly authorize or execute an operation.

## Current Repository Status

The workspace is still not a Git repository. Phase 1 MVP implementation began on
2026-06-06. Backend services, frontend modules, Docker Compose, plain Kubernetes
manifests, Alembic, CI, and
tests now exist. Infrastructure-as-code for Azure resources has not yet been created.

Created artifacts:

- `README.md`
- `docs/architecture/overview.md`
- `docs/architecture/repository-structure.md`
- `docs/architecture/data-architecture.md`
- `docs/architecture/service-contracts.md`
- `docs/architecture/security.md`
- `docs/architecture/deployment.md`
- `docs/architecture/observability.md`
- `docs/deployment/azure-production-deployment-guide.md`
- `docs/api/api-contracts.md`
- `docs/adrs/001` through `011`
- `docs/diagrams/*.mmd`
- `docs/runbooks/README.md`
- `docs/runbooks/tenant-access-revocation.md`
- `docs/roadmap.md`
- `docs/references.md`
- `database/schema.sql`
- `your-brain.md`

Implemented code:

- `packages/python/sentinel_common`: configuration, Entra JWT validation, identity
  profile client, tenant actor context, SQLAlchemy UoW, health/correlation middleware,
  CloudEvents, transactional audit outbox, outbox relay, and managed-identity Key Vault
  secret provider.
- `apps/identity-service`: tenant/user resolution, synchronization, permission
  calculation, backend PKCE login/callback/logout, HTTP-only sessions, encrypted OAuth
  connections, delegated ARM token broker, and role/permission/profile APIs.
- `apps/inventory-service`: subscription discovery, ARG paging, normalized resource and
  resource-group persistence, durable jobs, inventory worker, and relationship
  projection publication.
- `apps/relationship-service`: resource projection, versioned ARM-reference extractor,
  typed relationships, full rebuild, and bounded graph APIs.
- `apps/audit-service`: authenticated internal ingestion, idempotency, per-tenant
  advisory locking, SHA-256 chain, activity events, search, and operation timelines.
- `apps/change-intelligence-service`: persisted assessment boundary, canonical hashes,
  risk rule interfaces, and API lifecycle. No reviewed rules are registered yet.
- `apps/operations-service`: persisted operation intent, typed disabled action catalog,
  executor protocol, authorization hooks, and audit outbox integration. Execution is
  intentionally blocked.
- `apps/web`: Next.js 15, cookie-authenticated backend OAuth flow, TanStack Query,
  dashboard, resources, React Flow dependencies, audit, and settings.
- `docker-compose.yml`, hardened Dockerfiles, Nginx local gateway, Alembic baseline,
  plain AKS manifests, migration image, and GitHub Actions.

`database/schema.sql` is both the local PostgreSQL initialization baseline and the
source used by the first Alembic revision. The accepted long-term decision remains one
Alembic history per service-owned schema. Splitting the initial unified baseline is a
required hardening task before independent service release trains.

## Implementation Decisions Added

### Authentication integration

On 2026-06-07 Sentinel integrated the backend-owned authentication flow from
`Sowrabh0-0/azure-inventory-saas` commit
`218ba3179e4f6ca99e036f60e49cea971ca6ec34`. ADR 009 records the adaptation.

Implemented behavior:

- optional Entra tenant ID input
- backend authorization code + PKCE
- `HttpOnly`, `SameSite=Lax`, signed Sentinel session cookie
- encrypted and rotating Microsoft refresh-token storage in
  `identity.oauth_connections`
- first user per newly observed tenant receives `TenantAdministrator`
- subsequent users receive `Reader`
- downstream services forward the cookie to Identity for tenant/user/permission context
- Inventory obtains user-bound, short-lived ARM tokens from Identity's internal broker
- state-changing cookie requests enforce same-origin metadata
- browser MSAL dependencies and browser access-token handling were removed
- Azure async management clients require `aiohttp`; it is an explicit runtime
  dependency so subscription discovery and Resource Graph calls work.
- Inventory sync jobs persist both subscription IDs and the caller's Entra tenant
  ID when inserted. In-place mutation of the JSON scope was not persisted by
  SQLAlchemy and caused workers to crash with `KeyError: entra_tenant_id`.
  Malformed jobs now fail cleanly.
- `inventory.resources.state` maps explicitly to the existing PostgreSQL
  `inventory.resource_state` enum. Mapping it as `VARCHAR` caused asyncpg insert
  failures after Resource Graph returned data.
- Inventory no longer restricts Azure Resource Graph results to a short resource
  type allowlist. It imports all rows from `Resources` and resource groups from
  `ResourceContainers`. The corrected inventory image tag is `v1.0.5`.
- Resource Explorer renders discovered subscriptions with display name, Azure
  subscription ID, state, and last sync time, and surfaces inventory request
  errors. Selecting a subscription filters the resource API by the internal
  subscription record ID; an All subscriptions control restores the combined
  view. The corrected web image tag is `v1.0.5`.
- organizational and personal Microsoft accounts are accepted through `/common`
- organizational workspaces are isolated by Entra `tid`
- shared-consumer identities are isolated by `(tid, oid)` in single-user workspaces
- personal-account refresh tokens are redeemed through `/common`

### Local authentication and tenant bootstrap

There is no authentication mock. `tools/start-local.ps1` prompts for a real multi-tenant
Entra web application client ID and client secret. Identity derives tenant/user IDs
only from validated Microsoft claims. The first user in a newly observed tenant is
assigned `TenantAdministrator`; later users receive `Reader`.

### Customer Azure credential behavior

ARG uses async Azure SDK clients. The primary MVP credential is
`IdentityDelegatedCredential`, which asks Identity for a short-lived ARM token tied to
the tenant and user who requested the inventory job. Identity decrypts and rotates only
that user's stored refresh token.

Personal Microsoft accounts are supported when the provider app registration uses
"Accounts in any organizational directory and personal Microsoft accounts". They do
not need an invitation into another organization and can discover Azure subscriptions
available to their Microsoft identity. Accounts issued an Azure directory `tid` follow
normal tenant isolation. Tokens using Microsoft's shared consumer `tid` receive a
single-user workspace under ADR 010.

Certificate credentials and `DefaultAzureCredential` remain fallback paths for a future
organization-owned connector/workload identity. Key Vault retrieval/rotation and the
customer-side connector remain pending.

### Transactional audit delivery

Commands enqueue CloudEvents into `platform.outbox` in the same PostgreSQL transaction
as business state. `sentinel_common.outbox_worker` leases records, retries with
exponential backoff, recovers stale publishing leases, and sends them to Audit.

Local transport is authenticated HTTP. Production AKS must replace the relay transport
with Azure Service Bus while preserving the outbox/inbox semantics from ADR 004.

### Relationship projection

Relationship does not query Inventory tables. Inventory publishes sanitized resource
projections through an authenticated internal endpoint. After each sync, Inventory
requests a tenant rebuild so references are resolved even when target resources arrived
after source resources.

Graph traversal performs one edge query per depth, not one per node, and enforces depth
and node bounds. A dedicated graph snapshot job is still pending for very large results.

### Operation safety

All action catalog entries are `enabled=false`. Creating intent is allowed for contract
development, but execution returns `409` until assessment validation, approval state,
real executors, and post-condition checks are implemented. This is intentional, not a
mock executor.

### Plain AKS manifests

On 2026-06-07 ADR 011 replaced the Helm chart with ordered plain manifests under
`deploy/kubernetes`. The manifest set was later simplified at the user's request for a
one-resource-group Azure setup: two namespaces, ConfigMaps, Workload Identity service
accounts, Key Vault SecretProviderClasses, resource governance, web, six APIs, two
workers, default-deny NetworkPolicies, explicit allow rules, and an in-cluster Nginx
gateway exposed by a Kubernetes `LoadBalancer` Service.

All environment-specific values are marked `REPLACE_ME_*`. A dedicated
`apps/migration/Dockerfile` packages Alembic migrations.
`deploy/kubernetes/04-database-migration-job.yaml` runs that image as a short-lived
AKS Job. The Job uses the `identity-service` ServiceAccount, Workload Identity, and
Key Vault CSI mount to obtain `postgres-runtime-url`, then applies Alembic migrations
before Identity Service rollout. It is deleted and recreated for each schema release.
Container CI builds web, all services, and migration; a Kubernetes workflow parses
manifests and validates cross-resource references.

## Settled Architecture Decisions

### Platform shape

Sentinel is a provider-hosted regional control plane. It has a Next.js web application,
six independently deployable FastAPI bounded services, synchronous APIs, and separate
asynchronous worker deployments.

Services:

1. Identity
2. Inventory
3. Relationship
4. Change Intelligence
5. Operations
6. Audit

The service list is intentionally preserved from the product request. Do not merge
services merely for implementation convenience without a superseding ADR.

### User and workload identity

User sign-in uses a provider-owned multi-tenant Microsoft Entra web app registration.
Identity owns authorization code + PKCE, validates the Microsoft ID token, encrypts the
rotating refresh token, and issues an HTTP-only Sentinel session. ADR 009 supersedes
the earlier browser-MSAL/no-refresh-token decision.

Human identity and organization-owned automation identity remain conceptually
separate. The MVP permits Identity-owned encrypted delegated refresh tokens for
inventory discovery only. Other services and the browser never receive them.

The delegated Phase 1 model uses encrypted rotating refresh tokens for Inventory. A
future customer-side connector with managed identity is preferred for unattended
organization-owned Operations because it removes cross-tenant credential custody.

Runtime platform services use:

- VM system-assigned managed identity in the VM phase
- AKS Workload Identity and dedicated service accounts/managed identities in AKS

### Tenant isolation

The Entra `tid` claim maps to an internal tenant UUID. Every tenant-owned entity,
message, job, graph edge, assessment, operation, approval, and audit record carries
that internal `tenant_id`.

Isolation controls are cumulative:

- claim-derived tenant context
- explicit repository filters
- tenant-first indexes and uniqueness constraints
- PostgreSQL row-level security
- one tenant per background transaction
- negative cross-tenant integration/security tests

Do not trust `tenant_id` supplied only in request input.

ADR 010 refines tenant resolution for Microsoft consumer identities. Organizational
workspace keys are `tenant:<tid>`; shared-consumer workspace keys are
`personal:<tid>:<oid>`. The resulting internal UUID remains the isolation key used by
all downstream services.

### Data ownership

Phase 1 uses one private PostgreSQL Flexible Server and one database with schemas:

```text
identity
inventory
relationships
intelligence
operations
audit
```

Each service has its own database role and migration history. Services cannot query
another service schema. Foreign keys exist within bounded contexts. Cross-service IDs
are validated through APIs/events and are intentionally not cross-schema foreign keys.

This preserves a migration path to separate databases if scale or compliance requires
it.

### Asynchronous processing

Azure Service Bus Premium is required for durable work. Use CloudEvents 1.0 JSON,
at-least-once delivery, service-owned outbox/inbox, idempotent consumers, dead-letter
queues, and tenant-aware ordering only where required.

Discovery, relationship extraction, graph snapshot generation, impact assessment,
operation execution, and audit export are durable jobs. APIs persist command intent
and return `202 Accepted`.

### Inventory

ARG is the broad discovery mechanism. ARM GET calls enrich selected resources. Initial
supported resource families:

- resource groups
- AKS
- storage accounts
- Key Vault
- managed identities
- VNets
- Application Gateways
- load balancers
- App Services

Resource identity is normalized lowercase ARM ID scoped by tenant. Missing resources
must be confirmed across successful scans before being marked deleted.

### Relationship graph

Resources are graph nodes and the Relationship service owns typed, directed edges.
Edges retain evidence, confidence, dependency strength, extractor name/version, and
observation times.

PostgreSQL recursive CTEs and bounded graph snapshots are the Phase 1 graph engine.
Every graph request has maximum depth and node count. Do not introduce a graph database
without measured evidence that PostgreSQL fails defined scale/latency targets.

React Flow renders API graph snapshots. UI layout is not canonical graph data.

### Change intelligence

Risk analysis is deterministic in Phase 1. The result includes a score from 0-100, a
LOW/MEDIUM/HIGH label, findings, evidence, affected resources, recovery guidance, and
approval requirement.

Inputs include:

- action hazard
- target resource criticality/environment
- graph blast radius
- relationship confidence/strength
- recoverability
- requested execution window
- tenant policy overrides

Rule sets are versioned.

### Operation safety

An assessment canonicalizes and hashes action, target, parameters, target ETag,
inventory snapshot, graph snapshot, actor, and rule-set version. Approval binds to this
hash. Changed or stale input invalidates approval.

Operations execute through versioned typed executors. There is no arbitrary ARM
method/path, shell command, user script, or unrestricted `kubectl`.

Each executor declares:

- JSON/Pydantic input schema
- required Sentinel permission
- exact Azure permissions
- preconditions
- timeout
- retry safety/idempotency
- compensation capability
- post-operation verification

Initial executable catalog is VM start/stop/restart, App Service scale/restart,
Kubernetes Deployment restart/scale, supported secret rotation, and resource tag patch.
Key Vault deletion and similar destructive changes are analysis-only until dedicated
recovery and failure testing is complete.

### Audit

Business services commit state and outbox event atomically. Audit consumes all domain
events asynchronously, avoiding a synchronous availability dependency.

Transactional audit records support product search. Periodic NDJSON exports go to a
separate immutable storage account with manifests and hash-chain integrity. Never log
tokens, secret values, connection strings, private keys, or authorization headers.

### Deployment

Current simple Azure target:

- one resource group
- Docker Hub, not ACR
- AKS with one node pool
- public AKS `LoadBalancer` Service for the Sentinel gateway
- Azure Database for PostgreSQL Flexible Server
- one Key Vault
- one Blob Storage account
- one user-assigned managed identity shared by Sentinel workloads
- OIDC issuer, Workload Identity, and Key Vault CSI
- default-deny NetworkPolicies with explicit allow rules

For the minimal demonstrator, the identity service uses the Blob Storage account as a
visible post-login event sink. After a successful OAuth callback and database commit,
it writes a non-sensitive JSON receipt beneath
`sentinel-login-events/login-events/YYYY/MM/DD/`. The write uses AKS Workload Identity
and `DefaultAzureCredential`; no storage key or connection string is stored. The UAMI
requires `Storage Blob Data Contributor` on the Storage Account. Blob recording is
enabled only when `SENTINEL_LOGIN_BLOB_ACCOUNT_URL` is configured, and failures are
logged without failing user authentication.

The simple setup intentionally omits Application Gateway, ACR, Service Bus, Log
Analytics, immutable audit storage, multiple resource groups, and HPA/PDBs. Add those
later only when the deployment needs that level of hardening.

### Observability

Use OpenTelemetry APIs with Azure Monitor/Application Insights backend. Propagate W3C
trace context and `X-Correlation-ID` through HTTP, Service Bus, database records, and
Azure SDK operations.

Expose:

- `/health/live`
- `/health/ready`
- `/version`

Use structured JSON logs and bounded metric labels. General telemetry uses a hashed
tenant ID; authorized audit uses internal IDs.

## Planned Repository Structure

```text
apps/
  web/
  identity-service/
  inventory-service/
  relationship-service/
  change-intelligence-service/
  operations-service/
  audit-service/
packages/
  python/
  typescript/
contracts/
  openapi/
  asyncapi/
  schemas/
database/
  <one migration directory per service>
deploy/
  compose/
  kubernetes/
infrastructure/
  modules/
  environments/
docs/
tests/
tools/
```

Python services use domain, application, infrastructure, presentation, and bootstrap
layers. Domain/application layers must not import FastAPI, SQLAlchemy, Azure SDK, or
Service Bus implementations.

## Azure Resources

Current Azure resource baseline:

- `rg-sentinel`
- `vnet-sentinel`
- `aks-sentinel`
- `psql-sentinel-*` on Azure Database for PostgreSQL Flexible Server
- `kv-sentinel-*`
- `stsentinel*` Blob Storage account
- `id-sentinel-app` user-assigned managed identity
- `app-sentinel-auth` Entra app registration
- optional `vm-docker-build` only when no laptop or CI runner can build Docker images
- `sentinel-database-migration` AKS Job for Alembic schema updates

The field-level Azure resource specification and deployment order are maintained in
`docs/deployment/azure-production-deployment-guide.md`. The filename is historical;
the content now documents the simple one-resource-group AKS deployment. It includes
Portal fields, Docker Hub build/push commands, AKS migration Job execution, manifest
replacement, deployment, verification, and cleanup.

The deployment guide now documents the custom-domain HTTPS setup:
`https://sentinel.vaultrix.in` and
`https://sentinel.vaultrix.in/auth/callback`. DNS should point
`sentinel.vaultrix.in` to AKS LoadBalancer IP `4.187.176.232`. The gateway manifest
terminates TLS on port 443 using Kubernetes secret `sentinel-gateway-tls` in namespace
`sentinel-app`; port 80 redirects to HTTPS. `deploy/kubernetes/01-config.yaml` uses
secure cookies, and the current web image is
`elzabeth03/sentinel-web:v1.0.3`, built with
`NEXT_PUBLIC_API_BASE_URL=https://sentinel.vaultrix.in/api/v1`.
The current working Identity image is
`elzabeth03/sentinel-identity-service:v1.0.3`.

On 2026-06-09, `sentinel-database-migration` completed successfully inside AKS against
the current `sent` database. Identity Service then completed application startup and
returned HTTP 200 from `/health/live` and `/health/ready`. This proved the supported
migration flow and removed the Docker VM from the runtime/database deployment path.
The current demo Key Vault name in manifests is `RG-1-KV`. Its private endpoint and
private DNS record resolve `rg-1-kv.vault.azure.net` to `10.10.20.4` inside the AKS
VNet. Do not switch manifests to another vault name unless that vault also has a
private endpoint, DNS record, VNet link, required RBAC, and the complete secret set.

On 2026-06-08 a demo-only extension was appended to the deployment guide. The newest
minimal demo path runs only web, Identity, and the gateway. Inventory, Relationship,
Change Intelligence, Operations, Audit, Inventory Worker, and Outbox Relay are skipped.
The gateway still needs DNS names for skipped APIs, so the guide creates placeholder
ClusterIP Services without running those Deployments. This is a demo shortcut, not a
redesign of service boundaries.

On 2026-06-08 the Docker VM `RG-1/docker-vm` was reached through Azure Run Command
because direct SSH to `20.244.8.208` timed out. Auth-demo images were built on the VM:
`elzabeth03/sentinel-identity-service:v1.0.1`,
`elzabeth03/sentinel-web:v1.0.1`, and migration image
`elzabeth03/sentinel-migration:v1.0.2`. The web image was built with placeholder
`NEXT_PUBLIC_API_BASE_URL=http://REPLACE_ME_AKS_PUBLIC_IP/api/v1` and must be rebuilt
after the real AKS LoadBalancer IP is known. Azure PostgreSQL `RG-1/elz-db` had
`azure.extensions=pgcrypto` enabled. Migration against database `mydb` completed
successfully through revisions `20260606_0001`, `20260607_0002`, and `20260607_0003`.
After the LoadBalancer IP was known and Entra rejected public HTTP redirect URIs, the
web image was rebuilt and pushed as `elzabeth03/sentinel-web:v1.0.3` with
`NEXT_PUBLIC_API_BASE_URL=https://sentinel.vaultrix.in/api/v1`.

## API and Event Standards

- Business APIs under `/api/v1`
- RFC 9457-style problem responses
- cursor pagination
- `Idempotency-Key` for commands
- `If-Match` for concurrency-sensitive mutations
- `202` plus `Location` for durable jobs
- permissions, not role names, in code
- CloudEvents 1.0 JSON for domain events
- breaking event changes get a new versioned event type

Canonical permission names are listed in `docs/api/api-contracts.md`.

## Database Notes

`database/schema.sql` includes all requested tables:

- users
- roles
- permissions
- tenants
- subscriptions
- resources
- relationships
- operations
- change_assessments
- audit_logs
- approvals
- activity_events

It also includes user-role links, role-permission links, automation identities, sync
jobs, graph snapshots, findings, execution attempts, and export batches.

Audit logs are range partitioned by `occurred_at`; monthly partitions must be created
ahead of ingestion. The parent table's primary/unique keys include the partition key
because PostgreSQL requires that for partitioned uniqueness.

## Security Invariants

These are non-negotiable:

1. No hardcoded or source-controlled secrets.
2. No broad Owner role for customer access.
3. Refresh tokens may exist only encrypted in Identity and may only mint short-lived
   delegated Azure tokens through the internal broker.
4. No unbounded graph traversal.
5. No operation without current assessment and policy checks.
6. No self-approval where separation of duties is configured.
7. No direct cross-service schema reads.
8. No unsanitized Azure payloads in logs.
9. No production public data-plane endpoints.
10. No AI-direct execution in Phase 2.

## Open Decisions

Resolve these through review before or during Platform Bootstrap:

1. **IaC:** Terraform is recommended unless the organization mandates Bicep.
2. **Frontend token boundary:** resolved by ADR 009. Identity owns PKCE and issues an
   HTTP-only Sentinel session; the browser does not use MSAL.
3. **Customer automation credential:** delegated user OAuth is implemented for
   Inventory. Operations still requires a customer-side connector or narrowly scoped
   organization-owned identity; the connector is strategically safer.
4. **Internal service authentication:** Entra application tokens versus a service mesh
   identity layer. Start with Entra/workload identity and network policy unless mesh
   requirements already exist.
5. **Local Service Bus development:** Azure namespace versus an approved emulator or
   adapter. Production semantics must be tested against real Service Bus.
6. **Tenant deployment model:** shared control plane is the default; regulated
   customers may later require dedicated stamps.

## Next Implementation Steps

Follow `docs/roadmap.md`. The immediate sequence is:

1. Run Docker Compose on a host with Docker and validate the first Alembic migration
   against PostgreSQL 16.
2. Run `npm install`, TypeScript checking, and `next build` on a Node 22 host; generate
   and commit the lock file.
3. Split the unified baseline into service-owned Alembic histories/version tables.
4. Add service-specific database roles and force RLS, including a narrowly privileged
   worker role for cross-tenant queue claims.
5. Replace internal HTTP projection/audit relay transport with Azure Service Bus
   topics/subscriptions and inbox deduplication for AKS.
6. Implement Key Vault certificate loading/rotation and customer automation identity
   onboarding APIs.
7. Add ARG throttling telemetry, cancellation, stale-job recovery, and missing/deleted
   resource confirmation.
8. Add graph snapshot jobs and extractor packs for AKS identity, Key Vault access,
   load balancer/backend references, and private endpoints.
9. Add reviewed deterministic risk rules and assessment worker.
10. Implement approval tables/APIs, SoD, assessment freshness checks, and the first
    non-destructive Azure executor.
11. Add Azure infrastructure-as-code and later DNS/TLS ingress definitions when the
    public IP setup is no longer enough.
12. Add two-tenant PostgreSQL integration tests, Service Bus contract tests, and E2E
    browser tests.

## Verification Performed

On 2026-06-06:

- Python `compileall`: passed for apps, shared packages, tests, and migrations.
- Ruff: passed.
- MyPy strict shared package: passed.
- Pytest: 13 passed, 1 PostgreSQL integration test skipped because no local PostgreSQL
  service was available.
- Imports/OpenAPI: all six FastAPI applications imported and generated schemas
  successfully.

On 2026-06-07 after ADR 010:

- Ruff: passed for apps, shared packages, tests, and migrations.
- Python compileall: passed.
- Pytest: 16 passed, 1 PostgreSQL integration test skipped because PostgreSQL was not
  available.
- Imports/OpenAPI: all six FastAPI applications imported and generated schemas.
- Live personal-account OAuth and ARM discovery still require validation with an Entra
  app configured for organizational and personal Microsoft accounts.

On 2026-06-07 after the simple one-resource-group AKS deployment rewrite:

- Kubernetes manifests under `deploy/kubernetes` parse successfully as 55 resources
  across 15 files.
- ServiceAccount, SecretProviderClass, and Service selector references passed semantic
  validation.
- The simplified manifest set contains two namespaces, no Helm, no Ingress, no HPA/PDB,
  no `sentinel-system` namespace, one short-lived Kubernetes migration Job, and one
  `sentinel-gateway` LoadBalancer.
- GitHub Actions workflow YAML parses successfully.
- Ruff passed.
- Python compileall passed.
- Pytest: 16 passed, 1 PostgreSQL integration test skipped because PostgreSQL was not
  available.
- Stale deployment references were scanned; the remaining ACR/Application Gateway/etc.
  mentions in the simple Azure guide are explicit "not creating now" notes.

Not verified on this workstation:

- Next.js typecheck/build because Node/npm are not installed.
- Docker image/Compose startup because Docker is not installed.
- Fresh migration execution from this workstation; the AKS Job was validated against
  Azure PostgreSQL on 2026-06-09.
- Kubernetes API server-side validation because `kubectl` is not installed and no AKS
  cluster is connected.

## Definition of Production Ready

Sentinel is not production ready merely because containers start. Before Phase 1
production:

- architecture and threat model approved
- two-tenant isolation tests pass
- least-privilege custom roles reviewed
- backup restore and regional failover exercised
- operation failure injection and idempotency tested
- audit integrity and immutable export verified
- SLO dashboards and alerts active with runbooks
- images signed/scanned and admission policies enforced
- production migrations rehearsed on representative volume
- penetration and authorization testing complete
- support ownership and on-call escalation established
