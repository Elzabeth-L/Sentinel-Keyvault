# Sentinel Integrated Azure Deployment Guide

This guide describes the fuller integrated Azure deployment for Sentinel. It is a
separate target from the current minimal demo deployment.

The goal is a secure, realistic, single-resource-group platform with all Sentinel
microservices enabled:

- Web frontend
- Identity Service
- Inventory Service
- Relationship Service
- Change Intelligence Service
- Operations Service
- Audit Service
- Inventory worker
- Outbox/audit relay worker

This guide intentionally avoids multiple application resource groups. Azure may still
create an AKS-managed node resource group automatically; that is normal and not part of
the application resource-group design.

## 0. Target Architecture

Traffic flow:

```text
User
  -> DNS sentinel.vaultrix.in
  -> Azure Front Door Premium + WAF
  -> Application Gateway WAF v2
  -> Internal AKS ingress controller
  -> Sentinel web/API routes
  -> Sentinel microservices
  -> PostgreSQL / Key Vault / Storage / Azure Resource Graph
```

Network placement:

```text
Resource Group: rg-sentinel

VNet: vnet-sentinel 10.30.0.0/16

Subnets:
  snet-appgw              10.30.1.0/24   Application Gateway only
  snet-aks                10.30.2.0/23   AKS nodes and internal ingress
  snet-postgres           10.30.4.0/24   PostgreSQL Flexible Server delegated subnet
  snet-private-endpoints  10.30.5.0/24   Key Vault, Storage, ACR private endpoints
  snet-build              10.30.6.0/24   Optional build VM/self-hosted runner
```

Security model:

- Entra ID handles user login.
- Sentinel validates JWT/session state and applies internal RBAC.
- Users access their own Azure subscriptions using delegated Microsoft identity.
- Microservices use Azure Workload Identity, not stored cloud credentials.
- Key Vault stores all runtime secrets.
- PostgreSQL, Key Vault, ACR, and Storage are private from the VNet.
- Front Door and Application Gateway both run WAF policies.
- AKS uses network policies, namespace isolation, non-root containers, and resource
  limits.
- Azure Policy is enabled for AKS guardrails.

## 1. Create Resource Group

Azure Portal path:

```text
Resource groups > Create
```

Configuration:

| Field | Value |
| --- | --- |
| Subscription | `<SUBSCRIPTION_ID>` |
| Resource group | `<RESOURCE_GROUP>` such as `rg-sentinel` |
| Region | `<LOCATION>` such as `Central India` |
| Tags | `application=sentinel`, `owner=<OWNER>`, `cost-center=<COST_CENTER>` |

Review and create.

## 2. Create Virtual Network And Subnets

Azure Portal path:

```text
Virtual networks > Create
```

Basics:

| Field | Value |
| --- | --- |
| Resource group | `<RESOURCE_GROUP>` |
| Name | `<VNET_NAME>` such as `vnet-sentinel` |
| Region | `<LOCATION>` |

IP addresses:

| Field | Value |
| --- | --- |
| Address space | `<VNET_CIDR>` such as `10.30.0.0/16` |

Create these subnets:

| Subnet | CIDR | Special configuration |
| --- | --- | --- |
| `<SNET_APPGW>` | `<SNET_APPGW_CIDR>` | Dedicated to Application Gateway |
| `<SNET_AKS>` | `<SNET_AKS_CIDR>` | Used by AKS |
| `<SNET_POSTGRES>` | `<SNET_POSTGRES_CIDR>` | Delegate to `Microsoft.DBforPostgreSQL/flexibleServers` |
| `<SNET_PRIVATE_ENDPOINTS>` | `<SNET_PRIVATE_ENDPOINTS_CIDR>` | Private endpoints |
| `<SNET_BUILD>` | `<SNET_BUILD_CIDR>` | Optional build VM/self-hosted runner |

Security options:

| Field | Value |
| --- | --- |
| Bastion | `Disabled` unless you need browser SSH/RDP |
| Azure Firewall | `Disabled` for this architecture |
| DDoS Network Protection | `Disabled` initially; enable later if required |

Notes:

- Application Gateway requires its own subnet.
- PostgreSQL private access requires a delegated subnet.
- Private endpoints should not share the PostgreSQL delegated subnet.

## 3. Create Microsoft Entra App Registration

Azure Portal path:

```text
Microsoft Entra ID > App registrations > New registration
```

Registration:

| Field | Value |
| --- | --- |
| Name | `<APP_REG_NAME>` such as `app-sentinel-auth` |
| Supported account types | `Accounts in any organizational directory and personal Microsoft accounts` |
| Redirect URI platform | `Web` |
| Redirect URI | `<REDIRECT_URI>` such as `https://sentinel.vaultrix.in/auth/callback` |

Authentication:

| Field | Value |
| --- | --- |
| Web redirect URI | `<REDIRECT_URI>` |
| Front-channel logout URL | `<LOGOUT_URI>` |
| Access tokens implicit grant | `Unchecked` |
| ID tokens implicit grant | `Unchecked` |
| Allow public client flows | `No` |

Certificates and secrets:

| Field | Value |
| --- | --- |
| Client secret description | `sentinel-runtime` |
| Expiry | `6 months` or `12 months` |
| Storage | Copy value once and store only in Key Vault |

API permissions:

| API | Permission | Type |
| --- | --- | --- |
| Microsoft Graph | `openid` | Delegated |
| Microsoft Graph | `profile` | Delegated |
| Microsoft Graph | `email` | Delegated |
| Azure Service Management | `user_impersonation` | Delegated |

Do not hardcode tenant ID into the login flow. The app should support multi-tenant and
personal Microsoft account sign-in.

## 4. Create User-Assigned Managed Identities

Azure Portal path:

```text
Managed identities > Create
```

Create these identities in `<RESOURCE_GROUP>`:

| Name | Purpose |
| --- | --- |
| `<UAMI_PLATFORM_NAME>` | Shared platform access, web, relationship, intelligence |
| `<UAMI_IDENTITY_NAME>` | Identity Service secrets/session runtime |
| `<UAMI_INVENTORY_NAME>` | Inventory Service and inventory worker |
| `<UAMI_OPERATIONS_NAME>` | Future approved Azure operations |
| `<UAMI_AUDIT_NAME>` | Audit Service and outbox relay |

For each:

| Field | Value |
| --- | --- |
| Subscription | `<SUBSCRIPTION_ID>` |
| Resource group | `<RESOURCE_GROUP>` |
| Region | `<LOCATION>` |
| Name | value from table above |

After creation, copy:

- Client ID
- Object/principal ID

## 5. Create Azure Container Registry

Use ACR for the integrated setup. Docker Hub is fine for the minimal demo, but ACR is
cleaner for private enterprise deployment.

Azure Portal path:

```text
Container registries > Create
```

Basics:

| Field | Value |
| --- | --- |
| Resource group | `<RESOURCE_GROUP>` |
| Registry name | `<ACR_NAME>` such as `acrsentinel01` |
| Location | `<LOCATION>` |
| SKU | `Premium` |
| Admin user | `Disabled` |
| Public network access | `Disabled` after private endpoint is created |
| Zone redundancy | `Disabled` initially |
| Data endpoint | `Disabled` initially |
| Encryption | Microsoft-managed key |

Networking:

| Field | Value |
| --- | --- |
| Private endpoint | `Create` |
| Private endpoint name | `<ACR_PRIVATE_ENDPOINT>` |
| Target sub-resource | `registry` |
| VNet | `<VNET_NAME>` |
| Subnet | `<SNET_PRIVATE_ENDPOINTS>` |
| Private DNS integration | `Yes` |
| Private DNS zone | `privatelink.azurecr.io` |

RBAC:

| Principal | Role | Scope |
| --- | --- | --- |
| AKS kubelet identity | `AcrPull` | ACR |
| Build VM/self-hosted runner identity | `AcrPush` | ACR |

## 6. Create Key Vault

Azure Portal path:

```text
Key vaults > Create
```

Basics:

| Field | Value |
| --- | --- |
| Resource group | `<RESOURCE_GROUP>` |
| Key vault name | `<KEY_VAULT_NAME>` |
| Region | `<LOCATION>` |
| Pricing tier | `Standard` |
| Permission model | `Azure role-based access control` |
| Soft-delete | `Enabled` |
| Days to retain deleted vaults | `7` or `30` |
| Purge protection | `Enabled` for final integrated setup |

Networking:

| Field | Value |
| --- | --- |
| Public network access | `Disabled` |
| Private endpoint | `Create` |
| Private endpoint name | `<KV_PRIVATE_ENDPOINT>` |
| Target sub-resource | `vault` |
| VNet | `<VNET_NAME>` |
| Subnet | `<SNET_PRIVATE_ENDPOINTS>` |
| Private DNS integration | `Yes` |
| Private DNS zone | `privatelink.vaultcore.azure.net` |

RBAC:

| Principal | Role | Scope |
| --- | --- | --- |
| Your admin user | `Key Vault Administrator` | Key Vault |
| `<UAMI_IDENTITY_NAME>` | `Key Vault Secrets User` | Key Vault |
| `<UAMI_PLATFORM_NAME>` | `Key Vault Secrets User` | Key Vault |
| `<UAMI_INVENTORY_NAME>` | `Key Vault Secrets User` | Key Vault |
| `<UAMI_OPERATIONS_NAME>` | `Key Vault Secrets User` | Key Vault |
| `<UAMI_AUDIT_NAME>` | `Key Vault Secrets User` | Key Vault |
| Application Gateway managed identity | `Key Vault Secrets User` | Key Vault certificate secret |

Secrets to create are listed in `placeholders.md`.

## 7. Create PostgreSQL Flexible Server With Private Access

Azure Portal path:

```text
Azure Database for PostgreSQL flexible servers > Create
```

Basics:

| Field | Value |
| --- | --- |
| Resource group | `<RESOURCE_GROUP>` |
| Server name | `<POSTGRES_SERVER>` |
| Region | `<LOCATION>` |
| PostgreSQL version | `16` |
| Workload type | `Development` initially, scale later |
| Compute tier | `Burstable` for small/test, `General Purpose` for stable integrated env |
| Compute size | `Standard_B2s` minimum test, `D2ds_v5` or better for stable env |
| Storage | `32 GiB` minimum or portal minimum |
| Storage auto-grow | `Enabled` |
| Availability zone | `No preference` |
| High availability | `Disabled` initially; enable zone-redundant later if required |
| Authentication method | `PostgreSQL and Microsoft Entra authentication` |
| Admin username | `<POSTGRES_ADMIN>` |
| Password | `<POSTGRES_PASSWORD>` |

Networking:

| Field | Value |
| --- | --- |
| Connectivity method | `Private access (VNet Integration)` |
| Virtual network | `<VNET_NAME>` |
| Subnet | `<SNET_POSTGRES>` |
| Private DNS integration | `Yes` |
| Private DNS zone | `<POSTGRES_PRIVATE_DNS_ZONE>` |

Security:

| Field | Value |
| --- | --- |
| Require secure transport | `Enabled` |
| Minimum TLS version | `TLS 1.2` |

Backup:

| Field | Value |
| --- | --- |
| Backup retention | `7 days` initially |
| Geo-redundant backup | `Disabled` initially |

After creation:

1. Open `Databases`.
2. Add database `<POSTGRES_DB>`.
3. Open `Server parameters`.
4. Set `azure.extensions` to include `PGCRYPTO`.
5. Save and restart if Azure asks.

Connection string format:

```text
postgresql+asyncpg://<POSTGRES_ADMIN>:<POSTGRES_PASSWORD>@<POSTGRES_SERVER>.postgres.database.azure.com:5432/<POSTGRES_DB>?ssl=require
```

Store it in Key Vault as:

```text
postgres-runtime-url
```

## 8. Create Storage Account With Private Blob Endpoint

Azure Portal path:

```text
Storage accounts > Create
```

Basics:

| Field | Value |
| --- | --- |
| Resource group | `<RESOURCE_GROUP>` |
| Storage account name | `<STORAGE_ACCOUNT>` |
| Region | `<LOCATION>` |
| Performance | `Standard` |
| Redundancy | `Locally-redundant storage (LRS)` initially |

Advanced:

| Field | Value |
| --- | --- |
| Require secure transfer | `Enabled` |
| Minimum TLS version | `TLS 1.2` |
| Allow blob anonymous access | `Disabled` |
| Allow storage account key access | `Disabled` after managed identity is verified |
| Default to Microsoft Entra authorization | `Enabled` |
| Infrastructure encryption | `Disabled` initially |

Networking:

| Field | Value |
| --- | --- |
| Public network access | `Disabled` |
| Private endpoint | `Create` |
| Private endpoint name | `<BLOB_PRIVATE_ENDPOINT>` |
| Target sub-resource | `blob` |
| VNet | `<VNET_NAME>` |
| Subnet | `<SNET_PRIVATE_ENDPOINTS>` |
| Private DNS integration | `Yes` |
| Private DNS zone | `privatelink.blob.core.windows.net` |

Data protection:

| Field | Value |
| --- | --- |
| Blob soft delete | `Enabled`, `7 days` |
| Container soft delete | `Enabled`, `7 days` |
| Versioning | `Enabled` |
| Change feed | `Disabled` initially |

Containers:

```text
inventory-snapshots
change-reports
operation-artifacts
audit-exports
exports
```

RBAC:

| Principal | Role | Scope |
| --- | --- | --- |
| `<UAMI_AUDIT_NAME>` | `Storage Blob Data Contributor` | Storage account |
| `<UAMI_OPERATIONS_NAME>` | `Storage Blob Data Contributor` | Storage account |
| `<UAMI_INVENTORY_NAME>` | `Storage Blob Data Contributor` | Storage account |

## 9. Create Log Analytics And Application Insights

Azure Portal path:

```text
Log Analytics workspaces > Create
```

Log Analytics:

| Field | Value |
| --- | --- |
| Resource group | `<RESOURCE_GROUP>` |
| Name | `<LAW_NAME>` |
| Region | `<LOCATION>` |
| Pricing tier | `Pay-as-you-go` |
| Daily cap | Set a low cap initially, for example `1 GB/day` |
| Retention | `30 days` |

Application Insights:

| Field | Value |
| --- | --- |
| Resource group | `<RESOURCE_GROUP>` |
| Name | `<APPINSIGHTS_NAME>` |
| Region | `<LOCATION>` |
| Workspace | `<LAW_NAME>` |
| Application type | `Web` |

Store the connection string in Key Vault:

```text
applicationinsights-connection-string
```

## 10. Create AKS Cluster

Azure Portal path:

```text
Kubernetes services > Create > Create a Kubernetes cluster
```

Basics:

| Field | Value |
| --- | --- |
| Resource group | `<RESOURCE_GROUP>` |
| Cluster name | `<AKS_NAME>` |
| Region | `<LOCATION>` |
| Availability zones | `1,2,3` if available; otherwise default |
| AKS pricing tier | `Free` initially |
| Kubernetes version | Latest stable offered by Azure |
| Automatic upgrade | `Patch` |
| Node OS upgrade channel | `NodeImage` |
| Local accounts | `Disabled` |
| Authentication and authorization | `Microsoft Entra ID with Azure RBAC` |

System node pool:

| Field | Value |
| --- | --- |
| Name | `<AKS_NODE_POOL_NAME>` such as `system` |
| Mode | `System` |
| Node size | `Standard_B2ms` minimum test, `D2s_v5` or better stable |
| Scale method | `Manual` initially |
| Node count | `2` |
| Max pods | `30` |
| OS disk type | `Managed` |
| OS disk size | `64 GiB` |

User node pool:

| Field | Value |
| --- | --- |
| Name | `<AKS_USER_POOL_NAME>` such as `apps` |
| Mode | `User` |
| Node size | `Standard_B2ms` minimum test, `D2s_v5` or better stable |
| Scale method | `Autoscale` |
| Min nodes | `2` |
| Max nodes | `5` |
| Max pods | `30` |
| Labels | `workload=sentinel` |

Networking:

| Field | Value |
| --- | --- |
| Network configuration | `Azure CNI Overlay` or `Azure CNI` |
| Virtual network | `<VNET_NAME>` |
| Cluster subnet | `<SNET_AKS>` |
| Network policy | `Cilium` if offered, otherwise `Azure` |
| Load balancer SKU | `Standard` |
| Outbound type | `loadBalancer` / AKS managed outbound |
| DNS name prefix | `<AKS_DNS_PREFIX>` |
| Private cluster | `Disabled` initially for simpler operations; enable later if required |

Integrations:

| Field | Value |
| --- | --- |
| Container registry | Attach `<ACR_NAME>` |
| Azure Policy | `Enabled` |
| Azure Key Vault Secrets Provider | `Enabled` |
| OIDC issuer | `Enabled` |
| Workload Identity | `Enabled` |
| Container Insights | `Enabled`, workspace `<LAW_NAME>` |

Security:

| Field | Value |
| --- | --- |
| Defender for Containers | Optional; enable when budget allows |
| Secrets Store CSI rotation | `Enabled` |

## 11. Create Application Gateway WAF v2

Application Gateway is the regional ingress layer. It receives traffic from Front Door
and forwards to the internal AKS ingress private IP.

Azure Portal path:

```text
Application gateways > Create
```

Basics:

| Field | Value |
| --- | --- |
| Resource group | `<RESOURCE_GROUP>` |
| Name | `<APPGW_NAME>` |
| Region | `<LOCATION>` |
| Tier | `WAF V2` |
| Autoscaling | `Enabled` |
| Minimum instance count | `1` initially, `2` stable |
| Maximum instance count | `3` |
| Availability zone | `No preference` or zones if available |
| HTTP2 | `Enabled` |

Frontend:

| Field | Value |
| --- | --- |
| Frontend IP address type | `Public` |
| Public IP | Create new `<APPGW_PUBLIC_IP>` |
| Public IP SKU | `Standard` |
| Assignment | `Static` |

Backend:

| Field | Value |
| --- | --- |
| Backend pool name | `bp-aks-ingress` |
| Target type | `IP address` |
| Target | `<INGRESS_INTERNAL_IP>` |

Routing:

| Field | Value |
| --- | --- |
| Listener name | `https-sentinel` |
| Frontend protocol | `HTTPS` |
| Port | `443` |
| Certificate source | `Key Vault` |
| Certificate | `<TLS_CERT_SECRET_NAME>` |
| Rule type | `Basic` |
| Backend target | `bp-aks-ingress` |
| Backend protocol | `HTTPS` |
| Backend port | `443` |
| Probe path | `/health/live` or ingress health endpoint |

WAF:

| Field | Value |
| --- | --- |
| WAF policy | `<APPGW_WAF_POLICY>` |
| Mode | `Prevention` after testing, `Detection` during first deployment |
| OWASP ruleset | `3.2` |
| Request body inspection | `Enabled` |

Network:

| Field | Value |
| --- | --- |
| VNet | `<VNET_NAME>` |
| Subnet | `<SNET_APPGW>` |

## 12. Create Azure Front Door Premium

Front Door is the global public edge. It gives TLS, global WAF, managed certificate,
and a clean custom domain entry point.

Azure Portal path:

```text
Front Door and CDN profiles > Create
```

Profile:

| Field | Value |
| --- | --- |
| Resource group | `<RESOURCE_GROUP>` |
| Name | `<FRONT_DOOR_PROFILE>` |
| Tier | `Premium` |

Endpoint:

| Field | Value |
| --- | --- |
| Endpoint name | `<FRONT_DOOR_ENDPOINT>` |
| Enabled | `Yes` |

Origin group:

| Field | Value |
| --- | --- |
| Name | `og-appgw-sentinel` |
| Session affinity | `Disabled` |
| Health probe path | `/health/live` |
| Health probe protocol | `HTTPS` |
| Health probe interval | `60 seconds` |
| Load balancing sample size | `4` |
| Successful samples required | `3` |

Origin:

| Field | Value |
| --- | --- |
| Name | `origin-appgw` |
| Origin type | `Custom` |
| Host name | App Gateway public DNS name or IP DNS label |
| Origin host header | `<DOMAIN_NAME>` |
| HTTP port | `80` |
| HTTPS port | `443` |
| Priority | `1` |
| Weight | `1000` |
| Certificate subject name validation | `Enabled` |

Route:

| Field | Value |
| --- | --- |
| Name | `route-sentinel` |
| Domains | Front Door endpoint and `<DOMAIN_NAME>` |
| Patterns to match | `/*` |
| Accepted protocols | `HTTPS only` |
| Redirect HTTP to HTTPS | `Enabled` |
| Origin group | `og-appgw-sentinel` |
| Forwarding protocol | `HTTPS only` |
| Caching | `Disabled` |

Custom domain:

| Field | Value |
| --- | --- |
| Domain | `<DOMAIN_NAME>` |
| Certificate | `Azure managed certificate` |
| Minimum TLS version | `TLS 1.2` |

WAF policy:

| Field | Value |
| --- | --- |
| Name | `<FRONT_DOOR_WAF_POLICY>` |
| Mode | `Prevention` after testing |
| Managed rules | Microsoft Default Rule Set latest |
| Bot protection | `Enabled` if available |
| Custom rule | Allow only expected host `<DOMAIN_NAME>` |

DNS:

Create the CNAME/TXT records requested by Front Door for custom domain validation.

## 13. Configure AKS Ingress

Use an internal ingress controller behind Application Gateway.

Target behavior:

```text
Application Gateway public HTTPS
  -> internal ingress service private IP <INGRESS_INTERNAL_IP>
  -> web and API services
```

Ingress controller:

- Namespace: `<NAMESPACE_INGRESS>`
- Service type: `LoadBalancer`
- Azure annotation: internal load balancer
- Static IP: `<INGRESS_INTERNAL_IP>` from `<SNET_AKS>`

Routes:

| Path | Backend |
| --- | --- |
| `/` | `web` |
| `/auth/callback` | `web` |
| `/api/v1/auth/*` | `identity-service` |
| `/api/v1/inventory/*` | `inventory-service` |
| `/api/v1/relationships/*` | `relationship-service` |
| `/api/v1/analysis/*` | `change-intelligence-service` |
| `/api/v1/operations/*` | `operations-service` |
| `/api/v1/audit/*` | `audit-service` |

## 14. Workload Identity Federated Credentials

For each Kubernetes service account, create a federated credential on the matching
managed identity.

Federated credential fields:

| Field | Value |
| --- | --- |
| Scenario | `Kubernetes accessing Azure resources` |
| Cluster issuer URL | AKS OIDC issuer URL |
| Namespace | service namespace |
| Service account | service account name |
| Audience | `api://AzureADTokenExchange` |

Mappings:

| Service account | Managed identity |
| --- | --- |
| `sentinel-app/web` | `<UAMI_PLATFORM_NAME>` |
| `sentinel-app/identity-service` | `<UAMI_IDENTITY_NAME>` |
| `sentinel-app/inventory-service` | `<UAMI_INVENTORY_NAME>` |
| `sentinel-app/relationship-service` | `<UAMI_PLATFORM_NAME>` |
| `sentinel-app/change-intelligence-service` | `<UAMI_PLATFORM_NAME>` |
| `sentinel-app/operations-service` | `<UAMI_OPERATIONS_NAME>` |
| `sentinel-app/audit-service` | `<UAMI_AUDIT_NAME>` |
| `sentinel-workers/inventory-worker` | `<UAMI_INVENTORY_NAME>` |
| `sentinel-workers/outbox-relay` | `<UAMI_AUDIT_NAME>` |

## 15. RBAC Assignments

Azure resource RBAC:

| Principal | Role | Scope |
| --- | --- | --- |
| AKS kubelet identity | `AcrPull` | ACR |
| Build identity | `AcrPush` | ACR |
| App Gateway identity | `Key Vault Secrets User` | Key Vault |
| `<UAMI_IDENTITY_NAME>` | `Key Vault Secrets User` | Key Vault |
| `<UAMI_PLATFORM_NAME>` | `Key Vault Secrets User` | Key Vault |
| `<UAMI_INVENTORY_NAME>` | `Key Vault Secrets User` | Key Vault |
| `<UAMI_OPERATIONS_NAME>` | `Key Vault Secrets User` | Key Vault |
| `<UAMI_AUDIT_NAME>` | `Key Vault Secrets User` | Key Vault |
| `<UAMI_AUDIT_NAME>` | `Storage Blob Data Contributor` | Storage |
| `<UAMI_INVENTORY_NAME>` | `Storage Blob Data Contributor` | Storage |
| `<UAMI_OPERATIONS_NAME>` | `Storage Blob Data Contributor` | Storage |

Customer Azure access:

- Do not grant Sentinel broad provider-subscription permissions by default.
- Discovery uses the signed-in user's delegated Azure token.
- Users only see subscriptions/resources that their Microsoft account can access.
- Operations require internal Sentinel approval and the user must have sufficient Azure
  permission for the target operation.

## 16. Azure Policy Guardrails

Assign these policies at `<RESOURCE_GROUP>` or subscription scope as appropriate.

Recommended built-ins:

| Policy | Effect |
| --- | --- |
| Kubernetes cluster containers should only use allowed images | Audit initially |
| Kubernetes cluster pods should use approved host network and port range | Deny after testing |
| Kubernetes cluster containers should run with read-only root file system | Audit initially |
| Kubernetes cluster containers should not run as root | Deny after image verification |
| Kubernetes clusters should not allow privileged containers | Deny |
| Secrets should have expiration date | Audit |
| Key Vault should have purge protection enabled | Deny |
| Storage accounts should restrict network access | Audit/Deny |
| Secure transfer to storage accounts should be enabled | Deny |
| Public network access should be disabled for Key Vault | Deny |

Use `Audit` first while deploying. Move to `Deny` only after manifests are verified.

## 17. Kubernetes Security Baseline

Namespaces:

```text
sentinel-app
sentinel-workers
ingress-nginx
monitoring
```

Pod security:

- `runAsNonRoot: true`
- Numeric `runAsUser` and `runAsGroup`
- `readOnlyRootFilesystem: true`
- Drop all Linux capabilities
- No privileged containers
- CPU/memory requests and limits
- Liveness/readiness/startup probes

Network policies:

| From | To | Port |
| --- | --- | --- |
| ingress controller | web | `3000` |
| ingress controller | API services | `8000` |
| web | identity-service | `8000` |
| services | PostgreSQL | `5432` |
| services | Key Vault private endpoint | `443` |
| services | Azure Resource Manager / Resource Graph | `443` |
| services | Application Insights ingestion | `443` |

Secrets:

- Prefer Key Vault + Secrets Store CSI.
- Do not commit Kubernetes Secret manifests with secret values.
- CSI may sync runtime Kubernetes Secrets when env vars are required.

## 18. Build And Push Images

Use ACR for the integrated setup.

Image names:

```text
<ACR_LOGIN_SERVER>/sentinel-web:<IMAGE_TAG>
<ACR_LOGIN_SERVER>/sentinel-identity-service:<IMAGE_TAG>
<ACR_LOGIN_SERVER>/sentinel-inventory-service:<IMAGE_TAG>
<ACR_LOGIN_SERVER>/sentinel-relationship-service:<IMAGE_TAG>
<ACR_LOGIN_SERVER>/sentinel-change-intelligence-service:<IMAGE_TAG>
<ACR_LOGIN_SERVER>/sentinel-operations-service:<IMAGE_TAG>
<ACR_LOGIN_SERVER>/sentinel-audit-service:<IMAGE_TAG>
<ACR_LOGIN_SERVER>/sentinel-migration:<IMAGE_TAG>
```

Build arguments:

```text
NEXT_PUBLIC_API_BASE_URL=https://<DOMAIN_NAME>/api/v1
```

Migration:

- Run migration image once per schema version before rolling out services.
- In a final deployment, run migration as a Kubernetes Job using the same Key Vault
  secret access pattern.

## 19. Deploy Microservices

Deploy order:

1. Namespaces
2. ConfigMaps
3. Service accounts
4. SecretProviderClasses
5. Network policies baseline
6. Migration Job
7. Identity Service
8. Audit Service
9. Inventory Service and worker
10. Relationship Service
11. Change Intelligence Service
12. Operations Service
13. Web frontend
14. Internal ingress
15. Application Gateway backend health verification
16. Front Door route enablement

Health checks:

| Service | Path |
| --- | --- |
| web | `/` |
| identity-service | `/health/live`, `/health/ready` |
| inventory-service | `/health/live`, `/health/ready` |
| relationship-service | `/health/live`, `/health/ready` |
| change-intelligence-service | `/health/live`, `/health/ready` |
| operations-service | `/health/live`, `/health/ready` |
| audit-service | `/health/live`, `/health/ready` |

## 20. Audit And Governance Flow

For every user-visible action:

```text
User request
  -> Identity Service authorizes role/permission
  -> Target service validates tenant scope
  -> Audit event emitted
  -> If operation is risky, approval required
  -> Approved operation executes
  -> Result and evidence written to PostgreSQL and optionally Blob Storage
```

Audit records:

- user ID
- tenant ID
- subscription ID
- request ID / correlation ID
- operation type
- target resource ID
- approval ID if applicable
- before/after status
- timestamp
- service name

## 21. Final Validation Checklist

Edge:

- Front Door custom domain validated.
- HTTPS works for `<DOMAIN_NAME>`.
- WAF in Detection first, then Prevention.
- Application Gateway backend health is green.

Identity:

- App registration supports organizational and personal Microsoft accounts.
- Redirect URI is exactly `https://<DOMAIN_NAME>/auth/callback`.
- Client secret is only in Key Vault.
- Workload Identity federated credentials exist for every service account.

AKS:

- Pods run as non-root.
- Probes pass.
- Network policies do not block required traffic.
- Services can read Key Vault through private endpoint.
- Services can connect to PostgreSQL privately.

Data:

- PostgreSQL migration completed.
- `pgcrypto` extension is allowed.
- Storage containers exist.
- Blob access works using managed identity.

Observability:

- Logs arrive in Log Analytics.
- Application Insights connection string is configured.
- Correlation ID appears in service logs.

Security:

- No secret values in repository.
- Key Vault public access disabled.
- Storage public access disabled.
- ACR public access disabled.
- PostgreSQL public access disabled.
- RBAC assignments are scoped to resource level where possible.

## 22. What This Architecture Does Not Add Yet

Not included to avoid going too far:

- Azure Firewall
- Private AKS cluster
- Multi-region active-active deployment
- Separate compliance/audit resource group
- Customer-managed keys everywhere
- Service mesh
- Dedicated API Management

These can be added later if Sentinel moves from integrated deployment to hardened
enterprise production.
