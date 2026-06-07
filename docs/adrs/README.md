# Architecture Decision Records

| ADR | Decision | Status |
|---|---|---|
| [001](001-control-plane-and-service-boundaries.md) | Regional control plane and bounded services | Accepted |
| [002](002-multi-tenant-identity.md) | Multi-tenant Entra identity and customer automation identity | Accepted |
| [003](003-data-ownership-and-tenant-isolation.md) | Schema ownership, tenant key, and PostgreSQL RLS | Accepted |
| [004](004-asynchronous-workflows.md) | Service Bus, outbox/inbox, and idempotent workers | Accepted |
| [005](005-dependency-graph-storage.md) | PostgreSQL adjacency graph for Phase 1 | Accepted |
| [006](006-change-and-operation-safety.md) | Immutable assessments and allow-listed execution | Accepted |
| [007](007-runtime-secrets.md) | Workload identity and Key Vault CSI | Accepted |
| [008](008-deployment-evolution.md) | VM transition followed by private AKS | Accepted |
| [009](009-backend-owned-oauth-session.md) | Backend PKCE session and encrypted delegated tokens | Accepted |
| [010](010-personal-microsoft-account-isolation.md) | Personal Microsoft account workspace isolation | Accepted |
| [011](011-plain-kubernetes-manifests.md) | Plain Kubernetes manifests replace Helm packaging | Accepted |

ADRs are immutable after acceptance. Superseding decisions add a new ADR and link back.
