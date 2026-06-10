# Sentinel

Sentinel is an Azure Change Intelligence Platform for discovering Azure resources,
mapping dependencies, assessing operational change risk, executing approved actions,
and retaining an immutable governance trail.

This repository contains the first production-oriented Sentinel MVP implementation:

- Backend-owned Microsoft Entra PKCE login, HTTP-only sessions, tenant resolution,
  user synchronization, encrypted delegated tokens, and RBAC
- Azure Resource Graph subscription/resource discovery and durable inventory jobs
- event-fed resource dependency extraction and bounded graph traversal
- transactional audit outbox, append-only audit ingestion, and integrity chaining
- persisted Change Intelligence and Operations boundaries with execution disabled
  until reviewed rules, approvals, and Azure executors are deployed
- Next.js Resource Explorer, Dependency Explorer, Audit Center, and Settings modules
- Docker Compose, Alembic, plain Kubernetes manifests, GitHub Actions, and automated tests

Production uses **Azure Database for PostgreSQL Flexible Server**. The PostgreSQL
container in Docker Compose is only the local development equivalent.

## Start Here

- [Architecture overview](docs/architecture/overview.md)
- [Repository structure](docs/architecture/repository-structure.md)
- [Data architecture](docs/architecture/data-architecture.md)
- [Service contracts](docs/architecture/service-contracts.md)
- [API contracts](docs/api/api-contracts.md)
- [Security architecture](docs/architecture/security.md)
- [Deployment architecture](docs/architecture/deployment.md)
- [Azure production deployment guide](docs/deployment/azure-production-deployment-guide.md)
- [Terraform Azure deployment](terraform/README.md)
- [Terraform implementation plan](terraform/IMPLEMENTATION_PLAN.md)
- [Roadmap](docs/roadmap.md)
- [Session continuity](your-brain.md)

## Architecture Principles

1. Customer Azure access is explicit, consented, least-privileged, and auditable.
2. Every request and stored record is tenant scoped.
3. Analysis is separate from execution; assessed intent is immutable.
4. Destructive and high-risk operations require policy-driven approval.
5. Long-running work is asynchronous, idempotent, and observable.
6. Services own their data and communicate through versioned APIs and events.
7. Runtime workloads use managed identity or workload identity, never embedded credentials.
8. Audit evidence is append-only and exported to immutable storage.
9. AI is a future advisory capability and never a Phase 1 execution authority.

## Planned Top-Level Layout

```text
apps/             Deployable frontend and backend services
packages/         Shared, versioned libraries and generated contracts
contracts/        OpenAPI, AsyncAPI, and event schemas
database/         Service-specific Alembic migrations and local bootstrap
deploy/           Docker Compose and plain Kubernetes configuration
infrastructure/   Azure infrastructure as code
docs/             Architecture, ADRs, runbooks, diagrams, and roadmap
tests/            Cross-service contract, integration, security, and end-to-end tests
```

## Local Startup

Prerequisites:

- Docker Desktop with Docker Compose
- a Microsoft Entra web application registration configured for organizational
  directories and personal Microsoft accounts
- Azure permissions for the configured discovery identity

Run:

```powershell
./tools/start-local.ps1
```

The script creates an ignored `.env` file, generates local database/session/encryption
credentials, prompts for real Entra configuration, and starts the platform at
`http://localhost:8080`.

The first user who signs in from each new Entra tenant becomes that tenant's Sentinel
administrator. Personal Microsoft accounts receive isolated single-user workspaces.
Subsequent organizational users receive the read-only `Reader` role.

In the app registration, set **Supported account types** to:

```text
Accounts in any organizational directory and personal Microsoft accounts
```

The corresponding app manifest value is
`"signInAudience": "AzureADandPersonalMicrosoftAccount"`.

Configure this redirect URI on the Entra app:

```text
http://localhost:8080/auth/callback
```

Required delegated permission:

```text
Azure Service Management / user_impersonation
```

After sign-in:

1. Call `POST /api/v1/inventory/subscriptions/discover` to register accessible Azure
   subscriptions.
2. Call `POST /api/v1/inventory/sync-jobs` with selected subscription IDs.
3. The inventory worker persists ARG results and refreshes relationship projections.

There is no fake-login or fake-Azure mode.

## Verification

```powershell
python -m pip install -e ".[dev]"
python -m ruff check apps packages/python tests
python -m mypy packages/python/sentinel_common
python -m pytest -q
```

Frontend and container builds run in GitHub Actions using Node 22, Python 3.12, and
PostgreSQL 16.
