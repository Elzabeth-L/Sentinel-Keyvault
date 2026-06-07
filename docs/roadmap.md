# Sentinel Development Roadmap

## Phase 0: Architecture Foundation

Status: **implemented and under review**

- Architecture, service boundaries, data model, API conventions
- Security, deployment, observability, and ADR baseline
- Repository skeleton and engineering standards
- Threat model and tenant isolation test strategy
- IaC technology selection and environment naming standard

Exit criteria: architecture review approved; open decisions have owners; no service
implementation starts against undefined identity or tenant boundaries.

## Phase 1A: Platform Bootstrap

- [x] Monorepo toolchains for Python 3.12 and Node/Next.js 15
- [x] CI quality/security gates
- [x] Shared auth, database, audit outbox, and observability primitives
- [x] Local Docker Compose using PostgreSQL
- Simple Azure guide for one resource group, Docker Hub, AKS, Key Vault, PostgreSQL,
  Storage, and Docker build VM
- [x] Health/version endpoints and plain AKS manifests

Exit criteria: a blank service can build, deploy, authenticate with workload identity,
connect to its schema, publish an event, and emit correlated telemetry.

## Phase 1B: Identity and Tenant Onboarding

- Multi-tenant app registrations and verified publisher configuration
- Admin consent and customer tenant onboarding
- [x] User synchronization, permission catalog, default administrator role bootstrap
- Discovery and execution custom Azure role definitions
- Tenant suspension/offboarding controls
- Cross-tenant authorization and RLS security tests

Exit criteria: two test tenants can onboard with demonstrable data and authorization
isolation.

## Phase 1C: Inventory

- Subscription registration and permission validation
- [x] ARG discovery with durable database-backed sync jobs and pagination
- ARM enrichment for supported resource types
- Resource lifecycle, freshness, snapshots, and pagination
- [x] Resource Explorer frontend

Supported types: resource groups, AKS, storage accounts, Key Vault, managed identities,
VNets, Application Gateways, load balancers, and App Services.

## Phase 1D: Relationships

- [x] Versioned extractor framework
- [x] Typed edge evidence and confidence
- [x] Bounded breadth-first graph queries
- [x] React Flow Dependency Explorer
- Performance baseline on enterprise-sized synthetic inventories

## Phase 1E: Change Intelligence

- Versioned deterministic rule engine
- Immutable assessment input and stale-data validation
- Risk scoring, findings, blast radius, and recovery guidance
- Initial assessment packs for Key Vault deletion, AKS upgrade, managed identity
  deletion, and NSG modification
- Change Analysis frontend

## Phase 1F: Operations and Approvals

- Action catalog and typed executor SDK
- Operation/approval state machines, SoD, expiry, idempotency
- VM/App Service/Kubernetes/tag/secret rotation actions
- Pre/post-condition verification, retry, timeout, and cancellation
- Operations Center frontend

Destructive execution is enabled only after dedicated recovery and failure-injection
testing.

## Phase 1G: Audit and Platform Hardening

- Audit ingestion, search, operation timeline, immutable export
- Audit Center frontend
- SLOs, alerts, runbooks, dashboards, DR exercise
- Load, penetration, tenant-isolation, chaos, and restore testing
- DNS/TLS, stronger AKS deployment, and optional VM-to-AKS migration

## Phase 2: AI-Ready Extension

AI remains advisory:

- Introduce an `advisory` bounded context behind explicit contracts
- Ground recommendations in versioned inventory/graph/assessment evidence
- Store prompt/model/output provenance and human feedback
- Prevent model output from directly invoking Operations
- Require deterministic policy evaluation and human approval
- Add Azure AI Foundry only after privacy, evaluation, red-team, and cost controls

## Prioritized First Implementation Slice

1. Repository/toolchain bootstrap.
2. Identity service token validation and tenant context.
3. PostgreSQL identity schema and RLS integration tests.
4. Inventory service subscription registration and one ARG discovery worker.
5. Service Bus outbox/inbox and Audit event ingestion.
6. Minimal authenticated Resource Explorer.

This vertical slice proves the highest-risk assumptions before graph and execution
complexity is introduced.
