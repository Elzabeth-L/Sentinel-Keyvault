# Sentinel Simple Azure Deployment Guide

This is the lean Azure setup for getting Sentinel running in AKS without overbuilding
the environment. It uses one resource group, Docker Hub images, Azure Database for
PostgreSQL Flexible Server, Key Vault, Storage Account blob storage, and AKS.

Sentinel uses **Azure Database for PostgreSQL Flexible Server**.

This guide avoids ACR, Application Gateway, Azure Firewall, Bastion, Service Bus,
separate audit storage, Log Analytics, and extra resource groups for now. Those can be
added later when you harden the platform.

## Final Shape For Now

```text
User
  |
  | http://<AKS_PUBLIC_IP>
  v
AKS Service LoadBalancer: sentinel-gateway
  |
  +--> Next.js web
  +--> Identity API
  +--> Inventory API + worker
  +--> Relationship API
  +--> Change Intelligence API skeleton
  +--> Operations API skeleton
  +--> Audit API

Azure resources in one resource group:
  rg-sentinel
  vnet-sentinel
  aks-sentinel
  psql-sentinel
  kv-sentinel-<unique>
  stsentinel<unique>
  id-sentinel-app
  app-sentinel-auth
  vm-docker-build
```

## Important Reality Check About Public IP Login

Using the AKS LoadBalancer public IP is okay for the first simple deployment. The app
will be reachable at:

```text
http://<AKS_PUBLIC_IP>
```

However, Microsoft Entra sign-in for a public web redirect is much happier with HTTPS
and a real DNS name. If Entra refuses `http://<AKS_PUBLIC_IP>/auth/callback`, the fix
is not more AKS work. The fix is adding a DNS name and HTTPS later.

For now the manifests use:

```text
SENTINEL_FRONTEND_URL=http://REPLACE_ME_SENTINEL_PUBLIC_IP
SENTINEL_MICROSOFT_REDIRECT_URI=http://REPLACE_ME_SENTINEL_PUBLIC_IP/auth/callback
SENTINEL_SESSION_COOKIE_SECURE=false
```

Later, change those to `https://your-domain`.

## Values To Use

Keep names casual and simple:

| Value | Use |
| --- | --- |
| Resource group | `rg-sentinel` |
| Region | your closest low-cost region, for example `Central India` |
| VNet | `vnet-sentinel` |
| AKS subnet | `snet-aks` |
| Private endpoint subnet | `snet-private-endpoints` |
| AKS cluster | `aks-sentinel` |
| PostgreSQL server | `psql-sentinel-<unique>` |
| PostgreSQL database | `sentinel` |
| Storage account | `stsentinel<unique>` |
| Key Vault | `kv-sentinel-<unique>` |
| Managed identity | `id-sentinel-app` |
| Entra app registration | `app-sentinel-auth` |
| Docker build VM | `vm-docker-build` |
| Docker Hub namespace | your Docker Hub username |
| Image tag | `v1` or any tag you choose |

Azure global names must be unique, so add a short suffix where Azure asks for one.

## 1. Create One Resource Group

1. Open Azure Portal.
2. Search for `Resource groups`.
3. Select `Create`.
4. Fill:
   - Subscription: your Azure subscription.
   - Resource group: `rg-sentinel`.
   - Region: same region you will use for AKS.
5. Tags are optional for now.
6. Select `Review + create`.
7. Select `Create`.

No explicit resource provider registration is required here. Azure Portal usually
handles registration when you create resources. If Azure blocks creation because a
provider is not registered, register only that provider at that time.

## 2. Create A Virtual Network

1. Search for `Virtual networks`.
2. Select `Create`.
3. Basics:
   - Resource group: `rg-sentinel`.
   - Name: `vnet-sentinel`.
   - Region: same as the resource group.
4. IP addresses:
   - Address space: `10.20.0.0/16`.
5. Add subnet:
   - Name: `snet-aks`.
   - Address range: `10.20.1.0/24`.
6. Add subnet:
   - Name: `snet-private-endpoints`.
   - Address range: `10.20.2.0/24`.
7. Security:
   - Bastion: `Disable`.
   - Firewall: `Disable`.
   - DDoS protection: `Disable`.
8. Select `Review + create`.
9. Select `Create`.

The private endpoint subnet is optional for the cheapest possible setup, but keeping
it in the VNet now makes it easier to add private endpoints during PostgreSQL, Storage,
or Key Vault creation.

## 3. Create Microsoft Entra App Registration

This is your login application. It must allow personal Microsoft accounts too.

1. Search for `Microsoft Entra ID`.
2. Open `App registrations`.
3. Select `New registration`.
4. Fill:
   - Name: `app-sentinel-auth`.
   - Supported account types:
     `Accounts in any organizational directory and personal Microsoft accounts`.
   - Redirect URI platform: `Web`.
   - Redirect URI:
     `http://REPLACE_ME_SENTINEL_PUBLIC_IP/auth/callback`.
5. Select `Register`.

After creation:

1. Copy `Application (client) ID`.
2. Copy `Directory (tenant) ID`.
3. Open `Authentication`.
4. Confirm:
   - Web redirect URI: `http://REPLACE_ME_SENTINEL_PUBLIC_IP/auth/callback`.
   - Access tokens implicit grant: unchecked.
   - ID tokens implicit grant: unchecked.
   - Allow public client flows: `No`.
5. If Azure Portal refuses the public IP HTTP redirect, use a DNS+HTTPS redirect later.

Create the client secret:

1. Open `Certificates & secrets`.
2. Select `New client secret`.
3. Description: `sentinel-auth`.
4. Expiry: choose what you can manage, for example 6 months.
5. Select `Add`.
6. Copy the secret value immediately.

Add delegated Azure access:

1. Open `API permissions`.
2. Select `Add a permission`.
3. Select `APIs my organization uses`.
4. Search for `Azure Service Management`.
5. Add delegated permission `user_impersonation`.

Sentinel requests normal sign-in scopes plus:

```text
https://management.azure.com/user_impersonation
```

That is what lets a signed-in user discover Azure subscriptions/resources that their
own Microsoft account can access.

## 4. Create Azure Database For PostgreSQL Flexible Server

This is required. Sentinel stores users, tenants, resources, relationships, operations,
assessments, and audit/activity records in PostgreSQL.

1. Search for `Azure Database for PostgreSQL flexible servers`.
2. Select `Create`.
3. Basics:
   - Resource group: `rg-sentinel`.
   - Server name: `psql-sentinel-<unique>`.
   - Region: same as AKS.
   - PostgreSQL version: `16`.
   - Workload type: choose the lowest/dev option available.
   - Compute tier: `Burstable`.
   - Compute size: choose the smallest available option, usually `Standard_B1ms` or
     `Standard_B2s` depending on region availability.
   - Storage: minimum allowed by the Portal.
   - Storage auto-grow: `Disabled` if you want strict cost control, otherwise
     `Enabled`.
   - Availability zone: `No preference`.
   - High availability: `Disabled`.
   - Admin username: `sentinel_admin`.
   - Password: generate a strong password.
4. Networking:
   - For simplest setup: `Public access`.
   - Allow public access from any Azure service within Azure: `Unchecked` for now.
   - Do not add `0.0.0.0 - 255.255.255.255`.
   - Select `+ Add current client IP address`.
   - Firewall rule name: `my-laptop`.
   - Start IP address: your current public IP shown by the Portal.
   - End IP address: same as your current public IP.
   - Later, add a rule for the Docker VM public IP before running migrations.
   - Later, add a rule for the AKS outbound public IP before the pods connect to
     PostgreSQL.
5. Security:
   - Require secure transport: `Enabled`.
6. Backup:
   - Retention: minimum allowed, commonly `7 days`.
   - Geo-redundant backup: `Disabled`.
7. Select `Review + create`.
8. Select `Create`.

Create the database:

1. Open the PostgreSQL server.
2. Go to `Databases`.
3. Select `Add`.
4. Database name: `sentinel`.
5. Select `Save`.

Connection string format:

```text
postgresql+asyncpg://sentinel_admin:<PASSWORD>@psql-sentinel-<unique>.postgres.database.azure.com:5432/sentinel?ssl=require
```

Firewall rules you should end up with:

| Rule name | Start IP | End IP | When |
| --- | --- | --- | --- |
| `my-laptop` | your current public IP | same IP | During PostgreSQL creation |
| `docker-vm` | Docker VM public IP | same IP | Before running migration |
| `aks-outbound` | AKS outbound public IP | same IP | Before deploying app pods |

Keep `Allow public access from any Azure service within Azure` unchecked unless you are
temporarily debugging connectivity and cannot identify the exact AKS outbound IP.

## 5. Create Storage Account Blob Storage

Blob storage is not required for the first API calls, but it is part of Sentinel's
platform for future exports, reports, inventory snapshots, and operation artifacts.
Use one normal storage account for now.

1. Search for `Storage accounts`.
2. Select `Create`.
3. Basics:
   - Resource group: `rg-sentinel`.
   - Storage account name: `stsentinel<unique>`.
   - Region: same as AKS.
   - Performance: `Standard`.
   - Redundancy: `Locally-redundant storage (LRS)`.
4. Advanced:
   - Require secure transfer: `Enabled`.
   - Minimum TLS version: `Version 1.2`.
   - Allow Blob anonymous access: `Disabled`.
   - Allow storage account key access: `Enabled` for now, can be disabled later after
     managed identity access is fully wired.
5. Networking:
   - Public network access: `Enable`.
   - Public network access scope:
     `Enable from selected virtual networks and IP addresses`.
   - Virtual network subscription: your Azure subscription.
   - Virtual network: leave `None` for now unless you already know the exact subnet
     that should access Storage.
   - IPv4 addresses: select `+ Add your client IPv4 address`.
   - Do not choose `Enable from all networks`.
   - Private endpoint: skip for now.
   - Routing preference: `Microsoft network routing`.
6. Data protection:
   - Soft delete for blobs: optional, `7 days` is enough for now.
   - Versioning: optional.
7. Select `Review + create`.
8. Select `Create`.

Create these containers:

```text
inventory-snapshots
change-reports
operation-artifacts
exports
```

This keeps the storage account from being open to the whole internet. It is still a
public endpoint, but only selected IPs/networks can access it. Later, add the Docker VM
public IP and AKS outbound public IP if those workloads need direct blob access.

Private endpoints are better for a hardened setup, but they are not worth adding right
now unless you are ready to manage private DNS and subnet access. Skipping private
endpoints here does not mean the storage account is open to everyone, as long as
`Enable from selected virtual networks and IP addresses` is selected.

Separate immutable audit storage is intentionally not created now. The current app
keeps audit/activity records in PostgreSQL. Add immutable audit blob storage later
when you need compliance evidence exports.

## 6. Create Key Vault

Key Vault is required because secrets should not be in source code or Kubernetes YAML.

1. Search for `Key vaults`.
2. Select `Create`.
3. Basics:
   - Resource group: `rg-sentinel`.
   - Key vault name: `kv-sentinel-<unique>`.
   - Region: same as AKS.
   - Pricing tier: `Standard`.
4. Access configuration:
   - Permission model: `Azure role-based access control`.
5. Networking:
   - Public network access: `Disabled`.
   - Private endpoint: `Create`.
   - Private endpoint name: `pe-kv-sentinel`.
   - Target sub-resource: `vault`.
   - Virtual network: `vnet-sentinel`.
   - Subnet: `snet-private-endpoints`.
   - Private DNS integration: `Yes`.
   - Private DNS zone: `privatelink.vaultcore.azure.net`.
6. Soft-delete:
   - Enable soft-delete: `Enabled`.
   - Purge protection: optional for now. Enable later when this is no longer a throwaway
     setup.
7. Select `Review + create`.
8. Select `Create`.

Create these secrets:

```text
identity-database-url
identity-microsoft-client-secret
identity-session-secret
identity-token-encryption-key
inventory-database-url
relationship-database-url
intelligence-database-url
operations-database-url
audit-database-url
internal-service-token
```

For this simple setup, all `*-database-url` secrets can use the same PostgreSQL
connection string.

Generate `identity-session-secret` and `internal-service-token` as long random strings.
Generate `identity-token-encryption-key` as a Fernet key if the code expects one.

Because public network access is disabled, your laptop may not be able to read or
write Key Vault secrets directly. If the Portal or CLI blocks secret creation from
your laptop, add the secrets from a machine that can reach the private endpoint, such
as the Docker VM inside `vnet-sentinel`.

## 7. Create User-Assigned Managed Identity

One managed identity is enough for now. Later you can split identity per service.

1. Search for `Managed identities`.
2. Select `Create`.
3. Fill:
   - Resource group: `rg-sentinel`.
   - Region: same as AKS.
   - Name: `id-sentinel-app`.
4. Select `Review + create`.
5. Select `Create`.
6. Copy its `Client ID`.

Grant Key Vault access:

1. Open `kv-sentinel-<unique>`.
2. Open `Access control (IAM)`.
3. Select `Add role assignment`.
4. Role: `Key Vault Secrets User`.
5. Members: `id-sentinel-app`.
6. Save.

Optional storage access:

1. Open `stsentinel<unique>`.
2. Open `Access control (IAM)`.
3. Add role `Storage Blob Data Contributor`.
4. Member: `id-sentinel-app`.

## 8. Create AKS Cluster

1. Search for `Kubernetes services`.
2. Select `Create` > `Create a Kubernetes cluster`.
3. Basics:
   - Resource group: `rg-sentinel`.
   - Cluster name: `aks-sentinel`.
   - Region: same as other resources.
   - Availability zones: leave default or disabled.
   - AKS pricing tier: `Free`.
   - Kubernetes version: default stable version.
4. Node pools:
   - Use one system node pool only.
   - Node size: smallest size that can run the pods, usually `Standard_B2s` or
     `Standard_B2ms`.
   - Scale method: `Manual`.
   - Node count: `1` for lowest cost, `2` if one node is too tight.
5. Networking:
   - Network configuration: `Azure CNI` if available and simple in your Portal flow.
   - Virtual network: `vnet-sentinel`.
   - Cluster subnet: `snet-aks`.
   - Network policy: `Azure` or `Cilium` if offered. NetworkPolicies need this.
   - Load balancer: `Standard`.
6. Integrations:
   - Container registry: none. You are using Docker Hub.
7. Monitoring:
   - Disable Container Insights/managed Prometheus for now to reduce cost.
8. Advanced:
   - Enable OIDC issuer: `Yes`.
   - Enable Workload Identity: `Yes`.
   - Enable Azure Key Vault Secrets Provider: `Yes`.
9. Select `Review + create`.
10. Select `Create`.

After creation, connect:

```powershell
az aks get-credentials --resource-group rg-sentinel --name aks-sentinel
kubectl get nodes
```

## 9. Add Federated Credentials For Workload Identity

The manifests use these Kubernetes service accounts:

```text
sentinel-app/web
sentinel-app/identity-service
sentinel-app/inventory-service
sentinel-app/relationship-service
sentinel-app/change-intelligence-service
sentinel-app/operations-service
sentinel-app/audit-service
sentinel-workers/inventory-worker
sentinel-workers/outbox-relay
```

For each service account, add a federated credential to `id-sentinel-app`.

1. Open `id-sentinel-app`.
2. Open `Federated credentials`.
3. Select `Add credential`.
4. Scenario: `Kubernetes accessing Azure resources`.
5. Cluster issuer URL: copy from AKS `OIDC issuer URL`.
6. Namespace: use the namespace from the list above.
7. Service account: use the service account from the list above.
8. Name: for example `fc-identity-service`.
9. Audience: `api://AzureADTokenExchange`.
10. Save.

Repeat for all service accounts above.

## 10. Create Docker Build VM

Use this VM only to build and push Docker images if your laptop is not set up.

1. Search for `Virtual machines`.
2. Select `Create`.
3. Basics:
   - Resource group: `rg-sentinel`.
   - VM name: `vm-docker-build`.
   - Region: same region.
   - Image: Ubuntu Server 22.04 LTS or 24.04 LTS.
   - Size: small but usable, for example `Standard_B2s`.
   - Authentication: SSH public key.
   - Public inbound ports: allow SSH from your IP only.
4. Disks:
   - OS disk type: Standard SSD or Standard HDD for cost.
   - Size: 64 GiB or larger if Docker builds run out of space.
5. Networking:
   - VNet: `vnet-sentinel`.
   - Subnet: `snet-aks` or create a small `snet-vms`.
   - Public IP: yes, for SSH simplicity.
   - NSG: allow SSH only from your IP.
6. Monitoring:
   - Boot diagnostics: optional.
7. Select `Review + create`.
8. Select `Create`.

On the VM:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin
sudo usermod -aG docker $USER
```

Log out and back in, then clone/copy the Sentinel repo to the VM.

## 11. Build And Push Docker Images

Run these commands from the repository root on the Docker VM.

```bash
docker login

DOCKERHUB="your-dockerhub-username"
TAG="v1"
PUBLIC_IP="REPLACE_ME_SENTINEL_PUBLIC_IP"

docker build -t $DOCKERHUB/sentinel-identity-service:$TAG -f apps/identity-service/Dockerfile .
docker build -t $DOCKERHUB/sentinel-inventory-service:$TAG -f apps/inventory-service/Dockerfile .
docker build -t $DOCKERHUB/sentinel-relationship-service:$TAG -f apps/relationship-service/Dockerfile .
docker build -t $DOCKERHUB/sentinel-change-intelligence-service:$TAG -f apps/change-intelligence-service/Dockerfile .
docker build -t $DOCKERHUB/sentinel-operations-service:$TAG -f apps/operations-service/Dockerfile .
docker build -t $DOCKERHUB/sentinel-audit-service:$TAG -f apps/audit-service/Dockerfile .
docker build -t $DOCKERHUB/sentinel-migration:$TAG -f apps/migration/Dockerfile .
docker build \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://$PUBLIC_IP/api/v1 \
  -t $DOCKERHUB/sentinel-web:$TAG \
  -f apps/web/Dockerfile .

docker push $DOCKERHUB/sentinel-identity-service:$TAG
docker push $DOCKERHUB/sentinel-inventory-service:$TAG
docker push $DOCKERHUB/sentinel-relationship-service:$TAG
docker push $DOCKERHUB/sentinel-change-intelligence-service:$TAG
docker push $DOCKERHUB/sentinel-operations-service:$TAG
docker push $DOCKERHUB/sentinel-audit-service:$TAG
docker push $DOCKERHUB/sentinel-migration:$TAG
docker push $DOCKERHUB/sentinel-web:$TAG
```

If you do not know the AKS public IP yet, build the backend images first, deploy the
gateway, get the public IP, then rebuild and push only `sentinel-web`.

## 12. Run Database Migration

Migration just means: create/update the PostgreSQL tables the application needs. It is
not an extra Azure service.

Run this once from the Docker VM after PostgreSQL is reachable:

```bash
DOCKERHUB="your-dockerhub-username"
TAG="v1"
DATABASE_URL='postgresql+asyncpg://sentinel_admin:<PASSWORD>@psql-sentinel-<unique>.postgres.database.azure.com:5432/sentinel?ssl=require'

docker run --rm \
  -e SENTINEL_DATABASE_URL="$DATABASE_URL" \
  $DOCKERHUB/sentinel-migration:$TAG
```

Keep this migration image because it is the cleanest way to apply database schema
changes. The Kubernetes migration Job was removed for now to keep the AKS deployment
simple.

## 13. Update Kubernetes Placeholders

Edit files under `deploy/kubernetes`.

In all Deployment files, replace:

```text
REPLACE_ME_DOCKERHUB_USERNAME
REPLACE_ME_IMAGE_TAG
```

In `01-config.yaml`, replace:

```text
REPLACE_ME_IDENTITY_APP_CLIENT_ID
REPLACE_ME_PROVIDER_ENTRA_TENANT_ID
REPLACE_ME_SENTINEL_PUBLIC_IP
```

In `02-service-accounts.yaml` and `03-secret-provider-classes.yaml`, replace:

```text
REPLACE_ME_SENTINEL_UAMI_CLIENT_ID
REPLACE_ME_KEY_VAULT_NAME
REPLACE_ME_PROVIDER_ENTRA_TENANT_ID
```

In `40-network-policies.yaml`, replace:

```text
REPLACE_ME_POSTGRES_PRIVATE_IP_OR_CIDR
```

If PostgreSQL uses public access and you cannot identify a stable private IP/CIDR, you
can temporarily loosen the PostgreSQL egress policy during first testing. Tighten it
later.

## 14. Deploy To AKS

```powershell
kubectl apply -f deploy/kubernetes/00-namespaces.yaml
kubectl apply -f deploy/kubernetes/01-config.yaml
kubectl apply -f deploy/kubernetes/02-service-accounts.yaml
kubectl apply -f deploy/kubernetes/03-secret-provider-classes.yaml
kubectl apply -f deploy/kubernetes/04-resource-governance.yaml
kubectl apply -f deploy/kubernetes/10-web.yaml
kubectl apply -f deploy/kubernetes/11-identity-service.yaml
kubectl apply -f deploy/kubernetes/12-inventory-service.yaml
kubectl apply -f deploy/kubernetes/13-relationship-service.yaml
kubectl apply -f deploy/kubernetes/14-change-intelligence-service.yaml
kubectl apply -f deploy/kubernetes/15-operations-service.yaml
kubectl apply -f deploy/kubernetes/16-audit-service.yaml
kubectl apply -f deploy/kubernetes/20-workers.yaml
kubectl apply -f deploy/kubernetes/40-network-policies.yaml
kubectl apply -f deploy/kubernetes/50-gateway-loadbalancer.yaml
```

Get the public IP:

```powershell
kubectl get svc sentinel-gateway -n sentinel-app
```

If this is the first time you learned the public IP:

1. Update the Entra redirect URI.
2. Update `01-config.yaml`.
3. Rebuild and push `sentinel-web` with the real public IP.
4. Reapply config and restart pods:

```powershell
kubectl apply -f deploy/kubernetes/01-config.yaml
kubectl rollout restart deployment/web -n sentinel-app
kubectl rollout restart deployment/identity-service -n sentinel-app
```

## 15. Verify

```powershell
kubectl get pods -n sentinel-app
kubectl get pods -n sentinel-workers
kubectl get svc sentinel-gateway -n sentinel-app
kubectl logs deployment/identity-service -n sentinel-app
kubectl logs deployment/inventory-service -n sentinel-app
```

Open:

```text
http://<AKS_PUBLIC_IP>
```

Health checks:

```text
http://<AKS_PUBLIC_IP>/api/v1/auth/health/live
http://<AKS_PUBLIC_IP>/api/v1/inventory/health/live
```

## Why Audit Still Exists In The App

Audit is not an Azure resource here. It is one Sentinel microservice and a set of
PostgreSQL tables. It records user activity, operations, approvals, and service events.
That is useful even in the first MVP because it shows who did what.

What was removed for now:

- separate immutable audit storage account
- audit export pipeline
- compliance retention configuration

Those can come later.

## What We Are Not Creating Now

Do not create these unless you decide to harden the deployment later:

- Azure Container Registry
- Application Gateway
- Azure Firewall
- Azure Bastion
- Service Bus
- Log Analytics / Application Insights / Azure Monitor workspace
- separate audit storage account
- private AKS cluster
- multiple resource groups
- multiple managed identities per microservice

## Cleanup

For a simple test environment, deleting `rg-sentinel` removes all Azure resources from
this guide.

## Demo Extension: Deploy Only Auth Plus Inventory

Use this extension if you only want a quick demo now and do not want every
microservice running.

This keeps the full platform files in the repository, but runs only:

```text
web
identity-service
inventory-service
optional inventory-worker
sentinel-gateway
```

That gives you:

- Microsoft login
- profile/session validation
- inventory API health
- subscription/resource discovery path if `inventory-worker` is also running

The other services can stay present in the manifests and be scaled to zero.

### Demo Step 9: Federated Credentials

For the demo, create federated credentials only for these service accounts:

```text
sentinel-app/web
sentinel-app/identity-service
sentinel-app/inventory-service
sentinel-workers/inventory-worker
```

You can skip these until later:

```text
sentinel-app/relationship-service
sentinel-app/change-intelligence-service
sentinel-app/operations-service
sentinel-app/audit-service
sentinel-workers/outbox-relay
```

If a skipped workload is scaled to zero, it does not need Key Vault access yet.

### Demo Step 11: Build Fewer Images

Build and push only these images:

```bash
docker login

DOCKERHUB="your-dockerhub-username"
TAG="v1"
PUBLIC_IP="REPLACE_ME_SENTINEL_PUBLIC_IP"

docker build -t $DOCKERHUB/sentinel-identity-service:$TAG -f apps/identity-service/Dockerfile .
docker build -t $DOCKERHUB/sentinel-inventory-service:$TAG -f apps/inventory-service/Dockerfile .
docker build -t $DOCKERHUB/sentinel-migration:$TAG -f apps/migration/Dockerfile .
docker build \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://$PUBLIC_IP/api/v1 \
  -t $DOCKERHUB/sentinel-web:$TAG \
  -f apps/web/Dockerfile .

docker push $DOCKERHUB/sentinel-identity-service:$TAG
docker push $DOCKERHUB/sentinel-inventory-service:$TAG
docker push $DOCKERHUB/sentinel-migration:$TAG
docker push $DOCKERHUB/sentinel-web:$TAG
```

If you do not know the public IP yet, build the backend and migration images first.
After the gateway public IP exists, rebuild only `sentinel-web`.

### Demo Step 12: Run Migration

Still run the migration once. Even a tiny demo needs the database tables.

```bash
DOCKERHUB="your-dockerhub-username"
TAG="v1"
DATABASE_URL='postgresql+asyncpg://sentinel_admin:<PASSWORD>@psql-sentinel-<unique>.postgres.database.azure.com:5432/sentinel?ssl=require'

docker run --rm \
  -e SENTINEL_DATABASE_URL="$DATABASE_URL" \
  $DOCKERHUB/sentinel-migration:$TAG
```

### Demo Step 13: Replace Placeholders

Replace placeholders only for the files you apply.

Required:

```text
00-namespaces.yaml
01-config.yaml
02-service-accounts.yaml
03-secret-provider-classes.yaml
04-resource-governance.yaml
10-web.yaml
11-identity-service.yaml
12-inventory-service.yaml
20-workers.yaml
40-network-policies.yaml
50-gateway-loadbalancer.yaml
```

You still need Key Vault secrets for:

```text
identity-database-url
identity-microsoft-client-secret
identity-session-secret
identity-token-encryption-key
inventory-database-url
internal-service-token
```

### Demo Step 14: Apply Minimal Runtime

Apply the shared/base files:

```powershell
kubectl apply -f deploy/kubernetes/00-namespaces.yaml
kubectl apply -f deploy/kubernetes/01-config.yaml
kubectl apply -f deploy/kubernetes/02-service-accounts.yaml
kubectl apply -f deploy/kubernetes/03-secret-provider-classes.yaml
kubectl apply -f deploy/kubernetes/04-resource-governance.yaml
```

Apply the demo workloads:

```powershell
kubectl apply -f deploy/kubernetes/10-web.yaml
kubectl apply -f deploy/kubernetes/11-identity-service.yaml
kubectl apply -f deploy/kubernetes/12-inventory-service.yaml
kubectl apply -f deploy/kubernetes/20-workers.yaml
```

Scale down `outbox-relay` if you are not running Audit:

```powershell
kubectl scale deployment/outbox-relay -n sentinel-workers --replicas=0
```

The gateway references all API Service names. To avoid Nginx failing DNS resolution,
create the remaining Service objects by applying those service files, then scale their
Deployments to zero:

```powershell
kubectl apply -f deploy/kubernetes/13-relationship-service.yaml
kubectl apply -f deploy/kubernetes/14-change-intelligence-service.yaml
kubectl apply -f deploy/kubernetes/15-operations-service.yaml
kubectl apply -f deploy/kubernetes/16-audit-service.yaml

kubectl scale deployment/relationship-service -n sentinel-app --replicas=0
kubectl scale deployment/change-intelligence-service -n sentinel-app --replicas=0
kubectl scale deployment/operations-service -n sentinel-app --replicas=0
kubectl scale deployment/audit-service -n sentinel-app --replicas=0
```

Then apply networking and the gateway:

```powershell
kubectl apply -f deploy/kubernetes/40-network-policies.yaml
kubectl apply -f deploy/kubernetes/50-gateway-loadbalancer.yaml
```

Get the public IP:

```powershell
kubectl get svc sentinel-gateway -n sentinel-app
```

After the IP exists, update Entra redirect URI, update `01-config.yaml`, rebuild the
web image with the real `NEXT_PUBLIC_API_BASE_URL`, reapply config, and restart:

```powershell
kubectl apply -f deploy/kubernetes/01-config.yaml
kubectl rollout restart deployment/web -n sentinel-app
kubectl rollout restart deployment/identity-service -n sentinel-app
```

### Demo Step 15: Verify Demo

Expected running pods:

```text
web
identity-service
inventory-service
inventory-worker
sentinel-gateway
```

Expected scaled-to-zero Deployments:

```text
relationship-service
change-intelligence-service
operations-service
audit-service
outbox-relay
```

Check:

```powershell
kubectl get pods -n sentinel-app
kubectl get pods -n sentinel-workers
kubectl get svc sentinel-gateway -n sentinel-app
```

Open:

```text
http://<AKS_PUBLIC_IP>
```

Health checks:

```text
http://<AKS_PUBLIC_IP>/api/v1/auth/health/live
http://<AKS_PUBLIC_IP>/api/v1/inventory/health/live
```

When you are ready for the full platform, build the remaining images, add the skipped
federated credentials, and scale the remaining Deployments back to `1`.

## Minimal Demo Steps From Step 9 Onward

Use this section instead of the full Step 9 onward flow when you only want the demo
version running.

This demo deploys only:

```text
web
identity-service
inventory-service
sentinel-gateway
```

Optional:

```text
inventory-worker
```

Do not deploy Relationship, Change Intelligence, Operations, Audit, or Outbox Relay for
this minimal demo.

### Minimal Step 9: Add Federated Credentials

Create federated credentials only for:

```text
sentinel-app/web
sentinel-app/identity-service
sentinel-app/inventory-service
```

If you want inventory refresh/discovery worker running, also create:

```text
sentinel-workers/inventory-worker
```

Skip these for now:

```text
sentinel-app/relationship-service
sentinel-app/change-intelligence-service
sentinel-app/operations-service
sentinel-app/audit-service
sentinel-workers/outbox-relay
```

For each federated credential:

1. Open `id-sentinel-app`.
2. Open `Federated credentials`.
3. Select `Add credential`.
4. Scenario: `Kubernetes accessing Azure resources`.
5. Cluster issuer URL: copy from AKS `OIDC issuer URL`.
6. Namespace: use `sentinel-app` or `sentinel-workers`.
7. Service account: use the service account name from the list above.
8. Name: for example `fc-identity-service`.
9. Audience: `api://AzureADTokenExchange`.
10. Save.

### Minimal Step 10: Docker Build VM

Create the Docker VM the same way as the normal guide.

You still need the VM for:

```text
building images
pushing images to Docker Hub
running the database migration command
```

### Minimal Step 11: Build And Push Images

Run these commands from the repository root on the Docker VM:

```bash
docker login

DOCKERHUB="your-dockerhub-username"
TAG="v1"
PUBLIC_IP="REPLACE_ME_SENTINEL_PUBLIC_IP"

docker build -t $DOCKERHUB/sentinel-identity-service:$TAG -f apps/identity-service/Dockerfile .
docker build -t $DOCKERHUB/sentinel-inventory-service:$TAG -f apps/inventory-service/Dockerfile .
docker build -t $DOCKERHUB/sentinel-migration:$TAG -f apps/migration/Dockerfile .
docker build \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://$PUBLIC_IP/api/v1 \
  -t $DOCKERHUB/sentinel-web:$TAG \
  -f apps/web/Dockerfile .

docker push $DOCKERHUB/sentinel-identity-service:$TAG
docker push $DOCKERHUB/sentinel-inventory-service:$TAG
docker push $DOCKERHUB/sentinel-migration:$TAG
docker push $DOCKERHUB/sentinel-web:$TAG
```

If the AKS public IP is not known yet, use this order:

1. Build and push `identity-service`, `inventory-service`, and `migration`.
2. Deploy the gateway once.
3. Get the public IP.
4. Rebuild and push only `sentinel-web` with the real public IP.

### Minimal Step 12: Run Database Migration

Run migration once. This is still required because PostgreSQL starts empty.

```bash
DOCKERHUB="your-dockerhub-username"
TAG="v1"
DATABASE_URL='postgresql+asyncpg://sentinel_admin:<PASSWORD>@psql-sentinel-<unique>.postgres.database.azure.com:5432/sentinel?ssl=require'

docker run --rm \
  -e SENTINEL_DATABASE_URL="$DATABASE_URL" \
  $DOCKERHUB/sentinel-migration:$TAG
```

### Minimal Step 13: Replace Placeholders

For the minimal demo, replace placeholders in these files:

```text
deploy/kubernetes/00-namespaces.yaml
deploy/kubernetes/01-config.yaml
deploy/kubernetes/02-service-accounts.yaml
deploy/kubernetes/03-secret-provider-classes.yaml
deploy/kubernetes/04-resource-governance.yaml
deploy/kubernetes/10-web.yaml
deploy/kubernetes/11-identity-service.yaml
deploy/kubernetes/12-inventory-service.yaml
deploy/kubernetes/40-network-policies.yaml
deploy/kubernetes/50-gateway-loadbalancer.yaml
```

Only if you are running `inventory-worker`, also replace placeholders in:

```text
deploy/kubernetes/20-workers.yaml
```

Required Key Vault secrets for the minimal demo:

```text
identity-database-url
identity-microsoft-client-secret
identity-session-secret
identity-token-encryption-key
inventory-database-url
internal-service-token
```

For the minimal demo, you do not need these yet:

```text
relationship-database-url
intelligence-database-url
operations-database-url
audit-database-url
```

### Minimal Step 14: Deploy To AKS

Apply the base files:

```powershell
kubectl apply -f deploy/kubernetes/00-namespaces.yaml
kubectl apply -f deploy/kubernetes/01-config.yaml
kubectl apply -f deploy/kubernetes/02-service-accounts.yaml
kubectl apply -f deploy/kubernetes/03-secret-provider-classes.yaml
kubectl apply -f deploy/kubernetes/04-resource-governance.yaml
```

Apply only the minimal demo services:

```powershell
kubectl apply -f deploy/kubernetes/10-web.yaml
kubectl apply -f deploy/kubernetes/11-identity-service.yaml
kubectl apply -f deploy/kubernetes/12-inventory-service.yaml
```

If you want the inventory worker:

```powershell
kubectl apply -f deploy/kubernetes/20-workers.yaml
kubectl scale deployment/outbox-relay -n sentinel-workers --replicas=0
```

Apply networking:

```powershell
kubectl apply -f deploy/kubernetes/40-network-policies.yaml
```

Important for the minimal demo:

The current gateway config contains routes for all Sentinel APIs. If you do not deploy
the other API Services, Nginx may fail when it starts because those DNS names do not
exist.

For the minimal demo, create placeholder Kubernetes Services for the skipped APIs:

```powershell
kubectl create service clusterip relationship-service `
  --tcp=80:8000 `
  -n sentinel-app `
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create service clusterip change-intelligence-service `
  --tcp=80:8000 `
  -n sentinel-app `
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create service clusterip operations-service `
  --tcp=80:8000 `
  -n sentinel-app `
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create service clusterip audit-service `
  --tcp=80:8000 `
  -n sentinel-app `
  --dry-run=client -o yaml | kubectl apply -f -
```

Then apply the gateway:

```powershell
kubectl apply -f deploy/kubernetes/50-gateway-loadbalancer.yaml
```

Get the public IP:

```powershell
kubectl get svc sentinel-gateway -n sentinel-app
```

After the IP exists:

1. Add/update Entra redirect URI:

```text
http://<AKS_PUBLIC_IP>/auth/callback
```

2. Update `deploy/kubernetes/01-config.yaml`:

```text
SENTINEL_MICROSOFT_REDIRECT_URI=http://<AKS_PUBLIC_IP>/auth/callback
SENTINEL_FRONTEND_URL=http://<AKS_PUBLIC_IP>
SENTINEL_CORS_ORIGINS=http://<AKS_PUBLIC_IP>
```

3. Rebuild and push the web image:

```bash
DOCKERHUB="your-dockerhub-username"
TAG="v1"
PUBLIC_IP="<AKS_PUBLIC_IP>"

docker build \
  --build-arg NEXT_PUBLIC_API_BASE_URL=http://$PUBLIC_IP/api/v1 \
  -t $DOCKERHUB/sentinel-web:$TAG \
  -f apps/web/Dockerfile .

docker push $DOCKERHUB/sentinel-web:$TAG
```

4. Reapply config and restart:

```powershell
kubectl apply -f deploy/kubernetes/01-config.yaml
kubectl rollout restart deployment/web -n sentinel-app
kubectl rollout restart deployment/identity-service -n sentinel-app
```

### Minimal Step 15: Verify

Check pods:

```powershell
kubectl get pods -n sentinel-app
kubectl get pods -n sentinel-workers
```

Expected running app pods:

```text
web
identity-service
inventory-service
sentinel-gateway
```

If you deployed the worker, also expect:

```text
inventory-worker
```

Open:

```text
http://<AKS_PUBLIC_IP>
```

Health checks:

```text
http://<AKS_PUBLIC_IP>/api/v1/auth/health/live
http://<AKS_PUBLIC_IP>/api/v1/inventory/health/live
```

When you want the full platform later, build the remaining service images, create the
remaining federated credentials, create the remaining Key Vault database URL secrets,
and apply the normal full deployment steps.
