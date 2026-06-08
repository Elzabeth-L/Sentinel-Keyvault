# Sentinel Integrated Deployment Placeholders

Use this file as the checklist for every value that must be replaced before deployment.

## Core Naming

| Placeholder | Example | Where to get it / create it |
| --- | --- | --- |
| `<SUBSCRIPTION_ID>` | `a8270be7-dabc-4d92-98db-26a55025b0df` | Azure Portal > Subscriptions |
| `<LOCATION>` | `centralindia` | Azure region used for RG resources |
| `<RESOURCE_GROUP>` | `rg-sentinel` | Create in Azure Portal |
| `<DOMAIN_NAME>` | `sentinel.vaultrix.in` | Public DNS name for the app |
| `<DNS_ZONE>` | `vaultrix.in` | Existing public DNS zone/provider |

## Networking

| Placeholder | Example | Notes |
| --- | --- | --- |
| `<VNET_NAME>` | `vnet-sentinel` | Main application VNet |
| `<VNET_CIDR>` | `10.30.0.0/16` | Do not overlap with existing networks |
| `<SNET_APPGW>` | `snet-appgw` | Dedicated Application Gateway subnet |
| `<SNET_APPGW_CIDR>` | `10.30.1.0/24` | App Gateway requires its own subnet |
| `<SNET_AKS>` | `snet-aks` | AKS node subnet |
| `<SNET_AKS_CIDR>` | `10.30.2.0/23` | Larger because pods/nodes consume IPs |
| `<SNET_POSTGRES>` | `snet-postgres` | Delegated to PostgreSQL Flexible Server |
| `<SNET_POSTGRES_CIDR>` | `10.30.4.0/24` | Delegated subnet, no other resources |
| `<SNET_PRIVATE_ENDPOINTS>` | `snet-private-endpoints` | Key Vault, Storage, ACR private endpoints |
| `<SNET_PRIVATE_ENDPOINTS_CIDR>` | `10.30.5.0/24` | Disable private endpoint network policies where required |
| `<SNET_BUILD>` | `snet-build` | Optional Docker/build VM or self-hosted runner subnet |
| `<SNET_BUILD_CIDR>` | `10.30.6.0/24` | Can be skipped if GitHub Actions builds images |

## Edge And TLS

| Placeholder | Example | Notes |
| --- | --- | --- |
| `<FRONT_DOOR_PROFILE>` | `afd-sentinel` | Azure Front Door Premium |
| `<FRONT_DOOR_ENDPOINT>` | `sentinel` | Produces `<name>.azurefd.net` |
| `<FRONT_DOOR_CUSTOM_DOMAIN>` | `sentinel.vaultrix.in` | Custom domain on Front Door |
| `<FRONT_DOOR_WAF_POLICY>` | `waf-afd-sentinel` | Front Door WAF policy |
| `<APPGW_NAME>` | `agw-sentinel` | Application Gateway WAF v2 |
| `<APPGW_PUBLIC_IP>` | `pip-agw-sentinel` | Public IP for App Gateway |
| `<APPGW_WAF_POLICY>` | `waf-agw-sentinel` | Regional WAF policy |
| `<TLS_CERT_SECRET_NAME>` | `sentinel-tls-pfx` | Key Vault secret containing PFX certificate |

## Identity And Auth

| Placeholder | Example | Notes |
| --- | --- | --- |
| `<APP_REG_NAME>` | `app-sentinel-auth` | Microsoft Entra app registration |
| `<APP_CLIENT_ID>` | `ebad3d89-5d7e-4766-8859-6b10be8c48a7` | Application/client ID |
| `<APP_CLIENT_SECRET>` | generated value | Store in Key Vault only |
| `<APP_OBJECT_ID>` | GUID | App registration object ID |
| `<PROVIDER_TENANT_ID>` | `83474cb5-f1fa-4d06-906c-e5dad12ce3b9` | Home tenant where app is registered |
| `<REDIRECT_URI>` | `https://sentinel.vaultrix.in/auth/callback` | Web redirect URI |
| `<LOGOUT_URI>` | `https://sentinel.vaultrix.in/` | Front-channel/logout URI |

## AKS And Container Registry

| Placeholder | Example | Notes |
| --- | --- | --- |
| `<AKS_NAME>` | `aks-sentinel` | Main AKS cluster |
| `<AKS_DNS_PREFIX>` | `aks-sentinel` | AKS DNS prefix |
| `<AKS_NODE_POOL_NAME>` | `system` | System node pool |
| `<AKS_USER_POOL_NAME>` | `apps` | User node pool for microservices |
| `<ACR_NAME>` | `acrsentinel01` | Globally unique, lowercase only |
| `<ACR_LOGIN_SERVER>` | `acrsentinel01.azurecr.io` | From ACR overview page |
| `<INGRESS_INTERNAL_IP>` | `10.30.2.50` | Static private IP for ingress controller service |

## Managed Identities

| Placeholder | Example | Purpose |
| --- | --- | --- |
| `<UAMI_PLATFORM_NAME>` | `id-sentinel-platform` | CSI, basic platform reads |
| `<UAMI_IDENTITY_NAME>` | `id-sentinel-identity` | Identity Service secrets |
| `<UAMI_INVENTORY_NAME>` | `id-sentinel-inventory` | Azure Resource Graph delegated/user-token flows |
| `<UAMI_OPERATIONS_NAME>` | `id-sentinel-operations` | Future approved Azure operations |
| `<UAMI_AUDIT_NAME>` | `id-sentinel-audit` | Audit export/storage access |
| `<UAMI_CLIENT_ID_* >` | GUID | Client ID copied from each managed identity |
| `<UAMI_PRINCIPAL_ID_* >` | GUID | Object/principal ID used for RBAC assignments |

## Data Services

| Placeholder | Example | Notes |
| --- | --- | --- |
| `<POSTGRES_SERVER>` | `psql-sentinel` | Azure PostgreSQL Flexible Server |
| `<POSTGRES_DB>` | `sentinel` | Database name |
| `<POSTGRES_ADMIN>` | `sentinel_admin` | Admin username |
| `<POSTGRES_PASSWORD>` | generated | Store in Key Vault only |
| `<POSTGRES_PRIVATE_DNS_ZONE>` | `privatelink.postgres.database.azure.com` | Linked to VNet |
| `<KEY_VAULT_NAME>` | `kv-sentinel-01` | Globally unique |
| `<STORAGE_ACCOUNT>` | `stsentinel01` | Globally unique, lowercase |
| `<BLOB_PRIVATE_ENDPOINT>` | `pe-st-sentinel-blob` | Blob private endpoint |
| `<KV_PRIVATE_ENDPOINT>` | `pe-kv-sentinel` | Key Vault private endpoint |
| `<ACR_PRIVATE_ENDPOINT>` | `pe-acr-sentinel` | ACR private endpoint |

## Observability And Governance

| Placeholder | Example | Notes |
| --- | --- | --- |
| `<LAW_NAME>` | `law-sentinel` | Log Analytics workspace |
| `<APPINSIGHTS_NAME>` | `appi-sentinel` | Application Insights workspace-based |
| `<DCR_NAME>` | `dcr-sentinel-aks` | Data collection rule |
| `<POLICY_ASSIGNMENT_PREFIX>` | `pa-sentinel` | Azure Policy assignment names |

## Kubernetes Namespaces

| Placeholder | Value |
| --- | --- |
| `<NAMESPACE_APP>` | `sentinel-app` |
| `<NAMESPACE_WORKERS>` | `sentinel-workers` |
| `<NAMESPACE_INGRESS>` | `ingress-nginx` |
| `<NAMESPACE_MONITORING>` | `monitoring` |

## Kubernetes Service Accounts

| Service | Namespace | Managed identity |
| --- | --- | --- |
| `web` | `sentinel-app` | `<UAMI_PLATFORM_NAME>` |
| `identity-service` | `sentinel-app` | `<UAMI_IDENTITY_NAME>` |
| `inventory-service` | `sentinel-app` | `<UAMI_INVENTORY_NAME>` |
| `relationship-service` | `sentinel-app` | `<UAMI_PLATFORM_NAME>` |
| `change-intelligence-service` | `sentinel-app` | `<UAMI_PLATFORM_NAME>` |
| `operations-service` | `sentinel-app` | `<UAMI_OPERATIONS_NAME>` |
| `audit-service` | `sentinel-app` | `<UAMI_AUDIT_NAME>` |
| `inventory-worker` | `sentinel-workers` | `<UAMI_INVENTORY_NAME>` |
| `outbox-relay` | `sentinel-workers` | `<UAMI_AUDIT_NAME>` |

## Key Vault Secrets

| Secret name | Value |
| --- | --- |
| `postgres-runtime-url` | SQLAlchemy async PostgreSQL URL |
| `identity-microsoft-client-secret` | Entra app client secret |
| `identity-session-signing-key` | Random signing key |
| `identity-token-encryption-key` | Fernet key |
| `internal-api-token` | Random internal service token |
| `frontdoor-header-secret` | Random secret checked by App Gateway/ingress if enabled |
| `storage-account-name` | Storage account name if the app needs it |
| `applicationinsights-connection-string` | App Insights connection string |

## Container Images

| Placeholder | Example |
| --- | --- |
| `<IMAGE_TAG>` | `v1.1.0` |
| `<IMAGE_WEB>` | `<ACR_LOGIN_SERVER>/sentinel-web:<IMAGE_TAG>` |
| `<IMAGE_IDENTITY>` | `<ACR_LOGIN_SERVER>/sentinel-identity-service:<IMAGE_TAG>` |
| `<IMAGE_INVENTORY>` | `<ACR_LOGIN_SERVER>/sentinel-inventory-service:<IMAGE_TAG>` |
| `<IMAGE_RELATIONSHIP>` | `<ACR_LOGIN_SERVER>/sentinel-relationship-service:<IMAGE_TAG>` |
| `<IMAGE_CHANGE_INTELLIGENCE>` | `<ACR_LOGIN_SERVER>/sentinel-change-intelligence-service:<IMAGE_TAG>` |
| `<IMAGE_OPERATIONS>` | `<ACR_LOGIN_SERVER>/sentinel-operations-service:<IMAGE_TAG>` |
| `<IMAGE_AUDIT>` | `<ACR_LOGIN_SERVER>/sentinel-audit-service:<IMAGE_TAG>` |
| `<IMAGE_MIGRATION>` | `<ACR_LOGIN_SERVER>/sentinel-migration:<IMAGE_TAG>` |
