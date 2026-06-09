# Deployment Architecture

## Current Simple AKS Deployment

The current Azure deployment target is intentionally simple so Sentinel can be
demonstrated without overbuilding the cloud environment.

Current shape:

- one resource group
- one VNet
- AKS with one node pool
- Docker Hub images
- Azure Database for PostgreSQL Flexible Server
- one Storage Account for blob artifacts
- one Key Vault
- one user-assigned managed identity shared by the workloads
- AKS Workload Identity
- Azure Key Vault Secrets Store CSI Driver
- one public Kubernetes `LoadBalancer` Service named `sentinel-gateway`

The field-level portal guide is
[`docs/deployment/azure-production-deployment-guide.md`](../deployment/azure-production-deployment-guide.md).
The filename is historical; the current document describes the simple Azure setup.

## Request Routing

The public entry point is the `sentinel-gateway` LoadBalancer Service. It runs Nginx
inside AKS and routes:

```text
/                         -> web
/auth                     -> identity-service
/api/v1/auth              -> identity-service
/api/v1/inventory         -> inventory-service
/api/v1/relationships     -> relationship-service
/api/v1/analysis          -> change-intelligence-service
/api/v1/operations        -> operations-service
/api/v1/audit             -> audit-service
```

The first deployment uses `http://<AKS_PUBLIC_IP>`. Microsoft Entra authentication may
require DNS and HTTPS for a public redirect URI; that is a later hardening step.

## Namespaces

```text
sentinel-app      web and synchronous APIs
sentinel-workers  discovery and relay workers
```

Database migrations run as a short-lived Job in `sentinel-app`. The Job uses the
`identity-service` ServiceAccount, AKS Workload Identity, and the Identity
`SecretProviderClass` to obtain the database URL from Key Vault. It applies Alembic
migrations and exits before Identity Service is rolled out. A Docker VM is not part of
the migration path.

## Plain Manifest Strategy

ADR 011 keeps ordered plain Kubernetes manifests:

```text
deploy/kubernetes/
  00-namespaces.yaml
  01-config.yaml
  02-service-accounts.yaml
  03-secret-provider-classes.yaml
  04-database-migration-job.yaml
  04-resource-governance.yaml
  10-web.yaml
  11-identity-service.yaml
  12-inventory-service.yaml
  13-relationship-service.yaml
  14-change-intelligence-service.yaml
  15-operations-service.yaml
  16-audit-service.yaml
  20-workers.yaml
  40-network-policies.yaml
  50-gateway-loadbalancer.yaml
```

Operators replace all `REPLACE_ME_*` values and apply files in the order documented in
`deploy/kubernetes/README.md`. The files are intentionally explicit and contain no
rendering dependency.

Key Vault is the secret system of record. The current applications consume environment
variables, so the CSI provider synchronizes workload-specific Kubernetes Secrets.
File- or SDK-based secret loading should remove those copies later.

## Delivery Flow

1. Create Azure resources in one resource group.
2. Build and push Docker Hub images from any Docker-capable workstation or CI runner.
3. Replace manifest placeholders and apply namespaces, identity, and Key Vault CSI.
4. Recreate and wait for the AKS database migration Job.
5. Apply the application and gateway manifests.
6. Get the `sentinel-gateway` public IP.
7. Update Entra redirect URI, config, and web image with the real public IP.
8. Verify login, inventory, relationships, and audit records.

## Later Hardening Path

When the simple deployment proves the app flow, add the heavier pieces only as needed:

- DNS and HTTPS
- Application Gateway or Gateway API
- ACR
- Service Bus transport
- Log Analytics/Application Insights
- private endpoints
- separate managed identities per service
- multiple node pools
- autoscaling and disruption budgets
- immutable audit export storage
