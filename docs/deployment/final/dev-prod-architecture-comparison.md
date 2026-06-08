# Sentinel Dev vs Prod Azure Architecture

This document explains how to evolve Sentinel into a proper two-environment Azure
setup:

```text
RG-DEV   - lower cost, easier debugging, smaller scale
RG-PROD  - hardened, private, monitored, scalable
```

The environments should be separate. Do not share databases, Key Vaults, AKS clusters,
managed identities, or app registrations between dev and prod.

## High-Level Shape

```text
Developer / tester
  -> dev.sentinel.vaultrix.in
  -> RG-DEV

Real users
  -> sentinel.vaultrix.in
  -> RG-PROD
```

Both environments use the same application code and Kubernetes manifests, but with
different values, security posture, scaling, and Azure resource configuration.

## Environment Split

| Area | DEV | PROD |
| --- | --- | --- |
| Resource group | `RG-DEV` | `RG-PROD` |
| Domain | `dev.sentinel.vaultrix.in` | `sentinel.vaultrix.in` |
| Purpose | Build, test, demos, integration testing | Real customer use |
| Cost posture | Low cost | Reliability and security first |
| Data | Disposable/test data | Real tenant/resource/audit data |
| Access | Developers/admins | Restricted platform/admin groups |
| Public exposure | Can be simpler | Hardened edge with WAF |
| Monitoring | Basic | Full logs, alerts, dashboards |
| Backup | Short retention | Longer retention + restore testing |

## Recommended DEV Architecture

DEV should stay simple but still close enough to production that bugs are meaningful.

```text
RG-DEV
  vnet-dev
    snet-aks-dev
      aks-dev
        web
        identity-service
        inventory-service
        relationship-service
        change-intelligence-service
        operations-service
        audit-service
        workers

    snet-private-endpoints-dev
      Key Vault private endpoint
      Storage private endpoint
      ACR private endpoint optional

  psql-dev
  kv-dev
  stdev...
  acrdev...
  app-sentinel-dev
  managed identities
  basic Log Analytics
```

DEV can skip Azure Front Door. Use either:

```text
Option A:
Public AKS LoadBalancer / ingress

Option B:
Application Gateway WAF only
```

For most dev work, Option A is enough. If you need to test WAF/routing behavior, use
Application Gateway.

### DEV Resources

| Resource | DEV recommendation |
| --- | --- |
| Resource group | `RG-DEV` |
| VNet | `vnet-sentinel-dev`, for example `10.40.0.0/16` |
| AKS | Small cluster, 1 system node pool, optional 1 user pool |
| AKS node count | 1-2 nodes |
| AKS outbound | Default/loadBalancer outbound |
| Ingress | Public LoadBalancer or App Gateway |
| Front Door | Skip unless testing edge routing |
| PostgreSQL | Flexible Server, private preferred; public+firewall acceptable for quick dev |
| PostgreSQL HA | Disabled |
| PostgreSQL backup | 7 days |
| Key Vault | Private endpoint preferred, public selected networks acceptable for debugging |
| Storage | LRS, private endpoint optional |
| ACR | Basic or Standard; public network can be enabled for easier builds |
| Log Analytics | Enabled with low daily cap |
| App Insights | Enabled |
| Azure Policy | Audit mode |
| WAF | Detection mode if used |
| Secrets | Separate dev secrets |
| App registration | Separate dev app registration |
| Managed identities | Separate dev UAMIs |

### DEV Security Posture

DEV should still avoid bad habits:

- No secrets in repo.
- Separate Key Vault from prod.
- Separate Entra app registration from prod.
- Separate PostgreSQL from prod.
- No prod customer data.
- Developers can have broader access, but only in `RG-DEV`.
- Azure Policy can be `Audit` instead of `Deny`.
- WAF can run in `Detection`.
- PostgreSQL can be smaller and non-HA.

## Recommended PROD Architecture

PROD should be stricter and more private.

```text
RG-PROD
  Azure Front Door Premium + WAF
    -> Application Gateway WAF v2
      -> internal AKS ingress

  vnet-prod
    snet-appgw-prod
      Application Gateway WAF v2

    snet-aks-prod
      aks-prod
        all Sentinel microservices
        workers
        network policies
        workload identity

    snet-postgres-prod
      Azure PostgreSQL Flexible Server private access

    snet-private-endpoints-prod
      Key Vault private endpoint
      Storage blob private endpoint
      ACR private endpoint

  kv-prod
  psql-prod
  stprod...
  acrprod...
  law-prod
  appi-prod
  app-sentinel-prod
  prod managed identities
```

### PROD Resources

| Resource | PROD recommendation |
| --- | --- |
| Resource group | `RG-PROD` |
| VNet | `vnet-sentinel-prod`, for example `10.50.0.0/16` |
| Front Door | Premium with managed TLS and WAF |
| Application Gateway | WAF v2, autoscale, HTTPS backend |
| AKS | Separate prod cluster |
| AKS node pools | System pool + user pool |
| AKS node count | Minimum 2 nodes for user pool |
| AKS autoscaling | Enabled |
| AKS authentication | Entra ID + Azure RBAC |
| AKS local accounts | Disabled |
| AKS policy | Enabled |
| AKS ingress | Internal ingress behind App Gateway |
| PostgreSQL | Private VNet integration in delegated subnet |
| PostgreSQL HA | Enable zone-redundant HA when budget allows |
| PostgreSQL backup | 14-35 days depending retention needs |
| Key Vault | Private endpoint, public access disabled, purge protection enabled |
| Storage | Private endpoint, public access disabled, versioning + soft delete |
| ACR | Premium, private endpoint, public access disabled |
| Observability | Log Analytics + App Insights + alerts |
| Azure Policy | Deny for critical controls |
| WAF | Prevention mode |
| Secrets | Prod-only Key Vault secrets |
| App registration | Prod app registration |
| Managed identities | Prod-only UAMIs |

### PROD Security Posture

PROD should enforce:

- Key Vault public network access disabled.
- Storage public network access disabled.
- ACR public network access disabled.
- PostgreSQL public network access disabled.
- Front Door WAF in Prevention.
- Application Gateway WAF in Prevention after validation.
- AKS pods run as non-root.
- Kubernetes NetworkPolicies enabled.
- Separate managed identity per trust boundary.
- Least-privilege Azure RBAC.
- App registration secrets rotated.
- PostgreSQL backups enabled and restore tested.
- Container images scanned before deployment.
- Production deployments only through CI/CD.
- Developers do not have direct write access to prod workloads.

## Resource Difference Summary

| Component | DEV | PROD |
| --- | --- | --- |
| Front Door | Optional | Required |
| Application Gateway | Optional | Required |
| AKS ingress | Public LB acceptable | Internal only |
| PostgreSQL access | Public+firewall acceptable temporarily; private preferred | Private only |
| PostgreSQL HA | Disabled | Enabled when budget allows |
| Key Vault | Private preferred | Private only |
| Storage | Private optional | Private only |
| ACR | Public acceptable for dev | Private only |
| Azure Policy | Audit | Deny/Audit mix |
| WAF | Detection | Prevention |
| Logs | Low-cost | Full |
| Alerts | Minimal | Required |
| Backup | Short | Longer + tested |
| Data | Fake/test | Real |
| RBAC | Developer-friendly | Strict least privilege |

## Suggested Naming

| Resource | DEV | PROD |
| --- | --- | --- |
| Resource group | `RG-DEV` | `RG-PROD` |
| VNet | `vnet-sentinel-dev` | `vnet-sentinel-prod` |
| AKS | `aks-sentinel-dev` | `aks-sentinel-prod` |
| PostgreSQL | `psql-sentinel-dev` | `psql-sentinel-prod` |
| Key Vault | `kv-sentinel-dev-<unique>` | `kv-sentinel-prod-<unique>` |
| Storage | `stsentineldev<unique>` | `stsentinelprod<unique>` |
| ACR | `acrsentineldev<unique>` | `acrsentinelprod<unique>` |
| App registration | `app-sentinel-dev` | `app-sentinel-prod` |
| Front Door | optional `afd-sentinel-dev` | `afd-sentinel-prod` |
| App Gateway | optional `agw-sentinel-dev` | `agw-sentinel-prod` |
| Log Analytics | `law-sentinel-dev` | `law-sentinel-prod` |
| App Insights | `appi-sentinel-dev` | `appi-sentinel-prod` |

## Suggested Address Spaces

Use non-overlapping CIDRs:

| Network | DEV | PROD |
| --- | --- | --- |
| VNet | `10.40.0.0/16` | `10.50.0.0/16` |
| App Gateway subnet | `10.40.1.0/24` | `10.50.1.0/24` |
| AKS subnet | `10.40.2.0/23` | `10.50.2.0/23` |
| PostgreSQL delegated subnet | `10.40.4.0/24` | `10.50.4.0/24` |
| Private endpoint subnet | `10.40.5.0/24` | `10.50.5.0/24` |
| Build subnet | `10.40.6.0/24` | optional/no direct build VM |

## CI/CD Promotion Model

Recommended flow:

```text
feature branch
  -> build/test
  -> push image tag to dev ACR
  -> deploy to RG-DEV / aks-sentinel-dev
  -> smoke tests
  -> approval
  -> promote same image digest to prod ACR
  -> deploy to RG-PROD / aks-sentinel-prod
  -> health checks
```

Important:

- Do not rebuild different code for prod.
- Promote the same tested image digest.
- Use separate Key Vault secrets per environment.
- Use separate app registrations per environment.

## Final Recommendation

Use this model:

```text
DEV:
  Low-cost but still isolated.
  Can expose ingress more simply.
  Good for demos and testing.

PROD:
  Front Door + App Gateway WAF.
  Private data services.
  Strict RBAC and policy.
  Full monitoring and backup.
```

This gives Sentinel a clean growth path without overcomplicating the dev environment.
