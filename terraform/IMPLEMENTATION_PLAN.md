# Sentinel Terraform Implementation Plan

## 1. Purpose

This document is the implementation plan for rebuilding Sentinel's Azure
infrastructure with Terraform for isolated development and production
environments.

This is a planning document only. No Azure resources will be created, changed,
or deleted until the relevant plan has been reviewed and explicitly approved.

## 2. Target Outcome

The target platform will provide:

- Separate Azure subscriptions and Terraform state for development and
  production.
- One workload resource group per environment, plus a dedicated Terraform state
  resource group.
- Azure Front Door Premium with WAF as the production global entry point.
- Application Gateway WAF v2 as the regional ingress layer.
- Production AKS with separate system and user node pools, and development AKS
  with one combined node pool.
- Azure Container Registry instead of Docker Hub.
- Private Azure Key Vault, Storage, PostgreSQL, and ACR connectivity.
- Microsoft Entra ID, managed identities, Workload Identity, RBAC, and Azure
  Policy.
- Central logging, metrics, alerts, backup, and disaster-recovery controls.
- No application credentials embedded in Terraform or Kubernetes manifests.

## 3. Safety Gates

### 3.1 Confirmed subscription boundary

Both environments are in Microsoft Entra tenant
`83474cb5-f1fa-4d06-906c-e5dad12ce3b9`:

| Environment | Subscription | Subscription ID |
|---|---|---|
| Development | `sentinel-dev` | `6b01db76-626a-44a2-8119-17682410914a` |
| Production | `sentinel-prod` | `a8270be7-dabc-4d92-98db-26a55025b0df` |

Terraform provider configuration and GitHub environments will validate these
IDs explicitly. A development workflow must fail rather than run against the
production subscription, and vice versa.

### 3.2 No automatic cleanup

Before any deletion:

1. Export an inventory from subscription
   `6b01db76-626a-44a2-8119-17682410914a`.
2. Define an explicit allow-list of resource groups that may be deleted.
3. Protect Terraform state, DNS, Entra, and shared resources from deletion.
4. Obtain a separate, explicit approval for the deletion command.

### 3.3 Apply approval

Every environment will follow:

1. Format and static validation.
2. Security and policy checks.
3. Terraform plan saved as an artifact.
4. Human review of additions, modifications, replacements, and deletions.
5. Explicit approval before `terraform apply`.

Pushing to the configured branch will trigger the workflow directly; pull
requests are not required. Production apply will still use a protected GitHub
environment approval so an accidental push cannot immediately destroy or
replace production resources.

## 4. Environment Model

Environment-based folders are selected instead of Terraform CLI workspaces.
Each environment will have:
environment will have:

- A separate Azure subscription.
- A separate root module.
- A separate backend storage account and state key.
- Separate identities and CI/CD permissions.
- Separate variable files.
- Separate workload and state resource groups.

Proposed roots:

```text
terraform/
  bootstrap/
    dev/
    prod/
  environments/
    dev/
    prod/
  modules/
  tests/
  docs/
```

This is preferable to Terraform workspaces because the environments use
different subscriptions, state accounts, permissions, sizes, edge components,
and lifecycle rules. Folder-based roots make those differences visible in code,
reduce the chance of selecting the wrong workspace, and allow GitHub to assign
different OIDC identities and protections to each environment.

Terraform CLI workspaces will not be used for official dev/prod deployments.

## 5. Naming Standard

The requested naming style will be retained:

| Purpose | Production | Development |
|---|---|---|
| Workload resource group | `RG-1` | `DEV-RG-1` |
| State resource group | `RG-1-TFSTATE` | `DEV-RG-1-TFSTATE` |
| Virtual network | `RG-1-VNET-1` | `DEV-RG-1-VNET-1` |
| AKS | `RG-1-AKS` | `DEV-RG-1-AKS` |
| Application Gateway | `RG-1-APPGW` | `DEV-RG-1-APPGW` |
| Front Door profile | `RG-1-AFD` | Not deployed |
| PostgreSQL | `RG-1-POSTGRES` | `DEV-RG-1-POSTGRES` |

Resources with Azure naming restrictions, such as storage accounts, ACR, and
Key Vault, will use a lowercase deterministic name with an environment and
short uniqueness suffix. The module will validate length and character rules.

Every resource will receive at least:

- `environment`
- `application`
- `owner`
- `cost_center`
- `managed_by=terraform`
- `data_classification`
- `criticality`
- `repository`

## 6. Proposed Terraform Structure

```text
terraform/
  bootstrap/
    dev/
      main.tf
      variables.tf
      outputs.tf
      terraform.tfvars.example
    prod/
      main.tf
      variables.tf
      outputs.tf
      terraform.tfvars.example

  environments/
    dev/
      backend.hcl.example
      versions.tf
      providers.tf
      variables.tf
      locals.tf
      main.tf
      outputs.tf
      terraform.tfvars.example
    prod/
      backend.hcl.example
      versions.tf
      providers.tf
      variables.tf
      locals.tf
      main.tf
      outputs.tf
      terraform.tfvars.example

  modules/
    naming/
    resource-group/
    network/
    private-dns/
    monitoring/
    managed-identities/
    key-vault/
    storage/
    container-registry/
    postgresql/
    aks/
    application-gateway/
    front-door/
    policy/
    rbac/

  tests/
  docs/
```

Provider versions will be pinned, including `azurerm` and `azuread`. Each
environment root will target only its assigned subscription.

## 7. Terraform State Bootstrap

State infrastructure must be deployed before the workload root.

Each environment will have a dedicated state resource group and storage
account with:

- Blob versioning.
- Blob and container soft delete.
- TLS 1.2 minimum.
- Public blob access disabled.
- Shared-key access disabled after Entra-based access is verified.
- Entra RBAC for administrators and CI/CD identities.
- State locking through the Azure Blob lease used by the `azurerm` backend.
- Resource locks in production.

The state backend will not be private-only because operators and CI currently
have no private-network path. Its public endpoint will be restricted to
approved operator addresses and a CI runner with a stable public egress
address. Authentication will use Entra ID and GitHub OIDC; storage account keys
will not be used by CI.

Standard GitHub-hosted runner IP ranges are too broad and change over time.
The implementation will therefore use either a GitHub larger runner with static
public egress or a small dedicated runner with a fixed public egress address.
This runner does not need private VNet access.

The development and production backends will use different subscriptions,
storage accounts, containers, and keys. For example:

```text
dev storage account  -> tfstate/sentinel-dev.tfstate
prod storage account -> tfstate/sentinel-prod.tfstate
```

After every successful `terraform apply`, Terraform automatically writes the
new state to that environment's Azure Blob backend. Blob versioning and soft
delete preserve previous state versions. State will not rely on a local file or
on a GitHub Actions artifact.

State files and plan artifacts will be treated as sensitive because Terraform
state can contain infrastructure metadata and provider-returned values.

## 8. Production Architecture

### 8.0 Region selection

The preferred regional layout is:

| Environment | Preferred region | Fallback region |
|---|---|---|
| Production | Central India | East US, when subscription restrictions are removed |
| Development | South India | West US, when subscription access and availability are verified |

Azure Front Door is global. Read-only discovery on June 9, 2026 showed that
East US PostgreSQL provisioning is restricted for the production subscription,
and the selected AKS VM families are also unavailable there. Central India
supports the selected AKS sizes in zones 1 and 2 and PostgreSQL
`Standard_D2ds_v5` with zone-redundant HA. Therefore the implemented pair is
Central India/South India. The preflight checks remain in place because regional
and subscription availability can change.

### 8.1 Network

Proposed production address space:

```text
RG-1-VNET-1:          10.10.0.0/16
Application Gateway:  10.10.30.0/24
AKS nodes:             10.10.8.0/21
Private endpoints:     10.10.20.0/24
PostgreSQL delegated:  10.10.40.0/24
```

The reference diagram's `/24` AKS subnet is considered too restrictive for a
production cluster with multiple node pools and internal load balancers. The
final CIDR plan will be validated against expected node and service growth
before creation.

The network module will configure:

- NSGs per subnet.
- Route tables where required.
- Private DNS zones and VNet links.
- PostgreSQL subnet delegation.
- Private endpoint network policies.
- Explicit ingress and egress rules.
- No unnecessary public IP addresses on application workloads.

Private DNS zones will cover at least:

- Key Vault
- Blob Storage
- ACR
- PostgreSQL

### 8.2 Public request path

```text
User
  -> sentinel.vaultrix.in
  -> Azure Front Door Premium WAF
  -> Application Gateway WAF v2
  -> Internal AKS ingress service
  -> Sentinel web/API services
```

Preferred origin security is Front Door Premium Private Link to a private
Application Gateway frontend where the selected Azure configuration supports
it.

If a public Application Gateway frontend is required, it will be restricted to
the `AzureFrontDoor.Backend` service tag and validate the expected Front Door
identifier. It will not be left as a generally accessible second public entry
point.

Front Door production controls:

- Custom domain `sentinel.vaultrix.in`.
- Managed TLS certificate.
- WAF prevention mode.
- Microsoft-managed rules.
- Bot protection.
- Rate limiting for authentication and API paths.
- Health probes and origin failover configuration.
- Access and WAF logs sent to Log Analytics.

Application Gateway production controls:

- WAF v2 and autoscaling.
- End-to-end TLS where supported by the application ingress.
- Health probes for web and gateway endpoints.
- Private/internal AKS backend.
- Key Vault certificate integration when an origin certificate is required.
- Diagnostic logs and alerts.

### 8.3 AKS

Production AKS will use:

- A public API endpoint restricted to approved operator and stable CI egress
  addresses, because operators and CI currently have no private-network path.
- Azure CNI Overlay with Cilium network policy.
- Microsoft Entra integration and Azure RBAC.
- Local Kubernetes accounts disabled.
- OIDC issuer and Workload Identity.
- Azure Key Vault CSI provider.
- Azure Policy add-on.
- Managed identities instead of service principal credentials.
- Automatic node image upgrades and a controlled Kubernetes upgrade channel.
- Availability zones supported by the selected region, after final SKU and
  quota validation.

Only the AKS management API is public and allow-listed. Kubernetes application
services remain behind the internal ingress and Application Gateway. A future
VPN or privately networked runner can allow the API server to be converted to
private access without redesigning the workloads.

Initial node-pool design:

| Pool | Purpose | Initial scale |
|---|---|---|
| System | Core Kubernetes and platform components | 2 nodes, autoscale 2-3 |
| User | Sentinel APIs, web, and workers | 2 nodes, autoscale 2-6 |

Candidate VM sizes discovered in Central India include
`Standard_D2as_v5`, `Standard_D2ds_v5`, `Standard_D2s_v5`,
`Standard_D4as_v5`, `Standard_D4ds_v5`, and `Standard_D4s_v5`.
Zone 3 reported a subscription restriction during discovery, so it will not be
selected without a fresh successful availability and quota check.

The application deployment layer will continue to use Kubernetes resources.
The manifests will later be adapted to:

- Pull images from ACR.
- Use internal ingress rather than a public Kubernetes LoadBalancer.
- Use environment-specific image digests.
- Use one Kubernetes service account and federated identity per workload.
- Apply resource limits, disruption budgets, autoscaling, and network policies.

### 8.4 PostgreSQL

Azure Database for PostgreSQL Flexible Server will use:

- A delegated subnet.
- Private DNS.
- No public network access.
- PostgreSQL 16 unless application compatibility testing requires otherwise.
- TLS enforcement.
- Service-owned schemas and existing migration strategy.
- Point-in-time restore.
- Production backup retention up to 35 days.
- Zone-redundant HA and geo-redundant backup only where supported by the final
  region/SKU combination.

The production target is a supported General Purpose D-series SKU. The precise
SKU will not be fixed until `az postgres flexible-server list-skus` and quota
checks are rerun with a query that returns purchasable editions and HA
capabilities.

The application currently uses a PostgreSQL connection URL. Password-based
database authentication may remain during the first migration, with the value
stored only in Key Vault. Entra database authentication can be introduced
after application support is verified.

### 8.5 Key Vault

Production Key Vault will have:

- RBAC authorization.
- Public network access disabled.
- A private endpoint and private DNS.
- Purge protection enabled.
- 90-day soft-delete retention.
- Diagnostic settings.
- Resource lock.

Workloads will receive only `Key Vault Secrets User` or narrower permissions
needed by that workload. Administrative access will be assigned to Entra groups
and ideally activated through PIM rather than assigned directly to users.

### 8.6 Storage

The application storage account will have:

- Public network access disabled.
- Private blob endpoint.
- Public blob/container access disabled.
- Shared-key access disabled once managed-identity access is verified.
- Blob versioning.
- Blob and container soft delete.
- Lifecycle policies.
- Diagnostic settings.
- Zone-redundant or geo-redundant storage after regional and budget validation.

Containers will include the existing login-event use case and any approved
export or application-data containers.

Audit exports may use a separate production storage account because audit
immutability, retention, and writer permissions differ from normal application
storage. This will be enabled only if the audit workflow requires it.

### 8.7 Azure Container Registry

Production ACR will use the Premium SKU because private endpoints require it.
It will have:

- Public network access disabled.
- Private endpoint and private DNS.
- Admin account disabled.
- `AcrPull` for the AKS kubelet identity.
- `AcrPush` only for the deployment identity.
- Image retention and cleanup policy.
- Vulnerability scanning through Defender or the selected CI scanner.
- Optional geo-replication if the DR target justifies its cost.

Application deployment should use immutable image digests rather than mutable
tags for production.

#### Existing Docker Hub image migration

The existing Docker Hub images will be copied once into each environment's ACR
with server-side `az acr import`. This does not require a local Docker daemon.
The source images currently include:

```text
elzabeth03/sentinel-web:v1.0.5
elzabeth03/sentinel-identity-service:v1.0.3
elzabeth03/sentinel-inventory-service:v1.0.5
elzabeth03/sentinel-relationship-service:v1.0.0
elzabeth03/sentinel-change-intelligence-service:v1.0.0
elzabeth03/sentinel-operations-service:v1.0.0
elzabeth03/sentinel-audit-service:v1.0.0
elzabeth03/sentinel-migration:v1.0.3
```

The import pattern will be:

```bash
az acr import \
  --name <environment-acr-name> \
  --source docker.io/elzabeth03/sentinel-web:v1.0.5 \
  --image sentinel-web:v1.0.5
```

The same process will be repeated for every image and for both registries.
Docker Hub credentials are unnecessary if the repositories are public. If
Docker Hub access requires authentication, a short-lived Docker Hub token will
be supplied through GitHub Secrets and removed after migration.

The private ACR will allow the Azure Container Registry trusted-service
exception during import. This permits the server-side ACR import operation
without opening the registry to arbitrary public clients.

After the initial migration, Docker Hub will no longer be the deployment
source. Push-triggered workflows will build from this repository and publish to
the correct ACR. Because ACR public access is disabled and CI has no private
network path, builds will run inside Azure using managed ACR Tasks through the
trusted-service exception. GitHub will authenticate to Azure with OIDC and
trigger the task; it will not perform a direct `docker push` across the public
Internet. A dedicated ACR agent pool is needed only if future builds must reach
private dependencies inside the VNet.

Image tags will include the Git commit SHA. The workflow will resolve the
resulting digest and deploy that digest to AKS.

### 8.8 Managed identities

Separate user-assigned managed identities and federated credentials will be
created for:

- Identity service
- Inventory service and worker
- Relationship service
- Change intelligence service
- Operations service
- Audit service and outbox worker
- Database migration job
- Any gateway or web workload that accesses Azure resources

Each identity will receive only the resource-level roles it needs.

### 8.9 App registration

Terraform may configure the Microsoft Entra application, redirect URI,
permissions, and service principal. It will not generate an application client
secret because generated secrets are retained in Terraform state.

The selected approach is:

1. Use Workload Identity for every Azure resource access that supports it.
2. Retain the Entra application client secret temporarily because the current
   OAuth callback implementation expects it.
3. Create and rotate that secret outside Terraform.
4. Write it directly to the environment Key Vault.
5. Never store it in GitHub, Terraform variables, plans, or source code.
6. Replace it later with certificate/client-assertion authentication when the
   identity-service code supports that flow.

## 9. Development Architecture

Development will retain the same logical topology so changes can be tested
before production, but will use lower-cost settings:

- Resource group `DEV-RG-1`.
- VNet `10.20.0.0/16`.
- Domain `dev.sentinel.vaultrix.in`.
- No Azure Front Door.
- Application Gateway WAF v2 is the development public entry point.
- One AKS system-mode node pool that hosts both platform and Sentinel workloads.
- The single pool starts at one node and can autoscale to a small validated
  maximum.
- PostgreSQL Burstable SKU, no HA, and shorter backup retention.
- Storage LRS.
- Application Gateway WAF detection mode before rules are promoted to
  production prevention mode.
- Shorter log retention.
- Managed Grafana and expensive Defender plans configurable by budget.

Security fundamentals will remain consistent:

- No embedded secrets.
- Workload Identity.
- RBAC.
- Private data services.
- Policy checks.
- Logging and alerts.

Development will not be allowed to use production Key Vaults, databases,
registries, identities, state, or DNS records.

Development request path:

```text
User
  -> dev.sentinel.vaultrix.in
  -> Development Application Gateway WAF v2
  -> Internal AKS ingress service
  -> Sentinel web/API services
```

## 10. RBAC Model

Roles will be assigned to Entra groups and managed identities rather than
individual users wherever possible.

Proposed groups:

- Sentinel platform administrators
- Sentinel production operators
- Sentinel development contributors
- Sentinel security readers
- Sentinel database administrators
- Sentinel auditors

Examples:

- CI planning identity: Reader plus access to its state container.
- CI deployment identity: scoped Contributor plus User Access Administrator
  only where role assignments must be managed.
- AKS kubelet identity: `AcrPull`.
- Application identities: resource-specific data-plane roles.
- Human production access: eligible through PIM where available.
- Break-glass account: monitored, excluded from routine use, and protected by
  strong authentication.

Custom roles will be used only when built-in roles are materially broader than
required.

## 11. Azure Policy

Policy assignments will begin in audit mode and move to deny after validation.

Planned controls:

- Allowed Azure regions.
- Required tags.
- HTTPS and TLS minimums.
- Deny public blob access.
- Audit or deny public access for Key Vault, Storage, ACR, and PostgreSQL.
- Require diagnostic settings for supported resources.
- AKS baseline and restricted workload controls.
- Approved VM and database SKUs.
- Naming checks where Azure Policy can enforce them reliably.

Terraform module validation remains the primary naming enforcement mechanism.
Custom naming policies will be tested in audit mode before any deny assignment.

## 12. Monitoring and Alerting

The monitoring module will create:

- Log Analytics workspace.
- Application Insights.
- Azure Monitor managed Prometheus for AKS.
- Azure Managed Grafana in production if approved by budget.
- Action groups.
- Diagnostic settings for all supported resources.

Initial alerts:

- Front Door and Application Gateway 4xx/5xx, unhealthy origins, and WAF
  blocks.
- AKS unavailable nodes, pod restarts, pending pods, CPU, memory, and disk
  pressure.
- PostgreSQL CPU, storage, connection saturation, replication/HA, and backup
  failures.
- Key Vault authorization and availability failures.
- Storage availability and capacity.
- ACR authentication and image-pull failures.
- Certificate and secret expiry.

Application logs will carry correlation IDs and must not contain credentials,
tokens, or secret values.

## 13. Backup and Disaster Recovery

The initial design will use infrastructure recreation plus managed-service data
recovery:

- AKS is recreated from Terraform and Kubernetes manifests.
- PostgreSQL uses PITR and approved geo-redundant backup/replica options.
- Storage uses versioning, soft delete, and the approved redundancy tier.
- Key Vault uses soft delete and purge protection.
- ACR images are reproducible from source; geo-replication is optional.
- Terraform state uses versioning and soft delete.

A secondary full application stamp will not be created merely to draw a
multi-region diagram. It will be added when the required RTO/RPO and budget
justify it.

Until business requirements are formally defined, the initial engineering
targets will be:

| Environment | RPO target | RTO target |
|---|---|---|
| Production | 15 minutes | 4 hours |
| Development | Best effort | 1 business day |

These are starting targets, not contractual guarantees. Backup configuration
and restore tests will measure whether they are achievable. The targets will be
revised when the application's data-loss tolerance and downtime cost are known.

Runbooks will cover:

- PostgreSQL point-in-time restore.
- Storage object restore.
- Key Vault recovery.
- AKS rebuild.
- Front Door origin failover.
- Terraform state recovery.

Restore tests will be scheduled at least quarterly for production-critical
data.

## 14. DNS Plan

Production:

```text
sentinel.vaultrix.in -> Azure Front Door custom endpoint
```

Development:

```text
dev.sentinel.vaultrix.in -> Development Application Gateway public frontend
```

The registrar remains GoDaddy, but DNS hosting for Sentinel will move to Azure
DNS. To avoid disturbing unrelated `vaultrix.in` records, the preferred design
is an Azure DNS child zone named `sentinel.vaultrix.in`.

Migration sequence:

1. Terraform creates the `sentinel.vaultrix.in` public DNS zone in Azure.
2. Azure returns four authoritative name servers.
3. In GoDaddy DNS for `vaultrix.in`, add NS records delegating the `sentinel`
   subdomain to those Azure name servers.
4. Azure DNS manages the production zone apex and
   `dev.sentinel.vaultrix.in`.
5. Create the Front Door domain-validation and alias records in Azure DNS.
6. Create the development Application Gateway A record in Azure DNS.
7. Validate both environments before removing any old Sentinel DNS records.

This keeps domain registration at GoDaddy while Azure DNS becomes authoritative
for the Sentinel subdomain. No GoDaddy API credential is required in GitHub.

## 15. Delivery Phases

### Phase 0: Confirm and inventory

- Validate the confirmed dev/prod subscription IDs and tenant.
- Recheck Central India and South India resource/SKU availability immediately
  before apply.
- Inventory existing GoDaddy Sentinel DNS records before delegation.
- Capture current Azure resource inventory.
- Record the approved budget, initial RPO/RTO targets, and public management
  access path.
- Rerun SKU, quota, and feature-availability checks.

### Phase 1: Bootstrap state

- Create each environment's state resource group and account.
- Configure versioning, retention, RBAC, and locks.
- Configure CI/CD identity access.
- Migrate local state only if existing Terraform state must be retained.

### Phase 2: Foundation

- Create workload resource group.
- Create VNet, subnets, NSGs, routing, and private DNS.
- Create monitoring workspace and action groups.
- Assign initial audit policies.

### Phase 3: Private platform services

- Create Key Vault, Storage, ACR, and PostgreSQL.
- Create private endpoints and DNS records.
- Validate name resolution and private connectivity from the VNet.

### Phase 4: Identity and access

- Create managed identities.
- Assign least-privilege roles.
- Create Workload Identity federated credentials.
- Configure Entra application settings without putting its secret in state.

### Phase 5: AKS

- Create AKS and node pools.
- Attach ACR.
- Configure monitoring, policies, Workload Identity, and CSI.
- Validate Entra/Azure RBAC, API-server IP allow-listing, and workload
  scheduling.

### Phase 6: Edge

- Create Application Gateway and WAF policy.
- Deploy internal AKS ingress.
- In production, create Front Door, WAF, routes, origins, and custom domain.
- In development, publish Application Gateway directly without Front Door.
- Prove that the origin cannot be bypassed from the public Internet.

### Phase 7: Application integration

- Import the existing Docker Hub images into both ACRs.
- Configure ACR Tasks and push-triggered image builds.
- Update environment manifests to use ACR digests.
- Create Kubernetes service accounts and workload identity bindings.
- Load runtime secrets into Key Vault through the approved secure workflow.
- Run the Kubernetes database migration job.
- Deploy and validate all services.

### Phase 8: Hardening and validation

- Run security scanning and policy checks.
- Validate RBAC and network isolation.
- Enable WAF prevention after tuning.
- Validate backup and restore procedures.
- Complete operational documentation and handover.

### Phase 9: Development cleanup

- Produce the exact deletion inventory.
- Exclude state, DNS, Entra, and shared resources.
- Obtain explicit deletion approval.
- Delete only the approved resources.
- Confirm billing and residual resources afterward.

## 16. Validation Pipeline

The planned CI checks are:

```text
terraform fmt -check
terraform init
terraform validate
tflint
checkov or equivalent policy scan
terraform plan
```

Additional checks:

- Provider lock files for Windows and Linux runners.
- Secret scanning.
- Container and dependency scanning.
- Terraform documentation generation.
- Cost estimation where supported.
- Saved plan artifact and human-readable plan summary.

No CI job will automatically apply production changes from an unreviewed pull
request.

## 17. GitHub Actions Design

Pull requests are not required to trigger deployment. Workflows will use
`push` events:

| Push target | Result |
|---|---|
| `dev` branch | Validate, plan, apply development infrastructure, build images, deploy development |
| `master` branch | Validate and plan production, then wait for the protected production environment approval before apply/deploy |

Path filters will avoid rebuilding every image when unrelated files change.
For example, changes under `apps/inventory-service/**` build only the inventory
image, while shared Python package changes rebuild all affected Python
services.

The infrastructure workflow will:

1. Authenticate to Azure with GitHub OIDC.
2. Verify tenant and subscription IDs.
3. Initialize the correct remote backend.
4. Run format, validation, security checks, and plan.
5. Apply after the environment's required gate.
6. Leave the updated state in that environment's Blob backend.

The application workflow will:

1. Authenticate with OIDC.
2. Trigger the applicable ACR Task builds.
3. Tag images with the Git commit SHA.
4. Resolve and record immutable image digests.
5. Update/deploy the environment manifests.
6. Run the migration Job before rolling out services that require the new
   schema.
7. Verify rollout and health endpoints.

### 17.1 GitHub environments

Create GitHub environments named:

- `sentinel-dev`
- `sentinel-prod`

Each environment receives its own OIDC federated credential and Azure identity.
The trust subject is restricted to the repository, branch, and GitHub
environment. There is no Azure service-principal client secret.

### 17.2 GitHub variables

The following values are identifiers, not secrets, and should be GitHub
environment or repository variables:

```text
AZURE_TENANT_ID=83474cb5-f1fa-4d06-906c-e5dad12ce3b9
AZURE_SUBSCRIPTION_ID=<environment-subscription-id>
AZURE_CLIENT_ID=<environment-github-oidc-identity-client-id>
TFSTATE_RESOURCE_GROUP=<environment-state-resource-group>
TFSTATE_STORAGE_ACCOUNT=<environment-state-storage-account>
ACR_NAME=<environment-acr-name>
AZURE_RUNNER_LABEL=<stable-egress-runner-label>
NAME_SUFFIX=<unique-lowercase-suffix>
RESOURCE_OWNER=<team-or-owner>
COST_CENTER=<approved-cost-center>
OPERATOR_AND_CI_CIDRS=["203.0.113.10/32"]
ALERT_EMAIL=<alert-recipient>
```

### 17.3 GitHub secrets

Long-lived Azure credentials will not be stored in GitHub. OIDC removes the
need for `AZURE_CLIENT_SECRET`, subscription access keys, ACR passwords, and
Terraform backend keys.

Expected GitHub Secrets:

| Secret | Required | Purpose |
|---|---|---|
| `DOCKERHUB_USERNAME` | Temporary/optional | Authenticated import if Docker Hub rate limits or repository visibility require it |
| `DOCKERHUB_TOKEN` | Temporary/optional | Short-lived Docker Hub token; delete after all images are imported |
| `POSTGRES_BOOTSTRAP_PASSWORD` | Initially required per GitHub environment | Unique environment PostgreSQL bootstrap password; rotate after provisioning |

The Entra application client secret, session signing key, token encryption key,
database runtime URL, and internal API token will not be GitHub Secrets. They
will be created or rotated through a controlled administrative process and
written directly to the appropriate Key Vault.

If the PostgreSQL provider and application support Entra-only database
authentication at implementation time, the two bootstrap password secrets will
be omitted.

## 18. Deliverables

Implementation will produce:

- Reusable Terraform modules.
- Separate dev and prod environment roots.
- State bootstrap roots.
- Example variable and backend files without secrets.
- Architecture diagram updated to match the deployed design.
- Naming, tagging, RBAC, and policy matrix.
- Deployment and rollback guide.
- Secret provisioning and rotation guide.
- Backup and restore runbooks.
- CI/CD workflows for validation, plan, and approved apply.
- Migration guide from Docker Hub to ACR.
- Kubernetes integration notes without replacing the existing application
  structure.

## 19. Confirmed Decisions and Remaining Checks

Confirmed:

1. Dev subscription:
   `6b01db76-626a-44a2-8119-17682410914a`.
2. Prod subscription:
   `a8270be7-dabc-4d92-98db-26a55025b0df`.
3. Tenant: `83474cb5-f1fa-4d06-906c-e5dad12ce3b9`.
4. Development has no Front Door and only one AKS node pool.
5. Production uses Front Door and separate system/user AKS node pools.
6. Operators and CI do not currently have private-network access.
7. Budget is approved.
8. Sentinel DNS will be delegated from GoDaddy to Azure DNS.
9. Push events, rather than pull requests, trigger pipelines.
10. Folder-based dev/prod roots are used instead of Terraform workspaces.
11. Existing Docker Hub images are imported to ACR before Azure-side builds
    become the normal path.

Remaining implementation-time checks:

1. Verify all required services and quotas in Central India and South India.
2. Confirm the GitHub plan/runner option that supplies stable public egress.
3. Inventory current GoDaddy DNS records before adding the child-zone
   delegation.
4. Test whether Entra-only PostgreSQL authentication can replace bootstrap
   passwords without changing application behavior.

## 20. Current Discovery Notes

- The currently selected Azure subscription contains `RG-1` in Central India
  and an AKS managed resource group.
- The dev/prod subscription mapping is now explicitly confirmed in this plan.
- Candidate Central India D-series VM SKUs were visible, but zone 3 reported a
  restriction.
- Central India zones 1 and 2 remain available for the selected production AKS
  sizes.
- Central India PostgreSQL `Standard_D2ds_v5` supports zone-redundant HA.
- East US PostgreSQL provisioning is restricted for the production
  subscription, so East US is not the implemented production region.
- The current CLI identity cannot yet see the confirmed development
  subscription, so South India must be rechecked after correcting that access.
- SKU and quota results are time-sensitive and will be rerun immediately before
  the first plan.
- PostgreSQL SKU and HA support require a more precise preflight query before a
  final size is selected.

## 21. Definition of Done

The implementation is complete when:

- Dev and prod have isolated subscriptions, state, identities, and resources.
- `sentinel.vaultrix.in` reaches production only through Front Door and the
  approved regional ingress.
- Private services have no public data-plane access.
- AKS pulls only approved images from ACR.
- Workloads use federated managed identities and least-privilege RBAC.
- Secrets are absent from Git and committed Terraform files. Any unavoidable
  bootstrap secret is supplied through a protected runtime channel, treated as
  state-sensitive, rotated into Key Vault, and removed from GitHub afterward.
- Monitoring, alerts, backups, and restore runbooks are validated.
- Production Terraform plan contains no unexplained replacement or deletion.
- The deployed architecture and documentation agree.

## 22. Primary References

- [Store Terraform state in Azure Storage](https://learn.microsoft.com/azure/developer/terraform/store-state-in-azure-storage)
- [Import container images into ACR](https://learn.microsoft.com/azure/container-registry/container-registry-import-images)
- [Use private endpoints with ACR](https://learn.microsoft.com/azure/container-registry/container-registry-private-endpoints)
- [Allow trusted Azure services to access ACR](https://learn.microsoft.com/azure/container-registry/allow-access-trusted-services)
- [Onboard an apex domain to Azure Front Door](https://learn.microsoft.com/azure/frontdoor/front-door-how-to-onboard-apex-domain)
- [GitHub Actions larger runners and static egress](https://docs.github.com/actions/concepts/runners/larger-runners)
