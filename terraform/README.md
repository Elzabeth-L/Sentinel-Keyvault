# Sentinel Azure Terraform

This directory contains isolated Terraform roots for Sentinel development and
production infrastructure.

## Environment mapping

| Environment | Branch | GitHub environment | Subscription |
|---|---|---|---|
| Development | `dev` | `sentinel-dev` | `6b01db76-626a-44a2-8119-17682410914a` |
| Production | `master` | `sentinel-prod` | `a8270be7-dabc-4d92-98db-26a55025b0df` |

Both subscriptions use tenant
`83474cb5-f1fa-4d06-906c-e5dad12ce3b9`.

The implemented regions are Central India for production and South India for
development. East US was rejected by the current subscription SKU checks.

Environment folders are used instead of Terraform workspaces because each
environment has a different subscription, backend, identity, topology, and
approval policy.

## Deployment order

1. Review [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
2. Review [docs/DEPLOYMENT_CHECKLIST.md](docs/DEPLOYMENT_CHECKLIST.md).
3. Run `./terraform/scripts/preflight.ps1 -Environment all`.
4. Bootstrap the dev and prod state accounts.
5. Configure the two GitHub environments, variables, OIDC credentials, and
   protected production approval.
6. Push Terraform changes to `dev`.
7. Import the existing Docker Hub images into dev ACR.
8. Validate the full development deployment.
9. Push the approved changes to `master`.
10. Approve the production GitHub environment deployment.
11. Delegate `sentinel.vaultrix.in` from GoDaddy to the Azure DNS name servers
   returned by production Terraform.

No `terraform apply` was run while creating this code.

## Bootstrap

Bootstrap is intentionally manual because the GitHub OIDC identity and state
account do not exist yet:

```powershell
cd terraform/bootstrap/dev
Copy-Item terraform.tfvars.example terraform.tfvars
# Edit only the non-secret state name and CIDRs.
terraform init
terraform plan
terraform apply
```

Repeat in `terraform/bootstrap/prod`.

Copy each `github_client_id` output into the corresponding GitHub environment
variable `AZURE_CLIENT_ID`.

## State

The workload roots use separate Azure Blob backends:

```text
dev  -> DEV-RG-1-TFSTATE / sentinel-dev.tfstate
prod -> RG-1-TFSTATE     / sentinel-prod.tfstate
```

Terraform writes updated state to Blob Storage after every successful apply.
Versioning and soft delete retain older state versions.

## ACR migration

After ACR exists, import the current Docker Hub images without using a local
Docker daemon:

```powershell
./terraform/scripts/import-dockerhub-images.ps1 -AcrName <dev-acr-name>
./terraform/scripts/import-dockerhub-images.ps1 -AcrName <prod-acr-name>
```

For private Docker Hub repositories, pass a short-lived token:

```powershell
./terraform/scripts/import-dockerhub-images.ps1 `
  -AcrName <acr-name> `
  -DockerHubUsername <username> `
  -DockerHubToken <token>
```

Delete the token after import. Future pushes to `dev` or `master` trigger ACR
server-side builds tagged with the Git commit SHA.

## Secret policy

Do not commit:

- Terraform state or plans
- `terraform.tfvars`
- PostgreSQL passwords
- Entra application secrets
- Key Vault secret values
- Storage or registry access keys
- Kubernetes Secrets

GitHub uses OIDC rather than an Azure client secret. See
[GITHUB_CONFIGURATION.md](docs/GITHUB_CONFIGURATION.md) for the exact
variables and temporary secrets.
